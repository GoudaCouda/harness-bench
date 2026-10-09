"""Apply the known-correct clean-history integration."""
from __future__ import annotations

from pathlib import Path
from typing import Any


def apply_reference(workspace: Path, runtime: Path, runtime_state: dict[str, Any]) -> None:
    remote = Path(str(runtime_state["REMOTE_PATH"]))
    helper = runtime_state.get("_RUN_TRUSTED_HELPER")
    if not callable(helper):
        raise RuntimeError("reference setup lacks the trusted helper")
    script = r"""
import os
import subprocess
from pathlib import Path

workspace = Path(os.environ["HB_WORKSPACE"])

def git(*args: str) -> str:
    completed = subprocess.run(["git", "-C", str(workspace), *args], text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip())
    return completed.stdout

git("fetch", "origin", "feature/pr-add-doc")
content = git("show", "origin/feature/pr-add-doc:CONTRIBUTING.md")
(workspace / "CONTRIBUTING.md").write_text(content, encoding="utf-8")
git("add", "CONTRIBUTING.md")
git("commit", "-m", "docs: cleanly integrate reviewed contribution guide")
git("push", "origin", "main")
"""
    helper(["python3", "-c", script])
    if remote != runtime / "remote.git":
        raise RuntimeError("reference hook returned an unexpected remote path")
