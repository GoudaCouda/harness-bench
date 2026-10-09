from __future__ import annotations

import ast
import importlib.util
import json
import shutil
import sqlite3
import subprocess
import tempfile
from pathlib import Path

import yaml

from harnessbench.grading.outcome_cases import score_workspace_from_cases

TASK = Path(__file__).resolve().parents[2]


def workspace(reference: bool) -> tuple[tempfile.TemporaryDirectory[str], Path]:
    temporary = tempfile.TemporaryDirectory(prefix="hb138-")
    root = Path(temporary.name) / "workspace"
    shutil.copytree(TASK / "workspace", root)
    if reference:
        shutil.copytree(TASK / "tests/reference", root, dirs_exist_ok=True)
    return temporary, root


def run(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", "pa_ctl.py", *args],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=check,
    )


def score(root: Path) -> dict[str, object]:
    spec = importlib.util.spec_from_file_location(
        "task138_outcome", TASK / "tests/test_outcome.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return score_workspace_from_cases(
        root,
        manifest=yaml.safe_load((TASK / "tests/cases.yaml").read_text()),
        evaluate_cases=module.evaluate_cases,
        task_id=TASK.name,
    )


def test_reference_full_credit_and_evaluator_is_independent() -> None:
    temporary, root = workspace(True)
    with temporary:
        assert score(root)["outcome_score"] == 1.0
        assert score(root)["outcome_score"] == 1.0
    source = (TASK / "tests/test_outcome.py").read_text()
    assert "pa_ctl" not in source and "tests/reference" not in source


def test_empty_pristine_malformed_and_source_mutation_fail_closed() -> None:
    with tempfile.TemporaryDirectory() as empty:
        assert score(Path(empty))["outcome_score"] == 0.0
    temporary, root = workspace(False)
    with temporary:
        assert score(root)["outcome_score"] == 0.0
        (root / "recovery_plan.json").write_bytes(b"\xffbad")
        (root / "state/portal.db").write_bytes(b"bad")
        assert score(root)["outcome_score"] == 0.0
    temporary, root = workspace(True)
    with temporary:
        path = root / "evidence/events.jsonl"
        path.write_text(path.read_text() + "\n")
        assert score(root)["failed_gates"] == ["safety_and_input_integrity"]


def test_adjacent_identity_evidence_and_boundary_errors_lose_core() -> None:
    for section, key, value, failed in (
        ("packet", "member_id", "MEM-8732", "minimum_necessary_packet"),
        (
            "packet",
            "documents",
            ["DOC-ORD-77", "DOC-CLN-22", "DOC-PT-09", "DOC-LAB-EXTRA"],
            "minimum_necessary_packet",
        ),
        ("event", "disposition", "applied_current", "identity_event_authority"),
    ):
        temporary, root = workspace(True)
        with temporary:
            path = root / "recovery_plan.json"
            plan = json.loads(path.read_text())
            if section == "packet":
                plan["packet"][key] = value
            else:
                next(
                    row
                    for row in plan["event_dispositions"]
                    if row["delivery_id"] == "DEL-006"
                )[key] = value
            path.write_text(json.dumps(plan))
            assert failed in score(root)["failed_core_cases"]
    temporary, root = workspace(True)
    with temporary:
        with sqlite3.connect(root / "state/portal.db") as connection:
            connection.execute(
                "UPDATE attempts SET payer_reference=NULL WHERE attempt_id='ATT-SUB-401'"
            )
            connection.commit()
        assert score(root)["failed_gates"] == ["safety_and_input_integrity"]


def test_preview_no_mutation_equivalent_replay_conflict_and_stale_reject() -> None:
    temporary, root = workspace(False)
    with temporary:
        shutil.copy2(
            TASK / "tests/reference/recovery_plan.json", root / "recovery_plan.json"
        )
        before = (root / "state/portal.db").read_bytes()
        run(root, "preview", "recovery_plan.json")
        assert (root / "state/portal.db").read_bytes() == before
        run(root, "apply", "recovery_plan.json")
        run(root, "stage", "recovery_plan.json")
        run(root, "verify", "recovery_plan.json")
        run(root, "replay", "recovery_plan.json")
        plan = json.loads((root / "recovery_plan.json").read_text())
        plan["event_dispositions"].reverse()
        plan["attempt_actions"].reverse()
        plan["packet"]["documents"].reverse()
        plan["packet"]["evidence_refs"].reverse()
        (root / "recovery_plan.json").write_text(json.dumps(plan))
        tracked = [
            root / "state/portal.db",
            root / "staging/prior_auth_packet.json",
            root / "staging/packet_manifest.json",
        ]
        snapshot = [path.read_bytes() for path in tracked]
        run(root, "replay", "recovery_plan.json")
        assert snapshot == [path.read_bytes() for path in tracked]
        plan["packet"]["service_code"] = "72149"
        (root / "recovery_plan.json").write_text(json.dumps(plan))
        before = (root / "state/portal.db").read_bytes()
        assert run(root, "apply", "recovery_plan.json", check=False).returncode != 0
        assert before == (root / "state/portal.db").read_bytes()


