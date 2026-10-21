"""QR codes in uploaded images: decoded, routed to the URL engine, payment codes explained."""

import io

import cv2
import numpy as np
from PIL import Image

from tests.test_v2_documents import codes, run


def qr_png(payload: str, scale: int = 8) -> bytes:
    matrix = cv2.QRCodeEncoder.create().encode(payload)
    big = cv2.resize(matrix, None, fx=scale, fy=scale, interpolation=cv2.INTER_NEAREST)
    padded = cv2.copyMakeBorder(big, 40, 40, 40, 40, cv2.BORDER_CONSTANT, value=255)
    buf = io.BytesIO()
    Image.fromarray(padded).convert("RGB").save(buf, "PNG")
    return buf.getvalue()


def test_a_phishing_link_inside_a_qr_code_reaches_the_url_engine(client, auth):
    inv = run(client, auth, "poster.png", qr_png("http://sbi-kyc-update.verify-login.top/login"))
    qr = inv["result"]["image"]["qr"]
    assert qr["status"] == "done" and qr["codes"][0]["kind"] == "url"
    assert inv["result"]["url_intelligence"][0]["url"].startswith("http://sbi-kyc-update.verify-login.top")
    assert "brand_outside_domain" in codes(inv)
    assert inv["risk_level"] in ("MEDIUM", "HIGH", "CRITICAL")


def test_a_upi_payment_code_is_explained_not_scored(client, auth):
    payload = "upi://pay?pa=seller123@okaxis&pn=Ravi&am=1500&cu=INR"
    inv = run(client, auth, "pay.png", qr_png(payload))
    code = inv["result"]["image"]["qr"]["codes"][0]
    assert code["kind"] == "upi_payment" and code["upi"]["amount"] == "1500"
    signal = next(s for s in inv["result"]["signals"] if s["code"] == "qr_upi_payment")
    assert signal["severity"] == "INFO" and "never receive" in signal["explanation"]
    assert inv["risk_score"] == 0, "a payment QR on its own is not evidence of a scam"


def test_an_image_without_a_qr_code_reports_none(client, auth):
    blank = io.BytesIO()
    Image.fromarray(np.full((200, 200, 3), 255, dtype=np.uint8)).save(blank, "PNG")
    inv = run(client, auth, "blank.png", blank.getvalue())
    assert inv["result"]["image"]["qr"] == {"status": "done", "count": 0, "codes": []}
