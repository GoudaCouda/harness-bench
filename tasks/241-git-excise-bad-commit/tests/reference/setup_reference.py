"""Apply the known-correct history rewrite."""
from __future__ import annotations

from pathlib import Path
from typing import Any


def apply_reference(workspace: Path, runtime: Path, runtime_state: dict[str, Any]) -> None:
    helper = runtime_state.get("_RUN_TRUSTED_HELPER")
    if not callable(helper):
        raise RuntimeError("reference setup lacks the trusted helper")
    script = r"""
import os
import subprocess
from pathlib import Path

workspace = Path(os.environ["HB_WORKSPACE"])

def git(*args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(workspace), *args],
        text=True, capture_output=True, check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip())
    return completed.stdout

git("fetch", "origin", "work/cutover")
git("checkout", "main")
git("cherry-pick", "good-app")
git("cherry-pick", "good-docs")
git("push", "origin", "main")
"""
    helper(["python3", "-c", script])
