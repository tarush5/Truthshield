"""
TruthShield — Evidence Retriever (v3 — Production Grade)

Retrieves evidence from 7 sources concurrently with robust HTML/RSS fallbacks:
  1. DuckDuckGo search (via ddgs package, falling back to lite.duckduckgo.com scraper if rate-limited)
  2. DuckDuckGo news search (falling back to Google News RSS feed)
  3. Wikipedia API (extracts intro summary texts instead of raw HTML snippets)
  4. Wikidata Knowledge Graph (semantic description and aliases for entities)
  5. Google Fact Check Tools API (authenticated with API key from settings)
  6. RSS Fact-Check feeds (local matching Snopes, PolitiFact, FactCheck.org)
  7. Web Page Deep Scraping (URLScraper scrapes body of top results, selects matching paragraphs)
"""

import logging
import math
import re
import socket
from typing import List
from urllib.parse import quote_plus, urlparse

import requests
from bs4 import BeautifulSoup

# Set global default socket timeout to prevent any third-party library thread from hanging indefinitely
socket.setdefaulttimeout(10.0)

try:
    import feedparser
except ImportError:
    feedparser = None

try:
    from fuzzywuzzy import fuzz
except ImportError:
    fuzz = None

try:
    from ddgs import DDGS
except ImportError:
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        DDGS = None

from backend.config import get_settings, SOURCE_CREDIBILITY
from backend.models.schemas import Claim, Evidence

logger = logging.getLogger(__name__)


