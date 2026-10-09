from __future__ import annotations

import os
from pathlib import Path

import pytest

from harnessbench.grading.task_checks import sources_unchanged, workspace_redline_violations


def test_regular_auxiliary_files_and_cache_are_not_redlines(tmp_path: Path) -> None:
    seed = tmp_path / "seed"
    workspace = tmp_path / "workspace"
    seed.mkdir()
    workspace.mkdir()
    (seed / "controller.py").write_text("print('seed')\n", encoding="utf-8")
    (workspace / "controller.py").write_text("print('seed')\n", encoding="utf-8")
    (workspace / "notes.md").write_text("local analysis\n", encoding="utf-8")
    (workspace / "scratch").mkdir()
    (workspace / "scratch/query.sql").write_text("select 1;\n", encoding="utf-8")
    (workspace / "__pycache__").mkdir()
    (workspace / "__pycache__/helper.cpython-312.pyc").write_bytes(b"cache")

    assert workspace_redline_violations(workspace, seed_root=seed) == []


def test_links_special_files_and_executable_payloads_are_redlines(
    tmp_path: Path,
) -> None:
    if not hasattr(os, "mkfifo"):
        pytest.skip("FIFO creation is not available on this platform")
    seed = tmp_path / "seed"
    workspace = tmp_path / "workspace"
    seed.mkdir()
    workspace.mkdir()
    (workspace / "target.txt").write_text("target\n", encoding="utf-8")
    (workspace / "linked.txt").symlink_to("target.txt")
    script = workspace / "run.sh"
    script.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    script.chmod(0o755)
    fifo = workspace / "events.fifo"
    os.mkfifo(fifo)

    violations = workspace_redline_violations(workspace, seed_root=seed)

    assert "symlink:linked.txt" in violations
    assert "executable_payload:run.sh" in violations
    assert "special:events.fifo" in violations


def test_seed_executable_is_left_to_source_integrity_check(tmp_path: Path) -> None:
    seed = tmp_path / "seed"
    workspace = tmp_path / "workspace"
    seed.mkdir()
    workspace.mkdir()
    for root in (seed, workspace):
        controller = root / "controller.py"
        controller.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
        controller.chmod(0o755)

    assert workspace_redline_violations(workspace, seed_root=seed) == []


def test_sources_unchanged_ignores_generated_python_bytecode(tmp_path: Path) -> None:
    task_root = tmp_path / "task"
    seed = task_root / "workspace"
    workspace = tmp_path / "candidate"
    (seed / "repo/tests/__pycache__").mkdir(parents=True)
    (seed / "repo/tests/__pycache__/test_public.cpython-312.pyc").write_bytes(
        b"generated cache"
    )
    (seed / "repo/input.json").write_text("{}", encoding="utf-8")
    (workspace / "repo").mkdir(parents=True)
    (workspace / "repo/input.json").write_text("{}", encoding="utf-8")

    unchanged, changed = sources_unchanged(task_root, workspace)

    assert unchanged is True
    assert changed == []
