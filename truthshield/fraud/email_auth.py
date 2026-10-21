"""
SPF, DKIM and DMARC, read from pasted full headers.

A receiving mail server records what it verified in an
`Authentication-Results` header (RFC 8601). When a user pastes the full
headers ("Show original" / "View source"), those results are there to read.
This module reads them; it does not re-verify anything -- no DNS lookups, no
signature checks -- and says so.

Which header to trust: each server on the path prepends its own header, so
the topmost `Authentication-Results` is the one the recipient's own provider
added. Anything below it was already in the message when it arrived and could
have been written by the sender. Only the topmost one is read.

What a result means, stated because it bounds how it is used:

* A failure is evidence: the domain in the From line did not authorise this
  message (DMARC), or the sending server or signature did not check out.
* A pass is *not* evidence of safety. It shows the message really came from
  the domain it names; a lookalike domain registered by a fraudster passes
  all three. So a pass never lowers the risk score -- it is reported only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from truthshield.fraud.contract import Indicator, Severity

# Unfold RFC 5322 continuation lines (a line starting with whitespace
# continues the previous header) before matching.
_FOLD_RE = re.compile(r"\r?\n[ \t]+")
_AUTH_RESULTS_RE = re.compile(r"^authentication-results\s*:\s*(.+)$", re.IGNORECASE | re.MULTILINE)
_RECEIVED_SPF_RE = re.compile(r"^received-spf\s*:\s*([a-z]+)\b(.*)$", re.IGNORECASE | re.MULTILINE)
_METHOD_RE = re.compile(
    r"\b(spf|dkim|dmarc)\s*=\s*([a-z]+)\b([^;]*)", re.IGNORECASE,
)
_PROPERTY_RE = re.compile(r"\b(header\.(?:from|d|i)|smtp\.(?:mailfrom|helo))\s*=\s*([^\s;()]+)", re.IGNORECASE)

# Two-label public suffixes common in the mail this platform sees. A full
# public-suffix list would be exact; this keeps "bank.co.in" and "co.in" apart
# without a new dependency, and errs towards "not aligned" when unsure.
_SECOND_LEVEL = frozenset({
    "co.uk", "org.uk", "ac.uk", "gov.uk", "co.in", "org.in", "net.in", "gov.in", "nic.in",
    "ac.in", "edu.in", "res.in", "firm.in", "com.au", "net.au", "org.au", "gov.au",
    "co.jp", "co.nz", "com.br", "com.sg", "com.my", "co.za", "com.mx",
})

VERIFIED_RESULTS = {"pass", "fail", "softfail", "neutral", "none", "temperror", "permerror",
                    "policy", "bestguesspass"}


def organisational_domain(domain: str) -> str:
    labels = [x for x in (domain or "").lower().strip(".").split(".") if x]
    if len(labels) >= 3 and ".".join(labels[-2:]) in _SECOND_LEVEL:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


def _domain_of(value: str) -> str:
    value = (value or "").strip().strip("<>").lower()
    return value.rpartition("@")[2] if "@" in value else value


@dataclass
class AuthResults:
    """What the receiving server recorded. Results are lower-case RFC 8601 words."""

    source: str                          # "authentication-results" | "received-spf"
    authserv_id: Optional[str] = None
    spf: Optional[str] = None
    spf_domain: Optional[str] = None
    dkim: List[Dict[str, Optional[str]]] = field(default_factory=list)
    dmarc: Optional[str] = None
    dmarc_domain: Optional[str] = None
    headers_seen: int = 1

    def dkim_passed_for(self, from_domain: str) -> bool:
        org = organisational_domain(from_domain)
        return any(d["result"] == "pass" and d.get("domain")
                   and organisational_domain(d["domain"]) == org for d in self.dkim)

    def as_dict(self, from_domain: str = "") -> dict:
        return {
            "checked": True,
            "source": self.source,
            "authserv_id": self.authserv_id,
            "spf": self.spf,
            "spf_domain": self.spf_domain,
            "dkim": self.dkim,
            "dmarc": self.dmarc,
            "dmarc_domain": self.dmarc_domain,
            "dkim_aligned": self.dkim_passed_for(from_domain) if from_domain else None,
            "headers_seen": self.headers_seen,
            "verified_by": "receiving mail server (read from pasted headers, not re-verified)",
        }


def parse(text: str) -> Optional[AuthResults]:
    """The topmost Authentication-Results, else Received-SPF, else None."""
    unfolded = _FOLD_RE.sub(" ", text or "")
    found = _AUTH_RESULTS_RE.findall(unfolded)
    if found:
        top = found[0]
        authserv = top.split(";", 1)[0].strip().split()[0] if top.strip() else None
        out = AuthResults(source="authentication-results", authserv_id=authserv,
                          headers_seen=len(found))
        for method, result, rest in _METHOD_RE.findall(top):
            method, result = method.lower(), result.lower()
            if result not in VERIFIED_RESULTS:
                continue
            props = {k.lower(): _domain_of(v) for k, v in _PROPERTY_RE.findall(rest)}
            if method == "spf" and out.spf is None:
                out.spf = result
                out.spf_domain = props.get("smtp.mailfrom") or props.get("smtp.helo")
            elif method == "dkim":
                out.dkim.append({"result": result,
                                 "domain": props.get("header.d") or props.get("header.i")})
            elif method == "dmarc" and out.dmarc is None:
                out.dmarc = result
                out.dmarc_domain = props.get("header.from")
        if out.spf or out.dkim or out.dmarc:
            return out

    spf = _RECEIVED_SPF_RE.search(unfolded)
    if spf and spf.group(1).lower() in VERIFIED_RESULTS:
        domain = re.search(r"envelope-from=\"?([^\s\";]+)", spf.group(2), re.IGNORECASE)
        return AuthResults(source="received-spf", spf=spf.group(1).lower(),
                           spf_domain=_domain_of(domain.group(1)) if domain else None)
    return None


def indicators(auth: Optional[AuthResults], from_domain: str) -> List[Indicator]:
    """Failures only. A pass is reported, never scored as safety."""
    if auth is None:
        return []
    out: List[Indicator] = []
    who = f" by {auth.authserv_id}" if auth.authserv_id else ""

    if auth.dmarc == "fail":
        domain = auth.dmarc_domain or from_domain or "the sender's domain"
        out.append(Indicator(
            code="email_dmarc_fail", title="Sender failed DMARC", severity=Severity.HIGH,
            explanation=(
                f"The receiving server{who} recorded a DMARC failure for '{domain}': the "
                "owner of that domain did not authorise this message. That is how a forged "
                "From address shows up."
            ),
            evidence=f"dmarc=fail header.from={domain}",
        ))
        # DMARC already summarises SPF and DKIM for the From domain.
        return out

    if auth.spf in ("fail", "softfail"):
        hard = auth.spf == "fail"
        out.append(Indicator(
            code="email_spf_fail" if hard else "email_spf_softfail",
            title="Sending server not authorised (SPF)" if hard else "Sending server not clearly authorised (SPF)",
            severity=Severity.MEDIUM if hard else Severity.LOW,
            explanation=(
                f"The receiving server{who} found that the server which delivered this message is "
                f"{'not' if hard else 'probably not'} permitted to send mail for "
                f"'{auth.spf_domain or 'the envelope domain'}'. Forwarding can also cause this, "
                "so it is a reason for caution rather than proof."
            ),
            evidence=f"spf={auth.spf}" + (f" smtp.mailfrom={auth.spf_domain}" if auth.spf_domain else ""),
        ))

    if auth.dkim and all(d["result"] in ("fail", "permerror") for d in auth.dkim):
        domains = ", ".join(sorted({d["domain"] for d in auth.dkim if d.get("domain")})) or "the signing domain"
        out.append(Indicator(
            code="email_dkim_fail", title="Signature check failed (DKIM)", severity=Severity.MEDIUM,
            explanation=(
                f"The receiving server{who} could not verify the message's DKIM signature "
                f"({domains}). The message may have been altered or the signature forged. "
                "Mailing lists that edit messages can also break signatures."
            ),
            evidence="dkim=fail",
        ))
    return out


def limitations(auth: Optional[AuthResults]) -> List[str]:
    if auth is None:
        return [
            "SPF, DKIM and DMARC were not checked — paste the full headers (\"Show original\" "
            "or \"View source\" in your mail app) to include the receiving server's results. "
            "Without them a forged sender cannot be distinguished from a real one.",
        ]
    note = (
        "SPF, DKIM and DMARC results were read from the topmost Authentication-Results header "
        "in the pasted headers, as recorded by the receiving server; they were not re-verified."
        if auth.source == "authentication-results" else
        "Only an SPF result (Received-SPF) was present in the pasted headers; DKIM and DMARC "
        "were not checked."
    )
    out = [note]
    if auth.dmarc == "pass" or any(d["result"] == "pass" for d in auth.dkim) or auth.spf == "pass":
        out.append(
            "A passing authentication result shows the message came from the domain it names. "
            "It does not show that domain is legitimate: lookalike domains pass too, so a pass "
            "does not lower the risk score."
        )
    return out
