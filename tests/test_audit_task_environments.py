from __future__ import annotations

import importlib.util
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "tools/task_maintenance/audit_task_environments.py"
SPEC = importlib.util.spec_from_file_location("audit_task_environments", PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def make_task(root: Path, *, service: bool = False) -> Path:
    task = root / "001-example"
    (task / "workspace/repo").mkdir(parents=True)
    (task / "environment").mkdir()
    (task / "tests").mkdir()
    metadata = {
        "task_id": "001-example",
        "title": "Example",
        "domain": "Software Engineering",
        "prompt_file": "instruction.md",
        "workspace_dir": "workspace",
    }
    (task / "task.yaml").write_text(yaml.safe_dump(metadata), encoding="utf-8")
    (task / "instruction.md").write_text("Run `sqlite3` and inspect output.\n", encoding="utf-8")
    dockerfile = "FROM python:3.12\n"
    if service:
        dockerfile += 'EXPOSE 8080\nENTRYPOINT ["python3", "service.py"]\n'
    (task / "environment/Dockerfile").write_text(dockerfile, encoding="utf-8")
    (task / "workspace/repo/check.py").write_text(
        "import sqlite3, subprocess\nsubprocess.run(['git', 'status'])\n",
        encoding="utf-8",
    )
    return task / "task.yaml"


def test_inventory_is_evidence_not_an_automatic_review(tmp_path: Path) -> None:
    row = MODULE.inspect_task(make_task(tmp_path))
    assert row["manual_review_required"] is True
    assert row["manual_review_status"] == "pending"
    assert "sqlite3" in row["python_imports"]
    assert "git" in row["subprocess_commands"]
    assert "sqlite3" in row["prompt_command_hints"]
    assert row["static_classification"] == "shared_baseline_candidate"


def test_service_dockerfile_is_not_mislabeled_as_agent_overlay(tmp_path: Path) -> None:
    row = MODULE.inspect_task(make_task(tmp_path, service=True))
    assert row["static_classification"] == "service_candidate"
    assert row["dockerfile"]["has_entrypoint"] is True
    assert row["dockerfile"]["exposed_ports"] == ["8080"]
