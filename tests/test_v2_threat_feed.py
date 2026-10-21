"""Local threat-intelligence feeds and their effect on URL investigations."""

import os

import pytest

from truthshield.infra.threat_feed import ThreatFeed

FEED = """# test feed
evil-login.top
203.0.113.7
http://sites.example.com/phish/page1   # one page on a shared host
"""


@pytest.fixture
def feed_file(tmp_path):
    path = tmp_path / "feed.txt"
    path.write_text(FEED, encoding="utf-8")
    return path


class TestLookup:
    def test_domains_match_themselves_and_subdomains(self, feed_file):
        feed = ThreatFeed([str(feed_file)])
        assert feed.lookup("https://evil-login.top/x")["kind"] == "domain"
        assert feed.lookup("http://secure.www.evil-login.top")["matched"] == "evil-login.top"
        assert feed.lookup("http://203.0.113.7/login")["matched"] == "203.0.113.7"

    def test_url_entries_match_only_that_url(self, feed_file):
        feed = ThreatFeed([str(feed_file)])
        assert feed.lookup("http://sites.example.com/phish/page1/")["kind"] == "url"
        assert feed.lookup("http://sites.example.com/bakery") is None

    def test_no_suffix_or_lookalike_overmatch(self, feed_file):
        feed = ThreatFeed([str(feed_file)])
        assert feed.lookup("http://top") is None
        assert feed.lookup("http://not-evil-login.top") is None
        assert feed.lookup("http://example.com") is None

    def test_file_changes_are_picked_up(self, feed_file):
        feed = ThreatFeed([str(feed_file)])
        assert feed.lookup("http://new-scam.xyz") is None
        feed_file.write_text(FEED + "new-scam.xyz\n", encoding="utf-8")
        st = feed_file.stat()
        os.utime(feed_file, (st.st_atime, st.st_mtime + 5))
        feed.refresh(force=True)
        assert feed.lookup("http://new-scam.xyz")

    def test_missing_file_is_reported_not_raised(self, tmp_path):
        feed = ThreatFeed([str(tmp_path / "absent.txt")])
        assert feed.lookup("http://evil-login.top") is None
        assert feed.status()["files"][0]["loaded"] is False

    def test_unconfigured(self):
        assert not ThreatFeed([]).configured


def run_url(client, auth, url):
    r = client.post("/api/v1/investigations", json={"type": "url", "content": url}, headers=auth)
    assert r.status_code == 202, r.text
    return client.get(f"/api/v1/investigations/{r.json()['id']}", headers=auth).json()


class TestInvestigation:
    def test_without_a_feed_reputation_is_not_assessed(self, client, auth):
        inv = run_url(client, auth, "http://quiet-garden-photos.com/album/1")
        families = inv["result"]["risk"]["families"]
        assert families["reputation"]["assessed"] is False
        assert inv["result"]["url_intelligence"][0]["reputation"] == {"checked": False, "status": "NOT_CHECKED"}
        assert any("threat-intelligence feed" in u for u in inv["result"]["uncertainties"])

    def test_a_listed_url_is_a_retrieved_reputation_signal(self, client, auth, feed_file, monkeypatch):
        from truthshield.settings import get_settings

        monkeypatch.setattr(get_settings(), "THREAT_FEED_PATHS", str(feed_file))
        inv = run_url(client, auth, "http://evil-login.top/account/verify")
        factor = next(f for f in inv["risk_factors"] if f["code"] == "threat_feed_match")
        assert factor["family"] == "reputation" and factor["provenance"] == "retrieved"
        assert inv["result"]["risk"]["families"]["reputation"]["assessed"] is True
        assert inv["result"]["url_intelligence"][0]["reputation"]["listed"] is True
        assert inv["result"]["url_intelligence"][0]["reputation"]["status"] == "KNOWN_MALICIOUS"
        assert inv["result"]["url_intelligence"][0]["structure"] == "SUSPICIOUS"
        assert any("local threat feed" in u for u in inv["result"]["uncertainties"])

    def test_unlisted_url_with_a_feed_is_assessed_and_clean(self, client, auth, feed_file, monkeypatch):
        from truthshield.settings import get_settings

        monkeypatch.setattr(get_settings(), "THREAT_FEED_PATHS", str(feed_file))
        inv = run_url(client, auth, "http://quiet-garden-photos.com/album/2")
        assert inv["result"]["risk"]["families"]["reputation"]["assessed"] is True
        assert inv["result"]["url_intelligence"][0]["reputation"] == {"checked": True, "listed": False,
                                                                       "match": None, "status": "NO_KNOWN_LISTING"}
        assert inv["result"]["url_intelligence"][0]["structure"] == "NO_STRUCTURAL_INDICATORS"
