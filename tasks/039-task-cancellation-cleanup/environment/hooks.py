from __future__ import annotations

from typing import Any


def prepare_runtime(context: dict[str, Any]) -> dict[str, Any]:
    del context
    return {}


def after_round(
    context: dict[str, Any], runtime_state: dict[str, Any], adapter_result: Any
) -> dict[str, Any]:
    del context, adapter_result
    return runtime_state


def cleanup_runtime(context: dict[str, Any], runtime_state: dict[str, Any]) -> None:
    del context, runtime_state
