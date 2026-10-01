"""
Minimal, valid PDFs for tests -- written byte by byte so the suite needs no
PDF-writing dependency. Supports text lines, Info metadata, an OpenAction
JavaScript, and a genuine incremental update (a second xref section with
/Prev), which is exactly the structure the document engine looks for.
"""

from __future__ import annotations

from typing import Dict, List, Optional


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def build_pdf(
    lines: List[str],
    *,
    info: Optional[Dict[str, str]] = None,
    javascript: Optional[str] = None,
    incremental_updates: int = 0,
) -> bytes:
    content = "BT /F1 11 Tf 50 760 Td 14 TL " + " ".join(f"({_escape(l)}) Tj T*" for l in lines) + " ET"
    objects = {
        1: "<< /Type /Catalog /Pages 2 0 R" + (" /OpenAction 5 0 R" if javascript else "") + " >>",
        2: "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        3: "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
           "/Resources << /Font << /F1 6 0 R >> >> >>",
        4: f"<< /Length {len(content)} >>\nstream\n{content}\nendstream",
        6: "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    }
    if javascript:
        objects[5] = f"<< /S /JavaScript /JS ({_escape(javascript)}) >>"
    if info:
        objects[7] = "<< " + " ".join(f"/{k} ({_escape(v)})" for k, v in info.items()) + " >>"

    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = {}
    for num in sorted(objects):
        offsets[num] = len(out)
        out += f"{num} 0 obj\n{objects[num]}\nendobj\n".encode("latin-1")
    size = max(objects) + 1
    xref = len(out)
    out += f"xref\n0 {size}\n0000000000 65535 f \n".encode()
    for num in range(1, size):
        if num in offsets:
            out += f"{offsets[num]:010d} 00000 n \n".encode()
        else:
            out += b"0000000000 65535 f \n"
    trailer = f"/Size {size} /Root 1 0 R" + (" /Info 7 0 R" if info else "")
    out += f"trailer\n<< {trailer} >>\nstartxref\n{xref}\n%%EOF\n".encode()

    prev = xref
    for n in range(incremental_updates):
        num = size + n
        offset = len(out)
        out += f"{num} 0 obj\n<< /Note (edit {n}) >>\nendobj\n".encode()
        new_xref = len(out)
        out += f"xref\n{num} 1\n{offset:010d} 00000 n \n".encode()
        out += f"trailer\n<< /Size {num + 1} /Root 1 0 R /Prev {prev} >>\nstartxref\n{new_xref}\n%%EOF\n".encode()
        prev = new_xref
    return bytes(out)


def invoice(number="INV-2026-0042", subtotal="10,000.00", tax="1,800.00", total="11,800.00",
            issued="05/09/2026", due="20/09/2026", **kwargs) -> bytes:
    return build_pdf([
        "ACME Supplies Pvt Ltd",
        "TAX INVOICE",
        f"Invoice No: {number}",
        f"Invoice Date: {issued}",
        f"Due Date: {due}",
        "Bill To: Example Traders",
        "GSTIN: 29ABCDE1234F1Z5",
        "Item: Office chairs x 10",
        f"Subtotal: Rs. {subtotal}",
        f"GST 18%: Rs. {tax}",
        f"Total Amount Due: Rs. {total}",
    ], **kwargs)
