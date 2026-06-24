"""
TruthShield — Evidence Retriever (v4 — Production Grade, Multi-Source)

Retrieves evidence from up to 12 sources concurrently with robust fallback chains:

  Tier 1 — Fact-Check Databases (highest priority):
    1. Google Fact Check Tools API (ClaimReview database)
    2. RSS Fact-Check feeds (Snopes, PolitiFact, FactCheck.org, AltNews, BoomLive)

  Tier 2 — Reliable Web Search APIs:
    3. Google Custom Search Engine (CSE) — 100 free queries/day
    4. SerpAPI Google Search — real Google results + Knowledge Graph
    5. Brave Search API — 2000 free queries/month, high quality

  Tier 3 — News APIs:
    6. NewsData.io — 200 free queries/day, 80k+ sources
    7. GNews API — 100 free queries/day
    8. Google News RSS — unlimited, no key needed
    9. GDELT API — free, global real-time news monitoring

  Tier 4 — Knowledge Bases:
    10. Wikipedia API (intro extracts)
    11. Google Knowledge Graph API — entity verification
    12. Wikidata Knowledge Graph

  Tier 5 — Fallback:
    13. DuckDuckGo (ddgs package, only if Tier 2 returns nothing)
    14. Deep Page Scraping (top 2 URLs)
"""

import logging
import math
import re
import socket
from typing import List, Optional, Dict
from urllib.parse import quote_plus, urlparse

import requests
from bs4 import BeautifulSoup