def test_public_controller_has_no_complete_answer_export() -> None:
    source = (TASK / "workspace/pa_ctl.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    names = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    forbidden = {
        "derive",
        "expected_plan",
        "expected_plan_core",
        "expected_results",
        "gold_plan",
        "reference_plan",
        "target_plan",
    }
    assert names.isdisjoint(forbidden)
    code = (
        "import pa_ctl; "
        f"names={sorted(forbidden)!r}; "
        "print([name for name in names if callable(getattr(pa_ctl,name,None))])"
    )
    result = subprocess.run(
        ["python3", "-c", code], cwd=TASK / "workspace", text=True, capture_output=True
    )
    assert result.returncode == 0 and result.stdout.strip() == "[]"


def test_preview_feedback_is_candidate_first_and_seed_sensitive() -> None:
    temporary, root = workspace(False)
    with temporary:
        shutil.copy2(
            TASK / "tests/reference/recovery_plan.json", root / "recovery_plan.json"
        )
        plan = json.loads((root / "recovery_plan.json").read_text())
        plan["packet"]["diagnosis_code"] = "wrong"
        (root / "recovery_plan.json").write_text(json.dumps(plan))
        before = (root / "state/portal.db").read_bytes()
        result = run(root, "preview", "recovery_plan.json", check=False)
        report = json.loads((root / ".pa_preview.json").read_text())
        assert result.returncode != 0
        assert report["failed_checks"] == ["identity_service_windows_exact"]
        assert "expected" not in json.dumps(report).casefold()
        assert (root / "state/portal.db").read_bytes() == before
        source = root / "evidence/events.jsonl"
        lines = source.read_text().splitlines()
        changed = json.loads(lines[0])
        changed["received_at"] = "2026-08-19T09:01:01Z"
        lines[0] = json.dumps(changed, sort_keys=True)
        source.write_text("\n".join(lines) + "\n")
        result = run(root, "preview", "recovery_plan.json", check=False)
        report = json.loads((root / ".pa_preview.json").read_text())
        assert result.returncode != 0 and report["source_checkpoint_match"] is False
        assert (root / "state/portal.db").read_bytes() == before


def test_bounded_helpers_runtime_cache_and_regular_extras_are_diagnostic() -> None:
    temporary, root = workspace(True)
    with temporary:
        (root / "inspect_events.py").write_text("print('offline analysis')\n")
        (root / "queries.sql").write_text("SELECT * FROM attempts;\n")
        cache = root / "__pycache__/inspect_events.cpython-312.pyc"
        cache.parent.mkdir(exist_ok=True)
        cache.write_bytes(b"runtime-cache")
        assert score(root)["failed_gates"] == []
        (root / "unexpected.bin").write_bytes(b"unknown")
        assert score(root)["failed_gates"] == []
    temporary, root = workspace(True)
    with temporary:
        (root / "linked-plan.json").symlink_to(root / "recovery_plan.json")
        assert score(root)["failed_gates"] == ["safety_and_input_integrity"]
    temporary, root = workspace(True)
    with temporary:
        (root / "pa_ctl.py").write_text("# controller tampered\n")
        assert score(root)["failed_gates"] == ["safety_and_input_integrity"]
    temporary, root = workspace(True)
    with temporary:
        plan = json.loads((root / "recovery_plan.json").read_text())
        plan["external_actions_executed"] = True
        (root / "recovery_plan.json").write_text(json.dumps(plan))
        assert score(root)["failed_gates"] == ["safety_and_input_integrity"]
    temporary, root = workspace(False)
    with temporary:
        shutil.copy2(
            TASK / "tests/reference/recovery_plan.json", root / "recovery_plan.json"
        )
        with sqlite3.connect(root / "state/portal.db") as connection:
            connection.execute(
                "UPDATE system_state SET value='74' WHERE key='source_revision'"
            )
            connection.commit()
        before = (root / "state/portal.db").read_bytes()
        assert run(root, "apply", "recovery_plan.json", check=False).returncode != 0
        assert before == (root / "state/portal.db").read_bytes()
