"""
The investigation report: the result, reorganised around a reader's questions.

    What was analysed?  What was detected?  Why was it flagged?
    What evidence supports it?  How reliable is the assessment?
    Which checks ran?  What could not be verified?  What next?

Built deterministically from the finished result -- every line restates
something an engine produced, so the report can never say more than the
analysis did. Findings are kept apart by how they are known:

* CONFIRMED_OBSERVATION -- read directly from the input (a header value, a
  link, a decoded QR code, a recorded authentication result);
* HEURISTIC_INDICATOR -- a rule judged the wording or structure suspicious;
* RETRIEVED_EVIDENCE -- a retrieved source or threat feed said so;
* MODEL_PREDICTION -- a trained model's output;
* LLM_INTERPRETATION -- language-model prose, never a verified fact.
"""

from __future__ import annotations

from typing import List

KIND_OF = {
    "heuristic": "HEURISTIC_INDICATOR",
    "retrieved": "RETRIEVED_EVIDENCE",
    "ml_prediction": "MODEL_PREDICTION",
    "llm": "LLM_INTERPRETATION",
}

ENGINE_CHECKS = {
    "text": "Language, scam-pattern and manipulation analysis of the text",
    "url": "Link structure and lookalike-domain analysis",
    "evidence": "Fact-checking of claims against sources",
    "document": "PDF structure, metadata and consistency checks",
    "image": "Image metadata, QR codes and text extraction",
}


def _check(name: str, status: str, detail: str | None = None) -> dict:
    return {"check": name, "status": status, "detail": detail}


def _checks(result: dict) -> List[dict]:
    checks = []
    for engine in result.get("engines") or []:
        status = {"ok": "completed", "not_applicable": "not_applicable"}.get(engine.get("status"), "not_completed")
        checks.append(_check(ENGINE_CHECKS.get(engine.get("name"), engine.get("name")), status,
                             engine.get("detail")))

    urls = result.get("url_intelligence") or []
    if urls:
        fetched = [u for u in urls if (u.get("fetch") or {}).get("status") == "fetched"]
        checks.append(_check("Linked page retrieved and inspected",
                             "completed" if len(fetched) == len(urls) else "not_completed",
                             None if fetched else ((urls[0].get("fetch") or {}).get("reason"))))
        reputation = [(u.get("reputation") or {}).get("status") for u in urls]
        checks.append(_check(
            "Threat-intelligence reputation lookup",
            "not_completed" if "NOT_CHECKED" in reputation or None in reputation else "completed",
            "No threat feed is configured." if "NOT_CHECKED" in reputation else
            "A link with no known listing is not thereby safe; feeds list known threats only.",
        ))
        checks.append(_check("Domain registration age (WHOIS/RDAP)", "not_completed", "No provider is configured."))
        checks.append(_check("TLS certificate inspection", "not_completed", "Not performed."))

    email = result.get("email_authentication")
    if email is not None:
        checks.append(_check("Sender authentication (SPF, DKIM, DMARC)",
                             "completed" if email.get("checked") else "not_completed",
                             "Read from the receiving server's recorded results; not re-verified."
                             if email.get("checked") else "Full headers were not included."))

    claims = result.get("claims") or []
    live = {((c.get("retrieval") or {}).get("live_search")) for c in claims if c.get("checked")}
    if claims:
        checks.append(_check("Live web search for evidence",
                             "completed" if "used" in live else "not_completed",
                             None if "used" in live else "Only the local evidence store was searched, or "
                                                         "no live search was needed."))

    for key, label in (("image", "Text recognition (OCR) of the image"), ("document", "OCR of scanned pages")):
        ocr = ((result.get(key) or {}).get("ocr") or {}).get("status")
        if ocr and ocr != "not_needed":
            checks.append(_check(label, "completed" if ocr == "done" else "not_completed",
                                 ((result.get(key) or {}).get("ocr") or {}).get("detail")))

    llm = (result.get("explanation") or {}).get("llm_status")
    checks.append(_check("Language-model interpretation", "completed" if llm == "generated" else "not_completed",
                         "Explains findings only; it never decides the score or a claim."))
    return checks


