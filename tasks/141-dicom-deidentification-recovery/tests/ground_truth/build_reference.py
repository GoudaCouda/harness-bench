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

TASK = Path(__file__).resolve().parents[2]
STATIC = TASK / "workspace"
GROUND = TASK / "tests/ground_truth/ground_truth.json"
REFERENCE = TASK / "tests/reference"


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def run(workspace: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["python3", "dicomctl.py", *args], cwd=workspace, text=True, capture_output=True, check=check)


HANDOFF = """# DICOM de-identification recovery handoff

## Delivery authority and quarantine

The nine-delivery queue was adjudicated by first SOP Instance UID authority, not file name or date. DEL-02 CT-141-A, DEL-07 SEG-141-A, and DEL-04 MR-141-B were eligible and generated locally. DEL-04-RETRY was an exact duplicate redelivery and was ignored. DEL-05 reused the MR SOP UID with different content and was quarantined as a collision. DEL-03 was quarantined because BurnedInAnnotation was YES, so removing metadata alone could not address pixel text. DEL-06 was an unsupported encapsulated document. DEL-09 belonged to an unknown study. DEL-08 was ignored at the already-exported protected study boundary; its protected export was preserved.

## Transformation and referential integrity

Direct identifier tags PatientName, PatientBirthDate, AccessionNumber, InstitutionName, and ReferringPhysicianName were removed. PatientID was replaced by the study pseudonym. Non-allowlisted private tag 0043,1029 was removed while approved calibration tag 0019,1001 remained. Study and acquisition dates shifted by -37 days for PAT-A and +62 days for PAT-B. Study, series, SOP, and referenced SOP UIDs were remapped under namespace 2.25. The SEG reference resolves to the remapped CT SOP UID; it was not invented or left clinical.

## Recovery, verification, and local boundary

The J-DICOM-141 before-image journal was restored, the partial export record was rolled back, and PHI-bearing orphan INTERRUPTED-141.dcm was replaced by a non-PHI rollback tombstone before one local projection committed. Independent verification reparsed all three emitted DICOM datasets and confirmed identifier removal, date shifts, private-tag policy, UID graph, file hashes, and the protected boundary. The local research review packet and packet manifest bind the checkpoint, generated instances, quarantine set, handoff, and artifact hashes.

An array- and evidence-order-equivalent plan replayed as a semantic no-op with the SQLite database and export tree unchanged. A conflict probe changed DEL-03's quarantine reason; apply rejected it with a non-zero exit and unchanged database and export-tree hashes. Nothing was uploaded, transmitted, published, sent to PACS, or sent to a research repository. No patient was contacted, no clinical system was updated, and no source study was deleted.
"""


def build() -> None:
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location("dicomctl_fixture", STATIC / "dicomctl.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # Reference construction consumes grader-only truth.  The public controller
    # deliberately exposes no callable full-plan constructor.
    plan = json.loads(GROUND.read_text(encoding="utf-8"))["plan"]
    protected_before = (STATIC / "exports/protected/PROTECTED-141.dcm").read_bytes()
    with tempfile.TemporaryDirectory() as td:
        workspace = Path(td) / "workspace"
        shutil.copytree(STATIC, workspace, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        (workspace / "deid_plan.json").write_bytes(canonical(plan))
        run(workspace, "preview", "deid_plan.json")
        run(workspace, "apply", "deid_plan.json")
        run(workspace, "verify", "deid_plan.json")
        (workspace / "deid_handoff.md").write_text(HANDOFF, encoding="utf-8")
        run(workspace, "stage", "deid_plan.json")
        equivalent = dict(plan)
        equivalent["delivery_dispositions"] = list(reversed(plan["delivery_dispositions"]))
        equivalent["instance_decisions"] = [dict(row, evidence_refs=list(reversed(row["evidence_refs"]))) for row in reversed(plan["instance_decisions"])]
        equivalent["uid_map"] = list(reversed(plan["uid_map"]))
        (workspace / "equivalent_deid_plan.json").write_bytes(canonical(equivalent))
        run(workspace, "replay", "equivalent_deid_plan.json")
        conflict = json.loads(json.dumps(plan))
        target = next(row for row in conflict["instance_decisions"] if row["delivery_id"] == "DEL-03")
        target["reason"] = "metadata_only_remediation"
        (workspace / "conflict_deid_plan.json").write_bytes(canonical(conflict))
        db_before = digest((workspace / "state/imaging.db").read_bytes())
        exports_before = module.digest(module.canonical([]))
        payload = [(p.relative_to(workspace).as_posix(), digest(p.read_bytes())) for p in sorted((workspace / "exports").rglob("*")) if p.is_file()]
        exports_before = digest(canonical(payload))
        result = run(workspace, "apply", "conflict_deid_plan.json", check=False)
        payload_after = [(p.relative_to(workspace).as_posix(), digest(p.read_bytes())) for p in sorted((workspace / "exports").rglob("*")) if p.is_file()]
        probe = {
            "schema_version": 1,
            "command": "python3 dicomctl.py apply conflict_deid_plan.json",
            "exit_code": result.returncode,
            "changed_field": "instance_decisions[DEL-03].reason",
            "database_sha256_before": db_before,
            "database_sha256_after": digest((workspace / "state/imaging.db").read_bytes()),
            "export_tree_sha256_before": exports_before,
            "export_tree_sha256_after": digest(canonical(payload_after)),
            "rejected_without_mutation": result.returncode != 0 and db_before == digest((workspace / "state/imaging.db").read_bytes()) and exports_before == digest(canonical(payload_after)),
        }
        (workspace / "conflict_probe.json").write_bytes(canonical(probe))

        if REFERENCE.exists():
            shutil.rmtree(REFERENCE)
        shutil.copytree(workspace, REFERENCE)
        with sqlite3.connect(workspace / "state/imaging.db") as con:
            con.row_factory = sqlite3.Row
            export_rows = [dict(row) for row in con.execute("SELECT * FROM export_records ORDER BY sop_instance_uid")]
            runs = [dict(row) for row in con.execute("SELECT * FROM recovery_runs ORDER BY recovery_id")]
            journals = [dict(row) for row in con.execute("SELECT * FROM recovery_journal ORDER BY journal_id")]
            studies = [dict(row) for row in con.execute("SELECT * FROM studies ORDER BY study_instance_uid")]
        truth = {
            "plan": plan,
            "export_records": export_rows,
            "recovery_runs": runs,
            "recovery_journal": journals,
            "studies": studies,
            "protected_sha256": digest(protected_before),
            "orphan_dataset": json.loads((workspace / "exports/orphan/INTERRUPTED-141.dcm").read_bytes()[132:]),
            "output_datasets": {row["output_relpath"]: json.loads((workspace / row["output_relpath"]).read_bytes()[132:]) for row in plan["instance_decisions"] if row["output_relpath"]},
        }
        GROUND.write_text(json.dumps(truth, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    build()
