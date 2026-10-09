#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


TASK = Path(__file__).resolve().parents[2]
WORKSPACE = TASK / "workspace"
REFERENCE = TASK / "tests/reference"
sys.dont_write_bytecode = True


def canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def recreate(path: Path, schema: str) -> sqlite3.Connection:
    path.unlink(missing_ok=True)
    connection = sqlite3.connect(path)
    connection.executescript("PRAGMA journal_mode=DELETE;\n" + schema)
    return connection


def simple_pdf(lines: list[str]) -> bytes:
    escaped = [
        line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        for line in lines
    ]
    stream = (
        "BT /F1 10 Tf 40 760 Td "
        + " 0 -16 Td ".join(f"({line}) Tj" for line in escaped)
        + " ET"
    )
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        f"<< /Length {len(stream.encode('latin-1'))} >>\nstream\n{stream}\nendstream",
    ]
    data = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, body in enumerate(objects, 1):
        offsets.append(len(data))
        data.extend(f"{index} 0 obj\n{body}\nendobj\n".encode("latin-1"))
    xref = len(data)
    data.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        data.extend(f"{offset:010d} 00000 n \n".encode())
    data.extend(
        f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    return bytes(data)


def build_receipts() -> None:
    directory = WORKSPACE / "receipts"
    if directory.exists():
        shutil.rmtree(directory)
    directory.mkdir()
    pdf_201 = simple_pdf(
        [
            "Transaction ID: PC-201",
            "Merchant: Harbor Office Supply",
            "Currency: USD",
            "Subtotal cents: 7500",
            "Tax cents: 0",
            "Total cents: 7500",
        ]
    )
    (directory / "PC-201.pdf").write_bytes(pdf_201)
    (directory / "PC-203.html").write_text(
        "<!doctype html><html><body><p>Transaction ID: PC-203</p><p>Merchant: Metro AV</p>"
        "<p>Currency: USD</p><p>Subtotal cents: 26000</p><p>Tax cents: 0</p><p>Total cents: 26000</p></body></html>\n",
        encoding="utf-8",
    )
    (directory / "PC-204.json").write_text(
        json.dumps(
            {
                "transaction_id": "PC-204",
                "merchant": "Metro AV",
                "currency": "USD",
                "subtotal_cents": 26000,
                "tax_cents": 0,
                "total_cents": 26000,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (directory / "PC-205.html").write_text(
        "<!doctype html><html><body><p>Transaction ID: PC-205</p><p>Merchant: Civic Hotel</p>"
        "<p>Currency: USD</p><p>Subtotal cents: 10000</p><p>Tax cents: 1000</p><p>Total cents: 11000</p></body></html>\n",
        encoding="utf-8",
    )
    (directory / "PC-207.pdf").write_bytes(
        simple_pdf(
            [
                "Transaction ID: PC-207",
                "Merchant: Field Calibration Lab",
                "Currency: USD",
                "Subtotal cents: 8900",
                "Tax cents: 0",
                "Total cents: 8900",
            ]
        )
    )
    media = {
        "PC-201.pdf": "application/pdf",
        "PC-203.html": "text/html",
        "PC-204.json": "application/json",
        "PC-205.html": "text/html",
        "PC-207.pdf": "application/pdf",
    }
    manifest = {
        "schema_version": 1,
        "receipts": [
            {
                "transaction_id": name.split(".")[0],
                "path": f"receipts/{name}",
                "media_type": media[name],
                "sha256": sha(directory / name),
            }
            for name in sorted(media)
        ],
    }
    (WORKSPACE / "receipt_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def build_sources() -> None:
    connection = recreate(
        WORKSPACE / "issuer.db",
        """
        CREATE TABLE transactions (
          transaction_id TEXT PRIMARY KEY, cardholder_id TEXT NOT NULL, posted_at TEXT NOT NULL,
          local_date TEXT NOT NULL, merchant TEXT NOT NULL, amount_cents INTEGER NOT NULL,
          tax_cents INTEGER NOT NULL, currency TEXT NOT NULL, original_transaction_id TEXT,
          issuer_trace TEXT NOT NULL
        );
    """,
    )
    transactions = [
        (
            "PC-201",
            "EMP-17",
            "2026-07-03T16:12:00Z",
            "2026-07-03",
            "Harbor Office Supply",
            7500,
            0,
            "USD",
            None,
            "ISS-77101",
        ),
        (
            "PC-202",
            "EMP-22",
            "2026-07-08T18:20:00Z",
            "2026-07-08",
            "Northline Safety",
            12000,
            0,
            "USD",
            None,
            "ISS-77102",
        ),
        (
            "PC-203",
            "EMP-31",
            "2026-07-11T15:01:00Z",
            "2026-07-11",
            "Metro AV",
            26000,
            0,
            "USD",
            None,
            "ISS-77103",
        ),
        (
            "PC-204",
            "EMP-31",
            "2026-07-11T15:17:00Z",
            "2026-07-11",
            "Metro AV",
            26000,
            0,
            "USD",
            None,
            "ISS-77104",
        ),
        (
            "PC-205",
            "EMP-44",
            "2026-07-15T21:40:00Z",
            "2026-07-15",
            "Civic Hotel",
            11000,
            1000,
            "USD",
            None,
            "ISS-77105",
        ),
        (
            "PC-206",
            "EMP-17",
            "2026-07-19T10:05:00Z",
            "2026-07-19",
            "Harbor Office Supply",
            -5000,
            0,
            "USD",
            "PC-099",
            "ISS-77106",
        ),
        (
            "PC-207",
            "EMP-58",
            "2026-07-28T14:30:00Z",
            "2026-07-28",
            "Field Calibration Lab",
            8900,
            0,
            "USD",
            None,
            "ISS-77107",
        ),
    ]
    connection.executemany(
        "INSERT INTO transactions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", transactions
    )
    connection.commit()
    connection.execute("VACUUM")
    connection.close()

    connection = recreate(
        WORKSPACE / "erp.db",
        """
        CREATE TABLE posted_card_transactions (
          transaction_id TEXT PRIMARY KEY, period TEXT NOT NULL, amount_cents INTEGER NOT NULL,
          currency TEXT NOT NULL, posting_document TEXT NOT NULL, immutable_status TEXT NOT NULL
        );
    """,
    )
    connection.execute(
        "INSERT INTO posted_card_transactions VALUES (?, ?, ?, ?, ?, ?)",
        ("PC-099", "2026-06", 5000, "USD", "ERP-PC-202606-0099", "posted_locked"),
    )
    connection.commit()
    connection.execute("VACUUM")
    connection.close()

    connection = recreate(
        WORKSPACE / "acceptance.db",
        """
        CREATE TABLE acceptance_decisions (
          transaction_id TEXT PRIMARY KEY, status TEXT NOT NULL, accepted_cents INTEGER NOT NULL,
          approver_id TEXT NOT NULL, decided_at TEXT NOT NULL, evidence_id TEXT NOT NULL
        );
    """,
    )
    decisions = [
        ("PC-201", "accepted", 7500, "MGR-08", "2026-07-05T12:00:00Z", "ACC-8201"),
        ("PC-203", "accepted", 26000, "MGR-11", "2026-07-12T12:00:00Z", "ACC-8203"),
        ("PC-204", "accepted", 26000, "MGR-11", "2026-07-12T12:04:00Z", "ACC-8204"),
        ("PC-205", "accepted", 10000, "MGR-19", "2026-07-17T09:00:00Z", "ACC-8205"),
    ]
    connection.executemany(
        "INSERT INTO acceptance_decisions VALUES (?, ?, ?, ?, ?, ?)", decisions
    )
    connection.commit()
    connection.execute("VACUUM")
    connection.close()


def source_checkpoint() -> str:
    manifest = json.loads(
        (WORKSPACE / "receipt_manifest.json").read_text(encoding="utf-8")
    )
    paths = [
        WORKSPACE / "issuer.db",
        WORKSPACE / "erp.db",
        WORKSPACE / "acceptance.db",
        WORKSPACE / "close_context.json",
        WORKSPACE / "pcard_policy.md",
        WORKSPACE / "receipt_manifest.json",
        *(WORKSPACE / row["path"] for row in manifest["receipts"]),
    ]
    return digest({path.relative_to(WORKSPACE).as_posix(): sha(path) for path in paths})


def build_close_state() -> None:
    context = json.loads((WORKSPACE / "close_context.json").read_text(encoding="utf-8"))
    connection = recreate(
        WORKSPACE / "pcard_close_state.db",
        """
        CREATE TABLE close_journal (
          close_id TEXT PRIMARY KEY, period TEXT NOT NULL, source_checkpoint TEXT NOT NULL,
          phase TEXT NOT NULL, prepared_transaction_id TEXT NOT NULL,
          semantic_plan_sha256 TEXT, started_at TEXT NOT NULL, committed_at TEXT
        );
        CREATE TABLE prepared_actions (
          close_id TEXT NOT NULL, transaction_id TEXT NOT NULL, candidate_disposition TEXT NOT NULL,
          PRIMARY KEY(close_id, transaction_id)
        );
        CREATE TABLE close_runs (
          close_id TEXT PRIMARY KEY, source_checkpoint TEXT NOT NULL, semantic_plan_sha256 TEXT NOT NULL,
          action_count INTEGER NOT NULL, committed_at TEXT NOT NULL
        );
        CREATE TABLE transaction_dispositions (
          close_id TEXT NOT NULL, transaction_id TEXT NOT NULL, disposition TEXT NOT NULL,
          cleared_cents INTEGER NOT NULL, exception_cents INTEGER NOT NULL,
          evidence_json TEXT NOT NULL, receipt_sha256 TEXT,
          PRIMARY KEY(close_id, transaction_id)
        );
        CREATE TABLE split_edges (
          close_id TEXT NOT NULL, left_transaction_id TEXT NOT NULL, right_transaction_id TEXT NOT NULL,
          combined_cents INTEGER NOT NULL, PRIMARY KEY(close_id, left_transaction_id, right_transaction_id)
        );
        CREATE TABLE refund_links (
          close_id TEXT NOT NULL, refund_transaction_id TEXT NOT NULL, original_transaction_id TEXT NOT NULL,
          refund_cents INTEGER NOT NULL, PRIMARY KEY(close_id, refund_transaction_id)
        );
    """,
    )
    connection.execute(
        "INSERT INTO close_journal VALUES (?, ?, ?, 'prepared', 'PC-205', NULL, ?, NULL)",
        (
            context["close_id"],
            context["period"],
            source_checkpoint(),
            context["prepared_at"],
        ),
    )
    connection.execute(
        "INSERT INTO prepared_actions VALUES (?, 'PC-205', 'partial_nonreimbursable_tax')",
        (context["close_id"],),
    )
    connection.commit()
    connection.execute("VACUUM")
    connection.close()


def load_controller(workspace: Path):
    spec = importlib.util.spec_from_file_location(
        "pcard_fixture_controller", workspace / "pcardctl.py"
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load controller")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def reference_plan() -> dict[str, Any]:
    controller = load_controller(WORKSPACE)
    decisions = controller.derive_decisions()
    context = json.loads((WORKSPACE / "close_context.json").read_text(encoding="utf-8"))
    return {
        "schema_version": 1,
        "close_id": context["close_id"],
        "period": context["period"],
        "source_checkpoint": source_checkpoint(),
        "actions": [
            {
                "transaction_id": transaction_id,
                "disposition": value["disposition"],
                "evidence_refs": value["evidence_refs"],
            }
            for transaction_id, value in sorted(decisions.items())
        ],
        "external_actions_executed": False,
    }


def handoff() -> str:
    return """# July purchase-card close recovery handoff

The local close `PCLOSE-2026-07-CARDOPS` is committed and staged pending ERP posting approval. No external posting, payment, cardholder message, procurement approval, or notification occurred.

## Evidence and adjudication

PC-201 clears because its PDF receipt was parsed, its manifest SHA-256 matched, and ACC-8201 accepted the charge. PC-202 remains a full missing-receipt hold because no receipt artifact exists. PC-203 and PC-204 each have valid HTML/JSON receipt evidence and acceptance, but their same-cardholder, same-merchant, same-day connected component totals 520.00 USD while each charge is below the 500.00 threshold; both remain separately held for suspected split-purchase review. They were not collapsed into one ledger row.

PC-205 has a valid HTML receipt and acceptance for its 100.00 USD subtotal. Its 10.00 USD sales tax is separately retained as non-reimbursable, so only the subtotal clears. PC-206 is a -50.00 USD refund linked to immutable prior-month ERP posting PC-099; it is not netted against PC-202 or the split exceptions. PC-207 has a parsed, hash-matched PDF receipt but no acceptance row, so the entire charge remains held for department acceptance.

## Recovery and verification

The interrupted journal had only prepared PC-205; it did not prove an ERP posting. Recovery consumed that prepared action and committed one seven-action local close transaction. The issuer, ERP, acceptance, policy, manifest, and PDF/HTML/JSON receipts stayed immutable. Controller verification reconciled every disposition, cleared and exception cents, the split edge, refund link, journal, and source checkpoint.

Re-running apply with the same business close identity and semantically equivalent source-bound plan returned an idempotent replay. The staged receipt is digest-bound to the logical close, plan, verification, and source checkpoint; replay left the SQLite close state and staged receipt byte-for-byte unchanged. External ERP posting still requires independent approval.
"""


def write_source_hashes() -> None:
    protected = [
        "issuer.db",
        "erp.db",
        "acceptance.db",
        "close_context.json",
        "pcard_policy.md",
        "receipt_manifest.json",
        "pcardctl.py",
        *sorted(
            path.relative_to(WORKSPACE).as_posix()
            for path in (WORKSPACE / "receipts").iterdir()
        ),
    ]
    value = {name: sha(WORKSPACE / name) for name in protected}
    (WORKSPACE / "SOURCE_HASHES.json").write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def build_reference() -> None:
    if REFERENCE.exists():
        shutil.rmtree(REFERENCE)
    REFERENCE.mkdir()
    with tempfile.TemporaryDirectory(prefix="pcard-reference-") as temporary:
        target = Path(temporary) / "workspace"
        shutil.copytree(WORKSPACE, target)
        (target / "reconciliation_plan.json").write_text(
            json.dumps(reference_plan(), indent=2) + "\n", encoding="utf-8"
        )
        (target / "close_handoff.md").write_text(handoff(), encoding="utf-8")
        for arguments in (
            ("preview", "reconciliation_plan.json"),
            ("apply", "reconciliation_plan.json"),
            ("apply", "reconciliation_plan.json"),
            ("verify",),
            ("stage", "reconciliation_plan.json"),
            ("replay", "reconciliation_plan.json"),
        ):
            subprocess.run(
                ["python3", "pcardctl.py", *arguments],
                cwd=target,
                check=True,
                stdout=subprocess.PIPE,
                text=True,
            )
        for name in (
            "pcard_close_state.db",
            "reconciliation_plan.json",
            "pcard_verification.json",
            "pcard_stage_receipt.json",
            "close_handoff.md",
        ):
            shutil.copy2(target / name, REFERENCE / name)


def main() -> None:
    build_receipts()
    build_sources()
    build_close_state()
    write_source_hashes()
    build_reference()
    truth = {
        "close_id": "PCLOSE-2026-07-CARDOPS",
        "period": "2026-07",
        "source_checkpoint": source_checkpoint(),
        "transaction_count": 7,
        "gross_charges_cents": 91400,
        "refunds_cents": -5000,
        "net_feed_cents": 86400,
        "cleared_cents": 12500,
        "exception_cents": 73900,
    }
    (TASK / "tests/ground_truth/ground_truth.json").write_text(
        json.dumps(truth, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
