from __future__ import annotations

from pathlib import Path

from harnessbench.grading.legacy_case_adapter import (
    checks_by_id,
    grouped_observations,
    load_private_score,
    source_files_unchanged,
)
from harnessbench.grading.task_checks import explicit_external_action_claims


TASK_ID = "014-contract-summary-risk"
TESTS = Path(__file__).resolve().parent
TASK = TESTS.parent
GROUPS = {
    "effective_risk_register": ["closed_risk_set", "risk_C-*", "risk_O-*"],
    "effective_terms_summary": [
        "summary_effective_terms",
        "summary_open_risks",
    ],
    "review_boundary": [
        "summary_review_boundary",
    ],
    "business_handoff": ["risk_actions_and_owners"],
    "register_integrity": [
        "risk_csv_parseable",
        "risk_csv_header_exact",
        "severity_values_valid",
        "unique_clause_keys",
    ],
}
PRIVATE_GATES = []
REQUIRED_ARTIFACTS = ["contract_summary.md", "risk_clauses.csv"]
ALLOWED_MODIFIED_INPUTS = []
CHECK_EXECUTION_CLAIMS = False


def _adapt_private_result(private: dict[str, object]) -> dict[str, object]:
    if TASK_ID != "008-db-doc-consistency":
        return private
    row_scores = private.get("row_scores")
    rows = row_scores if isinstance(row_scores, dict) else {}

    def rows_pass(*tokens: str) -> bool:
        selected = [
            value
            for check_id, value in rows.items()
            if any(token in str(check_id) for token in tokens)
        ]
        return bool(selected) and all(
            isinstance(value, dict) and float(value.get("score") or 0.0) == 1.0
            for value in selected
        )

    details = private.get("details")
    detail = details if isinstance(details, dict) else {}
    checks = [
        {
            "id": "configuration_conflicts",
            "pass": rows_pass(
                "db_connection_pool_size",
                "api_rate_limit",
                "worker_timeout",
                "max_db_connections",
                "log_level",
            ),
        },
        {
            "id": "deployment_conflicts",
            "pass": rows_pass("region", "cpu_cores"),
        },
        {
            "id": "environment_override",
            "pass": rows_pass("session_timeout_min"),
        },
        {
            "id": "closed_audit_set",
            "pass": (
                float(private.get("contradiction_accuracy") or 0.0) == 1.0
                and detail.get("expected_count") == detail.get("actual_count")
                and detail.get("correct_count") == detail.get("expected_count")
            ),
        },
        {
            "id": "review_trace",
            "pass": float(private.get("progress") or 0.0) == 1.0,
        },
    ]
    return {**private, "checks": checks}


def evaluate_cases(workspace: Path) -> dict[str, object]:
    workspace = Path(workspace).resolve()
    try:
        private = load_private_score(
            workspace,
            task_id=TASK_ID,
            hidden_root=TESTS / "ground_truth",
        )
        private = _adapt_private_result(private)
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
