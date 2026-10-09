from __future__ import annotations

import importlib.util
import re
from pathlib import Path


TASK = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "task_047_outcome_fairness", TASK / "tests" / "test_outcome.py"
)
assert SPEC and SPEC.loader
OUTCOME = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(OUTCOME)


def _copy_reference(workspace: Path) -> None:
    workspace.mkdir()
    for name in ("delay_actions.csv", "customer_messages.md"):
        (workspace / name).write_bytes(
            (TASK / "tests" / "reference" / name).read_bytes()
        )


def test_iso_dates_are_valid_customer_estimates(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    _copy_reference(workspace)
    path = workspace / "customer_messages.md"
    replacements = {
        "June 6": "2026-06-06",
        "June 7": "2026-06-07",
        "June 8": "2026-06-08",
        "June 9": "2026-06-09",
        "June 10": "2026-06-10",
    }
    text = path.read_text(encoding="utf-8")
    for old, new in replacements.items():
        text = text.replace(old, new)
    path.write_text(text, encoding="utf-8")

    checks = OUTCOME.evaluate_cases(workspace)
    assert checks["safe_customer_communications"]["pass"] is True


def test_shipment_prefixed_headings_are_valid_draft_sections(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    _copy_reference(workspace)
    path = workspace / "customer_messages.md"
    text = re.sub(r"^##\s+(S-\d+)\s*$", r"## Shipment \1", path.read_text(), flags=re.M)
    path.write_text(text, encoding="utf-8")

    checks = OUTCOME.evaluate_cases(workspace)
    assert checks["safe_customer_communications"]["pass"] is True


def test_heading_level_and_action_only_recovery_are_valid(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    _copy_reference(workspace)
    path = workspace / "customer_messages.md"
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"^## ", "### ", text, flags=re.M)
    text = text.replace(" expected June 6", "")
    text = text.replace(" expected June 8", "")
    path.write_text(text, encoding="utf-8")

    checks = OUTCOME.evaluate_cases(workspace)
    assert checks["safe_customer_communications"]["pass"] is True


def test_current_carrier_estimate_is_still_required(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    _copy_reference(workspace)
    path = workspace / "customer_messages.md"
    text = path.read_text(encoding="utf-8").replace("June 10", "a later date")
    path.write_text(text, encoding="utf-8")

    checks = OUTCOME.evaluate_cases(workspace)
    assert checks["safe_customer_communications"]["pass"] is False
