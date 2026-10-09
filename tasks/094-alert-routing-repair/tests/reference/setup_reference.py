"""Exercise a hidden trusted reference driver twice against the task service."""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any


def _load_hooks(task_root: Path):
    path = task_root / "environment" / "hooks.py"
    spec = importlib.util.spec_from_file_location("hb094_reference_hooks", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load task-094 runtime hooks")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def apply_reference(
    workspace: Path,
    runtime: Path,
    state: dict[str, Any],
) -> None:
    del runtime
    hooks = _load_hooks(Path(__file__).resolve().parents[2])
    environment = {
        "ALERTMANAGER_URL": str(state["_local_alertmanager_url"]),
        "HOME": "/tmp",
        "LANG": "C.UTF-8",
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "PYTHONDONTWRITEBYTECODE": "1",
        "NO_PROXY": "127.0.0.1,localhost",
        "no_proxy": "127.0.0.1,localhost",
    }
    command = [
        sys.executable,
        str(
            Path(__file__).resolve().parents[1]
            / "ground_truth"
            / "reference_apply.py"
        ),
        "--alertmanager-url",
        str(state["_local_alertmanager_url"]),
    ]
    try:
        for run in (1, 2):
            completed = subprocess.run(
                command,
                cwd=workspace / "repo",
                env=environment,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            if completed.returncode != 0:
                raise RuntimeError(
                    f"reference apply run {run} failed: "
                    + (completed.stderr.strip() or completed.stdout.strip())
                )
        hooks.after_round(
            {"workspace": workspace, "round_index": 0},
            state,
            SimpleNamespace(ok=True),
        )
    finally:
        hooks.cleanup_runtime({}, state)
        private_root = state.get("_private_root")
        if isinstance(private_root, Path):
            shutil.rmtree(private_root, ignore_errors=True)
