from __future__ import annotations

import hashlib
import threading
import time
from pathlib import Path
from typing import Any


_INJECTORS: dict[str, tuple[threading.Event, threading.Thread]] = {}


def prepare_runtime(context: dict[str, Any]) -> dict[str, Any]:
    workspace = Path(context["workspace"])
    task_dir = (
        Path(context["task"].task_dir)
        if "task" in context
        else Path(__file__).resolve().parent
    )
    inbox = workspace / "ops_updates"
    inbox.mkdir(parents=True, exist_ok=True)
    (workspace).mkdir(parents=True, exist_ok=True)

    runtime_state: dict[str, Any] = {
        "OPS_UPDATE_INJECTION_SECONDS": "6,11,16,22,28,29",
        # Internal trusted state; the runner excludes non-scalars from the
        # published result. Only files this injector actually committed may be
        # subtracted from the agent's workspace mutation delta.
        "_injected_files": [],
    }
    # The reference builder materializes every delayed event synchronously.
    # Starting a real-time injector here would outlive its temporary workspace
    # and produce a background-thread race after the oracle audit finishes.
    if context.get("reference_mode") is True:
        return runtime_state

    start = time.time()
    stop = threading.Event()

    def inject() -> None:
        schedule = [
            (6, "update_003.json"),
            (11, "update_dup_002.json"),
            (16, "update_old.json"),
            (22, "update_004.json"),
            (28, "update_late.json"),
            (29, "update_005.json"),
        ]
        source_dir = task_dir / "environment" / "delayed_updates"
        for delay, name in schedule:
            remaining = start + delay - time.time()
            if remaining > 0 and stop.wait(remaining):
                return
            if stop.is_set():
                return
            try:
                source = source_dir / name
                destination = inbox / name
                temporary = destination.with_name(f".{name}.partial")
                temporary.write_bytes(source.read_bytes())
                temporary.chmod(0o644)
                temporary.replace(destination)
                destination.chmod(0o644)
                runtime_state["_injected_files"].append(name)
            except FileNotFoundError:
                # A failed/aborted trial may already have removed its isolated
                # workspace. That is normal cleanup, not a hook failure.
                return

    thread = threading.Thread(target=inject, daemon=True)
    _INJECTORS[str(workspace.resolve())] = (stop, thread)
    thread.start()
    return runtime_state


def environment_mutations(
    context: dict[str, Any],
    runtime_state: dict[str, Any],
    round_index: int,
) -> dict[str, dict[str, dict[str, object]]]:
    """Declare content-addressed files owned by the asynchronous environment."""
    del round_index
    task_dir = Path(context["task"].task_dir)
    created: dict[str, dict[str, object]] = {}
    injected = runtime_state.get("_injected_files", [])
    if not isinstance(injected, list):
        raise RuntimeError("async injector state is malformed")
    for name in sorted({str(value) for value in injected}):
        source = task_dir / "environment" / "delayed_updates" / name
        if not source.is_file():
            raise RuntimeError(f"injected source disappeared: {name}")
        payload = source.read_bytes()
        created[f"ops_updates/{source.name}"] = {
            "kind": "file",
            "sha256": hashlib.sha256(payload).hexdigest(),
            "size": len(payload),
        }
    return {"created": created, "modified": {}, "deleted": {}}


def quiesce_environment(
    context: dict[str, Any],
    runtime_state: dict[str, Any],
    round_index: int,
) -> None:
    del runtime_state, round_index
    key = str(Path(context["workspace"]).resolve())
    injector = _INJECTORS.get(key)
    if injector is None:
        return
    stop, thread = injector
    stop.set()
    thread.join(timeout=2)
    if thread.is_alive():
        raise RuntimeError("asynchronous update injector did not quiesce")


def after_round(
    context: dict[str, Any], runtime_state: dict[str, Any], adapter_result: Any
) -> dict[str, Any]:
    return runtime_state


def cleanup_runtime(context: dict[str, Any], runtime_state: dict[str, Any]) -> None:
    del runtime_state
    key = str(Path(context["workspace"]).resolve())
    injector = _INJECTORS.pop(key, None)
    if injector is None:
        return
    stop, thread = injector
    stop.set()
    thread.join(timeout=1)
