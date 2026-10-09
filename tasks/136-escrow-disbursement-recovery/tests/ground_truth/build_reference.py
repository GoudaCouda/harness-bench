from __future__ import annotations

import importlib.util
import shutil
import subprocess
import tempfile
from pathlib import Path


TASK = Path(__file__).resolve().parents[2]


HANDOFF = """# Escrow closeout recovery handoff

Recovery EDR-20260819-01 restored the interrupted SQLite before-image before one
atomic local projection. Delivery order was not treated as authority: the first
event ID won, accepted events were evaluated by source sequence, DL-004 was a
duplicate of EV-101-WIRE, ESC-999 was unknown, and the late ESC-103 wire was
ignored across its irreversible disbursement boundary.

ESC-101 conserves its 10,000,000-cent received wire across six signed and
verified instructions, including the 100,000-cent retained holdback. Its signed
closing authorization and recording confirmation are hash-grounded, so a local
disbursement review packet was staged. ESC-104 likewise conserves 7,200,000
cents and preserves its pre-existing recording timestamp; it is ready only for
local packet review. No money moved.

ESC-102 is held because the payoff instruction document names account suffix
9999 while the verified payee ledger requires 1122. The wire, signed closing
authorization, and recording event do not cure that instruction-identity
mismatch. ESC-106 is held because active allocations total 8,950,000 cents
against a 9,000,000-cent wire, so funds do not conserve. ESC-107 is held because
the event points to a closing-authorization document that does not exist; its
wire and recording evidence cannot replace signed authority.

ESC-103 remains disbursed exactly as recorded: its property, recording and
disbursement timestamps, and 6,500,000-cent disbursed amount were not reopened.
ESC-105 preserves its prior 4,920,000-cent disbursement and 80,000-cent retained
holdback. A matching signed holdback-release authorization supports only a local
release-review packet; the holdback was not released.

The verification binds the protected source checkpoint, normalized semantic
plan, final SQLite projection, event receipts, restored old journal, and new
before-image journal. The local disbursement packet and manifest hashes close to
the recovery receipt. Semantic replay accepted reordered/set-equivalent content
as the same plan and left database, packet, manifest, and receipt bytes stable.

No wire was sent, no disbursement was executed, no holdback release occurred,
no recording or filing was performed, and no notification was sent. Both
packets remain local review artifacts; no bank, recorder, payee,
buyer, seller, broker, or other external party was contacted.
"""


def load_controller(workspace: Path):
    spec = importlib.util.spec_from_file_location("escrow_reference_controller", workspace / "escrowctl.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load controller")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build() -> None:
    reference = TASK / "tests/reference"
    shutil.rmtree(reference, ignore_errors=True)
    with tempfile.TemporaryDirectory(prefix="hb136-reference-") as temporary:
        workspace = Path(temporary) / "workspace"
        shutil.copytree(TASK / "workspace", workspace)
        module = load_controller(workspace)
        spec = importlib.util.spec_from_file_location("escrow_reference_outcome", TASK / "tests/test_outcome.py")
        if spec is None or spec.loader is None:
            raise RuntimeError("cannot import evaluator")
        evaluator = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(evaluator)
        module.write_json(workspace / "recovery_plan.json", evaluator._truth()["plan"])
        for command in ("preview", "apply", "verify", "stage", "replay"):
            subprocess.run(
                ["python3", "escrowctl.py", command, "recovery_plan.json"],
                cwd=workspace, check=True,
            )
        (workspace / "escrow_handoff.md").write_text(HANDOFF, encoding="utf-8")
        reference.mkdir(parents=True)
        for locator in (
            "recovery_plan.json", ".escrow_preview.json", "escrow_handoff.md",
            "state/escrow.db", "state/verification.json", "state/recovery_receipt.json",
            "state/replay_report.json", "staging/disbursement_packet.json",
            "staging/packet_manifest.json",
        ):
            source = workspace / locator
            target = reference / locator
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)


if __name__ == "__main__":
    build()
