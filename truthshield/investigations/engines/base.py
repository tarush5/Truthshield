"""
The engine contract.

An engine is one analyser behind a fixed interface. The pipeline does not
know what any engine does; it asks whether it applies, runs it, and records
what it returned. Adding a modality means adding an engine, not editing the
pipeline.

`run` never raises. A failure becomes `status="error"` with a limitation,
because "this check crashed" and "this check found nothing" are different
answers and a report that conflates them clears inputs nobody examined.
"""

from __future__ import annotations

import abc
import logging
import time

from truthshield.investigations.types import (
    EngineKind, EngineResult, EngineStatus, InvestigationContext,
)

logger = logging.getLogger(__name__)


class Engine(abc.ABC):
    name: str = "engine"
    version: str = "0.0.0"
    kind: EngineKind = EngineKind.HEURISTIC
    describes: str = ""

    def applies_to(self, ctx: InvestigationContext) -> bool:
        return True

    @abc.abstractmethod
    def _run(self, ctx: InvestigationContext, result: EngineResult) -> None:
        """Populate `result`. May raise; `run` turns that into a reported error."""

    def blank(self, status: EngineStatus = EngineStatus.OK) -> EngineResult:
        return EngineResult(engine=self.name, version=self.version, kind=self.kind, status=status)

    def run(self, ctx: InvestigationContext) -> EngineResult:
        if not self.applies_to(ctx):
            result = self.blank(EngineStatus.NOT_APPLICABLE)
            result.detail = "Not applicable to this input."
            return result

        started = time.perf_counter()
        result = self.blank()
        try:
            self._run(ctx, result)
        except Exception as exc:
            logger.warning("Engine %s failed on %s: %s", self.name, ctx.investigation_id,
                           exc, exc_info=True)
            result = self.blank(EngineStatus.ERROR)
            result.detail = f"{type(exc).__name__}"
            result.limitations.append(
                f"The {self.name} engine failed ({type(exc).__name__}), so its checks did not run."
            )
        result.duration_ms = int((time.perf_counter() - started) * 1000)
        return result

    def describe(self) -> dict:
        return {
            "name": self.name,
            "version": self.version,
            "kind": self.kind.value,
            "describes": self.describes,
        }
