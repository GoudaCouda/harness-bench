from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path


def test_degree_controller_validate_finalize_verify_retry(tmp_path: Path) -> None:
    task = Path(__file__).resolve().parents[2]
    root = tmp_path / "workspace"
    shutil.copytree(task / "workspace", root)
    shutil.copy2(task / "tests/reference/degree_plan.json", root / "degree_plan.json")
    commands = [
        [sys.executable, "degreectl.py", "validate", "degree_plan.json"],
        [sys.executable, "degreectl.py", "finalize", "degree_plan.json"],
        [sys.executable, "degreectl.py", "verify"],
        [sys.executable, "degreectl.py", "finalize", "degree_plan.json"],
    ]
    output = [
        subprocess.run(
            command, cwd=root, check=True, capture_output=True, text=True
        ).stdout
        for command in commands
    ]
    assert '"status": "pass"' in output[0]
    assert '"status": "finalized"' in output[1]
    assert '"status": "pass"' in output[2]
    assert '"status": "idempotent"' in output[3]


def test_degree_controller_accepts_grounded_equivalent_course_labels(
    tmp_path: Path,
) -> None:
    task = Path(__file__).resolve().parents[2]
    root = tmp_path / "workspace"
    shutil.copytree(task / "workspace", root)
    value = json.loads(
        (task / "tests/reference/degree_plan.json").read_text(encoding="utf-8")
    )
    rows = {row["requirement"]: row for row in value["requirements"]}
    rows["statistics"]["applied_course"] = "STAT-200 satisfied by STAT-210 equivalency"
    rows["statistics"]["evidence_ids"] = ["STAT-210", "current equivalency"]
    rows["ethics"]["applied_course"] = "ETH-200 through HUM-110 substitution SUB-7"
    rows["ethics"]["evidence_ids"] = ["HUM-110", "approved SUB-7"]
    (root / "equivalent_plan.json").write_text(
        json.dumps(value, indent=2) + "\n", encoding="utf-8"
    )
    completed = subprocess.run(
        [sys.executable, "degreectl.py", "validate", "equivalent_plan.json"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    assert '"status": "pass"' in completed.stdout


def test_degree_controller_accepts_source_target_relation_representation(
    tmp_path: Path,
) -> None:
    task = Path(__file__).resolve().parents[2]
    root = tmp_path / "workspace"
    shutil.copytree(task / "workspace", root)
    value = json.loads(
        (task / "tests/reference/degree_plan.json").read_text(encoding="utf-8")
    )
    rows = value.pop("requirements")
    value["plan"] = rows
    by_id = {row["requirement"]: row for row in rows}
    for requirement in ("core_intro", "core_data", "math"):
        by_id[requirement]["evidence_ids"] = []
    by_id["statistics"].update(
        {"applied_course": "STAT-210", "evidence_ids": ["STAT-200"]}
    )
    by_id["ethics"].update({"applied_course": "HUM-110", "evidence_ids": ["SUB-7"]})
    by_id["capstone"].update({"status": "unsatisfied", "evidence_ids": []})
    (root / "source_target_plan.json").write_text(
        json.dumps(value, indent=2) + "\n", encoding="utf-8"
    )
    completed = subprocess.run(
        [sys.executable, "degreectl.py", "validate", "source_target_plan.json"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    assert '"status": "pass"' in completed.stdout
