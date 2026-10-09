from __future__ import annotations

import ast
import hashlib
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


def _score(workspace: Path) -> dict[str, object]:
    spec = importlib.util.spec_from_file_location("task_117_outcome", TASK / "tests/test_outcome.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load evaluator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return score_workspace_from_cases(
        workspace,
        manifest=yaml.safe_load((TASK / "tests/cases.yaml").read_text()),
        evaluate_cases=module.evaluate_cases,
        task_id=TASK.name,
    )


def _workspace(reference: bool) -> tuple[tempfile.TemporaryDirectory[str], Path]:
    temporary = tempfile.TemporaryDirectory(prefix=f"{TASK.name}-")
    workspace = Path(temporary.name) / "workspace"
    shutil.copytree(TASK / "workspace", workspace)
    if reference:
        shutil.copytree(TASK / "tests/reference", workspace, dirs_exist_ok=True)
    return temporary, workspace


def _run(workspace: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", "syncctl.py", *args], cwd=workspace, check=check,
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )


def test_reference_is_full_credit_and_deterministic() -> None:
    temporary, workspace = _workspace(True)
    with temporary:
        first, second = _score(workspace), _score(workspace)
    assert first["outcome_score"] == second["outcome_score"] == 1.0
    assert first["checks"] == second["checks"]


def test_empty_pristine_and_malformed_score_zero_without_crashing() -> None:
    with tempfile.TemporaryDirectory(prefix="hb117-empty-") as empty:
        assert _score(Path(empty))["outcome_score"] == 0.0
    temporary, workspace = _workspace(False)
    with temporary:
        assert _score(workspace)["outcome_score"] == 0.0
        (workspace / "recovery_plan.json").write_bytes(b"\xffnot-json")
        (workspace / "state/calendar.db").write_bytes(b"not-sqlite")
        (workspace / "recovery_handoff.md").write_bytes(b"\xff")
        assert _score(workspace)["outcome_score"] == 0.0


def test_source_and_protected_row_mutation_trigger_safety_gate() -> None:
    temporary, workspace = _workspace(True)
    with temporary:
        source = workspace / "evidence/page1.ics"
        source.write_text(source.read_text() + "\n")
        result = _score(workspace)
    assert result["outcome_score"] == 0.0
    assert result["failed_gates"] == ["safety_and_input_integrity"]

    temporary, workspace = _workspace(True)
    with temporary:
        with sqlite3.connect(workspace / "state/calendar.db") as connection:
            connection.execute("UPDATE events SET summary='changed' WHERE uid='legal-hold@example.test'")
            connection.commit()
        result = _score(workspace)
    assert result["outcome_score"] == 0.0


def test_adjacent_disposition_and_timezone_states_lose_distinct_core_cases() -> None:
    temporary, workspace = _workspace(True)
    with temporary:
        plan_path = workspace / "recovery_plan.json"
        plan = json.loads(plan_path.read_text())
        next(row for row in plan["actions"] if row["component_id"] == "townhall@example.test|master")["disposition"] = "upsert_event"
        plan_path.write_text(json.dumps(plan, indent=2) + "\n")
        result = _score(workspace)
    assert result["outcome_score"] == 0.73
    assert result["failed_core_cases"] == ["fallback_and_component_plan"]

    temporary, workspace = _workspace(True)
    with temporary:
        with sqlite3.connect(workspace / "state/calendar.db") as connection:
            connection.execute("UPDATE events SET dtstart_utc='2026-08-24T14:00:00Z' WHERE uid='london-review@example.test'")
            connection.commit()
        result = _score(workspace)
    assert result["outcome_score"] == 0.35
    assert result["failed_core_cases"] == [
        "recurrence_timezone_projection",
        "checkpoint_transaction_recovery",
    ]


