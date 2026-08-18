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

  Tier 4 — General web search (no key required):
    9. DuckDuckGo via the ddgs package — primary broad-coverage source

  Tier 5 — Knowledge Bases:
    10. Wikipedia API (intro extracts)
    11. Google Knowledge Graph API — entity verification
    12. Wikidata Knowledge Graph

  Tier 6 — Refinement:
    13. Deep Page Scraping (top 2 URLs, only with budget left)

Sources are collected against a deadline with early exit, so a slow upstream
cannot set the latency floor for every request.
"""

import logging
import math
import re
import socket
import time
from collections import OrderedDict
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

    # Stop waiting on slow sources once the fast, authoritative ones have
    # answered — the tail sources rarely change the verdict but always cost
    # the full timeout budget.
    EARLY_EXIT_STRONG = 3
    EARLY_EXIT_TOTAL = 8
    STRONG_SOURCE_SCORE = 0.85

    # Once we hold enough usable evidence, give the remaining sources only a
    # short grace period rather than the whole budget. Without this a single
    # slow upstream sets the latency floor for every request.
    MIN_USABLE_EVIDENCE = 5
    STRAGGLER_GRACE_SECONDS = 1.0
    MIN_RELEVANCE = 0.34

    # ── Class-level persistent HTTP session (Keep-Alive + connection pooling) ──
    _session = None

    # Claims extracted from one submission overlap heavily, so the same query
    # would otherwise hit every upstream source once per claim.
    _query_cache: "OrderedDict[str, List[Evidence]]" = OrderedDict()
    _QUERY_CACHE_MAX = 128
    _QUERY_CACHE_TTL = 300.0

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

    @staticmethod
    def _relevance(claim_text: str, ev: Evidence) -> float:
        """Fraction of the claim's content words present in this evidence item."""
        stop = {
            "the", "and", "for", "that", "this", "with", "from", "was", "were",
            "are", "has", "have", "had", "its", "their", "according", "said",
        }
        claim_words = {
            w for w in re.findall(r"\b[a-zA-Z]{4,}\b", claim_text.lower()) if w not in stop
        }
        if not claim_words:
            return 0.0
        ev_words = set(re.findall(r"\b[a-zA-Z]{4,}\b", f"{ev.title} {ev.snippet}".lower()))
        return len(claim_words & ev_words) / len(claim_words)

    @classmethod
    def _cache_get(cls, key: str) -> Optional[List[Evidence]]:
        entry = cls._query_cache.get(key)
        if entry is None:
            return None
        ts, evidence = entry
        if time.time() - ts > cls._QUERY_CACHE_TTL:
            del cls._query_cache[key]
            return None
        cls._query_cache.move_to_end(key)
        # Callers mutate Evidence.stance, so hand back independent copies.
        return [ev.model_copy(deep=True) for ev in evidence]

    @classmethod
    def _cache_set(cls, key: str, evidence: List[Evidence]) -> None:
        cls._query_cache[key] = (time.time(), [ev.model_copy(deep=True) for ev in evidence])
        cls._query_cache.move_to_end(key)
        while len(cls._query_cache) > cls._QUERY_CACHE_MAX:
            cls._query_cache.popitem(last=False)

    async def retrieve(self, claim: Claim) -> List[Evidence]:
        """Fetch evidence from all sources in parallel, dedup, and return."""
        # Preserve full claim for search — don't over-truncate
        search_query = self._formulate_search_query(claim.text)
        fact_check_query = self._formulate_factcheck_query(claim.text)

        cached = self._cache_get(search_query)
        if cached is not None:
            logger.info(f"Evidence cache HIT for '{search_query[:60]}' ({len(cached)} items)")
            return cached

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

        if getattr(settings, "BRAVE_API_KEY", ""):
            has_reliable_search = True
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

        # General web search — the only broad-coverage source that needs no API
        # key, so it runs as a primary source rather than a last-resort fallback.
        # Encyclopedia lookups alone cannot verify a claim.
        if not is_render:
            tasks.append(asyncio.create_task(
                asyncio.to_thread(self._ddg_combined_search, search_query)
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

        # Collect results as they land rather than waiting on the slowest source.
        # Fact-check databases and CSE usually answer in well under a second; the
        # news/GDELT tail routinely takes the entire budget without changing the
        # verdict, so stop once the authoritative sources have reported.
        deadline = time.monotonic() + max(3.0, timeout - 2.0)
        grace_deadline: Optional[float] = None
        pending = set(tasks)
        all_evidence: List[Evidence] = []
        strong_count = 0
        relevant_count = 0

        while pending:
            limit = deadline if grace_deadline is None else min(deadline, grace_deadline)
            remaining = limit - time.monotonic()
            if remaining <= 0:
                break
            done, pending = await asyncio.wait(
                pending, timeout=remaining, return_when=asyncio.FIRST_COMPLETED
            )
            if not done:
                break
            for task in done:
                try:
                    results = task.result()
                except Exception as exc:
                    logger.warning(f"Evidence source task failed: {exc}")
                    continue
                all_evidence.extend(results)
                for ev in results:
                    # Only evidence that actually discusses the claim counts
                    # toward "we have enough" — otherwise an off-topic
                    # encyclopedia hit ends the search for a claim we have
                    # found nothing about.
                    if self._relevance(claim.text, ev) >= self.MIN_RELEVANCE:
                        relevant_count += 1
                        if ev.source_score >= self.STRONG_SOURCE_SCORE:
                            strong_count += 1
            if strong_count >= self.EARLY_EXIT_STRONG and relevant_count >= self.EARLY_EXIT_TOTAL:
                logger.info(
                    f"Evidence early-exit: {strong_count} strong / {relevant_count} relevant "
                    f"with {len(pending)} sources still outstanding"
                )
                break
            if grace_deadline is None and relevant_count >= self.MIN_USABLE_EVIDENCE:
                grace_deadline = time.monotonic() + self.STRAGGLER_GRACE_SECONDS

        for task in pending:
            task.cancel()

        # Last-resort retry with a fact-check-oriented query when nothing
        # on-topic came back. Gated on relevance, not raw source score — a
        # high-scoring but off-topic hit is not evidence about this claim.
        if relevant_count < 2 and not is_render:
            logger.info("No on-topic evidence found. Retrying web search with fact-check query.")
            try:
                retry_results = await asyncio.wait_for(
                    asyncio.to_thread(self._ddg_combined_search, fact_check_query),
                    timeout=4.0
                )
                all_evidence.extend(retry_results)
            except Exception as e:
                logger.warning(f"Fact-check web search retry failed: {e}")

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

        # Deep scraping is a refinement, not a requirement — only run it with
        # budget left over, and never let it extend past the deadline.
        scrape_budget = deadline - time.monotonic()
        if urls_to_scrape and not is_render and scrape_budget > 1.0:
            try:
                async def scrape_single_url(url):
                    return await asyncio.to_thread(self._deep_scrape_single_url, url, claim.text)

                deep_tasks = [scrape_single_url(url) for url in urls_to_scrape[:2]]
                deep_results = await asyncio.wait_for(
                    asyncio.gather(*deep_tasks, return_exceptions=True),
                    timeout=scrape_budget,
                )
                for res in deep_results:
                    if isinstance(res, list):
                        all_evidence.extend(res)
            except asyncio.TimeoutError:
                logger.info("Deep scraping skipped: evidence budget exhausted")
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
            # Relevance dominates: a highly credible source that does not
            # discuss the claim is worse evidence than a moderate source that
            # does, so off-topic items are pushed below everything on-topic.
            rel = self._relevance(claim.text, ev)
            if rel < self.MIN_RELEVANCE:
                score -= 0.60
            else:
                score += rel * 0.40
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

        result = unique[: self.MAX_EVIDENCE_PER_CLAIM]
        self._cache_set(search_query, result)
        return result

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

        # Fetch all feeds concurrently — serially these cost 4x the slowest feed
        # and routinely consumed the whole evidence budget on their own.
        from concurrent.futures import ThreadPoolExecutor

        def _fetch(feed_spec):
            name, url = feed_spec
            try:
                resp = self._get_session().get(url, timeout=(2, 2))
                if resp.status_code != 200:
                    return name, None
                return name, resp.content
            except Exception as e:
                logger.debug(f"RSS feed '{name}' failed: {e}")
                return name, None

        with ThreadPoolExecutor(max_workers=len(feeds)) as pool:
            fetched = list(pool.map(_fetch, feeds))

        for name, content in fetched:
            if content is None:
                continue
            try:
                feed = feedparser.parse(content)
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

            # Without a key there is nothing to do here — Brave blocks the
            # HTML scrape, so it only ever cost a request and returned nothing.
            return []
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

            hits = data.get("query", {}).get("search", [])
            if not hits:
                return []

            titles = [item.get("title", "") for item in hits if item.get("title")]

            # One batched extracts call for every hit — the API accepts
            # pipe-separated titles, so this replaces one request per result.
            extracts: Dict[str, str] = {}
            try:
                ext_resp = self._get_session().get(
                    "https://en.wikipedia.org/w/api.php",
                    params={
                        "action": "query",
                        "prop": "extracts",
                        "exintro": 1,
                        "explaintext": 1,
                        "titles": "|".join(titles),
                        "format": "json",
                    },
                    timeout=4,
                )
                for page_data in ext_resp.json().get("query", {}).get("pages", {}).values():
                    if "extract" in page_data:
                        extracts[page_data.get("title", "")] = page_data["extract"]
            except Exception as ext_err:
                logger.debug(f"Batched Wikipedia extract fetch failed: {ext_err}")

            results = []
            for item in hits:
                page_title = item.get("title", "")
                snippet = extracts.get(page_title) or re.sub(
                    r"<[^>]+>", "", item.get("snippet", "")
                )
                results.append(
                    Evidence(
                        title=f"Wikipedia: {page_title}",
                        url=f"https://en.wikipedia.org/wiki/{quote_plus(page_title)}",
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
