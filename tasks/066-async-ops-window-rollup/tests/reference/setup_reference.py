from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any


def apply_reference(
    workspace: Path,
    runtime: Path,
    runtime_state: dict[str, Any],
) -> None:
    """Materialize the complete observed inbox without waiting for wall time."""
    del runtime, runtime_state
    task_dir = Path(__file__).resolve().parents[2]
    inbox = workspace / "ops_updates"
    inbox.mkdir(parents=True, exist_ok=True)
    for source in sorted((task_dir / "environment" / "delayed_updates").glob("*.json")):
        shutil.copyfile(source, inbox / source.name)
