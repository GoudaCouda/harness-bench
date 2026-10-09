from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAINTENANCE = ROOT / "tools" / "task_maintenance"
if str(MAINTENANCE) not in sys.path:
    sys.path.insert(0, str(MAINTENANCE))

from common import score_task_workspace  # noqa: E402
from harnessbench.grading.deterministic_oracle import (  # noqa: E402
    _csv_field_matches,
    load_oracle_spec,
    score_workspace_from_spec,
    validate_oracle_spec,
)
from harnessbench.grading.oracle_contract import (  # noqa: E402
    safe_score_workspace,
    workspace_manifest,
    workspace_mutation_report,
)


class DeterministicOracleTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.task = self.root / "task"
        self.workspace = self.root / "workspace"
        (self.task / "workspace").mkdir(parents=True)
        self.workspace.mkdir(parents=True)
        source = "source record\n"
        (self.task / "workspace" / "source.txt").write_text(source)
        (self.workspace / "source.txt").write_text(source)
        ground_truth = {
            "decisions": [
                {
                    "case_id": "C-1",
                    "decision": "HOLD",
                    "blocker_ids": ["OPS", "LEGAL"],
                    "amount": 12.5,
                },
                {
                    "case_id": "C-2",
                    "decision": "BLOCKED",
                    "blocker_ids": ["FINANCE"],
                    "amount": 123.45,
                },
            ]
        }
        (self.task / "ground_truth.json").write_text(
            json.dumps(ground_truth),
            encoding="utf-8",
        )
        self.spec = {
            "schema_version": 1,
            "task_id": "069-example",
            "checks": [
                {
                    "id": "decision_rows",
                    "weight": 3,
                    "condition": {
                        "type": "csv_records",
                        "path": "decisions.csv",
                        "key": ["case_id"],
                        "expected_from": {
                            "path": "ground_truth.json",
                            "format": "json",
                            "pointer": "/decisions",
                        },
                        "fields": {
                            "decision": {"compare": "casefold"},
                            "blocker_ids": {
                                "compare": "set",
                                "separator": ";",
                            },
                            "amount": {
                                "compare": "number",
                                "tolerance": 0.01,
                            },
                        },
                        "allow_extra_rows": False,
                    },
                },
                {
                    "id": "state",
                    "weight": 2,
                    "condition": {
                        "type": "json",
                        "path": "state.json",
                        "pointer": "/status",
                        "op": "equals",
                        "expected": "blocked",
                    },
                },
                {
                    "id": "owners",
                    "weight": 1,
                    "condition": {
                        "type": "json",
                        "path": "state.json",
                        "pointer": "/owners",
                        "op": "set_equals",
                        "expected": ["finance", "legal"],
                    },
                },
                {
                    "id": "total",
                    "weight": 1,
                    "condition": {
                        "type": "json",
                        "path": "state.json",
                        "pointer": "/totals/amount",
                        "op": "number_close",
                        "expected": 123.45,
                        "tolerance": 0.01,
                    },
                },
                {
                    "id": "audit",
                    "weight": 2,
                    "condition": {
                        "type": "text",
                        "path": "audit.md",
                        "contains_groups": [
                            ["hold", "blocked"],
                            ["POL-7", "policy 7"],
                            ["not executed", "no production change"],
                        ],
                        "excludes_all": [
                            "deployment completed",
                            "payment sent",
                        ],
                        "regex_none": [
                            r"\bwe\s+(?:sent|paid|filed)\b",
                            r"(?<!\bno\s)\brefund\s+was\s+sent\b",
                        ],
                        "case_sensitive": False,
                    },
                },
            ],
        }
        self.spec_path = self.task / "oracle_spec.json"
        self.spec_path.write_text(json.dumps(self.spec), encoding="utf-8")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_temporal_csv_comparator_accepts_only_equivalent_forms(self) -> None:
        rule = {"compare": "temporal"}
        self.assertTrue(
            _csv_field_matches(
                "check-in 2026-08-05",
                "2026-08-05",
                rule,
            )
        )
        self.assertTrue(
            _csv_field_matches(
                "2026-08-06T09:00:00-04:00",
                "2026-08-06T09:00-04:00",
                rule,
            )
        )
        self.assertFalse(
            _csv_field_matches(
                "2026-08-06T09:30-04:00",
                "2026-08-06T09:00-04:00",
                rule,
            )
        )
        self.assertFalse(
            _csv_field_matches(
                "2026-08-06",
                "2026-08-06T09:00-04:00",
                rule,
            )
        )
        self.assertFalse(
            _csv_field_matches(
                "wrong-date 2026-08-05",
                "2026-08-05",
                rule,
            )
        )

    def test_scalar_csv_accepted_values_are_explicit_and_bounded(self) -> None:
        rule = {
            "compare": "casefold",
            "accepted_values": ["Jules home landline"],
        }
        self.assertTrue(
            _csv_field_matches("JULES HOME LANDLINE", "Jules landline", rule)
        )
        self.assertTrue(_csv_field_matches("Jules landline", "Jules landline", rule))
        self.assertFalse(
            _csv_field_matches("Dana home landline", "Jules landline", rule)
        )

    def test_accepted_values_validation_rejects_non_scalar_comparators(self) -> None:
        self.spec["checks"][0]["condition"]["fields"]["decision"] = {
            "compare": "set",
            "accepted_values": ["blocked"],
        }
        errors = "\n".join(validate_oracle_spec(self.spec, task_dir=self.task))
        self.assertIn(
            "accepted_values: supported only for exact or casefold comparison",
            errors,
        )

    def write_reference_outputs(self) -> None:
        (self.workspace / "decisions.csv").write_text(
            "case_id,decision,blocker_ids,amount\n"
            "C-2,blocked,FINANCE,123.451\n"
            'C-1,hold,"LEGAL;OPS",12.50\n',
            encoding="utf-8",
        )
        (self.workspace / "state.json").write_text(
            json.dumps(
                {
                    "status": "blocked",
                    "owners": ["legal", "finance"],
                    "totals": {"amount": 123.451},
                }
            ),
            encoding="utf-8",
        )
        (self.workspace / "audit.md").write_text(
            "POL-7 requires a hold. No production change was made.\n",
            encoding="utf-8",
        )

    def score_with_contract(
        self,
        *,
        workspace_mutation: dict[str, object] | None = None,
    ) -> dict[str, object]:
        return safe_score_workspace(
            lambda workspace: score_workspace_from_spec(
                workspace,
                spec_path=self.spec_path,
            ),
            workspace=self.workspace,
            required_artifacts=[
                "decisions.csv",
                "state.json",
                "audit.md",
            ],
            task_id="069-example",
            workspace_mutation=workspace_mutation,
        )

    def test_structured_reference_scores_one_and_is_deterministic(self) -> None:
        self.write_reference_outputs()
        first = self.score_with_contract()
        second = self.score_with_contract()
        self.assertEqual(first["outcome_score"], 1.0)
        self.assertEqual(first["checks"], second["checks"])
        self.assertEqual(
            first["oracle_engine"],
            "declarative-deterministic-v1",
        )

    def test_contains_closed_rejects_extra_nested_ids_and_keys(self) -> None:
        self.write_reference_outputs()
        self.spec["checks"] = [
            {
                "id": "closed_state",
                "weight": 1,
                "condition": {
                    "type": "json",
                    "path": "state.json",
                    "pointer": "",
                    "op": "contains_closed",
                    "expected": {
                        "status": "blocked",
                        "owners": ["finance", "legal"],
                        "totals": {"amount": 123.451},
                    },
                },
            }
        ]
        self.spec_path.write_text(json.dumps(self.spec), encoding="utf-8")
        state_path = self.workspace / "state.json"

        # A flexible root correlation key is allowed and unordered closed
        # collections remain semantically equivalent.
        state_path.write_text(
            json.dumps(
                {
                    "workflow_id": "agent-run-7",
                    "status": "blocked",
                    "owners": ["legal", "finance"],
                    "totals": {"amount": 123.451},
                }
            ),
            encoding="utf-8",
        )
        self.assertEqual(
            score_workspace_from_spec(
                self.workspace,
                spec_path=self.spec_path,
            )["outcome_score"],
            1.0,
        )

        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["owners"].append("invented-owner")
        state_path.write_text(json.dumps(state), encoding="utf-8")
        self.assertEqual(
            score_workspace_from_spec(
                self.workspace,
                spec_path=self.spec_path,
            )["outcome_score"],
            0.0,
        )

        state["owners"] = ["finance", "legal"]
        state["totals"]["invented_total"] = 999
        state_path.write_text(json.dumps(state), encoding="utf-8")
        self.assertEqual(
            score_workspace_from_spec(
                self.workspace,
                spec_path=self.spec_path,
            )["outcome_score"],
            0.0,
        )

    def test_contains_closed_zero_extended_accepts_only_declared_zeroes(self) -> None:
        state_path = self.workspace / "state.json"
        self.spec["checks"] = [
            {
                "id": "dense_or_sparse_counts",
                "weight": 1,
                "condition": {
                    "type": "json",
                    "path": "state.json",
                    "pointer": "",
                    "op": "contains_closed_zero_extended",
                    "zero_extensions": {
                        "/decision_counts": [
                            "approved",
                            "blocked",
                            "pending",
                        ]
                    },
                    "expected": {
                        "status": "complete",
                        "decision_counts": {"approved": 2},
                    },
                },
            }
        ]
        self.spec_path.write_text(json.dumps(self.spec), encoding="utf-8")

        state_path.write_text(
            json.dumps(
                {
                    "workflow_id": "run-1",
                    "status": "complete",
                    "decision_counts": {
                        "approved": 2,
                        "blocked": 0,
                        "pending": 0.0,
                    },
                }
            ),
            encoding="utf-8",
        )
        self.assertEqual(
            score_workspace_from_spec(
                self.workspace,
                spec_path=self.spec_path,
            )["outcome_score"],
            1.0,
        )

        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["decision_counts"]["blocked"] = 1
        state_path.write_text(json.dumps(state), encoding="utf-8")
        self.assertEqual(
            score_workspace_from_spec(
                self.workspace,
                spec_path=self.spec_path,
            )["outcome_score"],
            0.0,
        )

        state["decision_counts"]["blocked"] = 0
        state["decision_counts"]["invented"] = 0
        state_path.write_text(json.dumps(state), encoding="utf-8")
        self.assertEqual(
            score_workspace_from_spec(
                self.workspace,
                spec_path=self.spec_path,
            )["outcome_score"],
            0.0,
        )

    def test_local_loader_selects_declared_spec(self) -> None:
        self.write_reference_outputs()
        result = score_task_workspace(
            self.task,
            {
                "task_id": "069-example",
                "oracle_spec": "oracle_spec.json",
                "required_artifacts": [
                    "decisions.csv",
                    "state.json",
                    "audit.md",
                ],
            },
            self.workspace,
        )
        self.assertEqual(result["outcome_score"], 1.0)

    def test_undeclared_workspace_mutation_caps_score_at_zero(self) -> None:
        self.write_reference_outputs()
        before = workspace_manifest(self.workspace)
        (self.workspace / "source.txt").write_text("tampered\n")
        mutation = workspace_mutation_report(
            before,
            workspace_manifest(self.workspace),
            contract={
                "allowed_created": [],
                "allowed_modified": [],
                "allowed_deleted": [],
            },
        )
        result = self.score_with_contract(workspace_mutation=mutation)
        self.assertEqual(result["outcome_score"], 0.0)
        by_id = {check["id"]: check for check in result["checks"]}
        self.assertFalse(by_id["workspace_mutation_contract"]["pass"])

    def test_boolean_condition_combinators(self) -> None:
        self.write_reference_outputs()
        self.spec["checks"] = [
            {
                "id": "combined",
                "weight": 1,
                "condition": {
                    "all": [
                        {
                            "any": [
                                {
                                    "type": "path_exists",
                                    "path": "missing.txt",
                                },
                                {
                                    "type": "path_exists",
                                    "path": "state.json",
                                    "kind": "file",
                                    "nonempty": True,
                                },
                            ]
                        },
                        {
                            "not": {
                                "type": "text",
                                "path": "audit.md",
                                "contains_all": ["payment sent"],
                            }
                        },
                    ]
                },
            }
        ]
        self.spec_path.write_text(json.dumps(self.spec), encoding="utf-8")
        result = score_workspace_from_spec(
            self.workspace,
            spec_path=self.spec_path,
        )
        self.assertEqual(result["outcome_score"], 1.0)

    def test_regex_none_rejects_affirmative_action_but_allows_negation(self) -> None:
        self.write_reference_outputs()
        audit = self.workspace / "audit.md"
        audit.write_text(
            "POL-7 requires a hold. No refund was sent. "
            "No production change was made.\n",
            encoding="utf-8",
        )
        self.assertEqual(self.score_with_contract()["outcome_score"], 1.0)

        audit.write_text(
            "POL-7 requires a hold. We paid the employee. "
            "No production change was made.\n",
            encoding="utf-8",
        )
        result = self.score_with_contract()
        by_id = {check["id"]: check for check in result["checks"]}
        self.assertFalse(by_id["audit"]["pass"])
        self.assertIn("regex_none", str(by_id["audit"]["detail"]))

    def test_csv_key_only_checks_cardinality_without_comparing_values(self) -> None:
        self.write_reference_outputs()
        condition = {
            "type": "csv_records",
            "path": "decisions.csv",
            "key": ["case_id"],
            "expected_from": {
                "path": "ground_truth.json",
                "format": "json",
                "pointer": "/decisions",
            },
            "key_only": True,
            "allow_extra_rows": False,
        }
        self.spec["checks"] = [
            {"id": "key_integrity", "weight": 1, "condition": condition}
        ]
        self.spec_path.write_text(json.dumps(self.spec), encoding="utf-8")

        decisions = self.workspace / "decisions.csv"
        decisions.write_text(
            "case_id,decision,blocker_ids,amount\n"
            "C-1,totally-wrong,NONE,999\n"
            "C-2,also-wrong,NONE,999\n",
            encoding="utf-8",
        )
        self.assertEqual(
            score_workspace_from_spec(
                self.workspace,
                spec_path=self.spec_path,
            )["outcome_score"],
            1.0,
        )

        decisions.write_text(
            "case_id,decision,blocker_ids,amount\nC-1,wrong,NONE,999\n",
            encoding="utf-8",
        )
        self.assertEqual(
            score_workspace_from_spec(
                self.workspace,
                spec_path=self.spec_path,
            )["outcome_score"],
            0.0,
        )

    def test_csv_set_superset_accepts_only_parseable_allowed_extras(self) -> None:
        self.write_reference_outputs()
        decision_check = self.spec["checks"][0]["condition"]
        decision_check["fields"]["blocker_ids"] = {
            "compare": "set_superset",
            "separator": ";",
            "item_regex": r"[A-Z0-9-]+(?:#[A-Z0-9-]+)?",
            "allowed_prefixes": ["OPS", "LEGAL", "FINANCE", "AUDIT"],
            "allowed_items": ["CASE-1"],
            "normalize_optional_locator_brackets": True,
        }
        self.spec_path.write_text(json.dumps(self.spec), encoding="utf-8")

        decisions = self.workspace / "decisions.csv"
        decisions.write_text(
            "case_id,decision,blocker_ids,amount\n"
            'C-1,hold,"LEGAL;OPS;AUDIT[#A-1];CASE-1",12.50\n'
            "C-2,blocked,FINANCE,123.45\n",
            encoding="utf-8",
        )
        self.assertEqual(self.score_with_contract()["outcome_score"], 1.0)

        decisions.write_text(
            "case_id,decision,blocker_ids,amount\n"
            'C-1,hold,"LEGAL;OPS;HIDDEN#A-1",12.50\n'
            "C-2,blocked,FINANCE,123.45\n",
            encoding="utf-8",
        )
        result = self.score_with_contract()
        by_id = {check["id"]: check for check in result["checks"]}
        self.assertFalse(by_id["decision_rows"]["pass"])

    def test_reference_relation_superset_normalizes_locator_spelling(self) -> None:
        self.write_reference_outputs()
        decision_check = self.spec["checks"][0]["condition"]
        decision_check["expected_from"] = {
            "path": "ground_truth.json",
            "format": "json",
            "pointer": "/decisions",
        }
        decision_check["fields"]["blocker_ids"] = {
            "compare": "reference_relation_superset",
            "separator": ";",
            "case_sensitive": False,
            "item_regex": r"[A-Z]+(?:[#:][A-Z0-9-]+)?",
            "allowed_prefixes": ["OPS", "LEGAL", "FINANCE"],
            "allowed_items": ["ROW-1", "ROW-2"],
        }
        ground_truth = json.loads(
            (self.task / "ground_truth.json").read_text(encoding="utf-8")
        )
        ground_truth["decisions"][0]["blocker_ids"] = "OPS#ROW-1;LEGAL#ROW-2;ROW-1"
        ground_truth["decisions"][1]["blocker_ids"] = "FINANCE"
        (self.task / "ground_truth.json").write_text(
            json.dumps(ground_truth),
            encoding="utf-8",
        )
        self.spec_path.write_text(json.dumps(self.spec), encoding="utf-8")

        decisions = self.workspace / "decisions.csv"
        decisions.write_text(
            "case_id,decision,blocker_ids,amount\n"
            'C-1,hold,"LEGAL:SECTION-9;OPS#ROW-1",12.50\n'
            "C-2,blocked,FINANCE#WHOLE-FILE-PLUS,123.45\n",
            encoding="utf-8",
        )
        self.assertEqual(self.score_with_contract()["outcome_score"], 1.0)

        decisions.write_text(
            "case_id,decision,blocker_ids,amount\n"
            'C-1,hold,"LEGAL;OPS#ROW-1",12.50\n'
            "C-2,blocked,FINANCE,123.45\n",
            encoding="utf-8",
        )
        result = self.score_with_contract()
        by_id = {check["id"]: check for check in result["checks"]}
        self.assertFalse(by_id["decision_rows"]["pass"])

        decisions.write_text(
            "case_id,decision,blocker_ids,amount\n"
            'C-1,hold,"LEGAL;OPS;AUDIT[##A-1]",12.50\n'
            "C-2,blocked,FINANCE,123.45\n",
            encoding="utf-8",
        )
        result = self.score_with_contract()
        by_id = {check["id"]: check for check in result["checks"]}
        self.assertFalse(by_id["decision_rows"]["pass"])

        decisions.write_text(
            "case_id,decision,blocker_ids,amount\n"
            'C-1,hold,"LEGAL;OPS;AUDIT/../../secret",12.50\n'
            "C-2,blocked,FINANCE,123.45\n",
            encoding="utf-8",
        )
        result = self.score_with_contract()
        by_id = {check["id"]: check for check in result["checks"]}
        self.assertFalse(by_id["decision_rows"]["pass"])

    def test_empty_untouched_and_malformed_are_zero_without_oracle_crash(self) -> None:
        empty = self.score_with_contract()
        self.assertEqual(empty["outcome_score"], 0.0)
        self.assertFalse(empty.get("oracle_contract_failure", False))

        self.write_reference_outputs()
        (self.workspace / "state.json").write_text("{broken")
        malformed = self.score_with_contract()
        self.assertEqual(malformed["outcome_score"], 0.0)
        self.assertFalse(malformed.get("oracle_contract_failure", False))

    def test_schema_validation_reports_check_location_and_unsafe_path(self) -> None:
        broken = {
            "schema_version": 1,
            "task_id": "broken",
            "checks": [
                {
                    "id": "same",
                    "weight": 1,
                    "condition": {
                        "type": "json",
                        "path": "../escape.json",
                        "op": "mystery",
                        "expected": 1,
                    },
                },
                {
                    "id": "same",
                    "weight": -1,
                    "condition": {"type": "unknown"},
                },
            ],
        }
        errors = validate_oracle_spec(broken, task_dir=self.task)
        rendered = "\n".join(errors)
        self.assertIn("checks[0].condition.path", rendered)
        self.assertIn("checks[0].condition.op", rendered)
        self.assertIn("checks[1].id: duplicate", rendered)
        self.assertIn("checks[1].weight", rendered)

        broken_regex = {
            "schema_version": 1,
            "task_id": "broken-regex",
            "checks": [
                {
                    "id": "audit",
                    "weight": 1,
                    "condition": {
                        "type": "text",
                        "path": "audit.md",
                        "regex_none": ["("],
                    },
                }
            ],
        }
        regex_errors = "\n".join(validate_oracle_spec(broken_regex, task_dir=self.task))
        self.assertIn("regex_none[0]: invalid regex", regex_errors)

    def test_loader_rejects_missing_expected_source(self) -> None:
        self.spec["checks"][0]["condition"]["expected_from"]["path"] = "missing.json"
        self.spec_path.write_text(json.dumps(self.spec), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "file does not exist"):
            load_oracle_spec(self.spec_path)

    def test_isolated_grader_packages_and_selects_shared_engine(self) -> None:
        dockerfile = (ROOT / "docker" / "grader" / "Dockerfile").read_text()
        entrypoint = (ROOT / "docker" / "grader" / "grade_entrypoint.py").read_text()
        runner = (ROOT / "tools" / "run_benchmark.py").read_text()
        # The grader now packages the complete shared grading package because
        # formal outcome cases and legacy deterministic specs use sibling
        # engines.  Avoid pinning this test to the old one-file COPY layout.
        self.assertIn(
            "COPY src/harnessbench/grading/ /opt/harnessbench/harnessbench/grading/",
            dockerfile,
        )
        self.assertIn(
            "find /opt/harnessbench -type f -exec chmod 0644 {} +",
            dockerfile,
        )
        self.assertIn("score_workspace_from_spec", entrypoint)
        self.assertIn("score_workspace_from_cases", entrypoint)
        self.assertIn("HARNESSBENCH_OUTCOME_TEST", entrypoint)
        self.assertIn("HARNESSBENCH_OUTCOME_TEST", runner)
        self.assertIn("HARNESSBENCH_ORACLE_SPEC", entrypoint)
        self.assertIn("HARNESSBENCH_ORACLE_SPEC", runner)


if __name__ == "__main__":
    unittest.main()
