#!/usr/bin/env python3
"""Build small deterministic synthetic PDF fixtures for case_20."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
ATTACHMENTS = {
    f"packet_{index:03d}.pdf": f"CASE20-DOCUMENT-{index:03d}"
    for index in range(1, 12)
}


def make_pdf(label: str) -> bytes:
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        None,
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    stream = f"BT /F1 12 Tf 72 720 Td ({label}) Tj ET\n".encode("ascii")
    objects[3] = b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"endstream"
    output = bytearray(b"%PDF-1.4\n%CASE20-SYNTHETIC\n")
    offsets = [0]
    for index, body in enumerate(objects, 1):
        offsets.append(len(output))
        output.extend(f"{index} 0 obj\n".encode("ascii"))
        output.extend(body)
        output.extend(b"\nendobj\n")
    xref = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode(
            "ascii"
        )
    )
    return bytes(output)


def main() -> None:
    target = ROOT / "attachments"
    target.mkdir(mode=0o775, exist_ok=True)
    records = []
    for filename, label in sorted(ATTACHMENTS.items()):
        payload = make_pdf(label)
        path = target / filename
        path.write_bytes(payload)
        records.append(
            {
                "path": f"attachments/{filename}",
                "sha256": hashlib.sha256(payload).hexdigest(),
                "size_bytes": len(payload),
                "media_type": "application/pdf",
                "synthetic_label": label,
            }
        )
    (ROOT / "attachment_manifest.json").write_text(
        json.dumps(
            {"schema_version": "case20_attachment_manifest_v1", "files": records},
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
