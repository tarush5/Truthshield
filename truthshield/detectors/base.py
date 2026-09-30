"""
Detector interface.

The contract that matters: **a detector that could not run says so.**

In the previous version every detector failed open. A deepfake detector whose
model would not import returned `confidence=0.0`, which the aggregator read as
"inspected, perfectly clean" and fed into the trust score as a positive
signal. An image whose OCR, captioning and deepfake model had all failed was
reported to the user as VERIFIED at 85% trust, having had nothing verified at
all.

Every detector here returns a DetectorResult carrying a DetectorStatus, and
the scorer only consults results whose status is OK. "We could not check this"
and "we checked and it was fine" are different answers and are now
representable as such.
"""

from __future__ import annotations

import abc
import logging
from typing import Optional

from truthshield.domain.types import (
    ContentPacket, DetectorResult, DetectorStatus,
)

logger = logging.getLogger(__name__)


class Detector(abc.ABC):
    """A single manipulation signal."""

    #: Stable identifier used in reports and metrics.
    name: str = "detector"

    #: Human-readable description of what a high score means.
    measures: str = ""

    @abc.abstractmethod
    def applies_to(self, packet: ContentPacket) -> bool:
        """Whether this detector has anything to say about this input."""

    @abc.abstractmethod
    def _run(self, packet: ContentPacket) -> DetectorResult:
        """Do the work. May raise; `analyze` turns that into an ERROR result."""

    def analyze(self, packet: ContentPacket) -> DetectorResult:
        """
        Run the detector, never raising.

        A detector failing must not take the analysis down, but it also must
        not silently look like a pass — hence ERROR rather than a zero score.
        """
        if not self.applies_to(packet):
            return DetectorResult(
                name=self.name,
                status=DetectorStatus.NOT_APPLICABLE,
                detail="No content of this kind was submitted",
            )
        try:
            return self._run(packet)
        except Exception as exc:
            logger.warning("Detector %s failed: %s", self.name, exc, exc_info=True)
            return DetectorResult(
                name=self.name,
                status=DetectorStatus.ERROR,
                detail=f"{type(exc).__name__}: {exc}",
            )


class OptionalDependency:
    """
    Import a heavy optional dependency once, remembering failure.

    A failed import is not cached by Python, so a module that is genuinely
    absent was re-attempted on every request — re-running the import
    machinery and re-logging the same warning each time.
    """

    __slots__ = ("_module_path", "_attr", "_value", "_attempted", "_error")

    def __init__(self, module_path: str, attr: Optional[str] = None):
        self._module_path = module_path
        self._attr = attr
        self._value = None
        self._attempted = False
        self._error: Optional[str] = None

    @property
    def available(self) -> bool:
        self._load()
        return self._value is not None

    @property
    def error(self) -> Optional[str]:
        self._load()
        return self._error

    def get(self):
        self._load()
        return self._value

    def _load(self) -> None:
        if self._attempted:
            return
        self._attempted = True
        try:
            import importlib
            module = importlib.import_module(self._module_path)
            self._value = getattr(module, self._attr) if self._attr else module
        except Exception as exc:
            self._error = f"{type(exc).__name__}: {exc}"
            logger.info(
                "Optional dependency %s unavailable (%s). Detectors relying on "
                "it will report UNAVAILABLE rather than a clean result.",
                self._module_path, self._error,
            )


# Resolved once per process.
torch = OptionalDependency("torch")
cv2 = OptionalDependency("cv2")
transformers = OptionalDependency("transformers")
pytesseract = OptionalDependency("pytesseract")
librosa = OptionalDependency("librosa")
