"""
TruthShield — WhatsApp Bot Integration
Twilio WhatsApp sandbox webhook for misinformation analysis.
"""

import logging
import os
import sys
import tempfile
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import PlainTextResponse

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("truthshield.whatsapp")

app = FastAPI(title="TruthShield WhatsApp Bot")

# ── Twilio Response Helper ────────────────────────────────────

def twiml_response(message: str) -> str:
    """Generate TwiML response XML."""
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Response>"
        f"<Message>{message}</Message>"
        "</Response>"
    )


def detect_lang_simple(text: str) -> str:
    """Quick language detection."""
    try:
        from langdetect import detect
        lang = detect(text)
        if lang in ("hi", "ta"):
            return lang
        return "en"
    except Exception:
        return "en"


# ── Conversation State ────────────────────────────────────────
# In production, use Redis for session management
user_sessions: dict = {}


# ── Webhook Endpoint ─────────────────────────────────────────

@app.post("/webhook")
async def whatsapp_webhook(
    Body: str = Form(""),
    From: str = Form(""),
    NumMedia: int = Form(0),
    MediaUrl0: str = Form(None),
    MediaContentType0: str = Form(None),
):
    """
    Handle incoming WhatsApp messages via Twilio webhook.

    Supported inputs:
    - Text messages
    - Forwarded images
    - Audio notes
    - Video clips
    """
    sender = From
    text = Body.strip()
    lang = detect_lang_simple(text) if text else "en"

    logger.info(f"Message from {sender}: text='{text[:50]}', media={NumMedia}")

    # Check if user has a pending session
    session = user_sessions.get(sender, {})

    # Handle follow-up commands
    if text in ("1", "2") and session.get("last_report"):
        report = session["last_report"]

        if text == "1":
            # Full explanation
            explanation = report.get("explanation", {})
            lang_key = f"text_{lang}"
            explain_text = explanation.get(lang_key, explanation.get("text_en", ""))

            if not explain_text:
                explain_text = (
                    "Analysis details:\n"
                    f"Trust Score: {report.get('credibility', {}).get('trust_score', '?')}/100\n"
                    f"Verdict: {report.get('credibility', {}).get('verdict', 'Unknown')}"
                )

            return PlainTextResponse(
                twiml_response(f"📋 *Full Explanation:*\n\n{explain_text}"),
                media_type="text/xml",
            )

        elif text == "2":
            # Sources
            sources = []
            for claim in report.get("claims", []):
                for ev in claim.get("evidence", []):
                    sources.append(f"• {ev.get('title', 'Source')}\n  {ev.get('url', '')}")

            sources_text = "\n".join(sources[:5]) if sources else "No sources available."
            return PlainTextResponse(
                twiml_response(f"🔗 *Sources:*\n\n{sources_text}"),
                media_type="text/xml",
            )

    # ── New Analysis Request ──────────────────────────────────

    # Step 1: Send "analyzing" message
    analysis_text = {
        "en": "Analyzing your content... ⏳",
        "hi": "आपकी सामग्री का विश्लेषण हो रहा है... ⏳",
        "ta": "உங்கள் உள்ளடக்கம் பகுப்பாய்வு செய்யப்படுகிறது... ⏳",
    }

    try:
        import requests

        # Call the TruthShield API
        api_url = os.getenv("TRUTHSHIELD_API_URL", "http://localhost:8000/api/v1")
        payload = {}

        if text and not MediaUrl0:
            payload = {"text": text, "lang": lang}
        elif MediaUrl0:
            # Download media and send to API
            payload = {"url": MediaUrl0, "lang": lang}

        if not payload:
            return PlainTextResponse(
                twiml_response("Please send text, an image, audio, or video to analyze."),
                media_type="text/xml",
            )

        # Make API call
        form_data = {}
        if "text" in payload:
            form_data["text"] = (None, payload["text"])
        if "url" in payload:
            form_data["url"] = (None, payload["url"])
        form_data["lang"] = (None, lang)

        response = requests.post(
            f"{api_url}/analyze",
            data={k: v[1] if isinstance(v, tuple) else v for k, v in form_data.items()},
            timeout=60,
        )

        if response.status_code == 200:
            report = response.json()

            # Store session
            user_sessions[sender] = {"last_report": report}

            # Format response
            trust_score = report.get("credibility", {}).get("trust_score", 50)
            verdict = report.get("credibility", {}).get("verdict", "Unknown")

            # Trust emoji
            if trust_score >= 75:
                emoji = "✅"
            elif trust_score >= 55:
                emoji = "⚠️"
            elif trust_score >= 35:
                emoji = "🟡"
            else:
                emoji = "🔴"

            # One-line verdict in user's language
            verdict_text = {
                "en": f"{emoji} *Trust Score: {trust_score}/100*\n{verdict}",
                "hi": f"{emoji} *विश्वास स्कोर: {trust_score}/100*\n{verdict}",
                "ta": f"{emoji} *நம்பிக்கை மதிப்பெண்: {trust_score}/100*\n{verdict}",
            }

            reply = (
                f"🛡️ *TruthShield Analysis*\n\n"
                f"{verdict_text.get(lang, verdict_text['en'])}\n\n"
                f"Reply '1' for full explanation\n"
                f"Reply '2' for sources"
            )

            return PlainTextResponse(
                twiml_response(reply), media_type="text/xml"
            )

        else:
            return PlainTextResponse(
                twiml_response("❌ Analysis failed. Please try again later."),
                media_type="text/xml",
            )

    except Exception as e:
        logger.error(f"Analysis error: {e}")
        return PlainTextResponse(
            twiml_response(
                "❌ Service temporarily unavailable. Please try again."
            ),
            media_type="text/xml",
        )


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "TruthShield WhatsApp Bot"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
