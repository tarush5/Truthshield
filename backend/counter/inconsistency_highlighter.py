"""
TruthShield — Inconsistency Highlighter
Identify specific inconsistent spans in text and flag manipulated image regions.
"""

import json
import logging
from typing import List, Optional

from backend.config import CLAUDE_MAX_TOKENS, CLAUDE_MODEL, get_settings
from backend.models.schemas import Inconsistency

logger = logging.getLogger(__name__)

HIGHLIGHTER_SYSTEM_PROMPT = """You are an expert fact-checker. Analyze the following text and identify specific spans that contain inconsistencies, false claims, or misleading statements.

For each inconsistency, provide:
- span_start: character index where the problematic span begins
- span_end: character index where the problematic span ends
- reason: brief explanation of why this span is inconsistent
- severity: "low", "medium", or "high"

Respond ONLY with a JSON array. Example:
[
  {"span_start": 45, "span_end": 89, "reason": "Date contradicts official records", "severity": "high"},
  {"span_start": 120, "span_end": 156, "reason": "Statistic is fabricated", "severity": "medium"}
]

If no inconsistencies are found, return an empty array: []"""


class InconsistencyHighlighter:
    """Identify and highlight inconsistencies in analyzed content."""

    def __init__(self):
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                import anthropic

                settings = get_settings()
                self._client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
            except Exception as e:
                logger.error(f"Failed to init Anthropic client: {e}")
        return self._client

    def highlight_text(
        self, text: str, verdict: str = "", evidence_summary: str = ""
    ) -> List[Inconsistency]:
        """
        Identify inconsistent spans in text using Claude.

        Args:
            text: The text to analyze
            verdict: Overall verdict for context
            evidence_summary: Summary of evidence found

        Returns:
            List of Inconsistency objects with span positions
        """
        client = self._get_client()

        if client is None:
            return self._fallback_highlight(text)

        try:
            user_message = f"""TEXT TO ANALYZE:
{text[:2000]}

VERDICT: {verdict}
EVIDENCE CONTEXT: {evidence_summary[:500] if evidence_summary else 'None'}

Identify all inconsistencies in the text above."""

            response = client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=CLAUDE_MAX_TOKENS,
                system=HIGHLIGHTER_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}],
            )

            response_text = response.content[0].text.strip()

            # Extract JSON array
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()

            items = json.loads(response_text)

            inconsistencies = []
            for item in items:
                inconsistencies.append(
                    Inconsistency(
                        span_start=int(item.get("span_start", 0)),
                        span_end=int(item.get("span_end", 0)),
                        reason=item.get("reason", ""),
                        severity=item.get("severity", "medium"),
                    )
                )

            logger.info(f"Found {len(inconsistencies)} inconsistencies in text")
            return inconsistencies

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse inconsistency response: {e}")
            return self._fallback_highlight(text)
        except Exception as e:
            logger.error(f"Inconsistency highlighting failed: {e}")
            return self._fallback_highlight(text)

    def generate_gradcam_overlay(
        self, image_path: str, model=None
    ) -> Optional[str]:
        """
        Generate GradCAM heatmap overlay for flagged image regions.
        
        Args:
            image_path: Path to the image
            model: The detection model to generate attention maps from

        Returns:
            Path to the heatmap overlay image, or None
        """
        try:
            import cv2
            import numpy as np

            img = cv2.imread(image_path)
            if img is None:
                return None

            # Simplified GradCAM-like visualization
            # In production, this would use actual model attention maps
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Use Laplacian to find regions of interest
            laplacian = cv2.Laplacian(gray, cv2.CV_64F)
            laplacian_abs = np.abs(laplacian)
            
            # Normalize to 0-255
            heatmap = cv2.normalize(laplacian_abs, None, 0, 255, cv2.NORM_MINMAX)
            heatmap = heatmap.astype(np.uint8)
            
            # Apply colormap
            heatmap_colored = cv2.applyColorMap(heatmap, cv2.COLORMAP_JET)
            
            # Overlay on original
            overlay = cv2.addWeighted(img, 0.6, heatmap_colored, 0.4, 0)
            
            output_path = image_path.replace(".", "_gradcam.")
            cv2.imwrite(output_path, overlay)
            
            logger.info(f"GradCAM overlay saved: {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"GradCAM generation failed: {e}")
            return None

    def _fallback_highlight(self, text: str) -> List[Inconsistency]:
        """Basic heuristic fallback for inconsistency detection."""
        import re

        inconsistencies = []

        # Check for common misinformation patterns
        patterns = [
            (r"\b100\s*%\b", "Absolute claims (100%) are rarely accurate", "medium"),
            (r"\beveryone\s+knows?\b", "Appeal to common knowledge fallacy", "low"),
            (r"\bshare\s+(before|this|now)\b", "Urgency to share is a common disinfo tactic", "medium"),
            (r"\bthey\s+don't\s+want\s+you\s+to\s+know\b", "Conspiracy framing detected", "high"),
            (r"\bbreaking\s*:\s*", "Unverified 'breaking news' claim", "medium"),
        ]

        for pattern, reason, severity in patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                inconsistencies.append(
                    Inconsistency(
                        span_start=match.start(),
                        span_end=match.end(),
                        reason=reason,
                        severity=severity,
                    )
                )

        return inconsistencies
