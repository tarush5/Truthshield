"""
Evidence engine.

For each extracted claim: retrieve, rank, decide stance, and assess -- the
1.x fact-check stack (multi-provider search, credibility ranking, NLI stance,
the verdict engine with its frozen-evidence accuracy benchmark), mapped onto
the 2.0 vocabulary:

    SUPPORTED · CONTRADICTED · MIXED · INSUFFICIENT_EVIDENCE

INSUFFICIENT_EVIDENCE is never forced into a decision. When retrieval cannot
run at all -- offline, disabled, timed out -- every claim is reported as not
checked, with the reason, rather than as unsupported.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
from datetime import datetime, timezone
from typing import List
from urllib.parse import urlparse

from truthshield.fraud.contract import Severity
from truthshield.investigations.engines.base import Engine
from truthshield.investigations.types import (
    EngineKind, EngineResult, EngineStatus, Family, InvestigationContext,
    ModelPredictionRecord, Provenance, Signal,
)

logger = logging.getLogger(__name__)

ASSESSMENT = {
    "VERIFIED": "SUPPORTED",
    "LIKELY TRUE": "SUPPORTED",
    "PARTIALLY TRUE": "SUPPORTED",
    "FALSE": "CONTRADICTED",
    "LIKELY FALSE": "CONTRADICTED",
    "MISLEADING": "CONTRADICTED",
    "MIXED EVIDENCE": "MIXED",
    "INSUFFICIENT EVIDENCE": "INSUFFICIENT_EVIDENCE",
}

OFFICIAL_SUFFIXES = (".gov", ".gov.in", ".nic.in", ".gov.uk", ".europa.eu", ".mil", ".int")
COMMUNITY_HOSTS = ("wikipedia.org", "reddit.com", "quora.com", "medium.com", "x.com", "twitter.com",
                   "facebook.com", "youtube.com")


# Minimum 1.x credibility score for a source to decide a claim on its own.
CREDIBLE = 0.7


def publisher_of(source_domain, url: str) -> str:
    """
    The publisher's bare host name.

    Providers disagree: some give `example.com`, some `https://www.example.com`,
    some nothing at all.
    """
    raw = (source_domain or "").strip() or url
    host = urlparse(raw).hostname if "://" in raw else raw.split("/")[0]
    return (host or "").lower().removeprefix("www.")


def source_category(domain: str, score: float) -> str:
    """
    PRIMARY / OFFICIAL / SECONDARY / COMMUNITY / UNKNOWN.

    A heuristic over the domain and the 1.x credibility score, labelled as
    such in the UI. A category is a characteristic of the source, never a
    guarantee that a particular article is right.
    """
    domain = (domain or "").lower()
    if domain.endswith(OFFICIAL_SUFFIXES) or domain in ("who.int", "pib.gov.in"):
        return "OFFICIAL"
    if any(domain == h or domain.endswith("." + h) for h in COMMUNITY_HOSTS):
        return "COMMUNITY"
    if score >= 0.7:
        return "SECONDARY"
    return "UNKNOWN"


def run_coroutine(coro):
    """Run a coroutine from sync code, whether or not a loop is already running here."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


