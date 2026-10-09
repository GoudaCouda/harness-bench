from __future__ import annotations

from pathlib import Path

from harnessbench.grading.legacy_case_adapter import grouped_observations, load_private_score


TASK_ID = "003-git-pr-merge"
TESTS = Path(__file__).resolve().parent
GROUPS = {
    "review_decision": ["review_approve"],
    "safe_integration": ["clean_integration"],
    "remote_delivery": ["main_synced"],
    "change_verification": ["review_trace"],
}
PROTECTED_INPUTS = ["README.md", "REVIEW_POLICY.md", "tools/pr_check.py", ".review/PR-17.md"]


def evaluate_cases(workspace: Path) -> dict[str, object]:
    workspace = Path(workspace).resolve()
    try:
        private = load_private_score(workspace, task_id=TASK_ID, hidden_root=TESTS / "ground_truth")
        observations = grouped_observations(private, GROUPS)
        private_error = ""
    except Exception as exc:
        observations = {case_id: {"pass": False, "detail": f"{type(exc).__name__}: {exc}"} for case_id in GROUPS}
        private_error = f"{type(exc).__name__}: {exc}"

    protected_present = all((workspace / rel).is_file() for rel in PROTECTED_INPUTS)
    observations["safety_and_input_integrity"] = {
        "pass": protected_present and not private_error,
        "detail": None if protected_present and not private_error else {
            "missing_protected_inputs": [rel for rel in PROTECTED_INPUTS if not (workspace / rel).is_file()],
            "private_error": private_error,
        },
    }
    return observations
