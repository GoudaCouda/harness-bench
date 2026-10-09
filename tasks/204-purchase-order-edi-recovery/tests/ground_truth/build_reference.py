#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

TASK = Path(__file__).resolve().parents[2]
WORKSPACE = TASK / "workspace"
REFERENCE = TASK / "tests/reference"


def controller():
    spec = importlib.util.spec_from_file_location("poedictl_reference", WORKSPACE / "poedictl.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot import controller")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    module = controller()
    plan = json.loads(
        (TASK / "tests/ground_truth/ground_truth.json").read_text(encoding="utf-8")
    )["plan"]
    (WORKSPACE / "edi_recovery_plan.json").write_text(
        json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (WORKSPACE / "procurement_handoff.md").write_text(
        """# Procurement EDI recovery handoff

The protected source checkpoint binds the recovered PO baseline, lines, source
revision, policy, and exact EDI delivery bytes. Delivery order was not treated
as business order. Transactions were keyed by sender, receiver, message type,
and transaction control number, then the highest revision was selected per PO
and type.

PO-1002 used 855 revision 2; revision 1 was stale. Its reduction to 8 units and
1,015-cent price remained inside the two-percent policy boundary. PO-1001,
PO-1002, and PO-1005 passed line-level 850/855/856/810 matching for a local
payable total of 43,120 cents. D-035-REDRIVE was an exact duplicate and ignored.
D-035-COLLISION reused the same 810 control identity with different content and
was quarantined; it did not replace the majority-consistent INV-1005 delivery.
Unknown PO traffic was also ignored.

PO-1003 is held because five invoiced units exceed four shipped units. PO-1004
is held because its 4,125-cent 810 price differs from the authoritative
4,000-cent 855 price. PO-1006 is held on supplier rejection, and PO-NOACK is
held because no authoritative 855 exists. These are distinct local exceptions,
not interchangeable generic failures.

Before projection, apply restored PO-1004 from the interrupted journal
before-image and then committed one atomic local state. PO-POSTED and its
INV-POSTED posting ID, posting timestamp, and 7,000-cent posted amount remained
immutable; later traffic did not reopen it. Verify reconciled the line match,
journal, protected fields, and recovery identity.

Stage produced only a local payable batch and hold queue. Their hashes, the
verification, and this handoff are bound by the stage manifest and receipt.
Equivalent ordering and JSON formatting replayed as an idempotent byte-stable
no-op under the same semantic recovery identity.

No EDI was sent, no invoice was posted or paid, no supplier was contacted, and
no external action was executed.
""",
        encoding="utf-8",
    )
    for command in ("preview", "apply", "verify", "stage", "replay"):
        subprocess.run(
            [sys.executable, "poedictl.py", command, "edi_recovery_plan.json"],
            cwd=WORKSPACE,
            check=True,
            stdout=subprocess.DEVNULL,
        )
    projection = module.database_projection()
    truth = {"schema_version": 1, "plan": plan, "database": projection}
    (TASK / "tests/ground_truth/ground_truth.json").write_text(
        json.dumps(truth, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if REFERENCE.exists():
        shutil.rmtree(REFERENCE)
    REFERENCE.mkdir(parents=True)
    for name in ("edi_recovery_plan.json", ".edi_preview.json", "procurement_handoff.md"):
        shutil.copy2(WORKSPACE / name, REFERENCE / name)
    (REFERENCE / "state").mkdir()
    for name in ("procurement.db", "verification.json", "recovery_receipt.json", "replay_report.json"):
        shutil.copy2(WORKSPACE / "state" / name, REFERENCE / "state" / name)
    shutil.copytree(WORKSPACE / "staging", REFERENCE / "staging")


if __name__ == "__main__":
    main()
