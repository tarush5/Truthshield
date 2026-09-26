"""
Configuration.

Two rules shape this module, both learned from the previous version:

1. **Fail closed.** Every setting that gates security defaults to the strict
   value. The old config defaulted APP_ENV to "development", which switched on
   an anonymous-guest fallback, so a deployment that simply forgot to set it
   served the analysis API to anyone. Defaults here are the ones that are safe
   to forget.

2. **Validate at startup, not at first use.** A misconfiguration should stop
   the process while someone is watching a deploy log, not surface hours later
   as a 500. The validators below raise rather than warn.
"""

from __future__ import annotations

import sys
import logging
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent

# The value shipped in the example env file. Refusing it by name stops the
# most common production mistake: copying .env.example and editing only the
# keys someone happens to care about.
PLACEHOLDER_SECRETS = {
    "",
    "change-me-in-production",
    "change_this_to_a_random_64_char_hex_string",
    "your_jwt_secret",
}

# Vite's default port and the ones it falls back to when that is taken. Only
# ever added outside production -- see `Settings.cors_origins`. Without this,
# running a second dev server silently produces a frontend whose every
# request fails preflight, reported to the user as "login failed".
DEV_SERVER_PORTS = (5173, 5174, 5175, 5176, 3000, 4173)


class Environment(str, Enum):
    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"

    @property
    def is_production(self) -> bool:
        return self is Environment.PRODUCTION

    @property
    def is_development(self) -> bool:
        return self is Environment.DEVELOPMENT


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ── Environment ───────────────────────────────────────────
    APP_ENV: Environment = Environment.PRODUCTION
    APP_HOST: str = "127.0.0.1"
    APP_PORT: int = 8000
    LOG_LEVEL: str = "INFO"

    # ── Security ──────────────────────────────────────────────
    JWT_SECRET_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_MINUTES: int = 60
    SUPABASE_JWT_SECRET: str = ""

    # Comma-separated exact origins. No wildcard: the API is called with
    # Authorization headers and credentials, which browsers refuse to combine
    # with "*" anyway.
    #
    # Outside production this list is widened to the local dev-server port
    # range -- see `cors_origins`. Vite takes the next free port when 5173 is
    # busy, and a second `npm run dev` therefore serves a frontend that every
    # request fails from, with a CORS preflight rejection that surfaces as
    # "login failed" and names nothing.
    CORS_ORIGINS: str = "http://localhost:5173"

    RATE_LIMIT: str = "60/minute"
    RATE_LIMIT_AUTH: str = "10/minute"     # login/OTP endpoints, brute-force surface

    MAX_UPLOAD_SIZE_MB: int = 25
    MAX_TEXT_LENGTH: int = 20_000

    # ── Persistence ───────────────────────────────────────────
    # Postgres in every real deployment. SQLite is permitted only outside
    # production, where it keeps `pytest` and a bare `uvicorn` working with no
    # services running.
    DATABASE_URL: str = "postgresql+psycopg2://truthshield:truthshield@localhost:5432/truthshield"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_ECHO: bool = False

    REDIS_URL: str = "redis://localhost:6379/0"
    CACHE_TTL_SECONDS: int = 900

    CELERY_BROKER_URL: str = ""
    CELERY_RESULT_BACKEND: str = ""
    # Runs tasks inline instead of dispatching them. Used by the test suite so
    # async paths are exercised without a worker process.
    CELERY_TASK_ALWAYS_EAGER: bool = False

    # ── Analysis ──────────────────────────────────────────────
    EVIDENCE_TIMEOUT_SECONDS: float = 8.0
    MAX_CLAIMS_PER_SUBMISSION: int = 3

    # Scientific literature (Europe PMC, OpenAlex) as an evidence source.
    #
    # Off because it measured badly, not because it is unfinished: OpenAlex
    # adds ~2s to a 1537ms median request and is about half relevant, and
    # Europe PMC cannot bridge colloquial claims to medical vocabulary. The
    # full numbers are in `infra/evidence/scholarly.py`. Worth enabling only
    # for a medical-claim deployment that can afford the latency.
    ENABLE_SCHOLARLY_SOURCES: bool = False

    # Local model inference. Off by default: the weights are hundreds of MB and
    # several seconds of cold start, and the system degrades honestly without
    # them rather than pretending it checked.
    ENABLE_ML_DETECTORS: bool = False
    MODEL_CACHE_DIR: Path = REPO_ROOT / ".model_cache"
    UPLOAD_DIR: Path = REPO_ROOT / ".uploads"

    # ── Third-party keys (all optional) ───────────────────────
    ANTHROPIC_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    GOOGLE_FACTCHECK_API_KEY: str = ""
    GOOGLE_CSE_API_KEY: str = ""
    GOOGLE_CSE_ID: str = ""
    SERPAPI_API_KEY: str = ""
    BRAVE_API_KEY: str = ""
    NEWSDATA_API_KEY: str = ""
    GNEWS_API_KEY: str = ""

    # ──────────────────────────────────────────────────────────
    # Derived
    # ──────────────────────────────────────────────────────────

    @property
    def cors_origins(self) -> List[str]:
        """
        Exact allowed origins.

        In development the configured list is extended with the ports Vite
        actually uses, on both hostnames: it falls back from 5173 when that
        port is taken, and `localhost` and `127.0.0.1` are different origins
        to a browser even though they are the same host to everything else.

        Production gets exactly what was configured and nothing more.
        """
        origins = [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]
        if self.APP_ENV.is_production:
            return origins

        extra = [
            f"http://{host}:{port}"
            for port in DEV_SERVER_PORTS
            for host in ("localhost", "127.0.0.1")
        ]
        seen = set(origins)
        return origins + [o for o in extra if o not in seen]

    @property
    def max_upload_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    @property
    def celery_broker(self) -> str:
        return self.CELERY_BROKER_URL or self.REDIS_URL

    @property
    def celery_backend(self) -> str:
        return self.CELERY_RESULT_BACKEND or self.REDIS_URL

    @property
    def uses_sqlite(self) -> bool:
        return self.DATABASE_URL.startswith("sqlite")

    # ──────────────────────────────────────────────────────────
    # Validation — all of it fatal
    # ──────────────────────────────────────────────────────────

    @field_validator("CORS_ORIGINS")
    @classmethod
    def _no_wildcard_origin(cls, v: str) -> str:
        if any(o.strip() == "*" for o in v.split(",")):
            raise ValueError(
                "CORS_ORIGINS may not contain '*'. The API is called with "
                "credentials, which browsers refuse to pair with a wildcard "
                "origin. List the exact frontend origins."
            )
        return v

    @model_validator(mode="after")
    def _secrets_must_be_real(self) -> "Settings":
        if self.JWT_SECRET_KEY in PLACEHOLDER_SECRETS:
            if self.APP_ENV.is_production:
                raise ValueError(
                    "JWT_SECRET_KEY is unset or still a placeholder while "
                    f"APP_ENV={self.APP_ENV.value}. This key signs every session "
                    "token and the placeholder is public in this repository, so "
                    "anyone could mint a token for any account.\n"
                    "\n"
                    "  First run here?  cp .env.example .env\n"
                    "                   That sets APP_ENV=development, which is "
                    "enough to start locally.\n"
                    "\n"
                    "  Deploying?       Generate a real key:\n"
                    '                   python -c "import secrets; '
                    'print(secrets.token_hex(32))"'
                )
            logger.warning(
                "JWT_SECRET_KEY is a placeholder. Tolerated only because "
                "APP_ENV=%s.", self.APP_ENV.value,
            )
        elif len(self.JWT_SECRET_KEY) < 32:
            raise ValueError("JWT_SECRET_KEY must be at least 32 characters.")
        return self

    @model_validator(mode="after")
    def _production_needs_real_infrastructure(self) -> "Settings":
        """
        SQLite is a single-file database with no concurrent writer story. The
        previous version fell back to it silently whenever Postgres was
        unreachable, so a production outage looked like a working service that
        had quietly lost every report.
        """
        if self.APP_ENV.is_production and self.uses_sqlite:
            raise ValueError(
                "DATABASE_URL points at SQLite while APP_ENV=production. "
                "Set a PostgreSQL URL."
            )
        return self

    @model_validator(mode="after")
    def _ensure_directories(self) -> "Settings":
        for directory in (self.UPLOAD_DIR, self.MODEL_CACHE_DIR):
            try:
                directory.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                logger.warning("Could not create %s: %s", directory, exc)
        return self


