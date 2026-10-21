"""Deceptive URL structures are flagged; ordinary official URLs are not."""

import pytest

from truthshield.investigations.evaluation import assess

DECEPTIVE = [
    ("https://sbi.co.in.verify-login.top/kyc", "brand_outside_domain"),
    ("https://hdfcbank.example-malicious.com/login", "brand_outside_domain"),
    ("http://paypal.com-secure-account.top/signin", "brand_outside_domain"),
    ("https://www.hdfcbank.com@evil-host.top/login", "userinfo_in_url"),
    ("https://xn--pypal-4ve.com/login", "punycode_host"),
    ("https://p\u0430ypal.com/login", "mixed_script_host"),
    ("http://192.168.10.5/bank/login", "ip_host"),
    ("https://paypal-verify.github.io/login", "brand_outside_domain"),
    ("https://amaz0n-orders.top/track", "typosquat_domain"),
]
OFFICIAL = [
    "https://www.icicibank.com/personal-banking", "https://onlinesbi.sbi/", "https://www.paypal.com/signin",
    "https://mail.google.com/mail/u/0", "https://www.amazon.in/gp/your-account/order-history",
    "https://docs.github.com/en/pages", "https://www.irctc.co.in/nget/train-search",
]


@pytest.mark.parametrize("url,signal", DECEPTIVE)
def test_deceptive_structures_are_flagged(url, signal):
    outcome = assess({"id": "u", "type": "url", "content": url, "label": "fraud"})
    assert outcome.flagged, (url, outcome.score)
    assert signal in outcome.top_signals


@pytest.mark.parametrize("url", OFFICIAL)
def test_official_urls_carry_no_structural_signal(url):
    outcome = assess({"id": "u", "type": "url", "content": url, "label": "benign"})
    assert outcome.score == 0 and not outcome.flagged, (url, outcome.top_signals)
