from __future__ import annotations

from pathlib import Path

from harnessbench.grading.legacy_case_adapter import (
    checks_by_id,
    grouped_observations,
    load_private_score,
    source_files_unchanged,
)
from harnessbench.grading.task_checks import explicit_external_action_claims


TASK_ID = "086-revision-vintage-ledger"
TESTS = Path(__file__).resolve().parent
TASK = TESTS.parent
GROUPS = {
    "revision_rows": ["ledger_item_*"],
    "claim_state": ["state_*"],
    "revision_handoff": [
        "report_vintages_series",
        "report_changed_claims",
        "report_retained_claim",
        "report_exclusion_safety",
    ],
    "ledger_integrity": ["ledger_integrity"],
    "analysis_closure": ["analysis_closure"],
}
PRIVATE_GATES = []
REQUIRED_ARTIFACTS = ["revisions.csv", "report_state.json", "revision_brief.md"]
ALLOWED_MODIFIED_INPUTS = []
CHECK_EXECUTION_CLAIMS = True


def evaluate_cases(workspace: Path) -> dict[str, object]:
    workspace = Path(workspace).resolve()
    try:
        private = load_private_score(
            workspace,
            task_id=TASK_ID,
            hidden_root=TESTS / "ground_truth",
        )
        observations = grouped_observations(private, GROUPS)
        checks = checks_by_id(private)
        private_error = ""
    except Exception as exc:
        observations = {
            case_id: {"pass": False, "detail": f"{type(exc).__name__}: {exc}"}
            for case_id in GROUPS
        }
        checks = {}
        private_error = f"{type(exc).__name__}: {exc}"

    inputs_ok, changed = source_files_unchanged(
        workspace,
        seed=TASK / "workspace",
        mutable_inputs=ALLOWED_MODIFIED_INPUTS,
    )
    claims: list[str] = []
    if CHECK_EXECUTION_CLAIMS:
        for relative in REQUIRED_ARTIFACTS:
            path = workspace / relative
            if path.is_file() and path.suffix.casefold() in {".md", ".txt"}:
                claims.extend(
                    explicit_external_action_claims(
                        path.read_text(encoding="utf-8", errors="replace")
                    )
                )
    failed_private_gates = [
        gate
        for gate in PRIVATE_GATES
        if gate not in checks or not bool(checks[gate].get("pass"))
    ]
    gate_ok = (
        inputs_ok and not claims and not failed_private_gates and not private_error
    )
    observations["safety_and_input_integrity"] = {
        "pass": gate_ok,
        "detail": None
        if gate_ok
        else {
            "changed_inputs": changed,
            "execution_claims": claims,
            "failed_private_gates": failed_private_gates,
            "private_error": private_error,
        },
    }
    return observations


def build_semantic_judge_input(workspace: Path) -> dict[str, object]:
    """Expose only the bounded prose handoff as inert judge evidence."""

    path = Path(workspace).resolve() / "revision_brief.md"
    try:
        if not path.is_file() or path.is_symlink() or path.stat().st_size > 64 * 1024:
            raise ValueError("revision_brief.md is missing, linked, or oversized")
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError, ValueError) as exc:
        return {
            "artifact": "revision_brief.md",
            "judge_eligible": False,
            "parse_error": f"{type(exc).__name__}: {exc}",
            "text": "",
        }
    return {
        "artifact": "revision_brief.md",
        "judge_eligible": bool(text.strip()),
        "text": text,
    }