@lru_cache
def get_settings() -> Settings:
    """
    The validated configuration, or a legible failure.

    The validators below fail closed on purpose: a missing signing key or a
    SQLite URL in production stops the process rather than starting a
    service that is quietly unsafe. That is right, but the raw Pydantic
    output buries the one useful sentence under fifteen lines of traceback,
    and on a hosting dashboard nobody scrolls to the bottom of a stack
    trace.

    The cost of that was real: a deployment served pre-rewrite code for
    weeks because every new container exited during startup, the platform
    rolled back to the last image that booted, and the health endpoint went
    on answering. The failure looked like nothing at all.

    So a configuration error is reported as an operator message first, with
    the traceback after it for anyone who wants the detail.
    """
    try:
        return Settings()
    except Exception as exc:
        problems = []
        for line in str(exc).splitlines():
            line = line.strip()
            # Pydantic prefixes the human-readable cause this way; the rest
            # of its output is type machinery and a docs URL.
            if line.startswith("Value error,"):
                problem = line[len("Value error,"):].strip()
                # Drop the trailing "[type=value_error, input_value={...}]",
                # which repeats the configuration back at the reader and
                # pushes the actual instruction off the line.
                problem = problem.split(" [type=")[0].strip()
                problems.append(problem)

        banner = [
            "",
            "=" * 72,
            "  TruthShield could not start: the configuration is not valid.",
            "=" * 72,
        ]
        if problems:
            for problem in problems:
                banner.append(f"  - {problem}")
        else:
            banner.append(f"  {str(exc).splitlines()[0][:200]}")

        banner += [
            "",
            "  In production the service requires, at minimum:",
            "    APP_ENV=production",
            "    JWT_SECRET_KEY   32+ random characters; changing it signs everyone out",
            "    DATABASE_URL     a postgresql:// URL (SQLite is refused here)",
            "    CORS_ORIGINS     the frontend's exact origin, no trailing slash",
            "",
            "  Nothing starts until these are set. That is deliberate -- a service",
            "  running without a real signing key is worse than one that is down.",
            "=" * 72,
            "",
        ]
        # stderr, unbuffered, before the traceback: hosting platforms
        # capture both, and this has to be the part that is read.
        print("\n".join(banner), file=sys.stderr, flush=True)
        raise


def reset_settings_cache() -> None:
    """Drop the cached Settings. Used by tests that vary the environment."""
    get_settings.cache_clear()
