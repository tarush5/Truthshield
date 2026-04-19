"""
TruthShield — Configuration Module
Centralized configuration management using Pydantic Settings.
"""

import os
from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings
from pydantic import Field


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

    # ── Database ──────────────────────────────────────────────
    DATABASE_URL: str = Field(
        default="postgresql://truthshield:truthshield_pass@localhost:5432/truthshield"
    )
    REDIS_URL: str = Field(default="redis://localhost:6379/0")

    # ── JWT Auth ──────────────────────────────────────────────
    JWT_SECRET_KEY: str = Field(default="change-me-in-production")
    JWT_ALGORITHM: str = Field(default="HS256")
    JWT_EXPIRATION_MINUTES: int = Field(default=60)

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
    APP_PORT: int = Field(default=8000)
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
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    @property
    def max_upload_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024

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
    "gov.in": 0.9,
    "gov.uk": 0.9,
    "gov": 0.85,
    "reuters.com": 0.85,
    "apnews.com": 0.85,
    "bbc.com": 0.8,
    "bbc.co.uk": 0.8,
    "thehindu.com": 0.8,
    "ndtv.com": 0.7,
    "indianexpress.com": 0.75,
    "nytimes.com": 0.8,
    "theguardian.com": 0.75,
    "wikipedia.org": 0.65,
    "snopes.com": 0.9,
    "factcheck.org": 0.9,
    "altnews.in": 0.9,
    "boomlive.in": 0.9,
    "smhoaxslayer.com": 0.85,
    "vishvasnews.com": 0.85,
    "washingtonpost.com": 0.8,
    "cnn.com": 0.7,
    "aljazeera.com": 0.75,
}

KNOWN_DISINFO_DOMAINS = [
    "naturalness.com",
    "infowars.com",
    "beforeitsnews.com",
    "yournewswire.com",
    "worldnewsdailyreport.com",
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
GEMINI_MAX_TOKENS = 512

# ── Supported Languages ──────────────────────────────────────
SUPPORTED_LANGUAGES = {"en": "English", "hi": "Hindi", "ta": "Tamil"}
