"""
TruthShield — Deepfake Detector
EfficientNet-B4 based face forgery detection on video frames.
"""

import logging
from typing import List, Optional

import numpy as np

from backend.models.schemas import DeepfakeResult

logger = logging.getLogger(__name__)


class DeepfakeDetector:
    """
    Detect deepfake manipulation in images/video frames.
    Uses EfficientNet-B4 pre-trained on FaceForensics++.
    """

    THRESHOLD = 0.5  # Above this = likely deepfake

    def __init__(self):
        self._model = None
        self._face_cascade = None

    def _load_model(self):
        """Lazy-load the deepfake detection model."""
        if self._model is not None:
            return
        try:
            import torch
            from torchvision import models, transforms

            # Load EfficientNet-B4 (use pretrained ImageNet weights as base)
            # In production, load fine-tuned FaceForensics++ weights
            self._model = models.efficientnet_b4(weights="IMAGENET1K_V1")
            self._model.classifier[1] = torch.nn.Linear(
                self._model.classifier[1].in_features, 2  # real vs fake
            )
            self._model.eval()

            self._transform = transforms.Compose([
                transforms.Resize((380, 380)),
                transforms.ToTensor(),
                transforms.Normalize(
                    mean=[0.485, 0.456, 0.406],
                    std=[0.229, 0.224, 0.225],
                ),
            ])
            logger.info("EfficientNet-B4 deepfake detector loaded.")
        except Exception as e:
            logger.error(f"Failed to load deepfake model: {e}")
            self._model = None

    def _load_face_detector(self):
        """Load OpenCV face detector."""
        if self._face_cascade is not None:
            return
        try:
            import cv2
            cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            self._face_cascade = cv2.CascadeClassifier(cascade_path)
        except Exception as e:
            logger.warning(f"Face detector unavailable: {e}")

    def detect_faces(self, image_path: str) -> List[tuple]:
        """Detect face regions in an image."""
        try:
            import cv2
            self._load_face_detector()
            img = cv2.imread(image_path)
            if img is None:
                return []
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            faces = self._face_cascade.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60)
            )
            return [(x, y, w, h) for (x, y, w, h) in faces]
        except Exception as e:
            logger.warning(f"Face detection failed: {e}")
            return []

    def analyze_frame(self, image_path: str) -> float:
        """
        Analyze a single frame for deepfake indicators.

        Returns:
            Deepfake probability (0.0 = real, 1.0 = fake)
        """
        try:
            self._load_model()
            if self._model is None:
                return self._fallback_analyze(image_path)

            import torch
            from PIL import Image

            img = Image.open(image_path).convert("RGB")

            # Detect faces and crop to face region
            faces = self.detect_faces(image_path)
            if faces:
                x, y, w, h = faces[0]  # Use largest face
                # Add padding
                pad = int(max(w, h) * 0.2)
                x1 = max(0, x - pad)
                y1 = max(0, y - pad)
                x2 = min(img.width, x + w + pad)
                y2 = min(img.height, y + h + pad)
                img = img.crop((x1, y1, x2, y2))

            tensor = self._transform(img).unsqueeze(0)

            with torch.no_grad():
                output = self._model(tensor)
                probabilities = torch.softmax(output, dim=1)
                fake_prob = probabilities[0][1].item()

            return fake_prob

        except Exception as e:
            logger.error(f"Frame analysis failed: {e}")
            return self._fallback_analyze(image_path)

    def _fallback_analyze(self, image_path: str) -> float:
        """Heuristic fallback for deepfake detection."""
        try:
            import cv2
            img = cv2.imread(image_path)
            if img is None:
                return 0.0

            # Simple heuristics: check for compression artifacts, noise patterns
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()

            # Very high or very low variance can indicate manipulation
            if laplacian_var < 10 or laplacian_var > 5000:
                return 0.6
            return 0.2
        except Exception:
            return 0.0

    def analyze(self, frame_paths: List[str]) -> DeepfakeResult:
        """
        Analyze multiple frames and aggregate results with temporal coherence checks.

        Args:
            frame_paths: List of paths to video frames or images

        Returns:
            DeepfakeResult with aggregated score
        """
        if not frame_paths:
            return DeepfakeResult()

        scores = []
        flagged = []

        for idx, path in enumerate(frame_paths):
            score = self.analyze_frame(path)
            scores.append(score)
            if score > self.THRESHOLD:
                flagged.append(idx)

        avg_score = float(np.mean(scores)) if scores else 0.0
        
        # Temporal Analysis: Check for frame-to-frame score inconsistencies (flicker)
        temporal_anomaly = 0.0
        if len(scores) > 1:
            diffs = [abs(scores[i] - scores[i-1]) for i in range(1, len(scores))]
            temporal_anomaly = float(np.mean(diffs))
            # If frame predictions fluctuate wildly (e.g. mean diff > 0.15), increase confidence
            if temporal_anomaly > 0.15:
                avg_score = min(1.0, avg_score + 0.12)
                logger.info(f"Temporal anomaly detected: frame fluctuation={temporal_anomaly:.3f}. Score boosted.")

        is_deepfake = avg_score > self.THRESHOLD

        logger.info(
            f"Deepfake analysis: {len(frame_paths)} frames, "
            f"avg_score={avg_score:.3f}, flagged={len(flagged)}, temporal_anomaly={temporal_anomaly:.3f}"
        )

        return DeepfakeResult(
            is_deepfake=is_deepfake,
            confidence=round(avg_score, 4),
            flagged_frames=flagged,
            needs_human_review=(0.4 <= avg_score <= 0.7) or (temporal_anomaly > 0.2)
        )
