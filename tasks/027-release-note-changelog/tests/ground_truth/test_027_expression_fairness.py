from __future__ import annotations

import importlib.util
from pathlib import Path


OUTCOME_PATH = Path(__file__).resolve().parents[1] / "test_outcome.py"


def _outcome_module():
    spec = importlib.util.spec_from_file_location("task027_outcome", OUTCOME_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_issue_context_includes_meaning_written_before_trailing_id() -> None:
    module = _outcome_module()
    line = "Usage field renamed from units to billable_units (ISSUE-103)"

    context = module._context(line, "ISSUE-103")

    assert "units" in context
    assert "billable_units" in context


def test_fixed_heading_supplies_the_resolution_meaning() -> None:
    module = _outcome_module()
    changelog = """\
## [2.4.0] - 2025-10-14

### Fixed
- Duplicate invoice rows in CSV export (ISSUE-102).
"""

    matches = module._product_change_matches(changelog)

    assert len(matches["ISSUE-102"]) == 1
