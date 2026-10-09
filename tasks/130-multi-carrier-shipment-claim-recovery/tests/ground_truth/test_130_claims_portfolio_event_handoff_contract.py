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


def _canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _score(workspace: Path) -> dict[str, object]:
    spec = importlib.util.spec_from_file_location("task_130_outcome", TASK / "tests/test_outcome.py")
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
    temporary = tempfile.TemporaryDirectory(prefix="hb130-")
    workspace = Path(temporary.name) / "workspace"
    shutil.copytree(TASK / "workspace", workspace)
    if reference:
        shutil.copytree(TASK / "tests/reference", workspace, dirs_exist_ok=True)
    return temporary, workspace


def _run(workspace: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", "claimsctl.py", *args], cwd=workspace, check=check,
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )


def test_reference_is_full_credit_and_deterministic() -> None:
    temporary, workspace = _workspace(True)
    with temporary:
        first = _score(workspace)
        second = _score(workspace)
    assert first["outcome_score"] == 1.0
    assert second["outcome_score"] == 1.0
    assert first["checks"] == second["checks"]


def test_reference_packet_prioritizes_denial_deadline_before_ready_claims() -> None:
    bundle = json.loads(
        (TASK / "tests/reference/staging/claim_packet_bundle.json").read_text(encoding="utf-8")
    )
    assert [row["case_id"] for row in bundle["packet_items"]] == [
        "CL-F1", "CL-A1", "CL-B1", "CL-C1"
    ]
    assert bundle["packet_items"][0]["packet_type"] == "denial_response"
    assert bundle["packet_items"][0]["response_deadline"] == "2026-08-24"


def test_empty_pristine_and_malformed_fail_closed() -> None:
    with tempfile.TemporaryDirectory(prefix="hb130-empty-") as empty:
        assert _score(Path(empty))["outcome_score"] == 0.0
    temporary, workspace = _workspace(False)
    with temporary:
        assert _score(workspace)["outcome_score"] == 0.0
        (workspace / "recovery_plan.json").write_bytes(b"\xffnot-json")
        (workspace / "state/claims.db").write_bytes(b"not-sqlite")
        (workspace / "claims_handoff.md").write_bytes(b"\xff")
        assert _score(workspace)["outcome_score"] == 0.0


