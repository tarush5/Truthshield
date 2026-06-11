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
    EVIDENCE_TIMEOUT: int = Field(default=5, description="Evidence retriever timeout in seconds")

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
    APP_ENV: str = Field(default="development")
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
SOURCE_CREDIBILITY = {
    "gov.in": 1.0,
    "gov.uk": 1.0,
    "gov": 1.0,
    "reuters.com": 0.95,
    "apnews.com": 0.95,
    "bbc.com": 0.92,
    "bbc.co.uk": 0.92,
    "who.int": 0.98,
    "un.org": 0.98,
    "thehindu.com": 0.8,
    "ndtv.com": 0.7,
    "indianexpress.com": 0.75,
    "nytimes.com": 0.8,
    "theguardian.com": 0.75,
    "wikipedia.org": 0.65,
    "snopes.com": 0.95,
    "factcheck.org": 0.95,
    "altnews.in": 0.95,
    "boomlive.in": 0.95,
    "fullfact.org": 0.95,
    "factcheck.afp.com": 0.95,
    "politifact.com": 0.95,
    "smhoaxslayer.com": 0.85,
    "vishvasnews.com": 0.85,
    "washingtonpost.com": 0.8,
    "cnn.com": 0.7,
    "aljazeera.com": 0.75,
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
CLAUDE_MODEL = "claude-sonnet-4-6"
CLAUDE_MAX_TOKENS = 1024

# ── Gemini Model Config ──────────────────────────────────────
GEMINI_MODEL = "gemini-2.0-flash"
GEMINI_MAX_TOKENS = 1024

# ── Supported Languages ──────────────────────────────────────
SUPPORTED_LANGUAGES = {"en": "English", "hi": "Hindi", "ta": "Tamil"}
