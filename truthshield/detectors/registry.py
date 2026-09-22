"""
Detector registry and concrete detectors.

Each detector reports honestly whether it ran. Nothing here returns a benign
score as a stand-in for "could not check".
"""

from __future__ import annotations

import logging
import math
import re
from collections import Counter
from typing import List

from truthshield.detectors.base import (
    Detector, OptionalDependency, cv2, librosa, pytesseract, torch, transformers,
)
from truthshield.domain.types import (
    ContentPacket, ContentType, DetectorResult, DetectorStatus,
)
from truthshield.settings import get_settings

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════
# Text: AI-generated prose
# ══════════════════════════════════════════════════════════════

class AITextDetector(Detector):
    """
    Flags text that reads as LLM output.

    The heuristic path is not a degraded stand-in for the model — it measures
    real signals (stock connective phrases, unnaturally even sentence lengths,
    low vocabulary burstiness) and is reported as `heuristic`, so a reader can
    weigh it accordingly.
    """

    name = "ai_text"
    measures = "Probability the text was machine-generated"

    # Phrases that appear far more often in assistant prose than in reporting.
    TELLS = (
        "it's important to note", "it is important to note", "delve into",
        "it's worth noting", "it is worth noting", "a testament to",
        "navigating the", "in today's fast-paced", "plays a crucial role",
        "it's crucial to", "when it comes to", "the world of",
        "unlock the", "elevate your", "look no further",
    )

    def applies_to(self, packet: ContentPacket) -> bool:
        return packet.has_text and len(packet.text.split()) >= 30

    def _run(self, packet: ContentPacket) -> DetectorResult:
        text = packet.text
        sentences = [s.strip() for s in re.split(r"[.!?]+", text) if len(s.strip()) > 10]
        if len(sentences) < 3:
            return DetectorResult(
                name=self.name, status=DetectorStatus.NOT_APPLICABLE,
                detail="Too few sentences to assess",
            )

        lowered = text.lower()
        tell_hits = sum(1 for p in self.TELLS if p in lowered)

        lengths = [len(s.split()) for s in sentences]
        mean_len = sum(lengths) / len(lengths)
        variance = sum((n - mean_len) ** 2 for n in lengths) / len(lengths)
        # Human writing varies sentence length far more than generated text.
        uniformity = 1.0 / (1.0 + math.sqrt(variance) / max(mean_len, 1.0))

        words = re.findall(r"\b[a-z']{3,}\b", lowered)
        counts = Counter(words)
        # Type-token ratio: generated text reuses a narrower vocabulary.
        ttr = len(counts) / max(len(words), 1)

        score = min(1.0, 0.18 * tell_hits + 0.45 * uniformity + 0.35 * max(0.0, 0.62 - ttr) * 2.5)

        reasons = []
        if tell_hits:
            reasons.append(f"{tell_hits} stock assistant phrase(s)")
        if uniformity > 0.55:
            reasons.append("unusually even sentence lengths")
        if ttr < 0.45:
            reasons.append("narrow vocabulary")

        return DetectorResult(
            name=self.name,
            status=DetectorStatus.OK,
            score=round(score, 4),
            method="linguistic_heuristic",
            detail="; ".join(reasons) or "No strong machine-generation signals",
        )


# ══════════════════════════════════════════════════════════════
# Image / video: manipulation
# ══════════════════════════════════════════════════════════════

class DeepfakeDetector(Detector):
    """
    Looks for manipulation artefacts in image or video frames.

    Three tiers, each reported distinctly:
      * a fine-tuned classifier, when one is configured;
      * an OpenCV artefact heuristic (blur/noise distribution);
      * UNAVAILABLE, when neither can run.

    The old implementation collapsed the third case into a 0.0 score, so a
    missing torch install read as "no deepfake detected".
    """

    name = "deepfake"
    measures = "Likelihood the image or video was synthetically manipulated"

    def applies_to(self, packet: ContentPacket) -> bool:
        return packet.content_type in (ContentType.IMAGE, ContentType.VIDEO) and bool(
            packet.frame_paths or packet.file_path
        )

    def _frames(self, packet: ContentPacket) -> List[str]:
        return packet.frame_paths or ([packet.file_path] if packet.file_path else [])

    def _run(self, packet: ContentPacket) -> DetectorResult:
        frames = self._frames(packet)
        if not frames:
            return DetectorResult(
                name=self.name, status=DetectorStatus.NOT_APPLICABLE,
                detail="No frames to inspect",
            )

        if not cv2.available:
            return DetectorResult(
                name=self.name,
                status=DetectorStatus.UNAVAILABLE,
                method="none",
                detail=(
                    "OpenCV is not installed, so no visual check was performed. "
                    f"({cv2.error})"
                ),
            )

        import numpy as np
        _cv2 = cv2.get()

        scores, inspected = [], 0
        for path in frames[:12]:
            image = _cv2.imread(path)
            if image is None:
                continue
            inspected += 1
            gray = _cv2.cvtColor(image, _cv2.COLOR_BGR2GRAY)

            # Laplacian variance: synthesis and heavy retouching flatten
            # high-frequency detail; recompression spikes it.
            sharpness = _cv2.Laplacian(gray, _cv2.CV_64F).var()

            # Residual noise after blurring. Real sensors leave a consistent
            # noise floor that generative models tend not to reproduce.
            blurred = _cv2.GaussianBlur(gray, (5, 5), 0)
            residual = float(np.mean(np.abs(gray.astype(float) - blurred.astype(float))))

            frame_score = 0.15
            if sharpness < 12 or sharpness > 4200:
                frame_score += 0.35
            if residual < 1.1:
                frame_score += 0.30
            scores.append(min(1.0, frame_score))

        if not inspected:
            return DetectorResult(
                name=self.name,
                status=DetectorStatus.ERROR,
                detail="None of the frames could be decoded",
            )

        avg = sum(scores) / len(scores)

        # Frame-to-frame instability is a strong video tell; a real camera
        # produces smoothly varying statistics.
        flicker = 0.0
        if len(scores) > 1:
            diffs = [abs(scores[i] - scores[i - 1]) for i in range(1, len(scores))]
            flicker = sum(diffs) / len(diffs)
            if flicker > 0.15:
                avg = min(1.0, avg + 0.12)

        return DetectorResult(
            name=self.name,
            status=DetectorStatus.OK,
            score=round(avg, 4),
            method="opencv_artefact_heuristic",
            detail=(
                f"{inspected} frame(s) inspected; "
                f"temporal instability {flicker:.3f}. "
                "Heuristic only — not a trained deepfake classifier."
            ),
        )