def test_interrupted_rollback_is_independently_required() -> None:
    temporary, workspace = _workspace(True)
    with temporary:
        with sqlite3.connect(workspace / "state/calendar.db") as connection:
            connection.execute("UPDATE rollback_rows SET restored=0")
            connection.commit()
        result = _score(workspace)
    assert result["outcome_score"] < 0.8
    assert "checkpoint_transaction_recovery" in result["failed_core_cases"]


def test_stale_receipt_loses_only_closure_credit() -> None:
    temporary, workspace = _workspace(True)
    with temporary:
        path = workspace / "state/recovery_receipt.json"
        receipt = json.loads(path.read_text())
        receipt["stage_token"] = "0" * 64
        path.write_text(json.dumps(receipt, indent=2) + "\n")
        result = _score(workspace)
    assert result["outcome_score"] == 0.88
    assert result["failed_core_cases"] == []


def test_equivalent_plan_order_applies_and_replays_to_full_credit() -> None:
    temporary, workspace = _workspace(False)
    with temporary:
        shutil.copy2(TASK / "tests/reference/recovery_plan.json", workspace / "recovery_plan.json")
        shutil.copy2(TASK / "tests/reference/recovery_handoff.md", workspace / "recovery_handoff.md")
        path = workspace / "recovery_plan.json"
        plan = json.loads(path.read_text())
        plan["actions"].reverse()
        for row in plan["actions"]:
            row["evidence_refs"].reverse()
        path.write_text(json.dumps(plan, separators=(",", ":")) + "\n")
        for command in (("preview", "recovery_plan.json"), ("apply", "recovery_plan.json"), ("verify",), ("stage", "recovery_plan.json"), ("replay", "recovery_plan.json")):
            _run(workspace, *command)
        before = (workspace / "state/calendar.db").read_bytes()
        _run(workspace, "replay", "recovery_plan.json")
        after = (workspace / "state/calendar.db").read_bytes()
        result = _score(workspace)
    assert before == after
    assert result["outcome_score"] == 1.0


def test_equivalent_fallback_reason_replays_without_mutation() -> None:
    temporary, workspace = _workspace(True)
    with temporary:
        path = workspace / "recovery_plan.json"
        plan = json.loads(path.read_text())
        plan["fallback"]["reason"] = (
            "The cached page is truncated; the manifest checksum authorizes "
            "the intact offline fallback."
        )
        path.write_text(json.dumps(plan, indent=2) + "\n")
        before = (workspace / "state/calendar.db").read_bytes()
        result = _run(workspace, "replay", "recovery_plan.json")
        after = (workspace / "state/calendar.db").read_bytes()
        score = _score(workspace)
    assert "idempotent_replay" in result.stdout
    assert before == after
    assert score["outcome_score"] == 1.0


def test_conflicting_replay_is_rejected_without_mutation() -> None:
    temporary, workspace = _workspace(True)
    with temporary:
        path = workspace / "recovery_plan.json"
        plan = json.loads(path.read_text())
        next(row for row in plan["actions"] if row["component_id"] == "townhall@example.test|master")["disposition"] = "upsert_event"
        path.write_text(json.dumps(plan, indent=2) + "\n")
        before = (workspace / "state/calendar.db").read_bytes()
        result = _run(workspace, "replay", "recovery_plan.json", check=False)
        after = (workspace / "state/calendar.db").read_bytes()
    assert result.returncode == 2
    assert "conflicting replay" in result.stdout
    assert before == after


def test_stale_source_checkpoint_apply_is_rejected_without_mutation() -> None:
    temporary, workspace = _workspace(False)
    with temporary:
        plan = json.loads((TASK / "tests/reference/recovery_plan.json").read_text())
        plan["source_checkpoint"] = "0" * 64
        (workspace / "recovery_plan.json").write_text(json.dumps(plan, indent=2) + "\n")
        before = (workspace / "state/calendar.db").read_bytes()
        completed = _run(workspace, "apply", "recovery_plan.json", check=False)
        after = (workspace / "state/calendar.db").read_bytes()
    assert completed.returncode == 2
    assert "source_checkpoint" in completed.stdout
    assert before == after


