from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import tempfile
from pathlib import Path


TASK = Path(__file__).resolve().parents[2]
REFERENCE = TASK / "tests/reference"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    evaluator = load_module("task140_evaluator", TASK / "tests/test_outcome.py")
    plan = evaluator._truth()["plan"]
    with tempfile.TemporaryDirectory(prefix="hb140-reference-") as raw:
        workspace = Path(raw) / "workspace"
        shutil.copytree(TASK / "workspace", workspace)
        (workspace / "recovery_plan.json").write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        for command in ("preview", "apply", "verify", "stage"):
            subprocess.run(["python3", "pvctl.py", command, "recovery_plan.json"], cwd=workspace, check=True, capture_output=True, text=True)
        equivalent = json.loads(json.dumps(plan))
        equivalent["case_decisions"].reverse()
        equivalent["delivery_dispositions"].reverse()
        for row in equivalent["case_decisions"]:
            row["selected_message_ids"].reverse()
            row["evidence_refs"] = [str(item).replace("#safety_cases:", "#case:").replace("#message_id:", "#message:") for item in reversed(row["evidence_refs"])]
        (workspace / "equivalent_recovery_plan.json").write_text(json.dumps(equivalent, separators=(",", ":")) + "\n", encoding="utf-8")
        subprocess.run(["python3", "pvctl.py", "replay", "equivalent_recovery_plan.json"], cwd=workspace, check=True, capture_output=True, text=True)
        conflict = json.loads(json.dumps(plan))
        next(row for row in conflict["case_decisions"] if row["case_id"] == "ICSR-2405")["next_local_action"] = "stage_local_review"
        (workspace / "conflict_probe_plan.json").write_text(json.dumps(conflict, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        tracked = {"database": workspace / "state/pv.db", "packet": workspace / "staging/pv_review_queue.json", "manifest": workspace / "staging/packet_manifest.json", "receipt": workspace / "state/recovery_receipt.json"}
        before = {key: sha(path) for key, path in tracked.items()}
        completed = subprocess.run(["python3", "pvctl.py", "apply", "conflict_probe_plan.json"], cwd=workspace, check=False, capture_output=True, text=True)
        after = {key: sha(path) for key, path in tracked.items()}
        report = {"schema_version": 1, "command": "python3 pvctl.py apply conflict_probe_plan.json", "exit_code": completed.returncode, "changed_field": "case_decisions[ICSR-2405].next_local_action", "before_sha256": before, "after_sha256": after}
        (workspace / "conflict_probe.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (workspace / "pv_handoff.md").write_text(
            """# Pharmacovigilance intake recovery handoff

The PV-RECOVERY-140-R1 local projection was recovered from the interrupted SQLite journal. The ICSR-2402 before-image was restored before the new atomic transaction; the old partial receipt was removed and the interrupted run is marked recovered. All immutable source digests matched the source checkpoint.

ICSR-2401 remains at accepted version 2: MSG-2401-V3 crossed the accepted acknowledgement boundary, so the accepted record is immutable and the message was held rather than applied. ICSR-2408 likewise remains version 1 while its acknowledgement is pending; MSG-2408-V2 was not projected and the next action remains await ACK.

For ICSR-2402, source sequence placed MSG-2402-V2 before MSG-2402-V3 even though file order differed. Both contiguous versions were selected, with final version 3 staged to expedited review. DEL-02-RETRY reused the V2 message identity and was ignored as a duplicate. ICSR-2404 is a new fatal serious case at V1 and is staged for expedited local review under the seven-calendar-day class. ICSR-2407 accepted its non-serious follow-up V2 into routine review.

ICSR-2403 remains held: its nullification has no reason, and the later envelope also uses an unpermitted terminology version, so neither changes the durable case. ICSR-2405 remains held because the patient identity does not match the durable case key. ICSR-2406 is preserved at V1 because its inbound payload is duplicate content. The unknown ICSR-9999 delivery was ignored.

Verification closed the exact case, report-version, receipt, submission, journal, and revision state. The local review packet and manifest are bound to the normalized plan and source checkpoint by SHA-256 hashes, as is the recovery receipt. The equivalent plan changed array order and locator spelling; semantic replay left the database, packet, manifest, and receipt byte stable. A conflicting ICSR-2405 action was rejected with a non-zero exit, and recorded before/after hashes prove no mutation.

This is local review staging only. There was no transmission of any safety report, no acknowledgement, no regulator or sponsor notification, no patient or reporter contact, and no external safety-system update. A human safety reviewer must resolve holds and approve any later regulated action.
""",
            encoding="utf-8",
        )
        if REFERENCE.exists():
            shutil.rmtree(REFERENCE)
        shutil.copytree(workspace, REFERENCE)
        (REFERENCE / "pvctl.py").unlink()
        shutil.rmtree(REFERENCE / "policy")
        shutil.rmtree(REFERENCE / "evidence")
        shutil.rmtree(REFERENCE / "__pycache__", ignore_errors=True)
        for path in REFERENCE.rglob("*"):
            if path.is_file():
                path.chmod(0o644)


if __name__ == "__main__":
    main()
