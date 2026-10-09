from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from harnessbench.grading.outcome_cases import score_workspace_from_cases  # noqa: E402


TASK = ROOT / "tasks" / "160-xbrl-prefiling-semantic-repair"


def score(workspace: Path) -> dict[str, object]:
    spec = importlib.util.spec_from_file_location(
        "task160_outcome", TASK / "tests" / "test_outcome.py"
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load task160 evaluator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    manifest = yaml.safe_load(
        (TASK / "tests" / "cases.yaml").read_text(encoding="utf-8")
    )
    return score_workspace_from_cases(
        workspace,
        manifest=manifest,
        evaluate_cases=module.evaluate_cases,
        task_id=TASK.name,
    )


def test_malformed_nested_filing_shapes_fail_cases_instead_of_oracle() -> None:
    with tempfile.TemporaryDirectory(prefix="task160-malformed-") as temporary:
        workspace = Path(temporary) / "workspace"
        shutil.copytree(TASK / "workspace", workspace)
        shutil.copytree(TASK / "tests" / "reference", workspace, dirs_exist_ok=True)
        path = workspace / "repaired_filing.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        value.update(
            {
                "entity": "0000123456",
                "period": "2025-12-31",
                "contexts": ["C-YEAR"],
                "facts": ["Revenue", "Assets"],
                "exhibit": "exhibit_101.xml",
            }
        )
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
        result = score(workspace)

    assert result["outcome_score"] < 1.0
    assert "semantic_filing_repair" in result["failed_core_cases"]


def test_malformed_preservation_shape_fails_case_instead_of_oracle() -> None:
    with tempfile.TemporaryDirectory(prefix="task160-malformed-state-") as temporary:
        workspace = Path(temporary) / "workspace"
        shutil.copytree(TASK / "workspace", workspace)
        shutil.copytree(TASK / "tests" / "reference", workspace, dirs_exist_ok=True)
        path = workspace / "validation_state.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        value.update(
            {
                "preserved_fact_values": "Revenue=1250000, Assets=2400000",
                "fact_preservation": "confirmed",
                "facts_preserved": False,
            }
        )
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
        result = score(workspace)

    assert result["outcome_score"] < 1.0
    check = next(
        item for item in result["checks"] if item["id"] == "case:validation_state_reconciliation"
    )
    assert check["pass"] is False
