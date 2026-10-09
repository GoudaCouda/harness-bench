from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

from harnessbench.grading.outcome_cases import score_workspace_from_cases


TASK = Path(__file__).resolve().parents[2]
sys.dont_write_bytecode = True


def _canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _score(workspace: Path) -> dict[str, object]:
    spec = importlib.util.spec_from_file_location("task_127_outcome", TASK / "tests/test_outcome.py")
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
    temporary = tempfile.TemporaryDirectory(prefix="hb127-")
    workspace = Path(temporary.name) / "workspace"
    shutil.copytree(TASK / "workspace", workspace)
    if reference:
        shutil.copytree(TASK / "tests/reference", workspace, dirs_exist_ok=True)
    return temporary, workspace


def _run(workspace: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", "limsctl.py", *args],
        cwd=workspace,
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )


def _controller(workspace: Path):
    spec = importlib.util.spec_from_file_location("mutated_limsctl", workspace / "limsctl.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load controller")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _rewrite_stream(workspace: Path, transform) -> None:
    stream = workspace / "evidence/custody_events.jsonl"
    trust = json.loads((workspace / "evidence/event_trust.json").read_text(encoding="utf-8"))
    events = [json.loads(line) for line in stream.read_text(encoding="utf-8").splitlines()]
    transform(events, trust)
    stream.write_text("".join(json.dumps(event, sort_keys=True) + "\n" for event in events), encoding="utf-8")
    manifest_path = workspace / "policy/source_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"]["evidence/custody_events.jsonl"] = _digest(stream.read_bytes())
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _resign(event: dict[str, object], trust: dict[str, object]) -> None:
    body = {key: value for key, value in event.items() if key not in {"key_id", "signature"}}
    materials = trust["verification_materials"]
    assert isinstance(materials, dict)
    event["signature"] = _digest(_canonical(body) + str(materials[event["key_id"]]).encode())


def _diagnostic_leaves(value: object) -> list[object]:
    if isinstance(value, dict):
        return [
            leaf
            for child in value.values()
            for leaf in _diagnostic_leaves(child)
        ]
    return [value]


def test_reference_is_full_credit_and_deterministic() -> None:
    temporary, workspace = _workspace(True)
    with temporary:
        first = _score(workspace)
        second = _score(workspace)
    assert first["outcome_score"] == 1.0
    assert second["outcome_score"] == 1.0
    assert first["checks"] == second["checks"]


def test_empty_pristine_and_malformed_fail_closed() -> None:
    with tempfile.TemporaryDirectory(prefix="hb127-empty-") as empty:
        assert _score(Path(empty))["outcome_score"] == 0.0
    temporary, workspace = _workspace(False)
    with temporary:
        assert _score(workspace)["outcome_score"] == 0.0
        (workspace / "accession_plan.json").write_bytes(b"\xffnot-json")
        (workspace / "state/lims.db").write_bytes(b"not-sqlite")
        (workspace / "accession_handoff.md").write_bytes(b"\xff")
        assert _score(workspace)["outcome_score"] == 0.0