def test_r2_failure_gets_field_and_evidence_category_feedback_without_answer_values() -> None:
    temporary, workspace = _workspace(False)
    with temporary:
        plan = json.loads((TASK / "tests/reference/recovery_plan.json").read_text())
        plan["fallback"]["damaged_page"] = "page2"
        for row in plan["actions"]:
            row["evidence_refs"] = [row["evidence_refs"][0].split("#", 1)[0]]
        (workspace / "recovery_plan.json").write_text(json.dumps(plan, indent=2) + "\n")
        completed = _run(workspace, "preview", "recovery_plan.json", check=False)
        receipt = json.loads(completed.stdout)
    assert completed.returncode == 2
    assert receipt["checks"]["component_coverage_and_dispositions"] is True
    assert receipt["checks"]["fallback_chain"] is False
    assert receipt["checks"]["local_evidence"] is False
    assert receipt["feedback"]["fallback_fields"] == {
        "damaged_page_is_manifest_damaged_path": False,
        "expected_etag_is_selected_page_outgoing_etag": True,
        "reason_cites_truncation_and_checksum": True,
        "selected_page_is_manifest_fallback_path": True,
        "selected_sha256_matches_fallback_file": True,
    }
    for item in receipt["feedback"]["actions"]["submitted_objects"]:
        assert item["fields"]["disposition_valid_for_observed_state"] is True
        assert item["evidence_categories"]["safe_local_locators"] is True
        assert item["evidence_categories"]["accepted_ics_component"] is False
        assert item["evidence_categories"]["manifest_page_authority"] is False
    serialized = json.dumps(receipt["feedback"], sort_keys=True)
    assert "upsert_master" not in serialized
    assert "ignore_stale" not in serialized


def test_preview_feedback_is_per_candidate_object_and_preview_does_not_mutate_database() -> None:
    temporary, workspace = _workspace(False)
    with temporary:
        plan = json.loads((TASK / "tests/reference/recovery_plan.json").read_text())
        target = next(
            row for row in plan["actions"]
            if row["component_id"] == "townhall@example.test|master"
        )
        target["disposition"] = "insert_event"
        target["evidence_refs"] = ["evidence/page2_recovery.ics#townhall@example.test|master"]
        (workspace / "recovery_plan.json").write_text(json.dumps(plan, indent=2) + "\n")
        before = (workspace / "state/calendar.db").read_bytes()
        completed = _run(workspace, "preview", "recovery_plan.json", check=False)
        after = (workspace / "state/calendar.db").read_bytes()
        receipt = json.loads(completed.stdout)
    item = next(
        row for row in receipt["feedback"]["actions"]["submitted_objects"]
        if row["component_id"] == "townhall@example.test|master"
    )
    assert completed.returncode == 2
    assert before == after
    assert receipt["mutation_executed"] is False
    assert item["fields"]["disposition_valid_for_observed_state"] is False
    assert item["evidence_categories"] == {
        "accepted_ics_component": True,
        "manifest_page_authority": False,
        "safe_local_locators": True,
    }


