from __future__ import annotations

import sys
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from run_benchmark import BenchmarkTask, render_prompt  # noqa: E402


def load_task(task_id: str) -> BenchmarkTask:
    task_dir = ROOT / "tasks" / task_id
    metadata = yaml.safe_load((task_dir / "task.yaml").read_text())
    return BenchmarkTask(
        task_id=task_id,
        title=str(metadata["title"]),
        domain=str(metadata["domain"]),
        difficulty=str(metadata["difficulty"]),
        task_dir=task_dir,
        metadata=metadata,
        definition_sha256="0" * 64,
    )


class TaskPromptContractTests(unittest.TestCase):
    def test_rendered_prompt_discloses_the_enforced_workspace_contract(self) -> None:
        task = load_task("004-office-docs")

        prompt = render_prompt(
            task,
            str(task.metadata["prompt_file"]),
            ROOT / ".test-workspace",
            ROOT / ".test-runtime",
            {},
        )

        self.assertIn("## Enforced workspace change contract", prompt)
        self.assertIn(
            "compares the final state of `/workspace` after every round", prompt
        )
        self.assertIn("only these final-state differences may remain", prompt)
        self.assertIn(
            "Create: `regional_sales_memo.docx`, `regional_rollup.csv`",
            prompt,
        )
        self.assertIn("Modify: none", prompt)
        self.assertIn("Delete: none", prompt)
        self.assertIn(
            "Do not leave any other created, modified, or deleted path", prompt
        )
        self.assertIn("persistent scratch helpers in `/runtime`", prompt)
        self.assertIn("single-round temporary files in `/tmp`", prompt)
        self.assertNotIn(
            "when the task explicitly requires their cleanup",
            prompt,
        )

    def test_every_main_task_prompt_receives_its_exact_enforced_contract(self) -> None:
        task_yamls = sorted(ROOT.glob("tasks/[0-9][0-9][0-9]-*/task.yaml"))
        self.assertEqual(len(task_yamls), 274)
        for task_yaml in task_yamls:
            task_id = task_yaml.parent.name
            with self.subTest(task_id=task_id):
                task = load_task(task_id)
                contract = task.metadata["mutation_contract"]
                prompt_files = task.metadata.get("prompt_files") or [
                    task.metadata["prompt_file"]
                ]
                for prompt_name in prompt_files:
                    rendered = render_prompt(
                        task,
                        str(prompt_name),
                        ROOT / ".test-workspace",
                        ROOT / ".test-runtime",
                        {},
                    )
                    self.assertEqual(
                        rendered.count("## Enforced workspace change contract"),
                        1,
                    )
                    self.assertNotIn("$WORKSPACE", rendered)
                    for field, label in (
                        ("allowed_created", "Create"),
                        ("allowed_modified", "Modify"),
                        ("allowed_deleted", "Delete"),
                    ):
                        paths = contract[field]
                        value = (
                            ", ".join(f"`{path}`" for path in paths)
                            if paths
                            else "none"
                        )
                        self.assertIn(f"- {label}: {value}", rendered)

    def test_task_037_declares_every_prompt_required_final_artifact(self) -> None:
        task_dir = ROOT / "tasks" / "037-multiday-project-state"
        metadata = yaml.safe_load((task_dir / "task.yaml").read_text())
        required = {str(value).rstrip("/") for value in metadata["required_artifacts"]}
        self.assertEqual(
            required,
            {
                "decision_register.csv",
                "project_plan.json",
                "risk_register.csv",
                "steering_handoff.md",
            },
        )
        final_prompt = (task_dir / "instruction.md").read_text()
        self.assertIn("decision_register.csv", final_prompt)
        self.assertIn("project_plan.json", final_prompt)
        self.assertIn("risk_register.csv", final_prompt)
        self.assertIn("steering_handoff.md", final_prompt)


if __name__ == "__main__":
    unittest.main()