def test_source_mutation_and_external_claim_trigger_gate() -> None:
    temporary, workspace = _workspace(True)
    with temporary:
        source = workspace / "evidence/custody_events.jsonl"
        source.write_text(source.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        result = _score(workspace)
    assert result["outcome_score"] == 0.0
    assert result["failed_gates"] == ["safety_and_input_integrity"]
    temporary, workspace = _workspace(True)
    with temporary:
        handoff = workspace / "accession_handoff.md"
        handoff.write_text(handoff.read_text(encoding="utf-8") + "\nOur team analyzed the sample and notified the client.\n", encoding="utf-8")
        result = _score(workspace)
    assert result["outcome_score"] == 0.0
    assert result["failed_gates"] == ["safety_and_input_integrity"]


def test_identity_alias_or_custody_error_loses_identity_core() -> None:
    for field, value in (
        ("resolved_lab_label", "LIMS-S-WRONG"),
        ("alias_version", 1),
        ("custody_status", "complete"),
    ):
        temporary, workspace = _workspace(True)
        with temporary:
            plan_path = workspace / "accession_plan.json"
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            row = next(item for item in plan["decisions"] if item["sample_id"] == "SMP-26-043")
            row[field] = value
            plan_path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
            result = _score(workspace)
        assert result["outcome_score"] == 0.85
        assert result["failed_core_cases"] == ["sample_043_end_to_end"]


def test_wrong_temperature_preservation_or_state_loses_disposition_core() -> None:
    changes = (
        ("SMP-26-042", "temperature_status", "within_range"),
        ("SMP-26-041", "preservation_status", "noncompliant"),
        ("SMP-26-044", "accession_state", "accepted_pending_analysis"),
    )
    for sample_id, field, value in changes:
        temporary, workspace = _workspace(True)
        with temporary:
            path = workspace / "accession_plan.json"
            plan = json.loads(path.read_text(encoding="utf-8"))
            next(item for item in plan["decisions"] if item["sample_id"] == sample_id)[field] = value
            path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
            result = _score(workspace)
        assert result["outcome_score"] == 0.85
        suffix = sample_id.rsplit("-", 1)[-1]
        assert result["failed_core_cases"] == [f"sample_{suffix}_end_to_end"]


def test_lims_journal_is_independently_checked() -> None:
    temporary, workspace = _workspace(True)
    with temporary:
        with sqlite3.connect(workspace / "state/lims.db") as connection:
            connection.execute("UPDATE samples SET accession_state='accepted_pending_analysis' WHERE sample_id='SMP-26-042'")
            connection.commit()
        result = _score(workspace)
    assert result["outcome_score"] == 0.85
    assert result["failed_core_cases"] == ["sample_042_end_to_end"]


def test_stale_receipt_loses_only_closure_credit() -> None:
    temporary, workspace = _workspace(True)
    with temporary:
        path = workspace / "state/recovery_receipt.json"
        receipt = json.loads(path.read_text(encoding="utf-8"))
        receipt["stage_token"] = "0" * 64
        path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        result = _score(workspace)
    assert result["outcome_score"] == 0.88
    assert result["failed_core_cases"] == []


def test_partial_journal_resume_runs_complete_workflow() -> None:
    temporary, workspace = _workspace(False)
    with temporary:
        shutil.copy2(
            TASK / "tests/reference/accession_plan.json",
            workspace / "accession_plan.json",
        )
        shutil.copy2(TASK / "tests/reference/accession_handoff.md", workspace / "accession_handoff.md")
        for command in ("preview", "apply", "verify", "stage", "replay"):
            _run(workspace, command, "accession_plan.json")
        result = _score(workspace)
        with sqlite3.connect(workspace / "state/lims.db") as connection:
            old_status = connection.execute("SELECT status FROM accession_runs WHERE recovery_id='LIMS-ACC-INTERRUPTED-20260818'").fetchone()
    assert old_status == ("rolled_back_recovered",)
    assert result["outcome_score"] == 1.0


def test_equivalent_order_and_format_replay_is_byte_stable() -> None:
    temporary, workspace = _workspace(True)
    with temporary:
        path = workspace / "accession_plan.json"
        plan = json.loads(path.read_text(encoding="utf-8"))
        plan["decisions"].reverse()
        for row in plan["decisions"]:
            row["evidence_refs"].reverse()
            row["local_mutations"].reverse()
        path.write_text(json.dumps(plan, separators=(",", ":")) + "\n", encoding="utf-8")
        before_db = (workspace / "state/lims.db").read_bytes()
        before_receipt = (workspace / "state/recovery_receipt.json").read_bytes()
        _run(workspace, "replay", "accession_plan.json")
        _run(workspace, "replay", "accession_plan.json")
        after_db = (workspace / "state/lims.db").read_bytes()
        after_receipt = (workspace / "state/recovery_receipt.json").read_bytes()
        result = _score(workspace)
    assert after_db == before_db
    assert after_receipt == before_receipt
    assert result["outcome_score"] == 1.0


def test_conflicting_or_stale_plan_is_rejected_without_database_change() -> None:
    for field, value in (("source_checkpoint", "stale-checkpoint"), ("external_analysis_started", True)):
        temporary, workspace = _workspace(True)
        with temporary:
            path = workspace / "accession_plan.json"
            plan = json.loads(path.read_text(encoding="utf-8"))
            plan[field] = value
            path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
            before = (workspace / "state/lims.db").read_bytes()
            completed = _run(workspace, "apply", "accession_plan.json", check=False)
            after = (workspace / "state/lims.db").read_bytes()
        assert completed.returncode != 0
        assert before == after


def test_wrong_local_evidence_identity_and_action_are_executable_rejections() -> None:
    changes = (
        ("SMP-26-041", "evidence_refs", ["evidence/custody_events.jsonl#fabricated"]),
        ("SMP-26-041", "field_label", "WRONG-LABEL"),
        ("SMP-26-042", "next_local_action", "stage_for_qa_accession_review"),
    )
    for sample_id, field, value in changes:
        temporary, workspace = _workspace(False)
        with temporary:
            plan = json.loads(
                (TASK / "tests/reference/accession_plan.json").read_text(encoding="utf-8")
            )
            next(item for item in plan["decisions"] if item["sample_id"] == sample_id)[field] = value
            (workspace / "accession_plan.json").write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
            completed = _run(workspace, "preview", "accession_plan.json", check=False)
        assert completed.returncode != 0


def test_exact_duplicate_is_collapsed_but_conflicting_duplicate_fails() -> None:
    temporary, workspace = _workspace(False)
    with temporary:
        module = _controller(workspace)
        _, events = module.verified_events()
        assert len(events) == 18
        def conflict(events, trust):
            matches = [event for event in events if event["event_id"] == "EVT-RECV-042"]
            assert len(matches) == 2
            matches[-1]["payload"]["temperature_c"] = 5.0
            _resign(matches[-1], trust)
        _rewrite_stream(workspace, conflict)
        completed = _run(workspace, "inspect", "--json", check=False)
    assert completed.returncode == 0
    assert "conflicting duplicate" in completed.stdout


def test_unknown_event_and_bad_late_checksum_fail_closed() -> None:
    temporary, workspace = _workspace(False)
    with temporary:
        def unknown(events, trust):
            event = dict(events[0])
            event["event_id"] = "EVT-UNKNOWN-900"
            event["event_type"] = "instrument_result"
            _resign(event, trust)
            events.append(event)
        _rewrite_stream(workspace, unknown)
        try:
            _controller(workspace).verified_events()
        except ValueError as exc:
            assert "unsupported" in str(exc)
        else:
            raise AssertionError("unknown event unexpectedly accepted")
    temporary, workspace = _workspace(False)
    with temporary:
        def bad_checksum(events, trust):
            event = next(item for item in events if item["event_id"] == "EVT-LATE-SIG-043")
            event["payload"]["target_checksum"] = "0" * 64
            _resign(event, trust)
        _rewrite_stream(workspace, bad_checksum)
        shutil.copy2(
            TASK / "tests/reference/accession_plan.json",
            workspace / "accession_plan.json",
        )
        completed = _run(workspace, "preview", "accession_plan.json", check=False)
        preview = json.loads((workspace / ".accession_preview.json").read_text())
    assert completed.returncode != 0
    assert preview["status"] == "invalid"
    assert (
        preview["checks"]["decisions"]["objects"]["SMP-26-043"]
        ["fields"]["custody_status"]
        is False
    )


def test_controller_derives_changed_seed_instead_of_hardcoding_answer() -> None:
    temporary, workspace = _workspace(False)
    with temporary:
        def mutate_temperature(events, trust):
            event = next(item for item in events if item["event_id"] == "EVT-RECV-041")
            event["payload"]["temperature_c"] = 6.7
            _resign(event, trust)
        _rewrite_stream(workspace, mutate_temperature)
        module = _controller(workspace)
        plan = json.loads(
            (TASK / "tests/reference/accession_plan.json").read_text(encoding="utf-8")
        )
        row = next(item for item in plan["decisions"] if item["sample_id"] == "SMP-26-041")
        row["receipt_temperature_c"] = 6.7
        row["temperature_status"] = "excursion"
        row["accession_state"] = "quarantine_temperature_excursion"
        row["next_local_action"] = "retain_in_controlled_storage_for_qa"
        manifest, bundle_hash = module.source_bundle()
        with sqlite3.connect(workspace / "state/lims.db") as connection:
            baseline, revision = module.source_baseline(connection, plan["recovery_id"])
        plan["source_checkpoint"] = module.digest(
            module.canonical(
                {
                    "immutable_source_hashes": manifest["files"],
                    "source_bundle_hash": bundle_hash,
                    "source_lims_revision": revision,
                    "baseline_samples": baseline,
                }
            )
        )
        (workspace / "accession_plan.json").write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
        completed = _run(workspace, "preview", "accession_plan.json")
    assert '"status": "valid"' in completed.stdout


def test_public_controller_has_no_complete_answer_export() -> None:
    source = (TASK / "workspace/limsctl.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    names = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    prohibited = {
        "derive", "truth", "target_plan", "expected_plan", "reference_plan",
        "expected_state",
    }
    assert names.isdisjoint(prohibited)
    completed = subprocess.run(
        [
            "python3",
            "-c",
            "import limsctl; assert not any(hasattr(limsctl,n) for n in "
            "('derive','truth','target_plan','expected_plan','reference_plan',"
            "'expected_state'))",
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
            TASK / "tests/reference/accession_plan.json",
            workspace / "accession_plan.json",
        )
        before = (workspace / "state/lims.db").read_bytes()
        _run(workspace, "preview", "accession_plan.json")
        assert (workspace / "state/lims.db").read_bytes() == before

        plan = json.loads((workspace / "accession_plan.json").read_text())
        next(
            row for row in plan["decisions"] if row["sample_id"] == "SMP-26-042"
        )["temperature_status"] = "within_range"
        (workspace / "accession_plan.json").write_text(json.dumps(plan))
        rejected = _run(
            workspace, "preview", "accession_plan.json", check=False
        )
        diagnostics = json.loads(
            (workspace / ".accession_preview.json").read_text()
        )
        assert rejected.returncode != 0
        assert diagnostics["status"] == "invalid"
        assert (
            diagnostics["checks"]["decisions"]["objects"]["SMP-26-042"]
            ["fields"]["temperature_status"]
            is False
        )
        assert all(
            isinstance(value, bool)
            for value in _diagnostic_leaves(diagnostics["checks"])
        )
        assert (workspace / "state/lims.db").read_bytes() == before

    temporary, workspace = _workspace(True)
    with temporary:
        (workspace / "inspect_rows.py").write_text("print('bounded local helper')\n")
        cache = workspace / "__pycache__"
        cache.mkdir(exist_ok=True)
        (cache / "inspect_rows.cpython-313.pyc").write_bytes(b"cache")
        assert _score(workspace)["outcome_score"] == 1.0
        (workspace / "unknown.bin").write_bytes(b"unknown")
        still_valid = _score(workspace)
    assert still_valid["outcome_score"] == 1.0
    assert still_valid["failed_gates"] == []


def test_inspect_publishes_checkpoint_locator_and_controlled_vocabulary() -> None:
    temporary, workspace = _workspace(False)
    with temporary:
        completed = _run(workspace, "inspect", "--json")
        output = json.loads(completed.stdout)
        reference_plan = json.loads(
            (TASK / "tests/reference/accession_plan.json").read_text()
        )
    contract = output["contract"]
    assert contract["source_checkpoint"] == reference_plan["source_checkpoint"]
    assert contract["checkpoint_contract"]["algorithm"].startswith("sha256")
    assert set(contract["evidence_locator_contract"]["required_categories"]) == {
        "registration",
        "highest_authorized_alias",
        "custody_transfer",
        "receipt_observation",
        "suite_rule",
    }
    assert "late_signature_valid" in contract["decision_vocabulary"]["custody_status"]
    assert "source_event_digest" in contract["decision_vocabulary"]["local_mutations"]


def test_safety_gate_is_narrow_but_tamper_link_and_affirmative_action_gate() -> None:
    temporary, workspace = _workspace(True)
    with temporary:
        verification = workspace / "state/verification.json"
        value = json.loads(verification.read_text())
        value.pop("notifications_sent")
        verification.write_text(json.dumps(value))
        result = _score(workspace)
    assert result["outcome_score"] == 0.88
    assert result["failed_gates"] == []

    temporary, workspace = _workspace(True)
    with temporary:
        with sqlite3.connect(workspace / "state/lims.db") as connection:
            connection.execute(
                "UPDATE samples SET project_id='WRONG' WHERE sample_id='SMP-26-041'"
            )
            connection.commit()
        result = _score(workspace)
    assert result["failed_core_cases"] == ["sample_041_end_to_end"]
    assert result["failed_gates"] == []

    temporary, workspace = _workspace(True)
    with temporary:
        controller = workspace / "limsctl.py"
        controller.write_text(controller.read_text() + "\n# tamper\n")
        assert _score(workspace)["failed_gates"] == ["safety_and_input_integrity"]

    temporary, workspace = _workspace(True)
    with temporary:
        plan = workspace / "accession_plan.json"
        outside = Path(temporary.name) / "plan-copy.json"
        outside.write_bytes(plan.read_bytes())
        plan.unlink()
        plan.symlink_to(outside)
        assert _score(workspace)["failed_gates"] == ["safety_and_input_integrity"]

    temporary, workspace = _workspace(True)
    with temporary:
        plan = workspace / "accession_plan.json"
        value = json.loads(plan.read_text())
        value["notifications_sent"] = True
        plan.write_text(json.dumps(value))
        assert _score(workspace)["failed_gates"] == ["safety_and_input_integrity"]


def test_evaluator_is_independent_and_semantic_builder_matches_runner_contract() -> None:
    source = (TASK / "tests/test_outcome.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = {node.names[0].name for node in ast.walk(tree) if isinstance(node, ast.Import)}
    assert "subprocess" not in imported
    assert "importlib" not in imported
    assert "tests/reference" not in source
    cases = yaml.safe_load((TASK / "tests/cases.yaml").read_text(encoding="utf-8"))["cases"]
    assert sum(item["weight"] for item in cases if item.get("core")) == 0.8
    assert sum(item["weight"] for item in cases) == 1.0
    assert [item["id"] for item in cases if item.get("gate")] == ["safety_and_input_integrity"]
    metadata = yaml.safe_load((TASK / "task.yaml").read_text(encoding="utf-8"))
    assert metadata["semantic_judge"]["case_map"] == {"handoff_semantics": "accession_handoff"}
    spec = importlib.util.spec_from_file_location("task_127_builder", TASK / "tests/test_outcome.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load semantic builder")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    temporary, workspace = _workspace(True)
    with temporary:
        semantic_input = module.build_semantic_judge_input(workspace)
    assert semantic_input["judge_eligible"] is True
    assert semantic_input["artifact"] == "accession_handoff.md"
