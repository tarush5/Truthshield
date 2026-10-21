"""
Threat-intelligence feeds from local files.

An operator points `THREAT_FEED_PATHS` at one or more plain-text lists --
exports from OpenPhish, URLhaus, PhishTank, a CERT advisory, or an internal
blocklist -- one entry per line, `#` for comments:

    evil-login.top                       a domain: it and its subdomains
    http://sites.example.com/phish/x     a URL: that URL only

A URL entry flags only that URL, because phishing pages are often hosted on
shared platforms whose other pages are fine.

"Real time" here means as fresh as the files: they are re-read when they
change on disk (checked at most every `RELOAD_SECONDS`), so a cron job that
refreshes them is all it takes. No network calls are made from here, and
nothing is claimed beyond the lists: a feed names known threats, so not being
on one says little about a new site.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

RELOAD_SECONDS = 30.0


def _host(value: str) -> str:
    return (value or "").strip().lower().rstrip(".").removeprefix("www.")


def normalise(url: str) -> Optional[str]:
    """Host and path, lower-cased host, no scheme, no fragment, no trailing slash."""
    raw = (url or "").strip()
    if "://" not in raw:
        raw = "http://" + raw
    try:
        parsed = urlparse(raw)
    except ValueError:
        return None
    if not parsed.hostname:
        return None
    path = parsed.path.rstrip("/")
    query = f"?{parsed.query}" if parsed.query else ""
    return f"{_host(parsed.hostname)}{path}{query}"


@dataclass
class FeedFile:
    path: Path
    mtime: float = 0.0
    hosts: set = field(default_factory=set)
    urls: set = field(default_factory=set)

    @property
    def entries(self) -> int:
        return len(self.hosts) + len(self.urls)

    def status(self) -> dict:
        return {
            "name": self.path.name,
            "entries": self.entries,
            "updated_at": (datetime.fromtimestamp(self.mtime, tz=timezone.utc).isoformat()
                           if self.mtime else None),
            "loaded": self.mtime > 0,
        }


class ThreatFeed:
    def __init__(self, paths: List[str]):
        self.files = [FeedFile(Path(p)) for p in paths if p.strip()]
        self._lock = threading.Lock()
        self._checked = 0.0

    @property
    def configured(self) -> bool:
        return bool(self.files)

    def _load(self, feed: FeedFile) -> None:
        try:
            mtime = feed.path.stat().st_mtime
        except OSError:
            if feed.mtime:
                logger.warning("threat feed %s is no longer readable; keeping the last copy", feed.path.name)
            return
        if mtime == feed.mtime:
            return
        hosts, urls = set(), set()
        with feed.path.open(encoding="utf-8", errors="replace") as handle:
            for line in handle:
                entry = line.split("#", 1)[0].strip()
                if not entry:
                    continue
                if "://" in entry or "/" in entry:
                    key = normalise(entry)
                    if key:
                        urls.add(key)
                elif "." in entry:
                    hosts.add(_host(entry))
        feed.hosts, feed.urls, feed.mtime = hosts, urls, mtime
        logger.info("threat feed %s loaded: %d entries", feed.path.name, feed.entries)

    def refresh(self, *, force: bool = False) -> None:
        now = time.monotonic()
        if not force and now - self._checked < RELOAD_SECONDS:
            return
        with self._lock:
            if not force and now - self._checked < RELOAD_SECONDS:
                return
            for feed in self.files:
                self._load(feed)
            self._checked = now

    def lookup(self, url: str) -> Optional[dict]:
        """The first feed entry matching `url`, or None."""
        if not self.configured:
            return None
        self.refresh()
        key = normalise(url)
        if key is None:
            return None
        host = key.split("/", 1)[0].split("?", 1)[0]
        labels = host.split(".")
        # The host itself and each parent domain with at least two labels:
        # "a.b.evil.top" matches an "evil.top" entry, never a bare "top".
        candidates = [".".join(labels[i:]) for i in range(len(labels) - 1)]
        for feed in self.files:
            if key in feed.urls:
                return {"feed": feed.path.name, "matched": key, "kind": "url", **_stamp(feed)}
            for candidate in candidates:
                if candidate in feed.hosts:
                    return {"feed": feed.path.name, "matched": candidate, "kind": "domain", **_stamp(feed)}
        return None

    def status(self) -> dict:
        self.refresh()
        return {
            "configured": self.configured,
            "entries": sum(f.entries for f in self.files),
            "files": [f.status() for f in self.files],
        }


def _stamp(feed: FeedFile) -> Dict[str, Optional[str]]:
    return {"feed_updated_at": feed.status()["updated_at"]}


_feed: Optional[ThreatFeed] = None
_feed_key: Optional[str] = None
_feed_lock = threading.Lock()


def get_threat_feed() -> ThreatFeed:
    """Process-wide feed, rebuilt if the configured paths change."""
    global _feed, _feed_key
    from truthshield.settings import get_settings

    key = get_settings().THREAT_FEED_PATHS or ""
    with _feed_lock:
        if _feed is None or key != _feed_key:
            # Comma-separated on every platform: ";" and ":" both appear in paths.
            _feed = ThreatFeed([p.strip() for p in key.split(",") if p.strip()])
            _feed_key = key
        return _feed