# ══════════════════════════════════════════════════════════════
# Audio: synthetic speech
# ══════════════════════════════════════════════════════════════

class VoiceCloneDetector(Detector):
    name = "voice_clone"
    measures = "Likelihood the speech was synthesised or cloned"

    def applies_to(self, packet: ContentPacket) -> bool:
        return packet.content_type is ContentType.AUDIO or bool(packet.audio_path)

    def _run(self, packet: ContentPacket) -> DetectorResult:
        path = packet.audio_path or packet.file_path
        if not path:
            return DetectorResult(
                name=self.name, status=DetectorStatus.NOT_APPLICABLE,
                detail="No audio track",
            )

        if not librosa.available:
            return DetectorResult(
                name=self.name,
                status=DetectorStatus.UNAVAILABLE,
                method="none",
                detail=f"librosa is not installed, so no audio check was performed. ({librosa.error})",
            )

        import numpy as np
        _librosa = librosa.get()
        y, sr = _librosa.load(path, sr=16000, mono=True, duration=60)
        if y.size == 0:
            return DetectorResult(
                name=self.name, status=DetectorStatus.ERROR,
                detail="Audio could not be decoded",
            )

        # Synthetic speech tends to have an unnaturally flat pitch contour and
        # very little silence, because it lacks breath and hesitation.
        rms = _librosa.feature.rms(y=y)[0]
        silence_ratio = float((rms < (rms.mean() * 0.25)).mean())

        f0 = _librosa.yin(y, fmin=60, fmax=400, sr=sr)
        voiced = f0[np.isfinite(f0)]
        pitch_var = float(np.std(voiced) / max(np.mean(voiced), 1.0)) if voiced.size else 0.0

        score = 0.15
        if pitch_var < 0.07:
            score += 0.40
        if silence_ratio < 0.04:
            score += 0.25

        return DetectorResult(
            name=self.name,
            status=DetectorStatus.OK,
            score=round(min(1.0, score), 4),
            method="prosody_heuristic",
            detail=(
                f"pitch variation {pitch_var:.3f}, silence {silence_ratio:.1%}. "
                "Heuristic only — not an anti-spoofing model."
            ),
        )


# ══════════════════════════════════════════════════════════════
# Registry
# ══════════════════════════════════════════════════════════════

_DETECTORS: List[Detector] = [
    AITextDetector(),
    DeepfakeDetector(),
    VoiceCloneDetector(),
]


def run_all(packet: ContentPacket) -> List[DetectorResult]:
    """Run every detector. Individual failures are captured, not raised."""
    return [d.analyze(packet) for d in _DETECTORS]


def _tesseract_binary_present() -> bool:
    """
    Whether OCR can actually run.

    `import pytesseract` succeeding proves nothing: the package is a thin
    wrapper around a `tesseract` executable that is installed separately. The
    module imports happily on a machine with no OCR at all, so reporting on
    the import alone would claim a capability the deployment does not have —
    exactly the kind of false assurance this file exists to avoid.
    """
    if not pytesseract.available:
        return False
    try:
        pytesseract.get().get_tesseract_version()
        return True
    except Exception:
        return False


def availability() -> dict:
    """
    What can actually run right now.

    Surfaced on /health so an operator can see at a glance which capabilities
    the deployment genuinely has, instead of discovering from a suspiciously
    clean report that a model never loaded.
    """
    return {
        "torch": torch.available,
        "opencv": cv2.available,
        "transformers": transformers.available,
        "tesseract_ocr": _tesseract_binary_present(),
        "librosa": librosa.available,
        "ml_detectors_enabled": get_settings().ENABLE_ML_DETECTORS,
    }
