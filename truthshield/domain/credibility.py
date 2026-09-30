"""
Source credibility.

The table and matching logic are carried over from the previous version
unchanged — they encode a set of bugs that were found the hard way and should
not be rediscovered:

* Matching is anchored to domain label boundaries. A naked substring test
  meant every host containing "gov" scored as an authoritative government
  source: govtjobsalert.blogspot.com, thegovernor.com and mygov-scam.tk all
  returned 1.0.
* There is exactly one implementation. Two copies previously drifted apart,
  with different unknown-domain defaults (0.30 vs 0.50) and different TLD
  tiers, and whichever ran last silently overwrote the other.
* The unknown-domain default is 0.50 because the demoted tiers below are
  calibrated against it. At 0.30 the demotions inverted, and aggregators and
  tabloids outranked genuinely unknown domains.
"""

from __future__ import annotations

from urllib.parse import urlparse

# ── Source Credibility Scores ─────────────────────────────────
# Score range: 0.0 (completely unreliable) to 1.0 (authoritative government source)
SOURCE_CREDIBILITY = {
    # ── Tier 1: Government & Official Organizations (0.95-1.0) ──
    "gov.in": 1.0,
    "gov.uk": 1.0,
    "gov.au": 1.0,
    "gov": 1.0,
    "who.int": 0.98,
    "un.org": 0.98,
    "unicef.org": 0.98,
    "worldbank.org": 0.97,
    "imf.org": 0.97,
    "nasa.gov": 0.98,
    "cdc.gov": 0.98,
    "nih.gov": 0.98,
    "europa.eu": 0.95,
    "pib.gov.in": 1.0,  # Press Information Bureau India

    # ── Tier 2: Fact-Checking Organizations (0.93-0.96) ──
    "snopes.com": 0.96,
    "factcheck.org": 0.96,
    "politifact.com": 0.96,
    "fullfact.org": 0.96,
    "factcheck.afp.com": 0.95,
    "altnews.in": 0.95,
    "boomlive.in": 0.95,
    "vishvasnews.com": 0.93,
    "smhoaxslayer.com": 0.90,
    "thequint.com/news/webqoof": 0.93,
    "checkyourfact.com": 0.90,
    "leadstories.com": 0.90,
    "africacheck.org": 0.93,
    "maldita.es": 0.93,

    # ── Tier 3: Wire Services (0.93-0.95) ──
    "reuters.com": 0.95,
    "apnews.com": 0.95,
    "afp.com": 0.93,
    "pti.in": 0.93,           # Press Trust of India
    "ians.in": 0.90,          # Indo-Asian News Service

    # ── Tier 4: Major International News (0.80-0.92) ──
    "bbc.com": 0.92,
    "bbc.co.uk": 0.92,
    "nytimes.com": 0.88,
    "washingtonpost.com": 0.85,
    "theguardian.com": 0.85,
    "economist.com": 0.88,
    "ft.com": 0.88,           # Financial Times
    "nature.com": 0.95,       # Nature journal
    "science.org": 0.95,      # Science journal
    "lancet.com": 0.95,       # The Lancet
    "bmj.com": 0.93,          # British Medical Journal
    "pubmed.ncbi.nlm.nih.gov": 0.95,
    "scholar.google.com": 0.80,

    # ── Tier 5: Major Regional/National News (0.70-0.82) ──
    "thehindu.com": 0.82,
    "indianexpress.com": 0.80,
    "ndtv.com": 0.75,
    "livemint.com": 0.78,
    "scroll.in": 0.75,
    "thewire.in": 0.75,
    "aljazeera.com": 0.78,
    "dw.com": 0.80,           # Deutsche Welle
    "france24.com": 0.78,
    "abc.net.au": 0.82,       # Australian Broadcasting Corporation
    "cbc.ca": 0.82,           # Canadian Broadcasting Corporation
    "npr.org": 0.82,
    "pbs.org": 0.82,
    "cnn.com": 0.72,
    "cnbc.com": 0.75,
    "bloomberg.com": 0.82,

    # ── Tier 6: Encyclopedias & Knowledge Bases (0.60-0.75) ──
    "wikipedia.org": 0.65,
    "britannica.com": 0.80,
    "wikidata.org": 0.75,

    # ── Tier 7: Sports & Specialized (0.70-0.85) ──
    "espncricinfo.com": 0.85,
    "icc-cricket.com": 0.90,
    "fifa.com": 0.90,
    "olympics.com": 0.90,

    # ── Tier 8: User-generated, social & homework sites (0.05-0.30) ──
    # Scored below the 0.50 unknown-domain default so they cannot be mistaken
    # for corroboration. Anonymous forums and joke listicles were previously
    # counted as supporting evidence for fabricated claims.
    "4chan.org": 0.05,
    "4channel.org": 0.05,
    "tiktok.com": 0.10,
    "pinterest.com": 0.10,
    "facebook.com": 0.15,
    "instagram.com": 0.15,
    "reddit.com": 0.20,
    "quora.com": 0.20,
    "answers.com": 0.20,
    "buzzfeed.com": 0.20,
    "neatorama.com": 0.20,
    "blogspot.com": 0.20,
    "wordpress.com": 0.20,
    "medium.com": 0.30,
    "brainly.com": 0.25,
    "chegg.com": 0.25,
    "coursehero.com": 0.25,
    "studyx.ai": 0.25,
    "numerade.com": 0.25,
    "youtube.com": 0.15,
    "x.com": 0.15,
    "twitter.com": 0.15,
    "vk.com": 0.10,
    "scribd.com": 0.20,
    "slideshare.net": 0.20,
    "homeworkify.net": 0.20,
    "gauthmath.com": 0.25,
    "vaia.com": 0.25,
    "toppr.com": 0.25,
    "doubtnut.com": 0.25,

    # ── Tier 9: Tabloids & low-editorial-standard outlets (0.25-0.40) ──
    # These carry a masthead and so were falling through to the unknown-domain
    # default, which ranked them alongside real reporting. A benchmark run
    # surfaced dailystar.co.uk as the top-ranked source for a moon-landing
    # hoax claim, above the Guardian and the Institute of Physics.
    "dailystar.co.uk": 0.25,
    "thesun.co.uk": 0.30,
    "dailymail.co.uk": 0.30,
    "mirror.co.uk": 0.35,
    "express.co.uk": 0.30,
    "nypost.com": 0.40,
    "tmz.com": 0.25,
    "radaronline.com": 0.25,
    "unilad.com": 0.25,
    "ladbible.com": 0.25,
    "cracked.com": 0.25,
    "theonion.com": 0.10,      # satire, routinely mistaken for reporting
    "babylonbee.com": 0.10,    # satire

    # ── Tier 10: Aggregators & redirect shells (0.45-0.50, deliberately neutral) ──
    # news.google.com links are interstitial redirects rather than articles, so
    # they are poor citations and sit just below the 0.50 unknown default to let
    # real reporting outrank them.
    #
    # They are NOT scored lower than that. An aggregator link says nothing about
    # whether a claim is true, but it made up ~28 of the evidence items per
    # benchmark run, so scoring it at 0.20 dragged the source-credibility
    # component down for every claim. That flipped "Water boils at 100 degrees
    # Celsius" from LIKELY TRUE (trust 78) to MIXED EVIDENCE (trust 45).
    # Neutral is the honest weight: demote for ranking, do not treat as a
    # signal of falsehood.
    "news.google.com": 0.45,
    "news.yahoo.com": 0.45,
    "msn.com": 0.45,
    "flipboard.com": 0.45,
}