class EvidenceRetriever:
    """Retrieve evidence from 7 free/robust sources concurrently."""

    MAX_EVIDENCE_PER_CLAIM = 10

    # ──────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────

    async def retrieve(self, claim: Claim) -> List[Evidence]:
        """Fetch evidence from all sources in parallel, dedup, and return."""
        wiki_query = (
            claim.entity
            if getattr(claim, "entity", None)
            else self._extract_search_terms(claim.text)
        )

        settings = get_settings()
        timeout = getattr(settings, "EVIDENCE_TIMEOUT", 12)

        import asyncio

        # We set up concurrent tasks for our sources
        async def run_ddg_both():
            # Run general search first
            results = await asyncio.to_thread(self._ddg_combined_search, claim.text)
            # Run fact-check specific search second (sequentially to prevent duckduckgo_search library deadlocks)
            query = f"{claim.text} site:snopes.com OR site:politifact.com OR site:factcheck.org OR site:boomlive.in OR site:fullfact.org"
            fc_results = await asyncio.to_thread(self._ddg_combined_search, query)
            return results + fc_results

        async def run_wikipedia():
            return await asyncio.to_thread(self._search_wikipedia, wiki_query)

        async def run_wikidata():
            return await asyncio.to_thread(self._search_wikidata, wiki_query)

        async def run_google_factcheck():
            return await asyncio.to_thread(self._google_factcheck, claim.text)

        async def run_rss_factcheck():
            return await asyncio.to_thread(self._rss_fact_check_feeds, claim.text)

        tasks = [
            asyncio.create_task(run_ddg_both()),
            asyncio.create_task(run_wikipedia()),
            asyncio.create_task(run_wikidata()),
            asyncio.create_task(run_google_factcheck()),
            asyncio.create_task(run_rss_factcheck()),
        ]

        # Allocate timeout - 2.5 seconds for deep scraping
        done, pending = await asyncio.wait(tasks, timeout=max(2.0, timeout - 2.5))

        for task in pending:
            task.cancel()

        all_evidence: List[Evidence] = []
        for task in done:
            try:
                results = task.result()
                all_evidence.extend(results)
            except Exception as exc:
                logger.warning(f"Evidence source task failed: {exc}")

        # Extract URLs for deep page scraping
        urls_to_scrape = []
        seen_urls = set()
        for ev in all_evidence:
            if ev.url and ev.url not in seen_urls:
                seen_urls.add(ev.url)
                domain = urlparse(ev.url).netloc.lower()
                # Do not deep-scrape wikipedia, wikidata, or fact-check APIs
                if (
                    "wikipedia.org" not in domain
                    and "wikidata.org" not in domain
                    and "googleapis.com" not in domain
                ):
                    urls_to_scrape.append(ev.url)

        # Run Deep Page Scraping on the top 2 candidate URLs in parallel concurrently
        if urls_to_scrape:
            try:
                # Wrap each scrape in a thread and run concurrently via asyncio.gather
                async def scrape_single_url(url):
                    return await asyncio.to_thread(self._deep_scrape_single_url, url, claim.text)
                
                deep_tasks = [scrape_single_url(url) for url in urls_to_scrape[:2]]
                deep_results = await asyncio.gather(*deep_tasks, return_exceptions=True)
                for res in deep_results:
                    if isinstance(res, list):
                        all_evidence.extend(res)
            except Exception as e:
                logger.warning(f"Deep web scraping failed: {e}")

        # Deduplicate by URL and Title
        seen = set()
        unique = []
        for ev in all_evidence:
            key = ev.url.strip().lower() if ev.url else ev.title.strip().lower()
            if key and key not in seen:
                seen.add(key)
                unique.append(ev)

        # Quality scoring function to sort evidence
        def get_evidence_quality(ev: Evidence) -> float:
            score = ev.source_score
            # Boost score for deep scraped articles
            if "[Deep Extract]" in ev.title:
                score += 0.15
            # Boost score for fact checkers
            domain = urlparse(ev.url).netloc.lower() if ev.url else ""
            if any(fc in domain for fc in ["snopes.com", "politifact.com", "factcheck.org", "boomlive.in", "fullfact.org"]):
                score += 0.20
            # Boost score based on relevance (overlap of terms)
            claim_words = set(re.findall(r"\b[a-zA-Z]{4,}\b", claim.text.lower()))
            snippet_words = set(re.findall(r"\b[a-zA-Z]{4,}\b", ev.snippet.lower()))
            overlap = len(claim_words.intersection(snippet_words))
            score += min(0.15, overlap * 0.02)
            # Penalize very short snippets
            if len(ev.snippet) < 50:
                score -= 0.10
            return score

        unique.sort(key=get_evidence_quality, reverse=True)

        logger.info(
            f"Evidence for '{claim.text[:50]}…': "
            f"Retrieved {len(unique)} unique evidence items (from {len(all_evidence)} raw)"
        )

        return unique[: self.MAX_EVIDENCE_PER_CLAIM]

    # ──────────────────────────────────────────────────────────
    # Source: Combined DuckDuckGo search (ddgs) & Custom Scraper
    # ──────────────────────────────────────────────────────────

    def _ddg_combined_search(self, query: str) -> List[Evidence]:
        """Combined web and news search via ddgs package, falling back to custom scrapers if blocked."""
        results = []

        # 1. Try official DDGS package first
        if DDGS is not None:
            try:
                with DDGS(timeout=4) as ddgs:
                    # Text Search
                    try:
                        for r in ddgs.text(query, max_results=4):
                            url = r.get("href", r.get("link", ""))
                            title = r.get("title", "")
                            snippet = r.get("body", r.get("snippet", ""))
                            if title and url:
                                results.append(
                                    Evidence(
                                        title=title,
                                        url=url,
                                        snippet=(snippet or "")[:300],
                                        source_score=self._score_source(url),
                                    )
                                )
                    except Exception as e:
                        logger.warning(f"ddgs text search failed for query '{query}': {e}")

                    # News Search
                    try:
                        for r in ddgs.news(query, max_results=3):
                            url = r.get("url", "")
                            title = r.get("title", "")
                            snippet = r.get("body", "")
                            if title and url:
                                results.append(
                                    Evidence(
                                        title=title,
                                        url=url,
                                        snippet=(snippet or "")[:300],
                                        source_score=self._score_source(url),
                                    )
                                )
                    except Exception as e:
                        logger.warning(f"ddgs news search failed for query '{query}': {e}")
            except Exception as e:
                logger.warning(f"DDGS instance initialization failed: {e}")

        # 2. Fall back to custom DDG Lite HTML scraper if no results found
        if not results:
            logger.info(f"Official DDG search returned 0 results. Triggering DDG Lite scraper fallback for: '{query}'")
            results.extend(self._ddg_lite_search(query))

        # 3. Trigger Google News RSS search as news search backup/enrichment if low on results
        if len(results) < 3:
            logger.info(f"Low search results. Fetching Google News RSS fallback for: '{query}'")
            results.extend(self._google_news_rss_search(query))

        return results

    def _ddg_lite_search(self, query: str, max_results: int = 5) -> List[Evidence]:
        """Scrape lite.duckduckgo.com when the official package is rate-limited."""
        url = "https://lite.duckduckgo.com/lite/"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        data = {"q": query}
        results = []
        try:
            resp = requests.post(url, headers=headers, data=data, timeout=6)
            if resp.status_code != 200:
                logger.warning(f"DDG Lite fallback returned status code {resp.status_code}")
                return []

            soup = BeautifulSoup(resp.text, "html.parser")
            rows = soup.find_all("td", class_="result-snippet")
            links = soup.find_all("a", class_="result-link")

            import urllib.parse
            for i in range(min(len(links), len(rows), max_results)):
                title = links[i].get_text(strip=True)
                href = links[i].get("href")
                if href and "/l/?" in href:
                    parsed = urllib.parse.urlparse(href)
                    qs = urllib.parse.parse_qs(parsed.query)
                    if "uddg" in qs:
                        href = qs["uddg"][0]
                snippet = rows[i].get_text(strip=True)

                if title and href:
                    results.append(
                        Evidence(
                            title=title,
                            url=href,
                            snippet=snippet[:300],
                            source_score=self._score_source(href),
                        )
                    )
            return results
        except Exception as e:
            logger.warning(f"DDG Lite scraper failed: {e}")
            return []

    def _google_news_rss_search(self, query: str, max_results: int = 4) -> List[Evidence]:
        """Query Google News RSS search for real-time news articles (free and no rate limit)."""
        import urllib.parse
        encoded_query = urllib.parse.quote_plus(query)
        url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"
        results = []
        try:
            resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=6)
            if resp.status_code != 200 or feedparser is None:
                return []

            feed = feedparser.parse(resp.content)
            for entry in feed.entries[:max_results]:
                title = entry.get("title", "")
                link = entry.get("link", "")
                summary = entry.get("summary", "")
                summary_clean = re.sub(r"<[^>]+>", "", summary).strip()

                if title and link:
                    results.append(
                        Evidence(
                            title=title,
                            url=link,
                            snippet=summary_clean[:300] or title,
                            source_score=self._score_source(link),
                        )
                    )
            return results
        except Exception as e:
            logger.warning(f"Google News RSS search failed: {e}")
            return []

    # ──────────────────────────────────────────────────────────
    # Source: Wikipedia (intro extracts)
    # ──────────────────────────────────────────────────────────

    def _search_wikipedia(self, entity: str) -> List[Evidence]:
        """Search Wikipedia and retrieve page intro extracts (much richer than snippets)."""
        if not entity:
            return []
        try:
            params = {
                "action": "query",
                "list": "search",
                "srsearch": entity,
                "format": "json",
                "srlimit": 2,
            }
            resp = requests.get(
                "https://en.wikipedia.org/w/api.php",
                params=params,
                headers={"User-Agent": "TruthShield/2.0"},
                timeout=5,
            )
            data = resp.json()

            results = []
            for item in data.get("query", {}).get("search", []):
                page_title = item.get("title", "")
                url = f"https://en.wikipedia.org/wiki/{quote_plus(page_title)}"
                
                # Fetch intro extract text
                snippet = ""
                try:
                    extract_params = {
                        "action": "query",
                        "prop": "extracts",
                        "exintro": 1,
                        "explaintext": 1,
                        "titles": page_title,
                        "format": "json",
                    }
                    ext_resp = requests.get(
                        "https://en.wikipedia.org/w/api.php",
                        params=extract_params,
                        headers={"User-Agent": "TruthShield/2.0"},
                        timeout=3,
                    )
                    ext_data = ext_resp.json()
                    pages = ext_data.get("query", {}).get("pages", {})
                    for page_id, page_data in pages.items():
                        if "extract" in page_data:
                            snippet = page_data["extract"]
                            break
                except Exception as ext_err:
                    logger.debug(f"Failed to fetch intro extract for Wiki page '{page_title}': {ext_err}")

                if not snippet:
                    snippet = re.sub(r"<[^>]+>", "", item.get("snippet", ""))

                results.append(
                    Evidence(
                        title=f"Wikipedia: {page_title}",
                        url=url,
                        snippet=snippet[:400],
                        source_score=0.65,
                    )
                )
            return results
        except Exception as e:
            logger.warning(f"Wikipedia search failed: {e}")
            return []

    # ──────────────────────────────────────────────────────────
    # Source: Wikidata Knowledge Graph
    # ──────────────────────────────────────────────────────────

    def _search_wikidata(self, query: str) -> List[Evidence]:
        """Query Wikidata Entity Search to extract labels, aliases, and descriptions."""
        if not query:
            return []
        try:
            search_params = {
                "action": "wbsearchentities",
                "search": query,
                "language": "en",
                "format": "json",
                "limit": 2
            }
            resp = requests.get(
                "https://www.wikidata.org/w/api.php",
                params=search_params,
                headers={"User-Agent": "TruthShield/2.0"},
                timeout=5
            )
            if resp.status_code != 200:
                return []

            data = resp.json()
            results = []
            for item in data.get("search", []):
                entity_id = item.get("id")
                label = item.get("label", "")
                description = item.get("description", "")
                aliases = item.get("aliases", [])

                alias_str = f" (also known as: {', '.join(aliases)})" if aliases else ""
                snippet = f"Entity: {label}{alias_str}. Description: {description}."

                results.append(
                    Evidence(
                        title=f"Wikidata: {label} ({entity_id})",
                        url=f"https://www.wikidata.org/wiki/{entity_id}",
                        snippet=snippet,
                        source_score=0.75,
                    )
                )
            return results
        except Exception as e:
            logger.warning(f"Wikidata search failed: {e}")
            return []

    # ──────────────────────────────────────────────────────────
    # Source: Google Fact Check Tools API
    # ──────────────────────────────────────────────────────────

    def _google_factcheck(self, query: str) -> List[Evidence]:
        """Search Google Fact Check Tools API using API key from settings if configured."""
        try:
            settings = get_settings()
            key = settings.GOOGLE_FACTCHECK_API_KEY

            params = {"query": query, "languageCode": "en"}
            if key and len(key) > 5:
                params["key"] = key

            resp = requests.get(
                "https://factchecktools.googleapis.com/v1alpha1/claims:search",
                params=params,
                timeout=5,
            )
            if resp.status_code != 200:
                logger.debug(f"Google Fact Check API skipped or status code {resp.status_code}")
                return []

            data = resp.json()
            results = []
            for claim_review in data.get("claims", [])[:3]:
                reviews = claim_review.get("claimReview", [])
                for review in reviews[:1]:
                    publisher = review.get("publisher", {}).get("name", "Fact Checker")
                    results.append(
                        Evidence(
                            title=f"{publisher} Fact Check: {review.get('title', claim_review.get('text', 'Fact Check'))}",
                            url=review.get("url", ""),
                            snippet=f"Claim Reviewed: {claim_review.get('text', '')} — Rating: {review.get('textualRating', 'N/A')}",
                            source_score=0.95,
                        )
                    )
            return results
        except Exception as e:
            logger.warning(f"Google Fact Check API failed: {e}")
            return []

    # ──────────────────────────────────────────────────────────
    # Source: RSS Fact-Check Feeds
    # ──────────────────────────────────────────────────────────

    def _rss_fact_check_feeds(self, query: str) -> List[Evidence]:
        """Fetch and locally search Snopes, PolitiFact, and FactCheck.org RSS feeds."""
        if feedparser is None or fuzz is None:
            return []

        feeds = [
            ("Snopes", "https://www.snopes.com/feed/"),
            ("PolitiFact", "https://www.politifact.com/rss/factchecks/"),
            ("FactCheck.org", "https://www.factcheck.org/feed/"),
        ]

        results = []
        query_words = set(re.findall(r"\b[a-zA-Z]{3,}\b", query.lower()))

        for name, url in feeds:
            try:
                resp = requests.get(url, headers={"User-Agent": "TruthShield/2.0"}, timeout=5)
                if resp.status_code != 200:
                    continue

                feed = feedparser.parse(resp.content)
                for entry in feed.entries[:10]:
                    title = entry.get("title", "")
                    link = entry.get("link", "")
                    summary = entry.get("summary", "")
                    summary_clean = re.sub(r"<[^>]+>", "", summary).strip()

                    title_words = set(re.findall(r"\b[a-zA-Z]{3,}\b", title.lower()))
                    overlap = query_words.intersection(title_words)
                    ratio = fuzz.token_set_ratio(query.lower(), title.lower())

                    # Match if significant word overlap or fuzzy title matching
                    if len(overlap) >= 3 or ratio > 65:
                        results.append(
                            Evidence(
                                title=f"{name} RSS: {title}",
                                url=link,
                                snippet=summary_clean[:300] or title,
                                source_score=0.95,
                            )
                        )
            except Exception as e:
                logger.debug(f"RSS feed '{name}' failed: {e}")

        return results

    # ──────────────────────────────────────────────────────────
    # Source: Web Page Deep Scraping
    # ──────────────────────────────────────────────────────────

    def _deep_scrape_single_url(self, url: str, query: str) -> List[Evidence]:
        """Scrape the full body of a single target search result page to retrieve matching paragraphs."""
        from backend.preprocessor.url_scraper import URLScraper
        scraper = URLScraper()
        results = []

        query_words = set(w.lower() for w in re.findall(r"\b[a-zA-Z]{4,}\b", query))
        if not query_words:
            return []

        try:
            scraped = scraper.scrape(url)
            text = scraped.get("text", "")
            title = scraped.get("title", "")
            if not text or len(text) < 100:
                return []

            # Split body text into paragraphs
            paragraphs = [p.strip() for p in text.split("\n\n") if len(p.strip()) > 30]
            
            # Match and score paragraphs by keyword overlap
            scored_paras = []
            for para in paragraphs:
                para_words = set(w.lower() for w in re.findall(r"\b[a-zA-Z]{4,}\b", para))
                overlap = len(query_words.intersection(para_words))
                if overlap > 0:
                    scored_paras.append((overlap, para))

            scored_paras.sort(key=lambda x: x[0], reverse=True)

            # Return the top 2 matching paragraphs as deep evidence
            for overlap_count, para in scored_paras[:2]:
                results.append(
                    Evidence(
                        title=f"[Deep Extract] {title or urlparse(url).netloc}",
                        url=url,
                        snippet=para[:400],
                        source_score=self._score_source(url) * 1.1,  # Boost score for deep scraped details
                    )
                )
        except Exception as e:
            logger.debug(f"Deep scraping failed for '{url}': {e}")

        return results

    # ──────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────

    @staticmethod
    def _extract_search_terms(text: str) -> str:
        """Pull out likely entity names or significant words for Wikipedia."""
        entities = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", text)
        if entities:
            return " ".join(entities[:3])
        words = text.split()[:8]
        return " ".join(w for w in words if len(w) > 3)[:80]

    @staticmethod
    def _score_source(url: str) -> float:
        """Score a source URL based on known credibility database."""
        try:
            domain = urlparse(url).netloc.lower().replace("www.", "")
            for known_domain, score in SOURCE_CREDIBILITY.items():
                if known_domain in domain:
                    return score
            return 0.5
        except Exception:
            return 0.5
