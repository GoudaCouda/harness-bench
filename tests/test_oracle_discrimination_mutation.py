from __future__ import annotations

import shutil
import sys
import unittest
import zipfile
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
MAINTENANCE = ROOT / "tools" / "task_maintenance"
if str(MAINTENANCE) not in sys.path:
    sys.path.insert(0, str(MAINTENANCE))

from common import load_task_metadata, score_task_workspace  # noqa: E402
import validate_oracle_discrimination as discrimination  # noqa: E402
from validate_oracle_quality import make_workspace  # noqa: E402


mutate_file = discrimination.mutate_file


class OfficeArtifactMutationTests(unittest.TestCase):
    def test_office_mutation_is_parseable_and_semantically_wrong(self) -> None:
        cases = (("004-office-docs", "regional_sales_memo.docx"),)
        for task_id, artifact in cases:
            with self.subTest(task=task_id):
                task_dir = ROOT / "tasks" / task_id
                metadata = load_task_metadata(task_dir / "task.yaml")
                workspace, cleanup_roots = make_workspace(
                    task_dir,
                    metadata,
                    "reference",
                )
                try:
                    baseline = score_task_workspace(
                        task_dir,
                        metadata,
                        workspace,
                    )["outcome_score"]
                    candidate = workspace / artifact
                    mutate_file(candidate)
                    self.assertTrue(zipfile.is_zipfile(candidate))
                    mutated = score_task_workspace(
                        task_dir,
                        metadata,
                        workspace,
                    )["outcome_score"]
                    self.assertEqual(baseline, 1.0)
                    self.assertLess(mutated, baseline)
                finally:
                    for cleanup_root in cleanup_roots:
                        shutil.rmtree(cleanup_root, ignore_errors=True)

    def test_infrastructure_failure_is_not_flattened_into_a_zero_score(self) -> None:
        with mock.patch.object(
            discrimination,
            "score_task_workspace",
            return_value={
                "outcome_score": 0.0,
                "oracle_contract_failure": True,
                "oracle_infrastructure_failure": True,
            },
        ):
            result = discrimination.score_result(Path("task"), {}, Path("workspace"))

        self.assertEqual(result["score"], 0.0)
        self.assertTrue(result["oracle_contract_failure"])
        self.assertTrue(result["oracle_infrastructure_failure"])


if __name__ == "__main__":
    unittest.main()
