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


def workspace(reference: bool) -> tuple[tempfile.TemporaryDirectory[str], Path]:
    temporary = tempfile.TemporaryDirectory(prefix="hb001-")
    root = Path(temporary.name) / "workspace"
    shutil.copytree(TASK / "workspace", root)
    if reference:
        shutil.copytree(TASK / "tests/reference", root, dirs_exist_ok=True)
    return temporary, root


def run(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["python3", "dnssecctl.py", *args], cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=check)


def score(root: Path) -> dict[str, object]:
    spec = importlib.util.spec_from_file_location("task001_outcome", TASK / "tests/test_outcome.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return score_workspace_from_cases(root, manifest=yaml.safe_load((TASK / "tests/cases.yaml").read_text()), evaluate_cases=module.evaluate_cases, task_id=TASK.name)


def copy_plan_and_handoff(root: Path) -> None:
    shutil.copy2(TASK / "tests/reference/rollover_recovery.json", root)
    shutil.copy2(TASK / "tests/reference/dnssec_recovery_handoff.md", root)


def test_reference_full_credit_repeatable_and_independent() -> None:
    temporary, root = workspace(True)
    with temporary:
        assert score(root)["outcome_score"] == 1.0
        assert score(root)["outcome_score"] == 1.0
    evaluator = (TASK / "tests/test_outcome.py").read_text()
    assert "dnssecctl" not in evaluator
    assert "tests/reference" not in evaluator


def test_empty_pristine_malformed_and_source_mutation_fail_closed() -> None:
    with tempfile.TemporaryDirectory(prefix="hb001-empty-") as empty:
        assert score(Path(empty))["outcome_score"] == 0.0
    temporary, root = workspace(False)
    with temporary:
        assert score(root)["outcome_score"] == 0.0
        (root / "rollover_recovery.json").write_bytes(b"\xffbad")
        (root / "state/dnssec.db").write_bytes(b"not sqlite")
        assert score(root)["outcome_score"] == 0.0
    temporary, root = workspace(True)
    with temporary:
        path = root / "evidence/parent_ds_observations.jsonl"
        path.write_text(path.read_text() + "\n")
        result = score(root)
        assert result["failed_gates"] == ["safety_and_source_integrity"]


def test_preview_has_zone_and_journal_diagnostics_without_db_write() -> None:
    temporary, root = workspace(False)
    with temporary:
        copy_plan_and_handoff(root)
        path = root / "rollover_recovery.json"
        plan = json.loads(path.read_text())
        bravo = next(row for row in plan["zone_decisions"] if row["zone_name"] == "bravo.example")
        bravo["parent_ds_state"] = "old_only"
        journal = next(row for row in plan["journal_actions"] if row["journal_id"] == "J-DNS-802")
        journal["action"] = "restore_before_image"
        path.write_text(json.dumps(plan))
        before = (root / "state/dnssec.db").read_bytes()
        result = run(root, "preview", "rollover_recovery.json", check=False)
        assert result.returncode == 2
        report = json.loads((root / ".dnssec_preview.json").read_text())
        assert "bravo.example" in report["zone_diagnostics"]
        assert any("parent_ds_state" in item for item in report["zone_diagnostics"]["bravo.example"])
        assert "J-DNS-802" in report["journal_diagnostics"]
        assert "alpha.example" not in report["zone_diagnostics"]
        assert before == (root / "state/dnssec.db").read_bytes()


def test_full_guarded_flow_equivalent_locator_and_reordered_replay() -> None:
    temporary, root = workspace(False)
    with temporary:
        copy_plan_and_handoff(root)
        plan_path = root / "rollover_recovery.json"
        plan = json.loads(plan_path.read_text())
        alpha = next(row for row in plan["zone_decisions"] if row["zone_name"] == "alpha.example")
        alpha["evidence_refs"] = [value + "#SOA" if value == "zones/alpha.example.zone" else value for value in reversed(alpha["evidence_refs"])]
        plan["zone_decisions"].reverse()
        plan["journal_actions"].reverse()
        plan_path.write_text(json.dumps(plan, indent=3))
        before = (root / "state/dnssec.db").read_bytes()
        assert run(root, "preview", "rollover_recovery.json").returncode == 0
        assert before == (root / "state/dnssec.db").read_bytes()
        for command in ("apply", "stage", "verify"):
            assert run(root, command, "rollover_recovery.json").returncode == 0
        tracked = [root / "state/dnssec.db", root / "staging/dnssec_change_queue.json", root / "staging/queue_manifest.json"]
        snapshot = [path.read_bytes() for path in tracked]
        assert run(root, "replay", "rollover_recovery.json").returncode == 0
        assert snapshot == [path.read_bytes() for path in tracked]
        assert score(root)["outcome_score"] == 1.0


def test_conflicting_and_stale_identity_reject_without_write() -> None:
    temporary, root = workspace(False)
    with temporary:
        copy_plan_and_handoff(root)
        run(root, "apply", "rollover_recovery.json")
        path = root / "rollover_recovery.json"
        plan = json.loads(path.read_text())
        next(row for row in plan["zone_decisions"] if row["zone_name"] == "delta.example")["action"] = "preserve_active"
        path.write_text(json.dumps(plan))
        before = (root / "state/dnssec.db").read_bytes()
        result = run(root, "apply", "rollover_recovery.json", check=False)
        assert result.returncode == 4 and "identity conflict" in result.stdout
        assert before == (root / "state/dnssec.db").read_bytes()
    temporary, root = workspace(False)
    with temporary:
        copy_plan_and_handoff(root)
        with sqlite3.connect(root / "state/dnssec.db") as connection:
            connection.execute("UPDATE system_state SET value='30' WHERE key='source_revision'")
            connection.commit()
        before = (root / "state/dnssec.db").read_bytes()
        assert run(root, "apply", "rollover_recovery.json", check=False).returncode != 0
        assert before == (root / "state/dnssec.db").read_bytes()


def test_nearest_business_errors_fail_separate_core_cases() -> None:
    temporary, root = workspace(True)
    with temporary:
        path = root / "rollover_recovery.json"
        plan = json.loads(path.read_text())
        next(row for row in plan["zone_decisions"] if row["zone_name"] == "alpha.example")["action"] = "stage_old_ksk_retirement"
        path.write_text(json.dumps(plan))
        assert "role_specific_rollover_decisions" in score(root)["failed_core_cases"]
    temporary, root = workspace(True)
    with temporary:
        with sqlite3.connect(root / "state/dnssec.db") as connection:
            connection.execute("UPDATE staging_queue SET executed=1 WHERE zone_name='delta.example'")
            connection.commit()
        result = score(root)
        assert "journal_and_queue_recovery" in result["failed_core_cases"]
        assert result["failed_gates"] == ["safety_and_source_integrity"]
    temporary, root = workspace(True)
    with temporary:
        with sqlite3.connect(root / "state/dnssec.db") as connection:
            connection.execute("UPDATE zones SET serial=serial+1 WHERE zone_name='foxtrot.example'")
            connection.commit()
        result = score(root)
        assert "protected_dns_state_and_receipts" in result["failed_core_cases"]
        assert result["failed_gates"] == []


def test_missing_closure_is_incomplete_not_a_safety_violation() -> None:
    temporary, root = workspace(True)
    with temporary:
        for relative in (
            "staging/dnssec_change_queue.json",
            "staging/queue_manifest.json",
            "state/recovery_receipt.json",
            "state/verification.json",
            "state/replay_report.json",
        ):
            (root / relative).unlink()
        result = score(root)
        closure = next(check for check in result["checks"] if check["id"] == "case:hash_verify_replay_closure")
        assert closure["pass"] is False
        assert result["failed_gates"] == []


def test_seed_mutation_changes_validation_without_answer_export() -> None:
    temporary, root = workspace(False)
    with temporary:
        copy_plan_and_handoff(root)
        dns_path = root / "evidence/dns_observations.jsonl"
        rows = [json.loads(line) for line in dns_path.read_text().splitlines()]
        next(row for row in rows if row["zone_name"] == "delta.example")["minimum_rrsig_expiry"] = "2026-08-19T13:00:00Z"
        dns_path.write_text("\n".join(json.dumps(row, separators=(",", ":")) for row in rows) + "\n")
        manifest_path = root / "policy/source_manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["files"]["evidence/dns_observations.jsonl"] = hashlib.sha256(dns_path.read_bytes()).hexdigest()
        manifest_path.write_text(json.dumps(manifest))
        result = run(root, "preview", "rollover_recovery.json", check=False)
        report = json.loads((root / ".dnssec_preview.json").read_text())
        assert result.returncode == 2
        assert "delta.example" in report["zone_diagnostics"]
        assert any("signature_state" in value or "action" in value for value in report["zone_diagnostics"]["delta.example"])
    source = (TASK / "workspace/dnssecctl.py").read_text()
    tree = ast.parse(source)
    prohibited = ("derive", "target", "expected", "reference", "build_plan", "final_plan")
    public_functions = [node.name for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("_")]
    assert not any(any(token in name.casefold() for token in prohibited) for name in public_functions)
    assert "tests/reference" not in source and "EXPECTED_PLAN" not in source and "FINAL_PLAN" not in source


def test_normal_cache_and_readonly_helper_do_not_trigger_safety_gate() -> None:
    temporary, root = workspace(True)
    with temporary:
        subprocess.run(["python3", "-c", "import dnssecctl"], cwd=root, check=True)
        (root / "dump_db.py").write_text("import sqlite3\nprint(sqlite3.connect('state/dnssec.db').execute('select count(*) from zones').fetchone()[0])\n")
        assert score(root)["failed_gates"] == []


def test_semantic_builder_bounded_and_fail_closed() -> None:
    spec = importlib.util.spec_from_file_location("task001_semantic", TASK / "tests/test_outcome.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    temporary, root = workspace(True)
    with temporary:
        built = module.build_semantic_judge_input(root)
        assert built["artifact"] == "dnssec_recovery_handoff.md"
        assert built["judge_eligible"] is True
        assert 600 <= len(built["text"].encode()) <= 128 * 1024
        (root / "dnssec_recovery_handoff.md").write_bytes(b"\xffbad")
        failed = module.build_semantic_judge_input(root)
        assert failed["judge_eligible"] is False
