"""
TruthShield — Configuration Module
Centralized configuration management using Pydantic Settings.
"""

import os
import logging
from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings
from pydantic import Field, model_validator


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # ── API Keys ──────────────────────────────────────────────
    ANTHROPIC_API_KEY: str = Field(default="", description="Anthropic Claude API key")
    GEMINI_API_KEY: str = Field(default="", description="Google Gemini API key (free from aistudio.google.com)")
    SERPAPI_API_KEY: str = Field(default="", description="SerpAPI key for evidence retrieval")
    OPENAI_API_KEY: str = Field(default="", description="OpenAI API key for Whisper")
    NEWSAPI_KEY: str = Field(default="")
    NEWSDATA_API_KEY: str = Field(default="", description="NewsData.io API key")
    GNEWS_API_KEY: str = Field(default="", description="GNews API key")
    GOOGLE_CSE_ID: str = Field(default="")
    GOOGLE_CSE_API_KEY: str = Field(default="")
    TWITTER_BEARER_TOKEN: str = Field(default="")
    REDDIT_CLIENT_ID: str = Field(default="")
    REDDIT_CLIENT_SECRET: str = Field(default="")
    TELEGRAM_API_ID: str = Field(default="")
    TELEGRAM_API_HASH: str = Field(default="")
    YOUTUBE_API_KEY: str = Field(default="")
    MASTODON_INSTANCE_URL: str = Field(default="https://mastodon.social")
    MASTODON_ACCESS_TOKEN: str = Field(default="")
    DISCORD_BOT_TOKEN: str = Field(default="")
    DISCORD_GUILD_IDS: str = Field(default="")

    GOOGLE_FACTCHECK_API_KEY: str = Field(default="", description="Google Fact Check Tools API Key")
    BRAVE_API_KEY: str = Field(default="", description="Brave Search API Key (free 2000/month)")
    EVIDENCE_TIMEOUT: int = Field(default=8, description="Evidence retriever timeout in seconds")

    # Local transformer models (DistilBERT zero-shot + MiniLM embeddings) cost
    # ~30s of cold start and hundreds of MB of RAM while contributing little:
    # verdicts come from retrieved evidence, and the heuristic/TF-IDF paths
    # cover their role. Opt in only if you have the headroom.
    ENABLE_HEAVY_MODELS: bool = Field(
        default=False, description="Load local HuggingFace models (slow cold start)"
    )

    # ── Database ──────────────────────────────────────────────
    DATABASE_URL: str = Field(
        default="postgresql://truthshield:truthshield_pass@localhost:5432/truthshield"
    )
    REDIS_URL: str = Field(default="redis://localhost:6379/0")

    # ── JWT Auth ──────────────────────────────────────────────
    JWT_SECRET_KEY: str = Field(default="change-me-in-production")
    JWT_ALGORITHM: str = Field(default="HS256")
    JWT_EXPIRATION_MINUTES: int = Field(default=60)

    # ── Supabase Auth ─────────────────────────────────────────
    SUPABASE_JWT_SECRET: str = Field(default="", description="Supabase JWT secret for verifying Supabase-issued tokens")

    # ── Twilio WhatsApp ───────────────────────────────────────
    TWILIO_ACCOUNT_SID: str = Field(default="")
    TWILIO_AUTH_TOKEN: str = Field(default="")
    TWILIO_WHATSAPP_NUMBER: str = Field(default="whatsapp:+14155238886")

    # ── Model Configuration ───────────────────────────────────
    WHISPER_MODEL: str = Field(default="base")
    XLM_ROBERTA_MODEL: str = Field(default="xlm-roberta-base")
    EFFICIENTNET_MODEL: str = Field(default="efficientnet-b4")

    # ── App Settings ──────────────────────────────────────────
    APP_ENV: str = Field(default="development")  # Use 'production' on Render/deployment
    APP_HOST: str = Field(default="0.0.0.0")
    APP_PORT: int = Field(default_factory=lambda: int(os.environ.get("PORT", 8000)))
    FRONTEND_URL: str = Field(default="http://localhost:5173")
    CORS_ORIGINS: str = Field(default="http://localhost:5173,http://localhost:3000")
    MAX_UPLOAD_SIZE_MB: int = Field(default=100)
    RATE_LIMIT: str = Field(default="30/minute")

    # ── Paths ─────────────────────────────────────────────────
    BASE_DIR: Path = Field(default_factory=lambda: Path(__file__).resolve().parent)
    UPLOAD_DIR: Path = Field(default_factory=lambda: Path(__file__).resolve().parent / "uploads")
    MODEL_CACHE_DIR: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parent / "model_cache"
    )

    @property
    def cors_origins_list(self) -> List[str]:
        origins = {origin.strip() for origin in self.CORS_ORIGINS.split(",")}
        # Always include FRONTEND_URL and known production origins
        if self.FRONTEND_URL:
            origins.add(self.FRONTEND_URL.rstrip("/"))
        origins.add("https://truthshield-five.vercel.app")
        origins.add("http://localhost:5173")
        origins.add("http://localhost:3000")
        return list(origins)

    @property
    def max_upload_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    @model_validator(mode="after")
    def _warn_default_jwt_secret(self) -> "Settings":
        if self.JWT_SECRET_KEY == "change-me-in-production" and self.APP_ENV != "development":
            _logger = logging.getLogger("truthshield.config")
            _logger.warning(
                "SECURITY WARNING: JWT_SECRET_KEY is still the default value "
                "'change-me-in-production' in %s mode. Set a strong secret "
                "via the JWT_SECRET_KEY environment variable.",
                self.APP_ENV,
            )
        return self

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Return cached settings singleton."""
    return Settings()


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

# ── Detection Weights ─────────────────────────────────────────
CREDIBILITY_WEIGHTS = {
    "text": 0.35,
    "deepfake": 0.25,
    "voice": 0.20,
    "ai_content": 0.20,
}

# ── Claude Model Config ───────────────────────────────────────
CLAUDE_MODEL = "claude-sonnet-5"
CLAUDE_MAX_TOKENS = 1024

# ── Gemini Model Config ──────────────────────────────────────
# flash-lite stays the primary: 2d69a2f found gemini-2.5-flash 404s on this
# project's key. The fallbacks below are real models — the previous chain
# listed gemini-3.5-flash and gemini-3.1-flash-lite, which do not exist, so
# every call burned the full retry budget before giving up.
GEMINI_MODEL = "gemini-2.5-flash-lite"
GEMINI_FALLBACK_MODELS = ["gemini-2.5-flash-lite", "gemini-2.0-flash", "gemini-2.5-flash"]
GEMINI_MAX_TOKENS = 1024

# ── Supported Languages ──────────────────────────────────────
SUPPORTED_LANGUAGES = {"en": "English", "hi": "Hindi", "ta": "Tamil"}