def test_source_mutation_and_external_action_claim_trigger_gate() -> None:
    temporary, workspace = _workspace(True)
    with temporary:
        source = workspace / "evidence/carrier_events.jsonl"
        source.write_text(source.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        result = _score(workspace)
    assert result["outcome_score"] == 0.0
    assert result["failed_gates"] == ["safety_and_input_integrity"]

    temporary, workspace = _workspace(True)
    with temporary:
        handoff = workspace / "claims_handoff.md"
        handoff.write_text(
            handoff.read_text(encoding="utf-8") + "\nOur team submitted the claim and contacted the carrier.\n",
            encoding="utf-8",
        )
        result = _score(workspace)
    assert result["outcome_score"] == 0.0
    assert result["failed_gates"] == ["safety_and_input_integrity"]


def test_amount_and_evidence_adjacent_errors_lose_authority_core() -> None:
    for case_id, field, value in (
        ("CL-B1", "locally_allowed_amount_cents", 50000),
        ("CL-D1", "locally_allowed_amount_cents", 70000),
        ("CL-C1", "evidence_refs", ["state/claims.db#claim_lines:LN-C1-S"]),
    ):
        temporary, workspace = _workspace(True)
        with temporary:
            path = workspace / "recovery_plan.json"
            plan = json.loads(path.read_text(encoding="utf-8"))
            next(row for row in plan["decisions"] if row["case_id"] == case_id)[field] = value
            path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
            result = _score(workspace)
        assert result["outcome_score"] == 0.8
        assert result["failed_core_cases"] == ["claim_evidence_and_amounts"]


def test_survivor_deadline_state_and_event_errors_lose_event_core() -> None:
    mutations = (
        ("CL-A2", "survivor_case_id", "CL-A2"),
        ("CL-F1", "response_deadline", "2026-08-25"),
        ("CL-E1", "final_state", "submitted"),
    )
    for case_id, field, value in mutations:
        temporary, workspace = _workspace(True)
        with temporary:
            path = workspace / "recovery_plan.json"
            plan = json.loads(path.read_text(encoding="utf-8"))
            next(row for row in plan["decisions"] if row["case_id"] == case_id)[field] = value
            path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
            result = _score(workspace)
        assert result["outcome_score"] == 0.82
        assert result["failed_core_cases"] == ["survivor_and_case_workflow"]


def test_database_journal_and_protected_fields_are_independently_checked() -> None:
    for statement in (
        "UPDATE cases SET approved_amount_cents=50000 WHERE case_id='CL-B1'",
        "UPDATE cases SET paid_amount_cents=0 WHERE case_id='CL-G1'",
        "UPDATE recovery_journal SET restored=0 WHERE recovery_id='CRR-INTERRUPTED-20260818'",
    ):
        temporary, workspace = _workspace(True)
        with temporary:
            with sqlite3.connect(workspace / "state/claims.db") as connection:
                connection.execute(statement)
                connection.commit()
            result = _score(workspace)
        if "paid_amount" in statement:
            assert result["outcome_score"] == 0.0
            assert result["failed_gates"] == ["safety_and_input_integrity"]
            assert "irreversible_claim_boundaries" in result["failed_core_cases"]
        else:
            assert result["outcome_score"] == 0.84
            assert result["failed_core_cases"] == ["journal_and_mutable_projection"]


def test_stale_checkpoint_and_bundle_hash_are_detected() -> None:
    temporary, workspace = _workspace(True)
    with temporary:
        path = workspace / "recovery_plan.json"
        plan = json.loads(path.read_text(encoding="utf-8"))
        plan["source_checkpoint"] = "0" * 64
        path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
        result = _score(workspace)
    assert result["outcome_score"] == 0.88
    assert result["failed_core_cases"] == ["source_checkpoint_and_event_authority"]

    temporary, workspace = _workspace(True)
    with temporary:
        path = workspace / "staging/packet_manifest.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifest["bundle_sha256"] = "0" * 64
        path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        result = _score(workspace)
    assert result["outcome_score"] == 0.88
    assert result["failed_core_cases"] == []


def test_equivalent_reordering_and_formatting_replay_is_byte_stable() -> None:
    temporary, workspace = _workspace(True)
    with temporary:
        path = workspace / "recovery_plan.json"
        plan = json.loads(path.read_text(encoding="utf-8"))
        plan["decisions"].reverse()
        plan["event_dispositions"].reverse()
        for row in plan["decisions"]:
            row["claim_line_ids"].reverse()
            row["evidence_refs"].reverse()
        path.write_text(json.dumps(plan, separators=(",", ":")) + "\n", encoding="utf-8")
        tracked = [
            workspace / "state/claims.db", workspace / "staging/claim_packet_bundle.json",
            workspace / "staging/packet_manifest.json", workspace / "state/recovery_receipt.json",
        ]
        before = [item.read_bytes() for item in tracked]
        _run(workspace, "replay", "recovery_plan.json")
        _run(workspace, "replay", "recovery_plan.json")
        after = [item.read_bytes() for item in tracked]
        result = _score(workspace)
    assert before == after
    assert result["outcome_score"] == 1.0


def test_same_identity_conflict_rejected_without_mutation() -> None:
    temporary, workspace = _workspace(True)
    with temporary:
        path = workspace / "recovery_plan.json"
        plan = json.loads(path.read_text(encoding="utf-8"))
        next(row for row in plan["decisions"] if row["case_id"] == "CL-B1")["locally_allowed_amount_cents"] = 50000
        path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
        before = (workspace / "state/claims.db").read_bytes()
        completed = _run(workspace, "apply", "recovery_plan.json", check=False)
        after = (workspace / "state/claims.db").read_bytes()
    assert completed.returncode != 0
    assert before == after


def test_controller_validates_changed_policy_seed_using_public_checkpoint() -> None:
    temporary, workspace = _workspace(False)
    with temporary:
        policy_path = workspace / "policy/claims_policy.json"
        policy = json.loads(policy_path.read_text(encoding="utf-8"))
        policy["damage_missing_packaging_percent"] = 50
        policy_path.write_text(json.dumps(policy, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        manifest_path = workspace / "policy/source_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["files"]["policy/claims_policy.json"] = _digest(policy_path.read_bytes())
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        plan = json.loads(
            (TASK / "tests/reference/recovery_plan.json").read_text(encoding="utf-8")
        )
        next(row for row in plan["decisions"] if row["case_id"] == "CL-B1")[
            "locally_allowed_amount_cents"
        ] = 25000
        next(row for row in plan["decisions"] if row["case_id"] == "CL-A1")[
            "locally_allowed_amount_cents"
        ] = 25000
        plan["totals"]["ready_packet_amount_cents"] -= 6000
        contract = json.loads(_run(workspace, "contract", "--json").stdout)
        plan["source_checkpoint"] = contract["source_checkpoint"]
        (workspace / "recovery_plan.json").write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
        completed = _run(workspace, "preview", "recovery_plan.json")
    assert '"status": "valid"' in completed.stdout


def test_public_contract_exposes_interface_not_completed_claims_plan() -> None:
    temporary, workspace = _workspace(False)
    with temporary:
        contract = json.loads(_run(workspace, "contract", "--json").stdout)
        reference = json.loads(
            (TASK / "tests/reference/recovery_plan.json").read_text(encoding="utf-8")
        )
    assert contract["source_checkpoint"] == reference["source_checkpoint"]
    assert len(contract["source_checkpoint"]) == 64
    assert set(contract["plan_schema"]["decision_fields"]) == {
        "case_id", "tracking_number", "carrier", "survivor_case_id",
        "disposition", "final_state", "requested_amount_cents",
        "locally_allowed_amount_cents", "response_deadline", "next_local_action",
        "claim_line_ids", "evidence_refs",
    }
    assert "ready_local_packet" in contract["controlled_vocabulary"]["disposition"]
    assert "applied_to_survivor" in contract["controlled_vocabulary"]["event_disposition"]
    assert contract["locator_grammar"]["evidence_blob"].endswith("#<blob_id>")
    assert contract["locator_grammar"]["carrier_event"].endswith("#<event_id>")
    assert not {"decisions", "event_dispositions", "totals"} & set(contract)


def test_preview_feedback_is_candidate_first_and_field_specific() -> None:
    temporary, workspace = _workspace(False)
    with temporary:
        plan = json.loads(
            (TASK / "tests/reference/recovery_plan.json").read_text(encoding="utf-8")
        )
        plan["source_checkpoint"] = "CRR-INTERRUPTED-20260818"
        decision = next(row for row in plan["decisions"] if row["case_id"] == "CL-B1")
        decision["disposition"] = "settled"
        decision["evidence_refs"] = ["evidence/blobs/BLOB-B1-INV.json#0"]
        event = next(
            row for row in plan["event_dispositions"]
            if row["delivery_id"] == "DL-001"
        )
        event["disposition"] = "accepted"
        plan["totals"]["ready_packet_amount_cents"] += 1
        (workspace / "recovery_plan.json").write_text(
            json.dumps(plan, indent=2) + "\n", encoding="utf-8"
        )
        completed = _run(
            workspace, "preview", "recovery_plan.json", check=False
        )
        current_checkpoint = json.loads(
            _run(workspace, "contract", "--json").stdout
        )["source_checkpoint"]
    assert completed.returncode != 0
    assert "decision CL-B1 differs in fields: disposition, evidence_refs" in completed.stdout
    assert "event DL-001 differs in fields: disposition" in completed.stdout
    assert "totals.ready_packet_amount_cents differs" in completed.stdout
    assert "source_checkpoint differs" in completed.stdout
    assert "claimsctl.py contract --json" in completed.stdout
    assert current_checkpoint not in completed.stdout
    assert "ready_local_packet" not in completed.stdout
    assert "applied" not in completed.stdout


def test_public_controller_has_no_complete_answer_export() -> None:
    source = (TASK / "workspace/claimsctl.py").read_text(encoding="utf-8")
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
            "import claimsctl; assert not any(hasattr(claimsctl,n) for n in "
            "('derive','target_plan','expected_plan','reference_plan'))",
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
            TASK / "tests/reference/recovery_plan.json",
            workspace / "recovery_plan.json",
        )
        before = (workspace / "state/claims.db").read_bytes()
        _run(workspace, "preview", "recovery_plan.json")
        assert (workspace / "state/claims.db").read_bytes() == before

    temporary, workspace = _workspace(True)
    with temporary:
        (workspace / "inspect_claims.py").write_text("print('bounded local helper')\n")
        cache = workspace / "__pycache__"
        cache.mkdir(exist_ok=True)
        (cache / "claimsctl.cpython-313.pyc").write_bytes(b"cache")
        assert _score(workspace)["outcome_score"] == 1.0
        (workspace / "unknown.bin").write_bytes(b"unknown")
        assert _score(workspace)["outcome_score"] == 1.0

    temporary, workspace = _workspace(True)
    with temporary:
        (workspace / "unsafe-link").symlink_to("recovery_plan.json")
        gated = _score(workspace)
    assert gated["outcome_score"] == 0.0
    assert gated["failed_gates"] == ["safety_and_input_integrity"]


def test_missing_closure_is_incomplete_but_not_a_safety_violation() -> None:
    temporary, workspace = _workspace(False)
    with temporary:
        shutil.copy2(
            TASK / "tests/reference/recovery_plan.json",
            workspace / "recovery_plan.json",
        )
        result = _score(workspace)
    assert result["outcome_score"] > 0.0
    assert result["outcome_score"] < 0.8
    assert result["failed_gates"] == []
    closure = next(
        check for check in result["checks"]
        if check["id"] == "case:packet_hash_and_replay_closure"
    )
    assert closure["pass"] is False


def test_evaluator_is_independent_and_never_imports_or_executes_controller() -> None:
    source = (TASK / "tests/test_outcome.py").read_text(encoding="utf-8")
    assert "import claimsctl" not in source
    assert "from claimsctl" not in source
    assert "subprocess" not in source
    assert "importlib" not in source
    assert "tests/reference" not in source


def test_case_weights_and_semantic_builder_runner_contract() -> None:
    cases = yaml.safe_load((TASK / "tests/cases.yaml").read_text(encoding="utf-8"))["cases"]
    assert sum(item["weight"] for item in cases if item.get("core")) == 0.8
    assert sum(item["weight"] for item in cases) == 1.0
    assert [item["id"] for item in cases if item.get("gate")] == ["safety_and_input_integrity"]
    metadata = yaml.safe_load((TASK / "task.yaml").read_text(encoding="utf-8"))
    assert metadata["semantic_judge"]["case_map"] == {"handoff_semantics": "claims_handoff"}
    assert metadata["semantic_judge"]["max_fallback_weight"] == 0.08
    spec = importlib.util.spec_from_file_location("task_130_builder", TASK / "tests/test_outcome.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load semantic builder")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    temporary, workspace = _workspace(True)
    with temporary:
        semantic_input = module.build_semantic_judge_input(workspace)
    assert semantic_input["judge_eligible"] is True
    assert semantic_input["artifact"] == "claims_handoff.md"
