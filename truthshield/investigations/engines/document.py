"""
Document (PDF) engine.

    PDF → structure scan → metadata → text per page → OCR for scanned pages →
    page classification → field extraction → numerical and date consistency →
    metadata anomalies → signals

Every finding is phrased as a *potential manipulation indicator*. A totals
mismatch or an editor in the metadata is a reason to check the document with
its issuer, never proof that it is forged -- genuine documents are re-saved,
merged and edited all the time.

Parsing is bounded: page cap, text cap, and the parser never executes
anything. Active content (JavaScript, launch actions, embedded files) is
detected by scanning for the PDF names that declare it, and reported.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from truthshield.fraud.contract import Severity
from truthshield.investigations.engines.base import Engine
from truthshield.investigations.types import (
    EngineKind, EngineResult, EngineStatus, Family, InvestigationContext, InvestigationType,
    ModelPredictionRecord, Provenance, Signal,
)

MAX_TEXT_CHARS = 200_000
SCANNED_PAGE_CHARS = 25

ACTIVE_CONTENT = {
    b"/JavaScript": ("Embedded JavaScript", Severity.HIGH),
    b"/JS": ("Embedded JavaScript", Severity.HIGH),
    b"/Launch": ("Launch action (can open other programs)", Severity.HIGH),
    b"/OpenAction": ("Action that runs when the document opens", Severity.MEDIUM),
    b"/EmbeddedFiles": ("Embedded file attachments", Severity.MEDIUM),
    b"/RichMedia": ("Embedded rich media", Severity.LOW),
    b"/XFA": ("XFA form (can carry scripts)", Severity.LOW),
}

# Tools whose presence in Producer/Creator shows the file was processed after
# it was first made. Legitimate uses are common, hence LOW.
EDITORS = (
    "ilovepdf", "smallpdf", "sejda", "pdfescape", "pdf-xchange", "foxit phantompdf", "nitro",
    "photoshop", "gimp", "canva", "pdffiller", "dochub", "inkscape", "pdf editor", "pdfelement",
)

DOC_TYPES: Dict[str, Tuple[str, ...]] = {
    "invoice": ("invoice", "tax invoice", "bill to", "invoice no", "invoice number", "amount due", "gstin"),
    "receipt": ("receipt", "payment received", "thank you for your payment", "transaction id", "paid"),
    "bank_statement": ("statement of account", "account statement", "opening balance", "closing balance",
                       "ifsc", "debit", "credit", "balance"),
    "contract": ("agreement", "hereinafter", "party", "terms and conditions", "witness", "signed"),
    "certificate": ("certificate", "certify that", "awarded", "has successfully completed"),
    "government": ("government of", "ministry", "department of", "notice", "order no", "gazette"),
}

MONEY = r"(?:₹|rs\.?|inr|usd|\$|€|£)?\s*([0-9]{1,3}(?:[,\s][0-9]{2,3})*(?:\.[0-9]{1,2})?|[0-9]+(?:\.[0-9]{1,2})?)"
LABELLED_AMOUNTS = {
    "subtotal": rf"\bsub[\s-]?total\b[^0-9₹$€£]{{0,20}}{MONEY}",
    "tax": rf"\b(?:tax(?!\s+invoice)|gst|igst|cgst\s*\+\s*sgst|vat)\b(?:\s*\(?\d{{1,2}}(?:\.\d+)?%\)?)?[^0-9₹$€£]{{0,20}}{MONEY}",
    "total": rf"\b(?:grand\s+total|total\s+amount|amount\s+due|total\s+due|total)\b[^0-9₹$€£]{{0,20}}{MONEY}",
}
INVOICE_NO = re.compile(r"\b(?:invoice|inv|bill)\s*(?:no|number|num|#)\.?\s*[:#\-]?\s*([A-Z0-9][A-Z0-9\-/]{2,30})", re.I)
DATE_TOKEN = r"(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}|\d{4}-\d{2}-\d{2}|\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}|[A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4})"
INVOICE_DATE = re.compile(rf"\b(?:invoice\s+date|date\s+of\s+issue|issue\s+date|dated?)\b\s*[:\-]?\s*{DATE_TOKEN}", re.I)
DUE_DATE = re.compile(rf"\b(?:due\s+date|payment\s+due|pay\s+by)\b\s*[:\-]?\s*{DATE_TOKEN}", re.I)
GSTIN = re.compile(r"\b\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]\b")
PAN = re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")
IFSC = re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b")


def parse_amount(raw: str) -> Optional[float]:
    try:
        return float(re.sub(r"[,\s]", "", raw))
    except ValueError:
        return None


def parse_date(raw: str) -> Optional[datetime]:
    raw = raw.strip().rstrip(".,")
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%y", "%d-%m-%y", "%Y-%m-%d",
                "%d %B %Y", "%d %b %Y", "%B %d %Y", "%b %d %Y", "%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def pdf_date(value) -> Optional[datetime]:
    """PDF metadata dates: D:YYYYMMDDHHmmSS(+HH'mm')."""
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    match = re.match(r"D:(\d{4})(\d{2})?(\d{2})?(\d{2})?(\d{2})?(\d{2})?", str(value))
    if not match:
        return None
    parts = [int(p) if p else d for p, d in zip(match.groups(), (0, 1, 1, 0, 0, 0))]
    try:
        return datetime(*parts, tzinfo=timezone.utc)
    except ValueError:
        return None


class DocumentEngine(Engine):
    name = "document"
    version = "1.0.0"
    kind = EngineKind.HEURISTIC
    describes = "PDF structure, metadata, text and OCR, field extraction, consistency and manipulation indicators"

    def applies_to(self, ctx: InvestigationContext) -> bool:
        return ctx.type is InvestigationType.DOCUMENT and bool(ctx.file_path)

    def _signal(self, **kw) -> Signal:
        return Signal(engine=self.name, engine_version=self.version, family=Family.DOCUMENT_MEDIA,
                      provenance=Provenance.HEURISTIC, **kw)

    def _run(self, ctx: InvestigationContext, result: EngineResult) -> None:
        from pypdf import PdfReader
        from pypdf.errors import PdfReadError

        from truthshield.settings import get_settings

        settings = get_settings()
        with open(ctx.file_path, "rb") as fh:
            raw = fh.read()

        structure = self._structure(raw, result)
        try:
            reader = PdfReader(ctx.file_path, strict=False)
        except (PdfReadError, ValueError, OSError) as exc:
            result.status = EngineStatus.ERROR
            result.detail = "The PDF could not be parsed."
            result.limitations.append(f"The PDF could not be parsed ({type(exc).__name__}); it may be malformed.")
            result.signals.append(self._signal(
                code="malformed_pdf", title="Malformed PDF", severity=Severity.MEDIUM,
                explanation="The file claims to be a PDF but its structure is broken. Damaged files are "
                            "sometimes produced by tampering tools; they can also simply be corrupted.",
                evidence=type(exc).__name__, confidence=0.4,
            ))
            return

        if reader.is_encrypted:
            try:
                reader.decrypt("")
            except Exception:
                pass
            if reader.is_encrypted:
                result.limitations.append("The PDF is encrypted with a password, so its text was not analysed.")
                result.artifacts["document"] = {"encrypted": True, **structure}
                return

        metadata = self._metadata(reader, result)
        pages, scanned, page_texts = len(reader.pages), [], []
        for index, page in enumerate(reader.pages[: settings.MAX_PDF_PAGES]):
            try:
                text = page.extract_text() or ""
            except Exception:
                text = ""
            if len(text.strip()) < SCANNED_PAGE_CHARS:
                scanned.append(index)
            page_texts.append(text)
        if pages > settings.MAX_PDF_PAGES:
            result.limitations.append(
                f"Only the first {settings.MAX_PDF_PAGES} of {pages} pages were analysed (page limit)."
            )

        ocr = self._ocr_scanned(reader, scanned, page_texts, result)
        full_text = "\n\n".join(page_texts)[:MAX_TEXT_CHARS]
        ctx.text = full_text

        doc_type, type_scores = self._classify(full_text)
        # Read by the text engine, which runs next on the same context.
        ctx.artifacts["document_type"] = doc_type
        fields = self._fields(full_text)
        self._consistency(fields, result)
        self._metadata_anomalies(metadata, structure, result)
        if doc_type == "invoice":
            missing = [name for name in ("invoice_number", "invoice_date", "total") if not fields.get(name)]
            if missing:
                result.signals.append(self._signal(
                    code="invoice_fields_missing", title="Standard invoice fields missing", severity=Severity.LOW,
                    explanation="Genuine invoices almost always carry a number, a date and a total. Missing "
                                "fields can mean an incomplete or fabricated document -- or a format these "
                                "rules do not recognise.",
                    evidence=", ".join(missing), confidence=0.4,
                ))

        result.artifacts["document"] = {
            "encrypted": False,
            "pages": pages,
            "pages_analysed": min(pages, settings.MAX_PDF_PAGES),
            "scanned_pages": [i + 1 for i in scanned],
            "ocr": ocr,
            "type": doc_type,
            "type_scores": type_scores,
            "fields": fields,
            "metadata": metadata,
            **structure,
            "text_chars": len(full_text),
            "page_previews": [t.strip()[:600] for t in page_texts[:5]],
        }
        result.features.update({"pages": pages, "text_chars": len(full_text), "incremental_saves": structure["incremental_saves"]})
        result.predictions.append(ModelPredictionRecord(
            model_name="document-rules", model_version=self.version, model_kind=EngineKind.HEURISTIC,
            task="document_classification", input_sha256=ctx.input_sha256,
            prediction={"type": doc_type, "scores": type_scores, "signals": [s.code for s in result.signals]},
            confidence=None,
        ))

    # ── Structure ─────────────────────────────────────────────

    def _structure(self, raw: bytes, result: EngineResult) -> dict:
        found = {}
        for marker, (title, severity) in ACTIVE_CONTENT.items():
            # Name followed by a delimiter, so /JS does not match /JSON.
            if re.search(re.escape(marker) + rb"[\s/<\[(]", raw):
                found.setdefault(title, severity)
        for title, severity in found.items():
            result.signals.append(self._signal(
                code="pdf_active_content", title=f"Active content: {title}", severity=severity,
                explanation="Invoices, statements and certificates have no need to run code. Active content "
                            "in such a document is a common malware and phishing technique.",
                evidence=title, confidence=0.75,
            ))

        eof_count = len(re.findall(rb"%%EOF", raw))
        incremental = max(0, eof_count - 1)
        if incremental:
            result.signals.append(self._signal(
                code="pdf_incremental_update", title="Modified after it was first saved",
                severity=Severity.MEDIUM if incremental >= 2 else Severity.LOW,
                explanation="The file contains incremental updates: content was appended to an already "
                            "finished PDF. Signing and form-filling do this legitimately; so does editing a "
                            "total or a name after the fact.",
                evidence=f"{incremental} incremental save{'s' if incremental != 1 else ''}", confidence=0.55,
            ))
        return {"active_content": sorted(found), "incremental_saves": incremental, "size_bytes": len(raw)}

    def _metadata(self, reader, result: EngineResult) -> dict:
        try:
            info = reader.metadata or {}
        except Exception:
            info = {}
        get = lambda k: str(info.get(k)) if info.get(k) else None  # noqa: E731
        created = pdf_date(info.get("/CreationDate"))
        modified = pdf_date(info.get("/ModDate"))
        return {
            "producer": get("/Producer"),
            "creator": get("/Creator"),
            "author": get("/Author"),
            "title": get("/Title"),
            "created": created.isoformat() if created else None,
            "modified": modified.isoformat() if modified else None,
        }

    def _metadata_anomalies(self, metadata: dict, structure: dict, result: EngineResult) -> None:
        tools = " ".join(filter(None, [metadata.get("producer"), metadata.get("creator")])).lower()
        editor = next((e for e in EDITORS if e in tools), None)
        if editor:
            result.signals.append(self._signal(
                code="pdf_editor_tool", title="Processed with a PDF or image editor", severity=Severity.LOW,
                explanation="The metadata names an editing tool. Many genuine documents pass through such "
                            "tools; combined with other indicators it suggests the file was altered.",
                evidence=f"Producer/Creator: {tools[:120]}", confidence=0.45,
            ))
        created, modified = metadata.get("created"), metadata.get("modified")
        if created and modified:
            c, m = datetime.fromisoformat(created), datetime.fromisoformat(modified)
            if m < c - timedelta(minutes=1):
                result.signals.append(self._signal(
                    code="pdf_dates_inconsistent", title="Modified before it was created", severity=Severity.MEDIUM,
                    explanation="The metadata says the file was modified before it was created, which normal "
                                "software does not produce. Metadata is easy to edit; this is what an edit can leave.",
                    evidence=f"created {created}, modified {modified}", confidence=0.55,
                ))
            elif m - c > timedelta(days=30):
                result.signals.append(self._signal(
                    code="pdf_modified_long_after", title="Modified long after creation", severity=Severity.INFO,
                    explanation="The file was changed more than a month after it was created.",
                    evidence=f"created {created}, modified {modified}", confidence=0.3,
                ))

    # ── OCR ───────────────────────────────────────────────────

    def _ocr_scanned(self, reader, scanned: List[int], page_texts: List[str], result: EngineResult) -> dict:
        if not scanned:
            return {"status": "not_needed"}
        from truthshield.providers import get_ocr_provider

        provider = get_ocr_provider()
        if not provider.available:
            result.limitations.append(
                f"{len(scanned)} page(s) appear to be scanned images ({', '.join(str(i + 1) for i in scanned[:10])}); "
                f"their text was not read because OCR is unavailable: {provider.unavailable_reason}"
            )
            return {"status": "unavailable", "detail": provider.unavailable_reason}

        pages_done, confidences = [], []
        for index in scanned[:10]:
            texts = []
            try:
                for image in reader.pages[index].images[:4]:
                    ocr = provider.recognize(image.image)
                    texts.append(ocr.text)
                    if ocr.mean_confidence is not None:
                        confidences.append(ocr.mean_confidence)
            except Exception as exc:
                result.limitations.append(f"OCR failed on page {index + 1} ({type(exc).__name__}).")
                continue
            if texts:
                page_texts[index] = "\n".join(texts)
                pages_done.append(index + 1)
        return {"status": "done", "engine": provider.name, "pages": pages_done,
                "mean_confidence": round(sum(confidences) / len(confidences), 1) if confidences else None}

    # ── Content ───────────────────────────────────────────────

    @staticmethod
    def _classify(text: str):
        lowered = text.lower()
        scores = {kind: sum(1 for k in keys if k in lowered) for kind, keys in DOC_TYPES.items()}
        best = max(scores, key=scores.get)
        return (best if scores[best] >= 2 else "other"), scores

    @staticmethod
    def _fields(text: str) -> dict:
        fields: Dict[str, object] = {}
        number = INVOICE_NO.search(text)
        if number:
            fields["invoice_number"] = number.group(1).strip()
        for name, pattern in (("invoice_date", INVOICE_DATE), ("due_date", DUE_DATE)):
            match = pattern.search(text)
            if match:
                parsed = parse_date(match.group(1))
                fields[name] = parsed.date().isoformat() if parsed else match.group(1)
        for name, pattern in LABELLED_AMOUNTS.items():
            # The *last* labelled total is the grand total on most layouts.
            matches = [parse_amount(m.group(1)) for m in re.finditer(pattern, text, re.I)]
            matches = [m for m in matches if m is not None]
            if matches:
                fields[name] = matches[-1] if name == "total" else matches[0]
        for name, pattern in (("gstin", GSTIN), ("pan", PAN), ("ifsc", IFSC)):
            values = sorted(set(pattern.findall(text)))
            if values:
                fields[name] = values[:5]
        return fields

    def _consistency(self, fields: dict, result: EngineResult) -> None:
        subtotal, tax, total = fields.get("subtotal"), fields.get("tax"), fields.get("total")
        if isinstance(subtotal, float) and isinstance(tax, float) and isinstance(total, float) and total > 0:
            expected = subtotal + tax
            if abs(expected - total) > max(1.0, 0.01 * total):
                result.signals.append(self._signal(
                    code="totals_mismatch", title="Totals do not add up", severity=Severity.HIGH,
                    explanation="Subtotal plus tax does not equal the stated total. Arithmetic errors happen, "
                                "but an edited total is the most common alteration made to an invoice.",
                    evidence=f"{subtotal:,.2f} + {tax:,.2f} = {expected:,.2f}, but the total says {total:,.2f}",
                    confidence=0.65,
                ))
        today = datetime.now(timezone.utc).date()
        issued, due = fields.get("invoice_date"), fields.get("due_date")
        issued_d = datetime.fromisoformat(issued).date() if isinstance(issued, str) and re.match(r"\d{4}-\d{2}-\d{2}$", issued) else None
        due_d = datetime.fromisoformat(due).date() if isinstance(due, str) and re.match(r"\d{4}-\d{2}-\d{2}$", due) else None
        if issued_d and due_d and due_d < issued_d:
            result.signals.append(self._signal(
                code="due_before_issue", title="Due date is before the issue date", severity=Severity.MEDIUM,
                explanation="Payment cannot fall due before the document was issued.",
                evidence=f"issued {issued_d}, due {due_d}", confidence=0.6,
            ))
        if issued_d and issued_d > today + timedelta(days=1):
            result.signals.append(self._signal(
                code="issue_date_in_future", title="Issued in the future", severity=Severity.MEDIUM,
                explanation="The issue date is after today.",
                evidence=str(issued_d), confidence=0.6,
            ))