KNOWN_DISINFO_DOMAINS = [
    "naturalnews.com",
    "infowars.com",
    "beforeitsnews.com",
    "yournewswire.com",
    "worldnewsdailyreport.com",
    "rt.com",
    "sputniknews.com",
    "principia-scientific.com",
    "nexusnewsfeed.com",
]


# ── Canonical Domain Credibility Scoring ─────────────────────
# Both SourceRanker and EvidenceRetriever previously carried their own copy of
# this lookup. The copies had drifted apart — different unknown-domain defaults
# (0.30 vs 0.50) and different TLD tiers — and SourceRanker.rank_evidence
# overwrites whatever the retriever assigned, so the retriever's numbers were
# dead code that still had to be kept in sync by hand. One implementation now
# serves both.
#
# Both copies also matched with a naked substring test (`known_domain in
# domain`). Because "gov" is a key worth 1.0, every host containing the letters
# "gov" scored as an authoritative government source: govtjobsalert.blogspot.com,
# thegovernor.com and mygov-scam.tk all came back 1.0, and pti.industries.com
# inherited Press Trust of India's 0.93. Matching is now anchored to domain
# label boundaries, so a pattern matches only the host itself or a subdomain of
# it.

# The score for a domain that is not in the table. The tier 8/9/10 entries above
# are calibrated against this value — aggregators sit just below it and tabloids
# below that — so it must stay 0.50 for those demotions to mean anything.
UNKNOWN_DOMAIN_SCORE = 0.50


def _normalize_host(host: str) -> str:
    """Lowercase a hostname and strip the www. prefix and any port."""
    host = host.lower().strip().rstrip(".")
    if ":" in host:
        host = host.split(":", 1)[0]
    if host.startswith("www."):
        host = host[4:]
    return host


def _host_matches(host: str, pattern: str) -> bool:
    """
    True when `host` is `pattern` or a subdomain of it.

    Anchored at label boundaries: "gov" matches "cdc.gov" but not
    "thegovernor.com", and "afp.com" matches "factcheck.afp.com" but not
    "notafp.com.example".
    """
    return host == pattern or host.endswith("." + pattern)


def score_domain(url: str) -> float:
    """
    Credibility score in [0.0, 1.0] for the source behind `url`.

    Known disinformation domains score 0.0 so callers can drop them outright.
    Where several table entries match, the most specific wins, so
    factcheck.afp.com keeps its fact-checker score rather than inheriting the
    wire service's.
    """
    try:
        parsed = urlparse(url if "//" in url else "//" + url)
        host = _normalize_host(parsed.netloc)
        path = (parsed.path or "").lower()
    except Exception:
        return UNKNOWN_DOMAIN_SCORE

    if not host:
        return UNKNOWN_DOMAIN_SCORE

    for disinfo_domain in KNOWN_DISINFO_DOMAINS:
        if _host_matches(host, _normalize_host(disinfo_domain)):
            return 0.0

    # Most specific match wins; a few entries qualify a domain with a path
    # prefix (thequint.com/news/webqoof), which is more specific still.
    best_score = None
    best_specificity = -1
    for pattern, score in SOURCE_CREDIBILITY.items():
        pattern_host, _, pattern_path = pattern.partition("/")
        if not _host_matches(host, _normalize_host(pattern_host)):
            continue
        if pattern_path and not path.startswith("/" + pattern_path):
            continue
        specificity = len(pattern)
        if specificity > best_specificity:
            best_specificity = specificity
            best_score = score

    if best_score is not None:
        return best_score

    # TLD fallbacks for hosts the table does not name.
    if host.endswith(".mil"):
        return 0.90
    if host.endswith((".edu", ".ac.in", ".ac.uk")):
        return 0.85
    if host.endswith(".org"):
        return 0.65

    return UNKNOWN_DOMAIN_SCORE
