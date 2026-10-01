"""
Uploads, PDF forensics and image OCR, through the real app.
"""

import io
import uuid

import pytest
from PIL import Image

from tests.pdf_factory import build_pdf, invoice


def upload(client, auth, name, data, mime="application/octet-stream", path="/api/v1/investigations/upload"):
    return client.post(path, files={"file": (name, data, mime)}, headers=auth)


def run(client, auth, name, data):
    r = upload(client, auth, name, data)
    assert r.status_code == 202, r.text
    inv = client.get(f"/api/v1/investigations/{r.json()['id']}", headers=auth).json()
    assert inv["status"] == "COMPLETED", inv.get("error")
    return inv


def codes(inv):
    return {s["code"] for s in inv["result"]["signals"]}


def png(text_size=(400, 120), exif_software=None, fmt="PNG"):
    img = Image.new("RGB", text_size, "white")
    buf = io.BytesIO()
    if exif_software:
        exif = Image.Exif()
        exif[305] = exif_software
        img.save(buf, fmt, exif=exif.tobytes())
    else:
        img.save(buf, fmt)
    return buf.getvalue()


@pytest.fixture
def other(client):
    r = client.post("/api/v1/auth/signup", json={"email": f"d{uuid.uuid4().hex[:10]}@example.com",
                                                 "password": "correct-horse-42"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


class TestIntake:
    def test_extension_must_match_contents(self, client, auth):
        r = upload(client, auth, "invoice.pdf", png())
        assert r.status_code == 415 and r.json()["error"]["code"] == "UNSUPPORTED_FILE"

    @pytest.mark.parametrize("name", ["setup.exe", "notes.txt", "archive.zip", "noextension"])
    def test_unsupported_types_are_refused(self, client, auth, name):
        assert upload(client, auth, name, b"%PDF-1.4 whatever").status_code == 415

    def test_oversized_upload_is_refused_and_leaves_no_temp_file(self, client, auth, monkeypatch):
        from truthshield.settings import get_settings
        from truthshield.storage import get_storage

        monkeypatch.setattr(get_settings(), "MAX_UPLOAD_SIZE_MB", 0)
        r = upload(client, auth, "big.pdf", invoice())
        assert r.status_code == 413 and r.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"
        assert not list((get_storage().root / "tmp").iterdir())

    def test_empty_file(self, client, auth):
        assert upload(client, auth, "empty.pdf", b"").status_code in (400, 415)

    def test_path_traversal_names_are_neutralised(self, client, auth):
        inv = run(client, auth, "../../../etc/passwd.pdf", invoice(number=f"PT-{uuid.uuid4().hex[:6]}"))
        assert inv["input"]["filename"] == "passwd.pdf"

    def test_files_are_stored_by_hash_and_hash_is_verified(self, client, auth):
        import hashlib
        data = invoice(number=f"H-{uuid.uuid4().hex[:6]}")
        inv = run(client, auth, "a.pdf", data)
        assert inv["input"]["sha256"] == hashlib.sha256(data).hexdigest()
        hashing = next(e for e in inv["timeline"] if e["stage"] == "HASHING")
        assert hashing["status"] == "completed"


class TestDocumentForensics:
    def test_clean_invoice_extracts_fields_and_classifies(self, client, auth):
        number = f"INV-{uuid.uuid4().hex[:6].upper()}"
        inv = run(client, auth, "invoice.pdf", invoice(number=number))
        doc = inv["result"]["document"]
        assert doc["type"] == "invoice" and doc["pages"] == 1
        fields = doc["fields"]
        assert fields["invoice_number"] == number
        assert fields["subtotal"] == 10000.0 and fields["tax"] == 1800.0 and fields["total"] == 11800.0
        assert fields["invoice_date"] == "2026-09-05" and fields["gstin"] == ["29ABCDE1234F1Z5"]
        assert "totals_mismatch" not in codes(inv)

    def test_altered_total_is_flagged_as_an_indicator(self, client, auth):
        inv = run(client, auth, "invoice.pdf", invoice(number=f"T-{uuid.uuid4().hex[:6]}", total="18,800.00"))
        signal = next(s for s in inv["result"]["signals"] if s["code"] == "totals_mismatch")
        assert "11,800.00" in signal["evidence"] and "18,800.00" in signal["evidence"]
        assert signal["family"] == "document_media" and signal["points"] > 0
        assert "forged" not in signal["explanation"].lower()
        assert inv["classification"] == "potential_document_manipulation"
        assert "issuer" in inv["result"]["recommended_actions"]["headline"]

    def test_invoice_wording_is_not_mistaken_for_a_scam_message(self, client, auth):
        """Measured false positive: "GST 18% ... amount due" fired government impersonation."""
        inv = run(client, auth, "clean.pdf", invoice(number=f"C-{uuid.uuid4().hex[:6]}"))
        found = codes(inv)
        assert not any(c.startswith("scam_") or c.startswith("manipulation_") for c in found)
        assert inv["risk_level"] == "LOW" and inv["result"]["claims"] == []
        assert any("Transactional document" in u for u in inv["result"]["uncertainties"])

    def test_due_before_issue(self, client, auth):
        inv = run(client, auth, "i.pdf", invoice(number=f"D-{uuid.uuid4().hex[:6]}", issued="20/09/2026", due="01/09/2026"))
        assert "due_before_issue" in codes(inv)

    def test_active_content_and_incremental_edits(self, client, auth):
        data = invoice(number=f"J-{uuid.uuid4().hex[:6]}", javascript="app.launchURL('http://x.top')",
                       incremental_updates=2,
                       info={"Producer": "iLovePDF", "CreationDate": "D:20260905100000",
                             "ModDate": "D:20260801100000"})
        inv = run(client, auth, "j.pdf", data)
        found = codes(inv)
        assert {"pdf_active_content", "pdf_incremental_update", "pdf_editor_tool", "pdf_dates_inconsistent"} <= found
        doc = inv["result"]["document"]
        assert doc["incremental_saves"] == 2 and "Embedded JavaScript" in doc["active_content"]
        assert doc["metadata"]["producer"] == "iLovePDF"

    def test_reused_invoice_number_across_documents(self, client, other):
        number = f"DUP-{uuid.uuid4().hex[:6]}"
        run(client, other, "first.pdf", invoice(number=number))
        second = run(client, other, "second.pdf", invoice(number=number, total="99,800.00", subtotal="88,000.00", tax="11,800.00"))
        signal = next(s for s in second["result"]["signals"] if s["code"] == "duplicate_invoice_number")
        assert number in signal["evidence"]

    def test_pdf_text_flows_into_the_text_and_url_engines(self, client, auth):
        data = build_pdf([
            "Dear customer, your account will be blocked today.",
            "Update your KYC immediately at http://sbi-kyc-verify.top/login and share the OTP.",
        ])
        inv = run(client, auth, "notice.pdf", data)
        found = codes(inv)
        assert "scam_bank_impersonation" in found and inv["result"]["url_intelligence"]
        engines = {e["name"]: e["status"] for e in inv["result"]["engines"]}
        assert engines["document"] == "ok" and engines["text"] == "ok"

    def test_malformed_pdf_is_reported_not_crashed(self, client, auth):
        inv = run(client, auth, "broken.pdf", b"%PDF-1.4\n garbage without structure")
        assert inv["status"] == "COMPLETED"
        doc_engine = next(e for e in inv["result"]["engines"] if e["name"] == "document")
        assert doc_engine["status"] in ("ok", "error")


class TestImages:
    def test_without_ocr_only_metadata_is_examined_and_it_says_so(self, client, auth):
        inv = run(client, auth, "screen.png", png())
        image = inv["result"]["image"]
        assert image["width"] == 400 and image["ocr"]["status"] == "unavailable"
        assert any("OCR is unavailable" in u for u in inv["result"]["uncertainties"])
        assert any("Pixel-level forensics" in u for u in inv["result"]["uncertainties"])

    def test_editing_software_in_exif(self, client, auth):
        inv = run(client, auth, "photo.jpg", png(exif_software="Adobe Photoshop 25.0", fmt="JPEG"))
        assert "image_editing_software" in codes(inv)

    def test_ocr_text_is_analysed_like_a_message(self, client, auth, monkeypatch):
        from truthshield.providers.base import BaseOCRProvider, OCRResult, OCRWord

        class FakeOCR(BaseOCRProvider):
            name = "fake-ocr"

            @property
            def available(self):
                return True

            def recognize(self, image, *, languages=None):
                text = "Your parcel is held at customs. Pay the release fee at http://dhl-release.top/pay today."
                return OCRResult(text=text, words=[OCRWord(w, 91.0, [0, 0, 10, 10]) for w in text.split()],
                                 languages="eng", engine="fake-ocr")

        monkeypatch.setattr("truthshield.providers.get_ocr_provider", lambda: FakeOCR())
        inv = run(client, auth, "whatsapp.png", png())
        assert inv["result"]["image"]["ocr"]["mean_confidence"] == 91.0
        assert inv["risk_level"] in ("HIGH", "CRITICAL") and inv["result"]["url_intelligence"]

    def test_decompression_bomb_guard(self, client, auth, monkeypatch):
        from truthshield.settings import get_settings
        monkeypatch.setattr(get_settings(), "MAX_IMAGE_PIXELS", 1000)
        inv = run(client, auth, "bomb.png", png(text_size=(400, 400)))
        image_engine = next(e for e in inv["result"]["engines"] if e["name"] == "image")
        assert image_engine["status"] == "error"
        assert any("pixel limit" in u for u in inv["result"]["uncertainties"])


class TestFileAccess:
    def test_owner_can_download_with_inert_headers_others_cannot(self, client, auth, other):
        data = invoice(number=f"F-{uuid.uuid4().hex[:6]}")
        inv = run(client, auth, "dl.pdf", data)
        r = client.get(f"/api/v1/investigations/{inv['id']}/file", headers=auth)
        assert r.status_code == 200 and r.content == data
        assert r.headers["x-content-type-options"] == "nosniff"
        assert r.headers["content-security-policy"] == "sandbox"
        assert client.get(f"/api/v1/investigations/{inv['id']}/file", headers=other).status_code == 404

    def test_delete_removes_the_stored_file(self, client, auth):
        from truthshield.storage import get_storage
        data = invoice(number=f"X-{uuid.uuid4().hex[:6]}")
        inv = run(client, auth, "del.pdf", data)
        key = inv["input"]["sha256"]
        assert get_storage().exists(key)
        client.delete(f"/api/v1/investigations/{inv['id']}", headers=auth)
        assert not get_storage().exists(key)

    def test_identical_uploads_share_storage_until_the_last_is_deleted(self, client, auth):
        from truthshield.storage import get_storage
        data = invoice(number=f"S-{uuid.uuid4().hex[:6]}")
        a, b = run(client, auth, "a.pdf", data), run(client, auth, "b.pdf", data)
        client.delete(f"/api/v1/investigations/{a['id']}", headers=auth)
        assert get_storage().exists(b["input"]["sha256"])
        client.delete(f"/api/v1/investigations/{b['id']}", headers=auth)
        assert not get_storage().exists(b["input"]["sha256"])


class TestSynchronous:
    def test_analyze_pdf(self, client, auth):
        r = upload(client, auth, "x.pdf", invoice(number=f"Y-{uuid.uuid4().hex[:6]}"), path="/api/v1/analyze/pdf")
        assert r.status_code == 200 and r.json()["result"]["document"]["type"] == "invoice"

    def test_analyze_image_rejects_a_pdf(self, client, auth):
        r = upload(client, auth, "x.pdf", invoice(), path="/api/v1/analyze/image")
        assert r.status_code == 415
