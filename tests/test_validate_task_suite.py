from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import sys

import yaml

MAINTENANCE = Path(__file__).resolve().parents[1] / "tools" / "task_maintenance"
if str(MAINTENANCE) not in sys.path:
    sys.path.insert(0, str(MAINTENANCE))

from validate_task_suite import (  # noqa: E402
    REQUIRED_DESIGN_SECTIONS,
    formal_environment_directory_required,
    validate_design_record,
    validate_formal_environment_dockerfile,
    validate_semantic_judge_record,
    validate_workspace_seed,
)

ROOT = Path(__file__).resolve().parents[1]


class ValidateTaskSuiteTests(unittest.TestCase):
    def _write_design(self, task_dir: Path, *, provenance_body: str) -> None:
        sections = []
        for section in REQUIRED_DESIGN_SECTIONS:
            body = provenance_body if section == "## 2. Idea provenance" else "Review."
            sections.append(f"{section}\n\n{body}")
        sections.append("- **Private user logs:** None were used.")
        (task_dir / "design.md").write_text(
            "\n\n".join(sections) + "\n",
            encoding="utf-8",
        )

    def test_source_url_must_be_in_idea_provenance_section(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task_dir = Path(temporary)
            self._write_design(
                task_dir,
                provenance_body="No public source was recorded.",
            )
            with_local_runtime_url = (task_dir / "design.md").read_text(
                encoding="utf-8"
            ) + "\nRuntime endpoint: http://127.0.0.1:8765/\n"
            (task_dir / "design.md").write_text(
                with_local_runtime_url,
                encoding="utf-8",
            )

            errors = validate_design_record(
                task_dir,
                {"task_id": "001-example", "design_file": "design.md"},
                expansion=False,
            )

        self.assertIn(
            "001-example: idea-provenance section has no source URL",
            errors,
        )

    def test_public_provenance_url_satisfies_the_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task_dir = Path(temporary)
            self._write_design(
                task_dir,
                provenance_body="Source: https://example.com/workflow",
            )

            errors = validate_design_record(
                task_dir,
                {"task_id": "001-example", "design_file": "design.md"},
                expansion=False,
            )

        self.assertNotIn(
            "001-example: idea-provenance section has no source URL",
            errors,
        )

    def test_fresh_export_may_omit_an_empty_workspace_seed(self) -> None:
        for task_id in ("003-git-pr-merge",):
            with self.subTest(task_id=task_id):
                source_task = ROOT / "tasks" / task_id
                metadata = yaml.safe_load(
                    (source_task / "task.yaml").read_text(encoding="utf-8")
                )
                source_seed = source_task / metadata["workspace_dir"]
                if source_seed.exists():
                    self.assertTrue(source_seed.is_dir())
                    self.assertEqual(list(source_seed.iterdir()), [])

                with tempfile.TemporaryDirectory() as temporary:
                    exported_task = Path(temporary) / task_id
                    exported_task.mkdir()
                    self.assertFalse(
                        (exported_task / metadata["workspace_dir"]).exists()
                    )
                    self.assertEqual(
                        validate_workspace_seed(exported_task, metadata),
                        [],
                    )

    def test_present_workspace_seed_must_be_a_real_safe_directory(self) -> None:
        metadata = {
            "task_id": "001-example",
            "workspace_dir": "workspace",
        }
        with tempfile.TemporaryDirectory() as temporary:
            task_dir = Path(temporary)
            workspace = task_dir / "workspace"
            workspace.write_text("not a directory\n", encoding="utf-8")
            self.assertEqual(
                validate_workspace_seed(task_dir, metadata),
                ["001-example: unsafe workspace seed"],
            )

        with tempfile.TemporaryDirectory() as temporary:
            task_dir = Path(temporary)
            outside = task_dir / "outside"
            outside.mkdir()
            (task_dir / "workspace").symlink_to(outside, target_is_directory=True)
            self.assertEqual(
                validate_workspace_seed(task_dir, metadata),
                ["001-example: unsafe workspace seed"],
            )

    def test_empty_shared_environment_does_not_require_placeholder_directory(
        self,
    ) -> None:
        self.assertFalse(
            formal_environment_directory_required(
                {
                    "schema_version": 1,
                    "mode": "shared",
                    "abi": "harnessbench-debian-bookworm-v1",
                    "required_tools": {},
                    "grader": {},
                    "services": [],
                }
            )
        )

    def test_file_backed_or_overlay_environment_requires_directory(self) -> None:
        self.assertTrue(
            formal_environment_directory_required(
                {
                    "schema_version": 1,
                    "mode": "shared",
                    "verifier": "verify_environment.py",
                }
            )
        )
        self.assertTrue(
            formal_environment_directory_required(
                {"schema_version": 1, "mode": "overlay"}
            )
        )

    def test_debian_formal_environment_has_named_writable_identity(self) -> None:
        dockerfile = """\
FROM python@example AS fetch
RUN touch /tool
FROM python@example
RUN groupadd --gid 1000 agent \\
    && useradd --uid 1000 --gid 1000 --create-home \\
       --home-dir /home/agent --shell /bin/sh --no-log-init agent \\
    && install -d -o agent -g agent /workspace
ENV HOME=/home/agent PYTHONUNBUFFERED=1
WORKDIR /workspace
USER agent:agent
"""

        self.assertEqual(
            validate_formal_environment_dockerfile("001-example", dockerfile),
            [],
        )

    def test_alpine_formal_environment_has_named_writable_identity(self) -> None:
        dockerfile = """\
FROM alpine@example
RUN addgroup -g 1000 agent \\
    && adduser -u 1000 -G agent -h /home/agent -D agent \\
    && mkdir -p /workspace \\
    && chown agent:agent /workspace
ENV HOME=/home/agent
WORKDIR /workspace
USER agent:agent
"""

        self.assertEqual(
            validate_formal_environment_dockerfile("001-example", dockerfile),
            [],
        )

    def test_numeric_user_without_passwd_identity_is_rejected(self) -> None:
        dockerfile = """\
FROM python@example
ENV HOME=/tmp
WORKDIR /workspace
USER 1000:1000
"""

        errors = validate_formal_environment_dockerfile(
            "001-example",
            dockerfile,
        )

        self.assertTrue(any("must create group" in error for error in errors))
        self.assertTrue(any("must create user" in error for error in errors))
        self.assertTrue(any("HOME=/home/agent" in error for error in errors))
        self.assertTrue(any("final USER" in error for error in errors))
        self.assertTrue(any("final WORKDIR" in error for error in errors))

    def test_identity_created_only_in_discarded_stage_is_rejected(self) -> None:
        dockerfile = """\
FROM python@example AS discarded
RUN groupadd --gid 1000 agent \\
    && useradd --uid 1000 --gid 1000 --create-home \\
       --home-dir /home/agent agent
FROM python@example
ENV HOME=/home/agent
WORKDIR /home/agent
USER agent:agent
"""

        errors = validate_formal_environment_dockerfile(
            "001-example",
            dockerfile,
        )

        self.assertTrue(any("must create group" in error for error in errors))
        self.assertTrue(any("must create user" in error for error in errors))

    def test_semantic_rubric_requires_questions_and_matching_case_ids(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task_dir = Path(temporary)
            rubric = task_dir / "tests" / "ground_truth" / "semantic_judge.yaml"
            rubric.parent.mkdir(parents=True)
            rubric.write_text(
                yaml.safe_dump(
                    {
                        "criteria": [
                            {"id": "handoff_semantics", "description": "Too vague"}
                        ]
                    }
                ),
                encoding="utf-8",
            )
            builder = task_dir / "tests" / "test_outcome.py"
            builder.write_text("def build_semantic_judge_input(workspace): return {}\n")
            metadata = {
                "task_id": "001-example",
                "semantic_judge": {
                    "rubric_file": "tests/ground_truth/semantic_judge.yaml",
                    "input_builder": "tests/test_outcome.py",
                    "default_model": "agent",
                    "score_role": "bounded_case_fallback",
                    "case_map": {"handoff_semantics": "handoff"},
                    "max_fallback_weight": 0.2,
                },
            }

            errors = validate_semantic_judge_record(task_dir, metadata)

        self.assertTrue(
            any("invalid semantic judge rubric" in error for error in errors)
        )

    def test_valid_semantic_contract_passes_static_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task_dir = Path(temporary)
            rubric = task_dir / "tests" / "ground_truth" / "semantic_judge.yaml"
            rubric.parent.mkdir(parents=True)
            rubric.write_text(
                yaml.safe_dump(
                    {
                        "criteria": [
                            {
                                "id": "handoff_semantics",
                                "question": "Does the handoff close the workflow?",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            builder = task_dir / "tests" / "test_outcome.py"
            builder.write_text("def build_semantic_judge_input(workspace): return {}\n")
            metadata = {
                "task_id": "001-example",
                "semantic_judge": {
                    "rubric_file": "tests/ground_truth/semantic_judge.yaml",
                    "input_builder": "tests/test_outcome.py",
                    "default_model": "agent",
                    "score_role": "bounded_case_fallback",
                    "case_map": {"handoff_semantics": "handoff"},
                    "max_fallback_weight": 0.2,
                },
            }

            errors = validate_semantic_judge_record(task_dir, metadata)

        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