# Set global default socket timeout to prevent any third-party library thread from hanging indefinitely
socket.setdefaulttimeout(12.0)

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
    """Retrieve evidence from 12+ sources concurrently with intelligent fallback chains."""

    MAX_EVIDENCE_PER_CLAIM = 15

    # ── Class-level persistent HTTP session (Keep-Alive + connection pooling) ──
    _session = None

    @classmethod
    def _get_session(cls) -> requests.Session:
        """Get or create a persistent requests.Session with connection pooling."""
        if cls._session is None:
            cls._session = requests.Session()
            cls._session.headers.update({
                "User-Agent": "TruthShield/3.0 (Fact-Checking Bot; +https://truthshield.app)",
                "Accept": "application/json, text/html, */*",
                "Connection": "keep-alive",
            })
            # Configure connection pooling
            adapter = requests.adapters.HTTPAdapter(
                pool_connections=15,
                pool_maxsize=30,
                max_retries=2,
            )
            cls._session.mount("https://", adapter)
            cls._session.mount("http://", adapter)
            logger.info("Persistent HTTP session created with connection pooling.")
        return cls._session

    # ──────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────

    async def retrieve(self, claim: Claim) -> List[Evidence]:
        """Fetch evidence from all sources in parallel, dedup, and return."""
        # Preserve full claim for search — don't over-truncate
        search_query = self._formulate_search_query(claim.text)
        fact_check_query = self._formulate_factcheck_query(claim.text)

        wiki_query = (
            claim.entity
            if getattr(claim, "entity", None)
            else self._extract_search_terms(claim.text)
        )

        settings = get_settings()
        timeout = getattr(settings, "EVIDENCE_TIMEOUT", 12)

        import asyncio
        import os

        is_render = os.getenv("RENDER") == "true" or os.getenv("LOW_MEMORY") == "true"

        # ── Build task list dynamically based on available API keys ──
        tasks = []

        # Tier 1 — Fact-Check Databases (always run)
        tasks.append(asyncio.create_task(
            asyncio.to_thread(self._google_factcheck, search_query)
        ))
        tasks.append(asyncio.create_task(
            asyncio.to_thread(self._rss_fact_check_feeds, search_query)
        ))

        # Tier 2 — Reliable Web Search APIs (based on available keys)
        has_reliable_search = False

        if settings.GOOGLE_CSE_API_KEY and settings.GOOGLE_CSE_ID:
            has_reliable_search = True
            tasks.append(asyncio.create_task(
                asyncio.to_thread(self._google_cse_search, search_query)
            ))
            # Also search for fact-check variant
            tasks.append(asyncio.create_task(
                asyncio.to_thread(self._google_cse_search, fact_check_query)
            ))

        if settings.SERPAPI_API_KEY:
            has_reliable_search = True
            tasks.append(asyncio.create_task(
                asyncio.to_thread(self._serpapi_search, search_query)
            ))

        # Brave Search — free, no key needed for basic search
        tasks.append(asyncio.create_task(
            asyncio.to_thread(self._brave_search, search_query)
        ))

        # Tier 3 — News APIs
        if settings.NEWSDATA_API_KEY:
            tasks.append(asyncio.create_task(
                asyncio.to_thread(self._newsdata_search, search_query)
            ))

        if settings.GNEWS_API_KEY:
            tasks.append(asyncio.create_task(
                asyncio.to_thread(self._gnews_search, search_query)
            ))

        tasks.append(asyncio.create_task(
            asyncio.to_thread(self._google_news_rss_search, search_query)
        ))

        tasks.append(asyncio.create_task(
            asyncio.to_thread(self._gdelt_search, search_query)
        ))

        # Tier 4 — Knowledge Bases
        tasks.append(asyncio.create_task(
            asyncio.to_thread(self._search_wikipedia, wiki_query)
        ))
        tasks.append(asyncio.create_task(
            asyncio.to_thread(self._search_wikidata, wiki_query)
        ))

        if settings.GOOGLE_CSE_API_KEY:
            tasks.append(asyncio.create_task(
                asyncio.to_thread(self._google_knowledge_graph, wiki_query)
            ))

        # Allocate timeout for all sources
        done, pending = await asyncio.wait(tasks, timeout=max(3.0, timeout - 2.0))

        for task in pending:
            task.cancel()

        all_evidence: List[Evidence] = []
        for task in done:
            try:
                results = task.result()
                all_evidence.extend(results)
            except Exception as exc:
                logger.warning(f"Evidence source task failed: {exc}")

        # Tier 5 — DuckDuckGo fallback (only if reliable search returned nothing)
        reliable_results = [ev for ev in all_evidence if ev.source_score >= 0.5]
        if len(reliable_results) < 3 and not is_render:
            logger.info("Reliable sources returned < 3 results. Triggering DuckDuckGo fallback.")
            try:
                ddg_results = await asyncio.wait_for(
                    asyncio.to_thread(self._ddg_combined_search, search_query),
                    timeout=4.0
                )
                all_evidence.extend(ddg_results)
            except Exception as e:
                logger.warning(f"DuckDuckGo fallback failed: {e}")

        # Deep Page Scraping on top 2 candidate URLs (skip on Render)
        urls_to_scrape = []
        seen_urls = set()
        for ev in all_evidence:
            if ev.url and ev.url not in seen_urls:
                seen_urls.add(ev.url)
                domain = urlparse(ev.url).netloc.lower()
                if not any(skip in domain for skip in [
                    "wikipedia.org", "wikidata.org", "googleapis.com",
                    "google.com/search", "bing.com", "duckduckgo.com"
                ]):
                    urls_to_scrape.append(ev.url)

        if urls_to_scrape and not is_render:
            try:
                async def scrape_single_url(url):
                    return await asyncio.to_thread(self._deep_scrape_single_url, url, claim.text)

                deep_tasks = [scrape_single_url(url) for url in urls_to_scrape[:3]]
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
            if "[Deep Extract]" in ev.title:
                score += 0.15
            domain = urlparse(ev.url).netloc.lower() if ev.url else ""
            if any(fc in domain for fc in [
                "snopes.com", "politifact.com", "factcheck.org",
                "boomlive.in", "fullfact.org", "altnews.in",
                "factchecktools.googleapis.com"
            ]):
                score += 0.25
            # Relevance: keyword overlap
            claim_words = set(re.findall(r"\b[a-zA-Z]{4,}\b", claim.text.lower()))
            snippet_words = set(re.findall(r"\b[a-zA-Z]{4,}\b", ev.snippet.lower()))
            overlap = len(claim_words.intersection(snippet_words))
            score += min(0.20, overlap * 0.025)
            # Penalize very short snippets
            if len(ev.snippet) < 50:
                score -= 0.10
            # Boost long, detailed snippets
            if len(ev.snippet) > 200:
                score += 0.05
            return score

        unique.sort(key=get_evidence_quality, reverse=True)

        logger.info(
            f"Evidence for '{claim.text[:60]}…': "
            f"Retrieved {len(unique)} unique items (from {len(all_evidence)} raw)"
        )

        return unique[: self.MAX_EVIDENCE_PER_CLAIM]

    # ──────────────────────────────────────────────────────────
    # TIER 1: Fact-Check Databases
    # ──────────────────────────────────────────────────────────

    def _google_factcheck(self, query: str) -> List[Evidence]:
        """Search Google Fact Check Tools API using API key from settings if configured."""
        try:
            settings = get_settings()
            key = settings.GOOGLE_FACTCHECK_API_KEY

            params = {"query": query, "languageCode": "en"}
            if key and len(key) > 5:
                params["key"] = key

            resp = self._get_session().get(
                "https://factchecktools.googleapis.com/v1alpha1/claims:search",
                params=params,
                timeout=5,
            )
            if resp.status_code != 200:
                logger.debug(f"Google Fact Check API status code {resp.status_code}")
                return []

            data = resp.json()
            results = []
            for claim_review in data.get("claims", [])[:5]:
                reviews = claim_review.get("claimReview", [])
                for review in reviews[:1]:
                    publisher = review.get("publisher", {}).get("name", "Fact Checker")
                    rating = review.get("textualRating", "N/A")
                    results.append(
                        Evidence(
                            title=f"{publisher} Fact Check: {review.get('title', claim_review.get('text', 'Fact Check'))}",
                            url=review.get("url", ""),
                            snippet=f"Claim Reviewed: {claim_review.get('text', '')} — Rating: {rating}",
                            source_score=0.96,
                        )
                    )
            return results
        except Exception as e:
            logger.warning(f"Google Fact Check API failed: {e}")
            return []

    def _rss_fact_check_feeds(self, query: str) -> List[Evidence]:
        """Fetch and locally search RSS feeds from major fact-checking organizations."""
        if feedparser is None:
            return []

        feeds = [
            ("Snopes", "https://www.snopes.com/feed/"),
            ("PolitiFact", "https://www.politifact.com/rss/factchecks/"),
            ("FactCheck.org", "https://www.factcheck.org/feed/"),
            ("Full Fact", "https://fullfact.org/feed/"),
        ]

        results = []
        query_words = set(re.findall(r"\b[a-zA-Z]{3,}\b", query.lower()))

        for name, url in feeds:
            try:
                resp = self._get_session().get(url, timeout=4)
                if resp.status_code != 200:
                    continue

                feed = feedparser.parse(resp.content)
                for entry in feed.entries[:15]:
                    title = entry.get("title", "")
                    link = entry.get("link", "")
                    summary = entry.get("summary", "")
                    summary_clean = re.sub(r"<[^>]+>", "", summary).strip()

                    title_words = set(re.findall(r"\b[a-zA-Z]{3,}\b", title.lower()))
                    overlap = query_words.intersection(title_words)

                    # Use fuzzy matching if fuzzywuzzy is available
                    ratio = 0
                    if fuzz:
                        ratio = fuzz.token_set_ratio(query.lower(), title.lower())

                    if len(overlap) >= 2 or ratio > 60:
                        results.append(
                            Evidence(
                                title=f"{name}: {title}",
                                url=link,
                                snippet=summary_clean[:500] or title,
                                source_score=0.95,
                            )
                        )
            except Exception as e:
                logger.debug(f"RSS feed '{name}' failed: {e}")

        return results

    # ──────────────────────────────────────────────────────────
    # TIER 2: Reliable Web Search APIs
    # ──────────────────────────────────────────────────────────

    def _google_cse_search(self, query: str, num: int = 5) -> List[Evidence]:
        """Google Custom Search Engine — 100 free queries/day, highest quality results."""
        try:
            settings = get_settings()
            key = settings.GOOGLE_CSE_API_KEY
            cx = settings.GOOGLE_CSE_ID
            if not key or not cx:
                return []

            params = {
                "key": key,
                "cx": cx,
                "q": query,
                "num": min(num, 10),
            }
            resp = self._get_session().get(
                "https://www.googleapis.com/customsearch/v1",
                params=params,
                timeout=5,
            )
            if resp.status_code != 200:
                logger.debug(f"Google CSE returned status {resp.status_code}")
                return []

            data = resp.json()
            results = []
            for item in data.get("items", [])[:num]:
                title = item.get("title", "")
                link = item.get("link", "")
                snippet = item.get("snippet", "")
                # Some results include pagemap with longer descriptions
                pagemap = item.get("pagemap", {})
                metatags = pagemap.get("metatags", [{}])
                if metatags:
                    og_desc = metatags[0].get("og:description", "")
                    if og_desc and len(og_desc) > len(snippet):
                        snippet = og_desc

                if title and link:
                    results.append(
                        Evidence(
                            title=f"Google: {title}",
                            url=link,
                            snippet=snippet[:500],
                            source_score=self._score_source(link),
                        )
                    )
            logger.info(f"Google CSE returned {len(results)} results")
            return results
        except Exception as e:
            logger.warning(f"Google CSE search failed: {e}")
            return []

    def _serpapi_search(self, query: str) -> List[Evidence]:
        """SerpAPI — real Google results including Knowledge Graph panels."""
        try:
            settings = get_settings()
            key = settings.SERPAPI_API_KEY
            if not key:
                return []

            params = {
                "api_key": key,
                "q": query,
                "engine": "google",
                "num": 5,
                "hl": "en",
            }
            resp = self._get_session().get(
                "https://serpapi.com/search",
                params=params,
                timeout=5,
            )
            if resp.status_code != 200:
                return []

            data = resp.json()
            results = []

            # Knowledge Graph (highest value for entity verification)
            kg = data.get("knowledge_graph", {})
            if kg:
                kg_title = kg.get("title", "")
                kg_desc = kg.get("description", "")
                kg_source = kg.get("source", {}).get("link", "")
                if kg_title and kg_desc:
                    # Build rich snippet from Knowledge Graph attributes
                    attrs = []
                    for key_name in ["type", "born", "died", "founded", "headquarters",
                                     "area", "population", "capital", "president",
                                     "prime_minister", "official_language"]:
                        val = kg.get(key_name)
                        if val:
                            attrs.append(f"{key_name.replace('_', ' ').title()}: {val}")
                    attrs_str = " | ".join(attrs[:5])
                    full_snippet = f"{kg_desc}. {attrs_str}" if attrs_str else kg_desc

                    results.append(
                        Evidence(
                            title=f"Knowledge Graph: {kg_title}",
                            url=kg_source or f"https://www.google.com/search?q={quote_plus(query)}",
                            snippet=full_snippet[:500],
                            source_score=0.90,
                        )
                    )

            # Organic results
            for item in data.get("organic_results", [])[:5]:
                title = item.get("title", "")
                link = item.get("link", "")
                snippet = item.get("snippet", "")
                if title and link:
                    results.append(
                        Evidence(
                            title=title,
                            url=link,
                            snippet=snippet[:500],
                            source_score=self._score_source(link),
                        )
                    )

            logger.info(f"SerpAPI returned {len(results)} results")
            return results
        except Exception as e:
            logger.warning(f"SerpAPI search failed: {e}")
            return []

    def _brave_search(self, query: str) -> List[Evidence]:
        """Brave Search API — free web search, no key needed for basic queries."""
        try:
            settings = get_settings()

            # Brave Search Web API (with API key if available)
            headers = {"Accept": "application/json"}
            brave_key = getattr(settings, "BRAVE_API_KEY", "")
            if brave_key:
                headers["X-Subscription-Token"] = brave_key
                params = {"q": query, "count": 5, "text_decorations": False}
                resp = self._get_session().get(
                    "https://api.search.brave.com/res/v1/web/search",
                    params=params,
                    headers=headers,
                    timeout=5,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    results = []
                    for item in data.get("web", {}).get("results", [])[:5]:
                        title = item.get("title", "")
                        link = item.get("url", "")
                        snippet = item.get("description", "")
                        if title and link:
                            results.append(
                                Evidence(
                                    title=f"Brave: {title}",
                                    url=link,
                                    snippet=snippet[:500],
                                    source_score=self._score_source(link),
                                )
                            )
                    if results:
                        logger.info(f"Brave Search API returned {len(results)} results")
                        return results

            # Fallback: Brave Search Goggles (no key needed, HTML scrape)
            resp = self._get_session().get(
                f"https://search.brave.com/search?q={quote_plus(query)}&source=web",
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
                timeout=4,
            )
            if resp.status_code != 200:
                return []

            soup = BeautifulSoup(resp.text, "html.parser")
            results = []
            for item in soup.select(".snippet")[:5]:
                title_el = item.select_one(".snippet-title")
                desc_el = item.select_one(".snippet-description")
                link_el = item.select_one("a[href]")
                if title_el and link_el:
                    href = link_el.get("href", "")
                    if href.startswith("/"):
                        continue
                    results.append(
                        Evidence(
                            title=f"Brave: {title_el.get_text(strip=True)}",
                            url=href,
                            snippet=(desc_el.get_text(strip=True) if desc_el else "")[:500],
                            source_score=self._score_source(href),
                        )
                    )
            logger.info(f"Brave Search scrape returned {len(results)} results")
            return results
        except Exception as e:
            logger.warning(f"Brave Search failed: {e}")
            return []

    # ──────────────────────────────────────────────────────────
    # TIER 3: News APIs
    # ──────────────────────────────────────────────────────────

    def _newsdata_search(self, query: str) -> List[Evidence]:
        """NewsData.io — 200 free queries/day, 80,000+ news sources worldwide."""
        try:
            settings = get_settings()
            key = settings.NEWSDATA_API_KEY
            if not key:
                return []

            params = {
                "apikey": key,
                "q": query,
                "language": "en",
                "size": 5,
            }
            resp = self._get_session().get(
                "https://newsdata.io/api/1/latest",
                params=params,
                timeout=5,
            )
            if resp.status_code != 200:
                return []

            data = resp.json()
            results = []
            for article in data.get("results", [])[:5]:
                title = article.get("title", "")
                link = article.get("link", "")
                desc = article.get("description", "") or article.get("content", "")
                source = article.get("source_name", "")
                if title and link:
                    results.append(
                        Evidence(
                            title=f"NewsData ({source}): {title}",
                            url=link,
                            snippet=(desc or title)[:500],
                            source_score=self._score_source(link),
                        )
                    )
            logger.info(f"NewsData.io returned {len(results)} results")
            return results
        except Exception as e:
            logger.warning(f"NewsData.io search failed: {e}")
            return []

    def _gnews_search(self, query: str) -> List[Evidence]:
        """GNews API — 100 free queries/day, aggregates from major news sources."""
        try:
            settings = get_settings()
            key = settings.GNEWS_API_KEY
            if not key:
                return []

            params = {
                "token": key,
                "q": query,
                "lang": "en",
                "max": 5,
            }
            resp = self._get_session().get(
                "https://gnews.io/api/v4/search",
                params=params,
                timeout=5,
            )
            if resp.status_code != 200:
                return []

            data = resp.json()
            results = []
            for article in data.get("articles", [])[:5]:
                title = article.get("title", "")
                link = article.get("url", "")
                desc = article.get("description", "") or article.get("content", "")
                source = article.get("source", {}).get("name", "")
                if title and link:
                    results.append(
                        Evidence(
                            title=f"GNews ({source}): {title}",
                            url=link,
                            snippet=(desc or title)[:500],
                            source_score=self._score_source(link),
                        )
                    )
            logger.info(f"GNews returned {len(results)} results")
            return results
        except Exception as e:
            logger.warning(f"GNews search failed: {e}")
            return []

    def _google_news_rss_search(self, query: str, max_results: int = 5) -> List[Evidence]:
        """Google News RSS — unlimited, no key needed."""
        import urllib.parse
        encoded_query = urllib.parse.quote_plus(query)
        url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"
        results = []
        try:
            resp = self._get_session().get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=4)
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
                            title=f"Google News: {title}",
                            url=link,
                            snippet=summary_clean[:500] or title,
                            source_score=self._score_source(link),
                        )
                    )
            return results
        except Exception as e:
            logger.warning(f"Google News RSS search failed: {e}")
            return []

    def _gdelt_search(self, query: str) -> List[Evidence]:
        """GDELT API — free, global real-time news monitoring (250+ countries, 100+ languages)."""
        try:
            params = {
                "query": query,
                "mode": "ArtList",
                "maxrecords": 5,
                "format": "json",
                "sort": "DateDesc",
            }
            resp = self._get_session().get(
                "https://api.gdeltproject.org/api/v2/doc/doc",
                params=params,
                timeout=8,
            )
            if resp.status_code != 200:
                return []

            data = resp.json()
            results = []
            for article in data.get("articles", [])[:5]:
                title = article.get("title", "")
                url = article.get("url", "")
                source = article.get("domain", "")
                seendate = article.get("seendate", "")
                if title and url:
                    results.append(
                        Evidence(
                            title=f"GDELT ({source}): {title}",
                            url=url,
                            snippet=f"{title} (Published: {seendate[:10] if seendate else 'Unknown'})",
                            source_score=self._score_source(url),
                        )
                    )
            logger.info(f"GDELT returned {len(results)} results")
            return results
        except Exception as e:
            logger.warning(f"GDELT search failed: {e}")
            return []

    # ──────────────────────────────────────────────────────────
    # TIER 4: Knowledge Bases
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
                "srlimit": 3,
            }
            resp = self._get_session().get(
                "https://en.wikipedia.org/w/api.php",
                params=params,
                timeout=4,
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
                    ext_resp = self._get_session().get(
                        "https://en.wikipedia.org/w/api.php",
                        params=extract_params,
                        timeout=4,
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
                        snippet=snippet[:500],
                        source_score=0.65,
                    )
                )
            return results
        except Exception as e:
            logger.warning(f"Wikipedia search failed: {e}")
            return []

    def _google_knowledge_graph(self, query: str) -> List[Evidence]:
        """Google Knowledge Graph Search API — entity verification with structured data."""
        try:
            settings = get_settings()
            key = settings.GOOGLE_CSE_API_KEY  # Reuses the same Google API key
            if not key:
                return []

            params = {
                "query": query,
                "key": key,
                "limit": 3,
                "indent": True,
            }
            resp = self._get_session().get(
                "https://kgsearch.googleapis.com/v1/entities:search",
                params=params,
                timeout=4,
            )
            if resp.status_code != 200:
                return []

            data = resp.json()
            results = []
            for element in data.get("itemListElement", [])[:3]:
                result = element.get("result", {})
                name = result.get("name", "")
                description = result.get("description", "")
                detailed_desc = result.get("detailedDescription", {})
                article_body = detailed_desc.get("articleBody", "")
                url = detailed_desc.get("url", "")
                types = result.get("@type", [])
                type_str = ", ".join(types[:3]) if isinstance(types, list) else str(types)

                snippet = f"{description}. {article_body}" if article_body else description
                if type_str:
                    snippet = f"[{type_str}] {snippet}"

                if name and snippet:
                    results.append(
                        Evidence(
                            title=f"Knowledge Graph: {name}",
                            url=url or f"https://www.google.com/search?kgmid={result.get('@id', '')}",
                            snippet=snippet[:500],
                            source_score=0.85,
                        )
                    )
            logger.info(f"Google Knowledge Graph returned {len(results)} results")
            return results
        except Exception as e:
            logger.warning(f"Google Knowledge Graph failed: {e}")
            return []

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
            resp = self._get_session().get(
                "https://www.wikidata.org/w/api.php",
                params=search_params,
                timeout=4,
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
    # TIER 5: Fallback — DuckDuckGo
    # ──────────────────────────────────────────────────────────

    def _ddg_combined_search(self, query: str) -> List[Evidence]:
        """Combined web and news search via ddgs package, falling back to DDG Lite scraper."""
        results = []

        import os
        is_render = os.getenv("RENDER") == "true" or os.getenv("LOW_MEMORY") == "true"

        if DDGS is not None and not is_render:
            try:
                with DDGS(timeout=3) as ddgs:
                    try:
                        for r in ddgs.text(query, max_results=5):
                            url = r.get("href", r.get("link", ""))
                            title = r.get("title", "")
                            snippet = r.get("body", r.get("snippet", ""))
                            if title and url:
                                results.append(
                                    Evidence(
                                        title=title,
                                        url=url,
                                        snippet=(snippet or "")[:500],
                                        source_score=self._score_source(url),
                                    )
                                )
                    except Exception as e:
                        logger.warning(f"ddgs text search failed: {e}")

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
                                        snippet=(snippet or "")[:500],
                                        source_score=self._score_source(url),
                                    )
                                )
                    except Exception as e:
                        logger.warning(f"ddgs news search failed: {e}")
            except Exception as e:
                logger.warning(f"DDGS initialization failed: {e}")

        if not results and not is_render:
            results.extend(self._ddg_lite_search(query))

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
            resp = self._get_session().post(url, headers=headers, data=data, timeout=4)
            if resp.status_code != 200:
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
                            snippet=snippet[:500],
                            source_score=self._score_source(href),
                        )
                    )
            return results
        except Exception as e:
            logger.warning(f"DDG Lite scraper failed: {e}")
            return []

    # ──────────────────────────────────────────────────────────
    # Deep Page Scraping
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

            paragraphs = [p.strip() for p in text.split("\n\n") if len(p.strip()) > 30]

            scored_paras = []
            for para in paragraphs:
                para_words = set(w.lower() for w in re.findall(r"\b[a-zA-Z]{4,}\b", para))
                overlap = len(query_words.intersection(para_words))
                if overlap > 0:
                    scored_paras.append((overlap, para))

            scored_paras.sort(key=lambda x: x[0], reverse=True)

            for overlap_count, para in scored_paras[:2]:
                results.append(
                    Evidence(
                        title=f"[Deep Extract] {title or urlparse(url).netloc}",
                        url=url,
                        snippet=para[:500],
                        source_score=self._score_source(url) * 1.1,
                    )
                )
        except Exception as e:
            logger.debug(f"Deep scraping failed for '{url}': {e}")

        return results

    # ──────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────

    @staticmethod
    def _formulate_search_query(text: str) -> str:
        """Formulate a search query that preserves the full claim semantics.
        
        KEY FIX: Previous version truncated to 7 words, losing critical context.
        Now preserves the full claim for short claims (< 120 chars) and uses
        smarter extraction for longer texts.
        """
        if not text:
            return ""
        
        text = text.strip()
        
        # Short claims (< 120 chars): use the FULL text as-is
        if len(text) <= 120:
            # Just clean up extra whitespace/punctuation
            clean = re.sub(r"[^\w\s\u0900-\u097F\u0B80-\u0BFF'-]", " ", text)
            return " ".join(clean.split())

        # Longer texts: extract the most important 12 words
        clean = re.sub(r"[^\w\s\u0900-\u097F\u0B80-\u0BFF]", " ", text)
        words = clean.split()

        stopwords = {
            "who", "was", "also", "with", "from", "that", "this", "then", "them",
            "their", "there", "have", "been", "were", "about", "above", "after",
            "he", "she", "they", "we", "you", "me", "him", "her", "us", "his",
            "और", "तथा", "तथापि", "लेकिन", "कि", "यह", "वह", "है", "हैं", "था", "थे",
            "மற்றும்", "ஆனால்", "அது", "இந்த", "அவர்", "இருந்தது", "உள்ளது"
        }

        filtered = [w for w in words if w.lower() not in stopwords and len(w) > 2]

        # Prioritize capitalized words (entities), numbers, and unique terms
        if len(filtered) > 12:
            entities = [w for w in filtered if w[0].isupper() and w.isalpha()]
            numbers = [w for w in filtered if any(c.isdigit() for c in w)]
            other = [w for w in filtered if w not in entities and w not in numbers]
            combined = entities[:5] + numbers[:3] + other[:4]
            return " ".join(combined[:12])

        return " ".join(filtered)

    @staticmethod
    def _formulate_factcheck_query(text: str) -> str:
        """Create a fact-check-specific search query to find existing fact-checks."""
        base = EvidenceRetriever._formulate_search_query(text)
        # Append "fact check" to target fact-checking articles
        return f"{base} fact check"

    @staticmethod
    def _extract_search_terms(text: str) -> str:
        """Pull out likely entity names or significant words for Wikipedia."""
        entities = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", text)
        if entities:
            return " ".join(entities[:4])
        words = text.split()[:10]
        return " ".join(w for w in words if len(w) > 3)[:100]

    @staticmethod
    def _score_source(url: str) -> float:
        """Score a source URL based on known credibility database."""
        try:
            domain = urlparse(url).netloc.lower().replace("www.", "")
            for known_domain, score in SOURCE_CREDIBILITY.items():
                if known_domain in domain:
                    return score
            # TLD-based scoring for unknown domains
            if domain.endswith((".gov", ".gov.in", ".gov.uk", ".gov.au")):
                return 0.95
            if domain.endswith((".edu", ".ac.in", ".ac.uk")):
                return 0.80
            if domain.endswith(".org"):
                return 0.60
            return 0.50
        except Exception:
            return 0.50
