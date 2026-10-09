from __future__ import annotations

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
    spec = importlib.util.spec_from_file_location(
        "task_122_outcome", TASK / "tests/test_outcome.py"
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load evaluator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return score_workspace_from_cases(
        workspace,
        manifest=yaml.safe_load(
            (TASK / "tests/cases.yaml").read_text(encoding="utf-8")
        ),
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


def _run(
    workspace: Path, *args: str, check: bool = True
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", "pcardctl.py", *args],
        cwd=workspace,
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )


def test_reference_is_full_credit_and_deterministic() -> None:
    temporary, workspace = _workspace(True)
    with temporary:
        first = _score(workspace)
        second = _score(workspace)
    assert first["outcome_score"] == 1.0
    assert second["outcome_score"] == 1.0
    assert first["checks"] == second["checks"]


def test_semantically_equivalent_handoff_wording_keeps_handoff_credit() -> None:
    temporary, workspace = _workspace(True)
    with temporary:
        path = workspace / "close_handoff.md"
        text = path.read_text(encoding="utf-8")
        text = text.replace("manifest SHA-256 matched", "manifest hash was verified")
        text = text.replace(
            "SQLite close state and staged receipt byte-for-byte unchanged",
            "local database and staged receipt stable and unchanged during replay",
        )
        text = text.replace(
            "staged pending ERP posting approval",
            "staged locally; no ERP posting was created and approval remains required",
        )
        path.write_text(text, encoding="utf-8")
        result = _score(workspace)
    assert result["outcome_score"] == 1.0


def test_pristine_and_malformed_workspaces_do_not_pass_or_crash() -> None:
    temporary, workspace = _workspace(False)
    with temporary:
        pristine = _score(workspace)
        (workspace / "pcard_close_state.db").write_bytes(b"not sqlite")
        (workspace / "reconciliation_plan.json").write_bytes(b"\xff{")
        malformed = _score(workspace)
    assert pristine["outcome_score"] == 0.0
    assert malformed["outcome_score"] == 0.0


def test_immutable_erp_or_receipt_mutation_triggers_gate() -> None:
    for relative in ("erp.db", "receipts/PC-201.pdf"):
        temporary, workspace = _workspace(True)
        with temporary:
            path = workspace / relative
            path.write_bytes(path.read_bytes() + b"tamper")
            result = _score(workspace)
        assert result["outcome_score"] == 0.0
        assert result["failed_gates"] == ["source_and_external_safety"]


def test_split_refund_or_tax_shortcuts_cannot_pass() -> None:
    statements = (
        "DELETE FROM split_edges",
        "UPDATE refund_links SET original_transaction_id='PC-201'",
        "UPDATE transaction_dispositions SET cleared_cents=11000, exception_cents=0 WHERE transaction_id='PC-205'",
    )
    for statement in statements:
        temporary, workspace = _workspace(True)
        with temporary:
            connection = sqlite3.connect(workspace / "pcard_close_state.db")
            connection.execute(statement)
            connection.commit()
            connection.close()
            result = _score(workspace)
        assert result["outcome_score"] < 0.8


def test_core_only_tier_is_exactly_threshold() -> None:
    temporary, workspace = _workspace(True)
    with temporary:
        for name in (
            "pcard_verification.json",
            "pcard_stage_receipt.json",
            "close_handoff.md",
        ):
            (workspace / name).unlink()
        result = _score(workspace)
    assert result["outcome_score"] == 0.8
    assert result["failed_core_cases"] == []


def test_equivalent_replay_is_idempotent_and_byte_stable() -> None:
    temporary, workspace = _workspace(False)
    with temporary:
        shutil.copy2(
            TASK / "tests/reference/reconciliation_plan.json",
            workspace / "reconciliation_plan.json",
        )
        shutil.copy2(
            TASK / "tests/reference/close_handoff.md", workspace / "close_handoff.md"
        )
        _run(workspace, "preview", "reconciliation_plan.json")
        _run(workspace, "apply", "reconciliation_plan.json")
        first_db = (workspace / "pcard_close_state.db").read_bytes()
        path = workspace / "reconciliation_plan.json"
        plan = json.loads(path.read_text(encoding="utf-8"))
        plan["actions"].reverse()
        for action in plan["actions"]:
            action["evidence_refs"].reverse()
        path.write_text(
            json.dumps(plan, separators=(",", ":")) + "\n", encoding="utf-8"
        )
        replay = _run(workspace, "apply", "reconciliation_plan.json")
        assert "idempotent_replay" in replay.stdout
        assert (workspace / "pcard_close_state.db").read_bytes() == first_db
        _run(workspace, "verify")
        _run(workspace, "stage", "reconciliation_plan.json")
        first_stage = (workspace / "pcard_stage_receipt.json").read_bytes()
        completed = _run(workspace, "replay", "reconciliation_plan.json")
        assert '"byte_stable": true' in completed.stdout
        assert (workspace / "pcard_close_state.db").read_bytes() == first_db
        assert (workspace / "pcard_stage_receipt.json").read_bytes() == first_stage
        result = _score(workspace)
    assert result["outcome_score"] == 1.0


def test_documented_locator_aliases_complete_full_workflow() -> None:
    temporary, workspace = _workspace(False)
    with temporary:
        plan = json.loads(
            (TASK / "tests/reference/reconciliation_plan.json").read_text()
        )
        for action in plan["actions"]:
            transaction_id = action["transaction_id"]
            refs = [
                ref
                for ref in action["evidence_refs"]
                if ref
                not in {
                    "pcard_policy.md#published-dispositions",
                    "acceptance.db#absence",
                }
            ]
            refs = [
                ref.replace(
                    "acceptance.db#acceptance_decisions/",
                    "acceptance.db#acceptance/",
                ).replace("erp.db#posted_card_transactions/", "erp.db#postings/")
                for ref in refs
            ]
            if transaction_id in {"PC-203", "PC-204"}:
                refs = [
                    ref for ref in refs if not ref.startswith("issuer.db#split-peer/")
                ]
                refs.append("split-graph#PC-203-PC-204")
            action["evidence_refs"] = refs
        (workspace / "reconciliation_plan.json").write_text(
            json.dumps(plan, indent=2) + "\n"
        )
        shutil.copy2(
            TASK / "tests/reference/close_handoff.md",
            workspace / "close_handoff.md",
        )
        for command in (
            ("preview", "reconciliation_plan.json"),
            ("apply", "reconciliation_plan.json"),
            ("apply", "reconciliation_plan.json"),
            ("verify",),
            ("stage", "reconciliation_plan.json"),
            ("replay", "reconciliation_plan.json"),
        ):
            _run(workspace, *command)
        result = _score(workspace)
    assert result["outcome_score"] == 1.0


def test_preview_names_each_missing_source_locator_without_mutation() -> None:
    temporary, workspace = _workspace(False)
    with temporary:
        plan = json.loads(
            (TASK / "tests/reference/reconciliation_plan.json").read_text()
        )
        target = next(
            row for row in plan["actions"] if row["transaction_id"] == "PC-201"
        )
        target["evidence_refs"] = ["issuer.db#transactions/PC-201"]
        path = workspace / "reconciliation_plan.json"
        path.write_text(json.dumps(plan, indent=2) + "\n")
        before = (workspace / "pcard_close_state.db").read_bytes()
        completed = _run(workspace, "preview", path.name, check=False)
        after = (workspace / "pcard_close_state.db").read_bytes()
    assert completed.returncode == 2
    assert "PC-201" in completed.stdout
    assert "acceptance.db#acceptance_decisions/PC-201" in completed.stdout
    assert "receipts/PC-201.pdf#sha256=" in completed.stdout
    assert before == after


def test_conflicting_replay_is_rejected_without_mutation() -> None:
    temporary, workspace = _workspace(True)
    with temporary:
        path = workspace / "reconciliation_plan.json"
        plan = json.loads(path.read_text(encoding="utf-8"))
        plan["actions"][0]["disposition"] = "hold_missing_receipt"
        path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
        before = (workspace / "pcard_close_state.db").read_bytes()
        completed = _run(workspace, "apply", "reconciliation_plan.json", check=False)
        after = (workspace / "pcard_close_state.db").read_bytes()
    assert completed.returncode != 0
    assert before == after


def test_public_derivation_changes_when_acceptance_seed_changes() -> None:
    temporary, workspace = _workspace(False)
    with temporary:
        connection = sqlite3.connect(workspace / "acceptance.db")
        connection.execute(
            "INSERT INTO acceptance_decisions VALUES (?, ?, ?, ?, ?, ?)",
            (
                "PC-207",
                "accepted",
                8900,
                "MGR-SEED",
                "2026-08-01T00:00:00Z",
                "ACC-SEED",
            ),
        )
        connection.commit()
        connection.close()
        inspection = json.loads(_run(workspace, "inspect", "--json").stdout)
        plan = json.loads(
            (TASK / "tests/reference/reconciliation_plan.json").read_text(
                encoding="utf-8"
            )
        )
        plan["source_checkpoint"] = inspection["source_checkpoint"]
        target = next(
            row for row in plan["actions"] if row["transaction_id"] == "PC-207"
        )
        target["disposition"] = "clear"
        target["evidence_refs"].append("acceptance.db#acceptance_decisions/PC-207")
        path = workspace / "reconciliation_plan.json"
        path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
        completed = _run(workspace, "preview", "reconciliation_plan.json")
    assert '"status": "pass"' in completed.stdout


def test_valid_changed_source_checkpoint_conflicts_after_commit() -> None:
    temporary, workspace = _workspace(True)
    with temporary:
        connection = sqlite3.connect(workspace / "acceptance.db")
        connection.execute(
            "INSERT INTO acceptance_decisions VALUES (?, ?, ?, ?, ?, ?)",
            (
                "PC-207",
                "accepted",
                8900,
                "MGR-SEED",
                "2026-08-01T00:00:00Z",
                "ACC-SEED",
            ),
        )
        connection.commit()
        connection.close()
        inspection = json.loads(_run(workspace, "inspect", "--json").stdout)
        path = workspace / "reconciliation_plan.json"
        plan = json.loads(path.read_text(encoding="utf-8"))
        plan["source_checkpoint"] = inspection["source_checkpoint"]
        target = next(
            row for row in plan["actions"] if row["transaction_id"] == "PC-207"
        )
        target["disposition"] = "clear"
        target["evidence_refs"].append("acceptance.db#acceptance_decisions/PC-207")
        path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
        _run(workspace, "preview", "reconciliation_plan.json")
        before = (workspace / "pcard_close_state.db").read_bytes()
        completed = _run(workspace, "apply", "reconciliation_plan.json", check=False)
        after = (workspace / "pcard_close_state.db").read_bytes()
    assert completed.returncode == 3
    assert '"status": "conflict"' in completed.stdout
    assert before == after


def test_evaluator_is_independent_of_public_controller() -> None:
    source = (TASK / "tests/test_outcome.py").read_text(encoding="utf-8")
    assert "import pcardctl" not in source
    assert "subprocess" not in source
