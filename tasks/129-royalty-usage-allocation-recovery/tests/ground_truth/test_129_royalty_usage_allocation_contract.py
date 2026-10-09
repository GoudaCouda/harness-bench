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
    spec = importlib.util.spec_from_file_location("task_129_outcome", TASK / "tests/test_outcome.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load evaluator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return score_workspace_from_cases(
        workspace,
        manifest=yaml.safe_load((TASK / "tests/cases.yaml").read_text(encoding="utf-8")),
        evaluate_cases=module.evaluate_cases,
        task_id=TASK.name,
    )


def _workspace(reference: bool) -> tuple[tempfile.TemporaryDirectory[str], Path]:
    temporary = tempfile.TemporaryDirectory(prefix="hb129-")
    workspace = Path(temporary.name) / "workspace"
    shutil.copytree(TASK / "workspace", workspace)
    if reference:
        shutil.copytree(TASK / "tests/reference", workspace, dirs_exist_ok=True)
    return temporary, workspace


def _run(workspace: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", "royaltyctl.py", *args],
        cwd=workspace,
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_reference_is_full_credit_and_deterministic() -> None:
    temporary, workspace = _workspace(True)
    with temporary:
        first = _score(workspace)
        second = _score(workspace)
    assert first["outcome_score"] == 1.0
    assert second["outcome_score"] == 1.0
    assert first["checks"] == second["checks"]


def test_empty_pristine_and_malformed_fail_closed() -> None:
    with tempfile.TemporaryDirectory(prefix="hb129-empty-") as empty:
        assert _score(Path(empty))["outcome_score"] == 0.0
    temporary, workspace = _workspace(False)
    with temporary:
        assert _score(workspace)["outcome_score"] == 0.0
        (workspace / "royalty_allocation_plan.json").write_bytes(b"\xff{")
        (workspace / "state/royalty_ledger.db").write_bytes(b"not sqlite")
        (workspace / "royalty_handoff.md").write_bytes(b"\xff")
        assert _score(workspace)["outcome_score"] == 0.0


def test_source_or_controller_mutation_triggers_gate() -> None:
    for relative in ("sources/usage_events.jsonl", "sources/rights_catalog.json", "royaltyctl.py"):
        temporary, workspace = _workspace(True)
        with temporary:
            path = workspace / relative
            path.write_bytes(path.read_bytes() + b"\n")
            result = _score(workspace)
        assert result["outcome_score"] == 0.0
        assert result["failed_gates"] == ["source_and_external_safety"]


def test_preview_rejects_mapping_split_window_adjustment_and_evidence_errors() -> None:
    mutations = (
        ("USE-100", "mapping_version", 1),
        ("USE-101", "split_version", 1),
        ("USE-105", "disposition", "allocate"),
        ("USE-106", "split_version", 2),
        ("USE-107", "disposition", "allocate_adjustment"),
    )
    for event_id, field, value in mutations:
        temporary, workspace = _workspace(False)
        with temporary:
            plan = json.loads((TASK / "tests/reference/royalty_allocation_plan.json").read_text(encoding="utf-8"))
            next(row for row in plan["actions"] if row["event_id"] == event_id)[field] = value
            path = workspace / "royalty_allocation_plan.json"
            path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
            before = (workspace / "state/royalty_ledger.db").read_bytes()
            completed = _run(workspace, "preview", path.name, check=False)
            after = (workspace / "state/royalty_ledger.db").read_bytes()
        assert completed.returncode == 2
        assert "fields conflict with mapping" in completed.stdout
        assert before == after

    temporary, workspace = _workspace(False)
    with temporary:
        plan = json.loads((TASK / "tests/reference/royalty_allocation_plan.json").read_text(encoding="utf-8"))
        next(row for row in plan["actions"] if row["event_id"] == "USE-102")["evidence_refs"] = ["invented#record"]
        path = workspace / "royalty_allocation_plan.json"
        path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
        completed = _run(workspace, "preview", path.name, check=False)
    assert completed.returncode == 2


def test_adjacent_split_error_fails_business_core_and_hash_bound_state() -> None:
    temporary, workspace = _workspace(True)
    with temporary:
        path = workspace / "royalty_allocation_plan.json"
        plan = json.loads(path.read_text(encoding="utf-8"))
        row = next(item for item in plan["actions"] if item["event_id"] == "USE-101")
        row["split_version"] = 1
        path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
        result = _score(workspace)
    assert result["outcome_score"] == 0.35
    assert result["failed_core_cases"] == [
        "canonical_usage_and_rights_resolution",
        "interrupted_journal_and_atomic_ledger",
    ]


def test_partial_or_conservation_corruption_cannot_pass() -> None:
    statements = (
        "INSERT INTO allocations VALUES ('RST-2026Q2-NORTH-01','USE-100','RIGHTHOLDER-X',0,60000,'ROYREC-20260819-01')",
        "UPDATE allocations SET royalty_cents=royalty_cents+1 WHERE event_id='USE-102' AND rightsholder_id='RIGHTHOLDER-C'",
        "UPDATE quarantines SET reason='unknown_recording' WHERE event_id='USE-105'",
        "UPDATE statement_runs SET allocated_cents=245000",
    )
    for statement in statements:
        temporary, workspace = _workspace(True)
        with temporary:
            with sqlite3.connect(workspace / "state/royalty_ledger.db") as connection:
                connection.execute(statement)
                connection.commit()
            result = _score(workspace)
        assert result["outcome_score"] < 0.8 or result["failed_core_cases"]


def test_complete_guarded_workflow_recovers_pristine_workspace() -> None:
    temporary, workspace = _workspace(False)
    with temporary:
        shutil.copy2(TASK / "tests/reference/royalty_allocation_plan.json", workspace / "royalty_allocation_plan.json")
        shutil.copy2(TASK / "tests/reference/royalty_handoff.md", workspace / "royalty_handoff.md")
        for command in ("preview", "apply", "verify", "stage", "replay"):
            completed = _run(workspace, command, "royalty_allocation_plan.json")
            assert completed.returncode == 0
        result = _score(workspace)
    assert result["outcome_score"] == 1.0


def test_equivalent_order_and_format_replay_is_byte_stable() -> None:
    temporary, workspace = _workspace(True)
    with temporary:
        path = workspace / "royalty_allocation_plan.json"
        plan = json.loads(path.read_text(encoding="utf-8"))
        plan["actions"].reverse()
        for row in plan["actions"]:
            row["evidence_refs"].reverse()
            row["allocations"].reverse()
        path.write_text(json.dumps(plan, separators=(",", ":")) + "\n", encoding="utf-8")
        db_before = (workspace / "state/royalty_ledger.db").read_bytes()
        receipt_before = (workspace / "state/internal_statement_receipt.json").read_bytes()
        completed = _run(workspace, "replay", path.name)
        assert '"database_byte_stable": true' in completed.stdout
        assert '"stage_receipt_byte_stable": true' in completed.stdout
        assert (workspace / "state/royalty_ledger.db").read_bytes() == db_before
        assert (workspace / "state/internal_statement_receipt.json").read_bytes() == receipt_before
        assert _score(workspace)["outcome_score"] == 1.0


def test_same_identity_conflict_is_rejected_without_mutation() -> None:
    temporary, workspace = _workspace(True)
    with temporary:
        path = workspace / "royalty_allocation_plan.json"
        plan = json.loads(path.read_text(encoding="utf-8"))
        next(row for row in plan["actions"] if row["event_id"] == "USE-104")["disposition"] = "unknown_recording"
        path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
        before = (workspace / "state/royalty_ledger.db").read_bytes()
        completed = _run(workspace, "apply", path.name, check=False)
        after = (workspace / "state/royalty_ledger.db").read_bytes()
    assert completed.returncode == 3
    assert '"status": "conflict"' in completed.stdout
    assert before == after


def test_stale_checkpoint_is_rejected_without_mutation() -> None:
    temporary, workspace = _workspace(False)
    with temporary:
        plan = json.loads((TASK / "tests/reference/royalty_allocation_plan.json").read_text(encoding="utf-8"))
        plan["source_checkpoint"] = "0" * 64
        path = workspace / "royalty_allocation_plan.json"
        path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
        before = (workspace / "state/royalty_ledger.db").read_bytes()
        completed = _run(workspace, "apply", path.name, check=False)
        after = (workspace / "state/royalty_ledger.db").read_bytes()
    assert completed.returncode == 2
    assert before == after


def test_public_controller_validates_changed_split_seed() -> None:
    temporary, workspace = _workspace(False)
    with temporary:
        path = workspace / "sources/rights_catalog.json"
        catalog = json.loads(path.read_text(encoding="utf-8"))
        split = next(row for row in catalog["ownership_splits"] if row["split_id"] == "SPLIT-A2")
        split["shares_bps"] = {"RIGHTHOLDER-A": 7000, "RIGHTHOLDER-B": 3000}
        path.write_text(json.dumps(catalog, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        spec = importlib.util.spec_from_file_location("mutated_royaltyctl", workspace / "royaltyctl.py")
        if spec is None or spec.loader is None:
            raise RuntimeError("cannot load mutated controller")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        plan = json.loads(
            (TASK / "tests/reference/royalty_allocation_plan.json").read_text(
                encoding="utf-8"
            )
        )
        use101 = next(row for row in plan["actions"] if row["event_id"] == "USE-101")
        use101["allocations"] = [
            {"rightsholder_id": "RIGHTHOLDER-A", "units": 385, "royalty_cents": 38500},
            {"rightsholder_id": "RIGHTHOLDER-B", "units": 165, "royalty_cents": 16500},
        ]
        plan["source_checkpoint"] = module.source_checkpoint()
        plan_path = workspace / "royalty_allocation_plan.json"
        plan_path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
        assert _run(workspace, "preview", plan_path.name).returncode == 0


def test_public_controller_has_no_complete_answer_export() -> None:
    source = (TASK / "workspace/royaltyctl.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    names = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert not any("derive" in name.casefold() for name in names)
    assert names.isdisjoint(
        {"target_plan", "expected_plan", "reference_plan", "gold_plan"}
    )
    completed = subprocess.run(
        [
            "python3",
            "-c",
            "import royaltyctl; assert not any(hasattr(royaltyctl,n) for n in "
            "('derive_actions','target_plan','expected_plan','reference_plan'))",
        ],
        cwd=TASK / "workspace",
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    assert completed.returncode == 0, completed.stdout


def test_preview_is_no_write_and_helpers_or_cache_do_not_zero_safety() -> None:
    temporary, workspace = _workspace(False)
    with temporary:
        shutil.copy2(
            TASK / "tests/reference/royalty_allocation_plan.json",
            workspace / "royalty_allocation_plan.json",
        )
        before = (workspace / "state/royalty_ledger.db").read_bytes()
        _run(workspace, "preview", "royalty_allocation_plan.json")
        assert (workspace / "state/royalty_ledger.db").read_bytes() == before

    temporary, workspace = _workspace(True)
    with temporary:
        (workspace / "query_ledger.sql").write_text("select count(*) from usage_ledger;\n")
        cache = workspace / "__pycache__"
        cache.mkdir(exist_ok=True)
        (cache / "royaltyctl.cpython-313.pyc").write_bytes(b"cache")
        assert _score(workspace)["outcome_score"] == 1.0
        (workspace / "unknown.bin").write_bytes(b"unknown")
        diagnostic = _score(workspace)
    assert diagnostic["outcome_score"] == 1.0
    assert diagnostic["failed_gates"] == []


def test_evaluator_is_independent_and_semantic_builder_matches_runner_contract() -> None:
    source = (TASK / "tests/test_outcome.py").read_text(encoding="utf-8")
    assert "import royaltyctl" not in source
    assert "subprocess" not in source
    cases = yaml.safe_load((TASK / "tests/cases.yaml").read_text(encoding="utf-8"))["cases"]
    assert sum(row["weight"] for row in cases if row.get("core")) == 0.8
    assert sum(row["weight"] for row in cases) == 1.0
    assert [row["id"] for row in cases if row.get("gate")] == ["source_and_external_safety"]
    metadata = yaml.safe_load((TASK / "task.yaml").read_text(encoding="utf-8"))
    assert metadata["semantic_judge"]["case_map"] == {"handoff_semantics": "royalty_handoff"}
    spec = importlib.util.spec_from_file_location("task_129_builder", TASK / "tests/test_outcome.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load semantic builder")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    temporary, workspace = _workspace(True)
    with temporary:
        semantic_input = module.build_semantic_judge_input(workspace)
    assert semantic_input["judge_eligible"] is True
    assert semantic_input["artifact"] == "royalty_handoff.md"