def _observations(result: dict) -> List[dict]:
    out = []
    inp = result.get("input") or {}
    out.append({"kind": "CONFIRMED_OBSERVATION",
                "text": f"Input of type {inp.get('type')}, {inp.get('size_bytes', 0)} bytes, "
                        f"SHA-256 {str(inp.get('sha256'))[:16]}..."})
    for url in (result.get("entities") or {}).get("urls", [])[:5]:
        out.append({"kind": "CONFIRMED_OBSERVATION", "text": f"Contains the link {url}"})
    email = result.get("email_authentication") or {}
    if email.get("checked"):
        out.append({"kind": "CONFIRMED_OBSERVATION",
                    "text": f"Receiving server {email.get('authserv_id') or '(unnamed)'} recorded "
                            f"SPF={email.get('spf') or 'none'}, DMARC={email.get('dmarc') or 'none'}"})
    for code in ((result.get("image") or {}).get("qr") or {}).get("codes", []):
        out.append({"kind": "CONFIRMED_OBSERVATION", "text": f"QR code decodes to: {code.get('payload', '')[:200]}"})
    if inp.get("redactions"):
        out.append({"kind": "CONFIRMED_OBSERVATION",
                    "text": "Personal data in the input was masked before storage: "
                            + ", ".join(str(r) for r in inp["redactions"][:6])})
    return out


def build(result: dict) -> dict:
    risk = result.get("risk") or {}
    explanation = result.get("explanation") or {}
    actions = result.get("recommended_actions") or {}
    contributions = [c for c in risk.get("contributions") or [] if c.get("points", 0) > 0]

    findings = _observations(result) + [
        {"kind": KIND_OF.get(c.get("provenance"), "HEURISTIC_INDICATOR"), "code": c.get("code"),
         "text": c.get("title"), "points": c.get("points"), "evidence": c.get("evidence"),
         "limitation": c.get("limitation")}
        for c in contributions
    ]
    if explanation.get("llm"):
        findings.append({"kind": "LLM_INTERPRETATION", "text": explanation["llm"],
                         "limitation": "Language-model prose; not independently verified."})

    evidence = []
    for claim in result.get("claims") or []:
        if not claim.get("checked"):
            continue
        evidence.append({
            "claim": claim.get("text"),
            "assessment": claim.get("assessment"),
            "corroboration": (claim.get("corroboration") or {}).get("level"),
            "reasoning": claim.get("reasoning"),
            "sources": [
                {"publisher": s.get("publisher"), "url": s.get("url"), "excerpt": s.get("passage"),
                 "stance": s.get("stance"), "citation": (s.get("citation") or {}).get("status"),
                 "retrieved_at": s.get("retrieved_at")}
                for s in (claim.get("sources") or [])[:5]
            ],
        })

    checks = _checks(result)
    return {
        "what_was_analysed": {
            "type": (result.get("input") or {}).get("type"),
            "language": (result.get("language") or {}).get("detected"),
            "links": len((result.get("entities") or {}).get("urls", [])),
            "claims_found": len(result.get("claim_screening") or []),
            "claims_fact_checked": sum(1 for c in result.get("claims") or [] if c.get("checked")),
        },
        "what_was_detected": {
            "classification": result.get("classification"),
            "determination": risk.get("determination"),
            "summary": explanation.get("summary"),
        },
        "why": {
            "score": risk.get("score"),
            "level": risk.get("level"),
            "score_represents": risk.get("represents"),
            "drivers": [{"title": c.get("title"), "points": c.get("points"), "evidence": c.get("evidence")}
                        for c in contributions[:5]],
            "method": "Points are each signal's exact share of the score; they add up to it.",
        },
        "findings": findings,
        "evidence": evidence,
        "reliability": {
            "confidence": risk.get("confidence"),
            "band": risk.get("confidence_band"),
            "statement": explanation.get("confidence"),
        },
        "checks": checks,
        "checks_completed": sum(1 for c in checks if c["status"] == "completed"),
        "checks_not_completed": sum(1 for c in checks if c["status"] == "not_completed"),
        "not_verified": result.get("uncertainties") or [],
        "next_steps": {
            "headline": actions.get("headline"),
            "urgency": actions.get("urgency"),
            "do_now": actions.get("do_now") or [],
            "do_not": actions.get("do_not") or [],
        },
    }
