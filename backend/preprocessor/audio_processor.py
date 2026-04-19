"""
TruthShield — Audio Processor
Transcription via Whisper + speaker embedding extraction.
"""

import logging
import os
import tempfile
from typing import Optional

from backend.models.schemas import ContentPacket, ContentType, Language

logger = logging.getLogger(__name__)


class AudioProcessor:
    """Process audio files — transcribe with Whisper and extract speaker embeddings."""

    def __init__(self):
        self._whisper_model = None

    def _load_whisper(self):
        """Lazy-load Whisper model."""
        if self._whisper_model is None:
            try:
                import whisper
                from backend.config import get_settings
                settings = get_settings()
                self._whisper_model = whisper.load_model(settings.WHISPER_MODEL)
                logger.info(f"Whisper model '{settings.WHISPER_MODEL}' loaded.")
            except Exception as e:
                logger.error(f"Failed to load Whisper: {e}")
                raise

    def transcribe(self, audio_path: str) -> dict:
        """
        Transcribe audio using Whisper.

        Returns:
            dict with 'text', 'language', 'segments'
        """
        try:
            self._load_whisper()
            result = self._whisper_model.transcribe(audio_path, task="transcribe")
            return {
                "text": result.get("text", "").strip(),
                "language": result.get("language", "en"),
                "segments": [
                    {
                        "start": seg["start"],
                        "end": seg["end"],
                        "text": seg["text"].strip(),
                    }
                    for seg in result.get("segments", [])
                ],
            }
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            return {"text": "", "language": "en", "segments": []}

    def extract_speaker_embedding(self, audio_path: str) -> Optional[list]:
        """
        Extract speaker embedding using ECAPA-TDNN via SpeechBrain.

        Returns:
            List of floats representing the speaker embedding, or None.
        """
        try:
            from speechbrain.inference.speaker import EncoderClassifier
            classifier = EncoderClassifier.from_hparams(
                source="speechbrain/spkrec-ecapa-voxceleb",
                run_opts={"device": "cpu"},
            )
            embedding = classifier.encode_batch(
                classifier.load_audio(audio_path).unsqueeze(0)
            )
            return embedding.squeeze().tolist()
        except Exception as e:
            logger.warning(f"Speaker embedding extraction failed: {e}")
            return None

    def process(
        self, audio_path: str, lang_hint: Optional[str] = None
    ) -> ContentPacket:
        """
        Process an audio file into a ContentPacket.

        Args:
            audio_path: Path to the audio file
            lang_hint: Optional language hint

        Returns:
            ContentPacket with transcribed text and speaker embedding
        """
        transcription = self.transcribe(audio_path)
        embedding = self.extract_speaker_embedding(audio_path)

        # Map Whisper language to our Language enum
        lang_map = {"en": Language.EN, "hi": Language.HI, "ta": Language.TA}
        if lang_hint:
            lang = lang_map.get(lang_hint, Language.EN)
        else:
            lang = lang_map.get(transcription["language"], Language.EN)

        logger.info(
            f"Audio processed: {len(transcription['text'])} chars transcribed, "
            f"language={lang.value}"
        )

        return ContentPacket(
            content_type=ContentType.AUDIO,
            text=transcription["text"] or None,
            lang=lang,
            embeddings=embedding,
            audio_path=audio_path,
            metadata={
                "transcription_segments": transcription["segments"],
                "whisper_language": transcription["language"],
                "has_speaker_embedding": embedding is not None,
            },
        )
