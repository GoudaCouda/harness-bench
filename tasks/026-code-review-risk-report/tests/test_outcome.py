from __future__ import annotations

import json
from pathlib import Path

from harnessbench.grading.legacy_case_adapter import (
    checks_by_id,
    grouped_observations,
    load_private_score,
    source_files_unchanged,
)
from harnessbench.grading.task_checks import explicit_external_action_claims


TASK_ID = "026-code-review-risk-report"
TESTS = Path(__file__).resolve().parent
TASK = TESTS.parent
GROUPS = {
    "authorization_and_tenant_review": ["authorization_and_tenant_review"],
    "worker_state_review": ["worker_state_review"],
    "data_lifecycle_review": ["data_lifecycle_review"],
    "actionable_handoff": ["actionable_handoff"],
    "prioritization_and_verification": ["prioritization_and_verification"],
    "report_integrity": ["report_integrity"],
}
PRIVATE_GATES = []
REQUIRED_ARTIFACTS = ["review_findings.json"]
ALLOWED_MODIFIED_INPUTS = []
CHECK_EXECUTION_CLAIMS = False


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
    """Expose a valid review report as inert data for one bounded prose case."""

    path = Path(workspace).resolve() / "review_findings.json"
    try:
        if not path.is_file() or path.is_symlink() or path.stat().st_size > 256 * 1024:
            raise ValueError("review_findings.json is missing, linked, or oversized")
        value = json.loads(path.read_text(encoding="utf-8"))
        findings = value.get("findings") if isinstance(value, dict) else None
        summary = value.get("summary") if isinstance(value, dict) else None
        eligible = bool(
            isinstance(summary, str)
            and summary.strip()
            and isinstance(findings, list)
            and findings
            and all(isinstance(finding, dict) for finding in findings)
        )
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        return {
            "artifact": "review_findings.json",
            "judge_eligible": False,
            "parse_error": f"{type(exc).__name__}: {exc}",
            "report": {},
        }
    return {
        "artifact": "review_findings.json",
        "judge_eligible": eligible,
        "report": value,
    }
