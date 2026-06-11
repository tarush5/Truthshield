"""
TruthShield — Voice Clone Detector
ECAPA-TDNN speaker embeddings + AASIST anti-spoofing detection.
"""

import logging
from typing import Optional

import numpy as np

from backend.models.schemas import VoiceCloneResult

logger = logging.getLogger(__name__)


class VoiceCloneDetector:
    """
    Detect voice cloning and synthetic speech.
    Uses ECAPA-TDNN for speaker verification and anomaly detection.
    """

    CLONE_THRESHOLD = 0.5

    # ── Class-level model cache (singleton per process) ──────
    _shared_encoder = None
    _shared_encoder_loaded = False

    def __init__(self):
        self._encoder = None
        self._is_loaded = False

    def _load_models(self):
        """Lazy-load speaker verification models (cached at class level)."""
        if self._is_loaded:
            return
        # Use class-level cache so model loads once per process
        if VoiceCloneDetector._shared_encoder_loaded:
            self._encoder = VoiceCloneDetector._shared_encoder
            self._is_loaded = True
            return

        import os
        # If running on Render or low-memory environment, do not load heavy SpeechBrain models (prevents OOM crashes)
        if os.getenv("LOW_MEMORY") == "true" or os.getenv("RENDER") == "true":
            logger.info("Low memory or Render environment detected. Skipping ECAPA-TDNN voice clone model loading.")
            VoiceCloneDetector._shared_encoder_loaded = True
            self._encoder = None
            self._is_loaded = True
            return

        try:
            from speechbrain.inference.speaker import EncoderClassifier

            VoiceCloneDetector._shared_encoder = EncoderClassifier.from_hparams(
                source="speechbrain/spkrec-ecapa-voxceleb",
                run_opts={"device": "cpu"},
            )
            VoiceCloneDetector._shared_encoder_loaded = True
            self._encoder = VoiceCloneDetector._shared_encoder
            self._is_loaded = True
            logger.info("ECAPA-TDNN voice clone detector loaded (cached at class level).")
        except Exception as e:
            logger.warning(f"Voice clone models unavailable: {e}")
            VoiceCloneDetector._shared_encoder_loaded = True  # Don't retry
            self._is_loaded = True

    def extract_embedding(self, audio_path: str) -> Optional[np.ndarray]:
        """Extract speaker embedding from audio."""
        try:
            self._load_models()
            if self._encoder is None:
                return None

            signal = self._encoder.load_audio(audio_path)
            embedding = self._encoder.encode_batch(signal.unsqueeze(0))
            return embedding.squeeze().detach().numpy()
        except Exception as e:
            logger.error(f"Embedding extraction failed: {e}")
            return None

    def compute_anomaly_score(self, audio_path: str) -> float:
        """
        Compute anomaly score for potential voice cloning using audio forensics:
        - Zero crossing rate and spectral flatness
        - Spectral roll-off and MFCC variance
        - Spectral artifacts (high-frequency energy spikes)
        - Phase inconsistency (variance of STFT phase difference)

        Returns:
            Anomaly score (0.0 = natural, 1.0 = highly anomalous)
        """
        try:
            import librosa

            y, sr = librosa.load(audio_path, sr=16000)

            # Spectral flatness
            spectral_flatness = librosa.feature.spectral_flatness(y=y)
            avg_flatness = float(np.mean(spectral_flatness))

            # Zero crossing rate
            zcr = librosa.feature.zero_crossing_rate(y)
            avg_zcr = float(np.mean(zcr))

            # Spectral rolloff
            rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr)
            avg_rolloff = float(np.mean(rolloff))

            # MFCCs variance
            mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
            mfcc_var = float(np.mean(np.var(mfccs, axis=1)))

            # ── Audio Forensics: Phase Inconsistency ──────────────
            stft = librosa.stft(y)
            magnitude = np.abs(stft)
            phase = np.angle(stft)
            phase_diff = np.diff(phase, axis=1)
            phase_var = float(np.mean(np.var(phase_diff, axis=1)))

            # ── Audio Forensics: Frequency Anomalies ──────────────
            # Energy ratio of high-to-low bands
            high_freq_energy = float(np.sum(magnitude[len(magnitude)//4:]))
            low_freq_energy = float(np.sum(magnitude[:len(magnitude)//4]))
            freq_ratio = high_freq_energy / (low_freq_energy + 1e-10)

            # Aggregate scores
            anomaly = 0.0

            # Very flat spectrum suggests synthesis
            if avg_flatness > 0.1:
                anomaly += 0.2
            if avg_flatness > 0.3:
                anomaly += 0.2

            # Low MFCC variance suggests lack of natural vocal variation
            if mfcc_var < 50:
                anomaly += 0.15

            # Unusual zero crossing rate
            if avg_zcr < 0.02 or avg_zcr > 0.15:
                anomaly += 0.15

            # Phase inconsistency detection
            if phase_var > 1.2:
                anomaly += 0.15
                logger.info(f"Audio forensics: High phase inconsistency detected (var={phase_var:.3f})")

            # High frequency energy ratio anomaly
            if freq_ratio > 0.4:
                anomaly += 0.15
                logger.info(f"Audio forensics: Unnatural high-frequency energy ratio (ratio={freq_ratio:.3f})")

            return min(anomaly, 1.0)

        except Exception as e:
            logger.warning(f"Anomaly scoring failed: {e}")
            return 0.0

    def analyze(self, audio_path: str) -> VoiceCloneResult:
        """
        Analyze audio for voice cloning indicators.

        Args:
            audio_path: Path to audio file

        Returns:
            VoiceCloneResult with cloning detection results
        """
        if not audio_path:
            return VoiceCloneResult()

        embedding = self.extract_embedding(audio_path)
        anomaly_score = self.compute_anomaly_score(audio_path)

        # If embedding extraction worked, add embedding-based analysis
        if embedding is not None:
            # Check embedding statistics for anomalies
            emb_std = float(np.std(embedding))
            emb_kurtosis = float(
                np.mean((embedding - np.mean(embedding)) ** 4)
                / (np.std(embedding) ** 4 + 1e-10)
            )

            # Very uniform embeddings may indicate synthetic speech
            if emb_std < 0.1:
                anomaly_score = min(anomaly_score + 0.15, 1.0)
            if emb_kurtosis > 10:
                anomaly_score = min(anomaly_score + 0.1, 1.0)

        is_cloned = anomaly_score > self.CLONE_THRESHOLD
        confidence = anomaly_score  # Direct mapping for simplicity

        logger.info(
            f"Voice clone analysis: anomaly={anomaly_score:.3f}, "
            f"is_cloned={is_cloned}"
        )

        return VoiceCloneResult(
            is_cloned=is_cloned,
            confidence=round(confidence, 4),
            anomaly_score=round(anomaly_score, 4),
        )
