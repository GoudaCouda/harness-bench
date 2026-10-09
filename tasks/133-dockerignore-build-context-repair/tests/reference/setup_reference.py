from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any


def apply_reference(workspace: Path, runtime: Path, runtime_state: dict[str, Any]) -> None:
    del runtime, runtime_state
    subprocess.run(["python3", "tools/audit_context.py"], cwd=workspace / "repo", check=True, stdout=subprocess.PIPE, text=True)