class EvidenceEngine(Engine):
    name = "evidence"
    version = "1.0.0"
    kind = EngineKind.RETRIEVAL
    describes = "Claim verification against retrieved sources (search, credibility ranking, NLI stance)"

    def applies_to(self, ctx: InvestigationContext) -> bool:
        return bool(ctx.artifacts.get("claims"))

    def _run(self, ctx: InvestigationContext, result: EngineResult) -> None:
        from truthshield.settings import get_settings

        settings = get_settings()
        claims = ctx.artifacts["claims"][: settings.MAX_CLAIMS_PER_SUBMISSION]

        if not (settings.network_allowed and settings.EVIDENCE_RETRIEVAL_ENABLED):
            result.status = EngineStatus.UNAVAILABLE
            result.detail = "Evidence retrieval is disabled (offline mode)."
            result.artifacts["claims"] = [self._unchecked(c, result.detail) for c in claims]
            result.limitations.append(
                "Extracted claims were not checked against external sources: evidence "
                "retrieval is disabled in this deployment (offline mode)."
            )
            return

        budget = settings.EVIDENCE_TIMEOUT_SECONDS * 2 + 4
        try:
            verdicts = run_coroutine(asyncio.wait_for(self._verify(claims), timeout=budget))
        except asyncio.TimeoutError:
            result.status = EngineStatus.ERROR
            result.detail = "Evidence retrieval timed out."
            result.artifacts["claims"] = [self._unchecked(c, result.detail) for c in claims]
            result.limitations.append(
                f"Evidence retrieval did not finish within {budget:.0f}s; claims are reported "
                "as not checked. Evidence unavailable from the configured providers."
            )
            return

        assessed = []
        retrieved_at = datetime.now(timezone.utc).isoformat()
        for claim, verdict in zip(claims, verdicts):
            if isinstance(verdict, Exception) or verdict is None:
                assessed.append(self._unchecked(claim, "Retrieval failed for this claim."))
                result.limitations.append(f"Evidence for claim {claim['id']} was unavailable from the providers.")
                continue
            assessed.append(self._assess(ctx, claim, verdict, retrieved_at, result))

        result.artifacts["claims"] = assessed
        result.features["claims_checked"] = sum(1 for a in assessed if a["checked"])
        result.features["sources_retrieved"] = sum(len(a["sources"]) for a in assessed)

    async def _verify(self, claims: List[dict]):
        from truthshield.domain.evidence.ranker import SourceRanker
        from truthshield.domain.verdict import adapters
        from truthshield.domain.verdict.engine import VerdictEngine
        from truthshield.domain.verdict.legacy_types import Claim as LegacyClaim
        from truthshield.infra.evidence.retriever import EvidenceRetriever

        retriever, ranker, engine = EvidenceRetriever(), SourceRanker(), VerdictEngine()

        async def check(item: dict):
            claim = LegacyClaim(text=item["text"], entity=item.get("entity"),
                                date=item.get("date"), location=item.get("location"))
            evidence = await retriever.retrieve(claim)
            evidence = ranker.filter_disinfo(ranker.rank_evidence(evidence))
            legacy = await asyncio.to_thread(engine.evaluate_claim, claim, evidence, False)
            return adapters.from_legacy_claim_verdict(legacy)

        return await asyncio.gather(*(check(c) for c in claims), return_exceptions=True)

    def _unchecked(self, claim: dict, reason: str) -> dict:
        return {**claim, "assessment": "NOT_CHECKED", "checked": False, "confidence": None,
                "reasoning": reason, "sources": []}

    def _assess(self, ctx, claim: dict, verdict, retrieved_at: str, result: EngineResult) -> dict:
        assessment = ASSESSMENT.get(verdict.verdict.value, "INSUFFICIENT_EVIDENCE")
        reasoning = verdict.reasoning

        sources = []
        for item in verdict.evidence[:8]:
            domain = publisher_of(item.source_domain, item.url)
            sources.append({
                "title": item.title,
                "url": item.url,
                "publisher": domain,
                "category": source_category(domain, item.source_score),
                "credibility": round(item.source_score, 2),
                "stance": item.stance.value,
                "passage": (item.snippet or "")[:500],
                "retrieved_at": retrieved_at,
                "published_at": None,   # not exposed by every provider; never guessed
            })

        # A decision resting only on low-credibility sources is not a decision.
        # Measured failure: "It is 100% proven" was marked SUPPORTED on the
        # strength of a stock-analysis blog and a product launch that happened
        # to contain the words "100%" and "proven".
        downgraded = False
        if assessment in ("SUPPORTED", "CONTRADICTED"):
            stance = "SUPPORTS" if assessment == "SUPPORTED" else "REFUTES"
            decisive = [s for s in sources if s["stance"] == stance]
            if not any(s["credibility"] >= CREDIBLE or s["category"] in ("OFFICIAL", "PRIMARY") for s in decisive):
                downgraded = True
                reasoning = (
                    f"{reasoning} Downgraded to insufficient evidence: every source that "
                    f"{'supported' if stance == 'SUPPORTS' else 'contradicted'} this claim is low-credibility."
                ).strip()
                assessment = "INSUFFICIENT_EVIDENCE"

        result.predictions.append(ModelPredictionRecord(
            model_name="claim-verification", model_version=self.version,
            model_kind=EngineKind.RETRIEVAL, task="claim_assessment",
            input_sha256=ctx.input_sha256,
            prediction={"claim_id": claim["id"], "assessment": assessment,
                        "verdict": verdict.verdict.value, "sources": len(sources),
                        "downgraded": downgraded},
            confidence=round(verdict.confidence, 3),
        ))

        refuting = [s for s in sources if s["stance"] == "REFUTES"]
        if assessment == "CONTRADICTED" and verdict.confidence >= 0.4:
            lead = refuting[0] if refuting else (sources[0] if sources else None)
            result.signals.append(Signal(
                code="claim_contradicted", title="Claim contradicted by sources",
                family=Family.EVIDENCE,
                severity=Severity.HIGH if verdict.verdict.value in ("FALSE", "LIKELY FALSE") else Severity.MEDIUM,
                provenance=Provenance.RETRIEVED,
                engine=self.name, engine_version=self.version,
                explanation=(
                    f"Claim {claim['id']} is contradicted by retrieved sources"
                    + (f", including {lead['publisher']}" if lead else "")
                    + ". Sources can themselves be wrong; see the evidence tab."
                ),
                evidence=claim["text"][:200],
                confidence=round(verdict.confidence, 2),
            ))
        elif assessment == "MIXED":
            result.signals.append(Signal(
                code="claim_mixed_evidence", title="Sources disagree about a claim",
                family=Family.EVIDENCE, severity=Severity.LOW, provenance=Provenance.RETRIEVED,
                engine=self.name, engine_version=self.version,
                explanation=f"Retrieved sources both support and contradict claim {claim['id']}.",
                evidence=claim["text"][:200], confidence=round(verdict.confidence, 2),
            ))

        return {
            **claim,
            "assessment": assessment,
            "checked": True,
            "confidence": round(verdict.confidence, 3),
            "reasoning": reasoning,
            "downgraded": downgraded,
            "sources": sources,
            "support_count": sum(1 for s in sources if s["stance"] == "SUPPORTS"),
            "contradict_count": len(refuting),
        }
