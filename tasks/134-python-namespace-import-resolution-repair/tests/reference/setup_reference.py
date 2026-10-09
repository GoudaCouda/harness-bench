from __future__ import annotations
import subprocess
from pathlib import Path
from typing import Any

def apply_reference(workspace: Path, runtime: Path, runtime_state: dict[str, Any]) -> None:
    del runtime, runtime_state
    marker=workspace/"repo/services/api/src/acme/__init__.py"
    marker.unlink()
    subprocess.run(["python3","tools/probe_imports.py"],cwd=workspace/"repo",check=True,stdout=subprocess.PIPE,text=True)
