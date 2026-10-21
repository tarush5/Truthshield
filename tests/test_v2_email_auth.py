"""SPF / DKIM / DMARC read from pasted full headers."""

from truthshield.fraud import email_auth
from truthshield.fraud.registry import analyze

FORGED = """Delivered-To: me@example.org
Received: by 2002:a05:6000:1:b0 with SMTP id x; Tue, 1 Oct 2026 09:12:01 -0700
Authentication-Results: mx.google.com;
       dkim=fail header.i=@hdfcbank.com header.s=s1;
       spf=fail (google.com: domain of alerts@hdfcbank.com does not designate 203.0.113.9 as permitted sender) smtp.mailfrom=alerts@hdfcbank.com;
       dmarc=fail (p=REJECT sp=REJECT dis=NONE) header.from=hdfcbank.com
Authentication-Results: attacker.example; dmarc=pass header.from=hdfcbank.com
From: HDFC Bank <alerts@hdfcbank.com>
To: me@example.org
Subject: Account update

Please review the attached statement.
"""

GENUINE = """Delivered-To: me@example.org
Authentication-Results: mx.google.com;
       dkim=pass header.i=@mail.newsletter.example.com header.s=k1;
       spf=pass smtp.mailfrom=bounce@mail.newsletter.example.com;
       dmarc=pass (p=NONE) header.from=newsletter.example.com
From: Example News <hello@newsletter.example.com>
To: me@example.org
Subject: This week's issue

Here is this week's issue. Unsubscribe at any time.
"""

LOOKALIKE_PASS = """Authentication-Results: mx.example.net;
       dkim=pass header.d=hdfcbank-secure.top;
       spf=pass smtp.mailfrom=noreply@hdfcbank-secure.top;
       dmarc=pass header.from=hdfcbank-secure.top
From: HDFC Bank <noreply@hdfcbank-secure.top>
To: me@example.org
Subject: Verify your account

Your account will be suspended. Verify your password and login now: http://hdfcbank-secure.top/login
"""


class TestParse:
    def test_reads_only_the_topmost_header(self):
        auth = email_auth.parse(FORGED)
        assert auth.authserv_id == "mx.google.com"
        # The lower, sender-supplied "dmarc=pass" is ignored.
        assert auth.dmarc == "fail"
        assert auth.dmarc_domain == "hdfcbank.com"
        assert auth.spf == "fail"
        assert auth.spf_domain == "hdfcbank.com"
        assert auth.dkim == [{"result": "fail", "domain": "hdfcbank.com"}]
        assert auth.headers_seen == 2

    def test_folded_headers_are_unfolded(self):
        auth = email_auth.parse(GENUINE)
        assert (auth.spf, auth.dmarc) == ("pass", "pass")
        assert auth.dkim_passed_for("newsletter.example.com")

    def test_received_spf_fallback(self):
        auth = email_auth.parse(
            "Received-SPF: softfail (domain of transitioning x@y.com) envelope-from=\"x@y.com\";\n"
            "From: a@y.com\nSubject: hi\n"
        )
        assert (auth.source, auth.spf, auth.spf_domain) == ("received-spf", "softfail", "y.com")

    def test_no_headers_is_none(self):
        assert email_auth.parse("From: a@b.com\nSubject: hi\n\nbody") is None

    def test_organisational_domain(self):
        assert email_auth.organisational_domain("mail.hdfcbank.co.in") == "hdfcbank.co.in"
        assert email_auth.organisational_domain("a.b.example.com") == "example.com"


def _email(result):
    return next(f for f in result["findings"] if f["detector"] == "email_fraud")


class TestDetector:
    def test_dmarc_failure_is_a_high_indicator_and_subsumes_spf_dkim(self):
        finding = _email(analyze(FORGED))
        codes = {i["code"] for i in finding["indicators"]}
        assert "email_dmarc_fail" in codes
        assert not codes & {"email_spf_fail", "email_dkim_fail"}
        assert finding["extra"]["authentication"]["dmarc"] == "fail"
        assert any("topmost Authentication-Results" in x for x in finding["limitations"])

    def test_spf_and_dkim_failures_without_dmarc(self):
        text = FORGED.replace("dmarc=fail (p=REJECT sp=REJECT dis=NONE) header.from=hdfcbank.com", "")
        codes = {i["code"] for i in _email(analyze(text))["indicators"]}
        assert {"email_spf_fail", "email_dkim_fail"} <= codes

    def test_genuine_pass_adds_no_indicator(self):
        result = analyze(GENUINE)
        assert not result["findings"] or not any(
            i["code"].startswith("email_") for f in result["findings"] for i in f["indicators"]
        )

    def test_pass_on_a_lookalike_domain_does_not_lower_risk(self):
        with_auth = analyze(LOOKALIKE_PASS)
        without = analyze(LOOKALIKE_PASS.split("\n", 3)[3])
        assert with_auth["risk_score"] >= without["risk_score"] > 0
        limits = _email(with_auth)["limitations"]
        assert any("does not lower the risk score" in x for x in limits)

    def test_without_headers_authentication_is_listed_as_unchecked(self):
        finding = _email(analyze(LOOKALIKE_PASS.split("\n", 3)[3]))
        assert finding["extra"]["authentication"] == {"checked": False}
        assert any("not checked" in x and "SPF" in x for x in finding["limitations"])
