from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


def _initialize(workspace: Path) -> None:
    database = workspace / "repo/state/projection.db"
    if database.exists():
        return
    database.parent.mkdir(parents=True, exist_ok=True)
    sql = (workspace / "repo/seed/initial_state.sql").read_text(encoding="utf-8")
    connection = sqlite3.connect(database)
    try:
        connection.executescript(sql)
        connection.commit()
    finally:
        connection.close()


def prepare_runtime(context: dict[str, Any]) -> dict[str, Any]:
    _initialize(Path(context["workspace"]))
    return {}


def after_round(
    context: dict[str, Any], runtime_state: dict[str, Any], adapter_result: Any
) -> dict[str, Any]:
    del context, adapter_result
    return runtime_state


def cleanup_runtime(context: dict[str, Any], runtime_state: dict[str, Any]) -> None:
    del context, runtime_state
