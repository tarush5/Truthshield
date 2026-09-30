"""
Which evidence sources this deployment can actually reach.

The retriever fans out across a dozen providers and quietly skips the ones
with no API key. That is the right runtime behaviour -- an analysis should
not fail because an optional provider is unconfigured -- but it made a
badly degraded deployment indistinguishable from a healthy one. With no
keys at all the system still returns *a* result, just a much worse one,
built from whatever the keyless fallbacks scraped together.

That is not a hypothetical. It is the default state of a fresh checkout:
`.env.example` ships every search key blank, so the system runs on
DuckDuckGo, Google News RSS and Wikipedia alone, and the reports it
produces look normal while resting on a fraction of the intended evidence.

This module names that state so `/health` can report it, and so the
difference between "no keys configured" and "search is broken" is visible
without reading the retriever.
"""

from __future__ import annotations

from typing import Dict, List

from truthshield.settings import get_settings

# Providers that need no credentials. Always attempted, and the only thing
# standing between an unconfigured deployment and no evidence at all.
KEYLESS = (
    ("wikipedia", "Wikipedia and Wikidata"),
    ("factcheck_rss", "Fact-check RSS feeds"),
    ("google_news_rss", "Google News RSS"),
    ("duckduckgo", "DuckDuckGo"),
)

# Providers gated on an API key: the setting that enables each, and what it
# contributes that the keyless set cannot.
KEYED = (
    ("google_factcheck", ("GOOGLE_FACTCHECK_API_KEY",),
     "Google Fact Check Tools — published fact-checks with explicit ratings"),
    ("google_cse", ("GOOGLE_CSE_API_KEY", "GOOGLE_CSE_ID"),
     "Google Programmable Search — the broadest general web index"),
    ("serpapi", ("SERPAPI_API_KEY",),
     "SerpAPI — Google results without scraping"),
    ("brave", ("BRAVE_API_KEY",),
     "Brave Search — an independent index"),
    ("newsdata", ("NEWSDATA_API_KEY",),
     "NewsData — current news coverage"),
    ("gnews", ("GNEWS_API_KEY",),
     "GNews — current news coverage"),
)


def _configured(setting_names) -> bool:
    settings = get_settings()
    return all(bool(getattr(settings, name, "")) for name in setting_names)


def search_providers() -> Dict:
    """
    Provider status, and an honest verdict on the search tier.

    `degraded` is the field that matters. It is true when no keyed provider
    is configured, which means every result came from the keyless fallbacks
    -- usable for a demo, well short of what the pipeline is designed around.
    """
    active: List[str] = [key for key, _ in KEYLESS]
    missing: List[Dict] = []

    for key, settings_needed, contributes in KEYED:
        if _configured(settings_needed):
            active.append(key)
        else:
            missing.append({
                "provider": key,
                "requires": list(settings_needed),
                "contributes": contributes,
            })

    keyed_active = len(active) - len(KEYLESS)

    return {
        "active": active,
        "keyed_active": keyed_active,
        "missing": missing,
        "degraded": keyed_active == 0,
        "detail": (
            "No search API keys are configured. Evidence comes only from "
            "DuckDuckGo, RSS feeds and Wikipedia, which is materially worse "
            "than the intended retrieval and will show up as weak or "
            "off-topic sources."
            if keyed_active == 0
            else f"{keyed_active} keyed search provider(s) configured."
        ),
    }


def llm_providers() -> Dict:
    """
    Whether a grounded explanation can be generated at all.

    Absent a key this is not an error -- the engine's own reasoning is shown
    instead -- but an operator wondering why no explanations ever appear
    should be able to see the reason here rather than infer it.
    """
    settings = get_settings()
    available = [
        name for name, key in (
            ("gemini", settings.GEMINI_API_KEY),
            ("anthropic", settings.ANTHROPIC_API_KEY),
        ) if key
    ]
    return {
        "active": available,
        "available": bool(available),
        "detail": (
            "No LLM key configured; reports show the engine's own reasoning "
            "instead of a generated explanation."
            if not available
            else f"Grounded explanations via {', '.join(available)}."
        ),
    }
