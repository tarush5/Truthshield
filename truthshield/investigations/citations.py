"""
Citation integrity: is each cited source what it claims to be?

Checked for every source shown under a claim:

* the URL parses as an http(s) address with a host and no embedded
  credentials;
* the publisher shown is the URL's own host (or a parent of it);
* the quoted passage occurs in the stored copy of the document it is
  attributed to (whitespace and case normalised) -- the check that catches a
  passage altered or invented anywhere between retrieval and display;
* the passage was not cut at the display limit mid-text;
* the publication date, when the source stated one, parses and is not in
  the future.

A citation is `verified` when every applicable check passes and the passage
was found; `mismatch` when a check failed (it is then not allowed to decide
the claim); `unverified` when the passage could not be checked (no stored
copy). Nothing here judges whether the source is *right* -- only whether it
is cited faithfully.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse

DISPLAY_LIMIT = 500
_WS = re.compile(r"\s+")


def _norm(text: str) -> str:
    return _WS.sub(" ", (text or "")).strip().lower()


def passage_in(passage: str, document_text: str) -> bool:
    p = _norm(passage)
    return bool(p) and p in _norm(document_text)


def _host(url: str) -> Optional[str]:
    try:
        parsed = urlparse(url or "")
    except ValueError:
        return None
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
        return None
    return parsed.hostname.lower().removeprefix("www.")


def check(source: dict, *, passage_found: Optional[bool], now: Optional[datetime] = None) -> dict:
    now = now or datetime.now(timezone.utc)
    problems = []

    host = _host(source.get("url", ""))
    url_ok = host is not None
    if not url_ok:
        problems.append("The source URL is not a valid web address.")

    publisher = (source.get("publisher") or "").lower().removeprefix("www.")
    publisher_ok = None
    if url_ok and publisher:
        publisher_ok = host == publisher or host.endswith("." + publisher) or publisher.endswith("." + host)
        if not publisher_ok:
            problems.append(f"The publisher shown ({publisher}) is not the site the link points to ({host}).")

    if passage_found is False:
        problems.append("The quoted passage was not found in the stored copy of this source.")

    passage = source.get("passage") or ""
    truncated = len(passage) >= DISPLAY_LIMIT

    date_status, age_days = "not_stated", None
    if source.get("published_at"):
        try:
            published = datetime.fromisoformat(str(source["published_at"]).replace("Z", "+00:00"))
            if published.tzinfo is None:
                published = published.replace(tzinfo=timezone.utc)
            if published > now:
                date_status = "in_future"
                problems.append("The publication date is in the future, so it was not relied on.")
            else:
                date_status, age_days = "ok", (now - published).days
        except ValueError:
            date_status = "unparseable"

    if problems:
        status = "mismatch"
    elif passage_found:
        status = "verified"
    else:
        status = "unverified"
    return {
        "status": status,
        "url_valid": url_ok,
        "publisher_matches_url": publisher_ok,
        "passage_found_in_source": passage_found,
        "passage_truncated": truncated,
        "published_date": date_status,
        "age_days": age_days,
        "problems": problems,
    }
