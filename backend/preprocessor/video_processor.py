"""
TruthShield — Video Processor
Keyframe extraction with OpenCV + audio track separation.
"""

import logging
import os
import tempfile
import uuid
from pathlib import Path
from typing import List, Optional, Tuple

from backend.models.schemas import ContentPacket, ContentType, Language

logger = logging.getLogger(__name__)


class VideoProcessor:
    """Process video files — extract keyframes and audio track."""

    KEYFRAME_INTERVAL_SEC = 2  # Extract a frame every 2 seconds

    def extract_keyframes(
        self, video_path: str, output_dir: Optional[str] = None
    ) -> List[str]:
        """
        Extract keyframes from video at fixed intervals.

        Args:
            video_path: Path to the video file
            output_dir: Directory to save extracted frames

        Returns:
            List of paths to extracted frame images
        """
        try:
            import cv2
        except ImportError:
            logger.error("OpenCV not available. Cannot extract keyframes.")
            return []

        if output_dir is None:
            output_dir = tempfile.mkdtemp(prefix="truthshield_frames_")

        os.makedirs(output_dir, exist_ok=True)

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            logger.error(f"Cannot open video: {video_path}")
            return []

        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        frame_interval = int(fps * self.KEYFRAME_INTERVAL_SEC)
        frame_paths = []
        frame_count = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_count % frame_interval == 0:
                frame_filename = f"frame_{frame_count:06d}.jpg"
                frame_path = os.path.join(output_dir, frame_filename)
                cv2.imwrite(frame_path, frame)
                frame_paths.append(frame_path)

            frame_count += 1

        cap.release()
        logger.info(f"Extracted {len(frame_paths)} keyframes from {video_path}")
        return frame_paths

    def extract_audio(self, video_path: str, output_path: Optional[str] = None) -> Optional[str]:
        """
        Extract audio track from video using ffmpeg via subprocess.

        Args:
            video_path: Path to the video file
            output_path: Path to save extracted audio

        Returns:
            Path to extracted audio file, or None on failure
        """
        if output_path is None:
            output_path = os.path.join(
                tempfile.mkdtemp(prefix="truthshield_audio_"),
                "extracted_audio.wav",
            )

        try:
            import subprocess

            cmd = [
                "ffmpeg", "-i", video_path,
                "-vn",  # No video
                "-acodec", "pcm_s16le",  # WAV format
                "-ar", "16000",  # 16kHz sample rate (good for Whisper)
                "-ac", "1",  # Mono
                "-y",  # Overwrite
                output_path,
            ]
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=120
            )
            if result.returncode == 0 and os.path.exists(output_path):
                logger.info(f"Audio extracted to {output_path}")
                return output_path
            else:
                logger.error(f"ffmpeg error: {result.stderr[:500]}")
                return None
        except FileNotFoundError:
            logger.error("ffmpeg not found. Install ffmpeg for audio extraction.")
            return None
        except Exception as e:
            logger.error(f"Audio extraction failed: {e}")
            return None

    def get_video_info(self, video_path: str) -> dict:
        """Get basic video metadata."""
        try:
            import cv2
            cap = cv2.VideoCapture(video_path)
            info = {
                "fps": cap.get(cv2.CAP_PROP_FPS),
                "frame_count": int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
                "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                "duration_sec": (
                    cap.get(cv2.CAP_PROP_FRAME_COUNT) / cap.get(cv2.CAP_PROP_FPS)
                    if cap.get(cv2.CAP_PROP_FPS) > 0
                    else 0
                ),
            }
            cap.release()
            return info
        except Exception as e:
            logger.error(f"Failed to get video info: {e}")
            return {}

    def process(
        self, video_path: str, lang_hint: Optional[str] = None
    ) -> ContentPacket:
        """
        Process a video file into a ContentPacket.
        Extracts keyframes and audio, then transcribes the audio.

        Args:
            video_path: Path to the video file
            lang_hint: Optional language hint

        Returns:
            ContentPacket with transcribed audio text, keyframe paths, metadata
        """
        # Extract keyframes
        frame_paths = self.extract_keyframes(video_path)

        # Extract and transcribe audio
        audio_path = self.extract_audio(video_path)
        transcription_text = None
        lang = Language(lang_hint) if lang_hint else Language.EN

        if audio_path:
            from backend.preprocessor.audio_processor import AudioProcessor
            audio_proc = AudioProcessor()
            audio_packet = audio_proc.process(audio_path, lang_hint)
            transcription_text = audio_packet.text
            lang = audio_packet.lang

        video_info = self.get_video_info(video_path)

        logger.info(
            f"Video processed: {len(frame_paths)} frames, "
            f"audio={'yes' if audio_path else 'no'}, lang={lang.value}"
        )

        return ContentPacket(
            content_type=ContentType.VIDEO,
            text=transcription_text,
            lang=lang,
            image_paths=frame_paths,
            audio_path=audio_path,
            video_path=video_path,
            metadata={
                "video_info": video_info,
                "keyframe_count": len(frame_paths),
                "has_audio": audio_path is not None,
            },
        )