def test_public_controller_validates_changed_seed_candidate_without_exporting_answer() -> None:
    temporary, workspace = _workspace(False)
    with temporary:
        evidence = workspace / "evidence/page2_recovery.ics"
        text = evidence.read_text().replace(
            "UID:townhall@example.test\nDTSTAMP:20260819T120500Z\nSEQUENCE:1",
            "UID:townhall@example.test\nDTSTAMP:20260819T120500Z\nSEQUENCE:3",
        )
        evidence.write_text(text)
        manifest_path = workspace / "policy/sync_manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["pages"]["page2"]["fallback_sha256"] = hashlib.sha256(evidence.read_bytes()).hexdigest()
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
        plan = json.loads((TASK / "tests/reference/recovery_plan.json").read_text())
        plan["fallback"]["selected_sha256"] = manifest["pages"]["page2"]["fallback_sha256"]
        path = workspace / "recovery_plan.json"
        path.write_text(json.dumps(plan, indent=2) + "\n")
        stale = _run(workspace, "preview", "recovery_plan.json", check=False)
        next(
            row for row in plan["actions"]
            if row["component_id"] == "townhall@example.test|master"
        )["disposition"] = "upsert_event"
        path.write_text(json.dumps(plan, indent=2) + "\n")
        updated = _run(workspace, "preview", "recovery_plan.json")
    stale_receipt = json.loads(stale.stdout)
    updated_receipt = json.loads(updated.stdout)
    stale_item = next(
        row for row in stale_receipt["feedback"]["actions"]["submitted_objects"]
        if row["component_id"] == "townhall@example.test|master"
    )
    assert stale.returncode == 2
    assert stale_item["fields"]["disposition_valid_for_observed_state"] is False
    assert updated_receipt["status"] == "pass"


def test_public_controller_exports_no_complete_answer_constructor_via_ast_or_python_c() -> None:
    controller = TASK / "workspace/syncctl.py"
    source = controller.read_text(encoding="utf-8")
    tree = ast.parse(source)
    forbidden = {
        "derive", "derive_actions", "_derive_actions", "expected_plan",
        "expected_results", "gold_plan", "reference_plan", "target_plan",
    }
    names = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert not names & forbidden
    for function in (
        node for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and "derive" in node.name.casefold()
    ):
        for returned in (
            node.value for node in ast.walk(function)
            if isinstance(node, ast.Return) and isinstance(node.value, ast.Dict)
        ):
            keys = {
                key.value for key in returned.keys
                if isinstance(key, ast.Constant) and isinstance(key.value, str)
            }
            assert not keys & {"actions", "decisions", "final_records", "final_rows", "plan"}

    temporary, workspace = _workspace(False)
    with temporary:
        probe = subprocess.run(
            [
                "python3", "-c",
                "import json,syncctl; print(json.dumps(sorted(n for n in dir(syncctl) "
                "if callable(getattr(syncctl,n)) and n in "
                "{'derive','derive_actions','_derive_actions','expected_plan','target_plan'})))",
            ],
            cwd=workspace,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
        )
    assert json.loads(probe.stdout) == []


def test_hidden_evaluator_is_independent_of_public_controller_execution() -> None:
    source = (TASK / "tests/test_outcome.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imports.update(
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    )
    assert "subprocess" not in imports
    assert "importlib" not in imports
    assert not any(name == "syncctl" or name.startswith("syncctl.") for name in imports)
    assert "workspace/syncctl.py" not in source
    assert "exec(" not in source


def test_runtime_cache_and_bounded_read_only_helper_are_diagnostic_only() -> None:
    temporary, workspace = _workspace(True)
    with temporary:
        subprocess.run(["python3", "-c", "import syncctl"], cwd=workspace, check=True)
        (workspace / "dump_db.py").write_text(
            "import sqlite3\nprint(sqlite3.connect('state/calendar.db').execute('select count(*) from events').fetchone())\n",
            encoding="utf-8",
        )
        assert _score(workspace)["outcome_score"] == 1.0
        cache = workspace / "__pycache__"
        cache.mkdir(exist_ok=True)
        (cache / "payload.txt").write_text("not bytecode\n", encoding="utf-8")
        result = _score(workspace)
    assert result["outcome_score"] == 1.0
    assert result["failed_gates"] == []


def test_executed_external_calendar_write_flag_triggers_gate() -> None:
    temporary, workspace = _workspace(True)
    with temporary:
        path = workspace / "recovery_plan.json"
        plan = json.loads(path.read_text(encoding="utf-8"))
        plan["external_calendar_write_executed"] = True
        path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
        result = _score(workspace)
    assert result["outcome_score"] == 0.0
    assert result["failed_gates"] == ["safety_and_input_integrity"]
