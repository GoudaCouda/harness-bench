from __future__ import annotations

import ast
import asyncio
import json
from pathlib import Path

from harnessbench.grading.task_checks import (
    explicit_external_action_claims,
    observation,
    sources_unchanged,
    workspace_redline_violations,
)

TASK = Path(__file__).resolve().parents[1]
SEED = TASK / "workspace"
MUTABLE = ("repo/src/pool.py",)
FORBIDDEN_NAMES = {
    "open",
    "exec",
    "eval",
    "compile",
    "input",
    "breakpoint",
    "globals",
    "locals",
    "vars",
    "getattr",
    "setattr",
    "delattr",
    "help",
    "memoryview",
}
FORBIDDEN_ASYNCIO = {
    "open_connection",
    "start_server",
    "create_subprocess_exec",
    "create_subprocess_shell",
    "to_thread",
    "run_coroutine_threadsafe",
}


def _read(path, limit):
    try:
        if not path.is_file() or path.is_symlink() or path.stat().st_size > limit:
            return "", "missing, linked, or oversized"
        return path.read_text(encoding="utf-8"), "loaded"
    except (OSError, UnicodeError) as exc:
        return "", f"{type(exc).__name__}: {exc}"


def _load(source):
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return None, f"syntax error: {exc}"
    if (
        sum(1 for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom)))
        != 1
    ):
        return None, "source must import exactly asyncio"
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if (
                len(node.names) != 1
                or node.names[0].name != "asyncio"
                or node.names[0].asname is not None
            ):
                return None, "only plain import asyncio is allowed"
        elif isinstance(node, ast.ImportFrom):
            return None, "from-import is not allowed"
        elif isinstance(node, ast.Name) and node.id in FORBIDDEN_NAMES:
            return None, f"forbidden capability: {node.id}"
        elif isinstance(node, ast.Attribute):
            if node.attr.startswith("_"):
                return None, "private attribute access is not allowed"
            if (
                isinstance(node.value, ast.Name)
                and node.value.id == "asyncio"
                and node.attr in FORBIDDEN_ASYNCIO
            ):
                return None, f"forbidden asyncio capability: {node.attr}"
    queue_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "asyncio"
        and node.func.attr == "Queue"
    ]
    if len(queue_calls) != 1:
        return None, "one asyncio.Queue is required"
    queue_call = queue_calls[0]
    bounded = (
        len(queue_call.args) == 1
        and isinstance(queue_call.args[0], ast.Name)
        and queue_call.args[0].id == "queue_size"
    ) or any(
        keyword.arg == "maxsize"
        and isinstance(keyword.value, ast.Name)
        and keyword.value.id == "queue_size"
        for keyword in queue_call.keywords
    )
    if not bounded:
        return None, "Queue must be constructed with queue_size"
    functions = [
        node
        for node in tree.body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "run_batch"
    ]
    if len(functions) != 1:
        return None, "run_batch async function is required"

    real_import = __import__

    def safe_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name != "asyncio" or fromlist or level:
            raise ImportError("only asyncio is available")
        return real_import(name)

    builtins = {
        "__import__": safe_import,
        "all": all,
        "any": any,
        "bool": bool,
        "callable": callable,
        "dict": dict,
        "enumerate": enumerate,
        "Exception": Exception,
        "OverflowError": OverflowError,
        "float": float,
        "int": int,
        "isinstance": isinstance,
        "len": len,
        "list": list,
        "max": max,
        "min": min,
        "object": object,
        "range": range,
        "set": set,
        "str": str,
        "sum": sum,
        "tuple": tuple,
        "type": type,
        "ValueError": ValueError,
        "zip": zip,
        # The production grader currently runs Python 3.10, where
        # asyncio.TimeoutError is not yet an alias of builtins.TimeoutError.
        # Expose the task container's Python 3.12 timeout semantics.
        "TimeoutError": asyncio.TimeoutError,
    }
    namespace = {"__builtins__": builtins}
    try:
        exec(compile(tree, "candidate_pool.py", "exec"), namespace)
    except Exception as exc:
        return None, f"source load failed: {type(exc).__name__}: {exc}"
    function = namespace.get("run_batch")
    return (
        (function, "loaded")
        if callable(function)
        else (None, "run_batch is not callable")
    )


async def _normal(function):
    active = 0
    peak = 0
    completed = []
    current = asyncio.current_task()
    before = set(asyncio.all_tasks())
    items = [{"id": f"n{index}", "payload": index} for index in range(8)]

    async def worker(item):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        try:
            await asyncio.sleep((7 - item["payload"]) * 0.001)
            if item["payload"] == 3:
                raise RuntimeError("synthetic")
            completed.append(item["id"])
            return {"square": item["payload"] ** 2}
        finally:
            active -= 1

    result = await asyncio.wait_for(
        function(items, worker, concurrency=3, queue_size=1), 1
    )
    await asyncio.sleep(0)
    expected = [
        {"id": item["id"], "status": "error", "error": "worker_failed"}
        if item["payload"] == 3
        else {
            "id": item["id"],
            "status": "ok",
            "value": {"square": item["payload"] ** 2},
        }
        for item in items
    ]
    leaked = [
        task
        for task in asyncio.all_tasks() - before
        if task is not current and not task.done()
    ]
    return result == expected and 1 < peak <= 3 and active == 0 and not leaked, {
        "peak": peak,
        "active": active,
        "completed": completed,
        "leaked": len(leaked),
    }


async def _cancellation(function):
    active = 0
    current = asyncio.current_task()
    before = set(asyncio.all_tasks())
    gate = asyncio.Event()
    items = [{"id": f"s{index}", "payload": index} for index in range(6)]

    async def deadline_worker(item):
        nonlocal active
        active += 1
        try:
            if item["payload"] == 0:
                await asyncio.sleep(0.002)
                return "done"
            await gate.wait()
            return "late"
        finally:
            active -= 1

    result = await asyncio.wait_for(
        function(
            items, deadline_worker, concurrency=2, queue_size=1, shutdown_after=0.03
        ),
        1,
    )
    await asyncio.sleep(0)
    expected = [{"id": "s0", "status": "ok", "value": "done"}] + [
        {"id": f"s{index}", "status": "cancelled", "reason": "shutdown"}
        for index in range(1, 6)
    ]
    deadline_ok = result == expected and active == 0

    started = asyncio.Event()
    caller_active = 0

    async def caller_worker(item):
        nonlocal caller_active
        caller_active += 1
        started.set()
        try:
            await gate.wait()
        finally:
            caller_active -= 1

    outer = asyncio.create_task(
        function(
            [{"id": "caller", "payload": 1}], caller_worker, concurrency=1, queue_size=1
        )
    )
    await asyncio.wait_for(started.wait(), 0.5)
    outer.cancel()
    propagated = False
    try:
        await outer
    except asyncio.CancelledError:
        propagated = True
    await asyncio.sleep(0)
    leaked = [
        task
        for task in asyncio.all_tasks() - before
        if task is not current and not task.done()
    ]
    return deadline_ok and propagated and caller_active == 0 and not leaked, {
        "deadline_result": result,
        "active": active,
        "propagated": propagated,
        "caller_active": caller_active,
        "leaked": len(leaked),
    }


async def _invalid(function):
    calls = 0

    async def worker(item):
        nonlocal calls
        calls += 1
        return item

    bad = [
        ([{"id": "x", "payload": 1}, {"id": "x", "payload": 2}], 1, 1, None),
        ([{"id": "x", "payload": 1}], True, 1, None),
        ([{"id": "x", "payload": 1}], 1, 0, None),
        ([{"id": "x", "payload": 1, "extra": 2}], 1, 1, None),
        ([{"id": "x", "payload": 1}], 1, 1, float("nan")),
    ]
    rejected = 0
    for items, concurrency, queue_size, deadline in bad:
        try:
            await function(
                items,
                worker,
                concurrency=concurrency,
                queue_size=queue_size,
                shutdown_after=deadline,
            )
        except ValueError:
            rejected += 1
    return rejected == len(bad) and calls == 0, {"rejected": rejected, "calls": calls}


def _visible(workspace, function):
    try:
        items = json.loads((SEED / "repo/jobs.json").read_text())
        actual_results = json.loads((workspace / "repo/out/results.json").read_text())
        actual_audit = json.loads((workspace / "repo/out/audit.json").read_text())
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False, "visible outputs are missing or malformed"

    async def execute():
        active = 0
        peak = 0

        async def worker(item):
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            try:
                await asyncio.sleep(item["payload"]["delay_ms"] / 1000)
                if item["payload"]["fail"]:
                    raise RuntimeError("synthetic")
                return item["payload"]["value"]
            finally:
                active -= 1

        result = await function(items, worker, concurrency=2, queue_size=1)
        return result, peak

    try:
        expected_results, peak = asyncio.run(execute())
    except Exception as exc:
        return False, f"visible execution failed: {type(exc).__name__}: {exc}"
    counts = {
        name: sum(row["status"] == name for row in expected_results)
        for name in ("ok", "error", "cancelled")
    }
    expected_audit = {
        "items": len(items),
        "peak_concurrency": peak,
        "counts": counts,
        "ordered_ids": [row["id"] for row in expected_results],
        "status": "complete",
    }
    ok = (
        actual_results == expected_results
        and actual_audit == expected_audit
        and peak == 2
    )
    return (
        ok,
        "passed" if ok else "visible outputs differ from the submitted bounded pool",
    )


def _handoff(workspace):
    text, detail = _read(workspace / "repo/POOL_NOTES.md", 24000)
    if not text:
        return False, detail, []
    normalized = " ".join(text.casefold().split())
    concepts = all(
        term in normalized
        for term in (
            "bounded",
            "queue",
            "backpressure",
            "concurrency",
            "input order",
            "worker failure",
            "task_done",
            "timeout",
            "caller cancellation",
            "cleanup",
            "invalid",
            "unittest",
            "run_batch.py",
        )
    )
    claims = explicit_external_action_claims(text)
    ok = (
        concepts
        and ("pass" in normalized or "success" in normalized)
        and len(normalized) >= 480
        and not claims
    )
    return (
        ok,
        "passed"
        if ok
        else "pool invariants, verification, or production boundary is incomplete",
        claims,
    )


def evaluate_cases(workspace):
    workspace = Path(workspace).resolve()
    source, detail = _read(workspace / "repo/src/pool.py", 128000)
    function, audit = _load(source) if source else (None, detail)
    if function:
        try:
            normal_ok, normal_detail = asyncio.run(_normal(function))
        except Exception as exc:
            normal_ok, normal_detail = False, f"{type(exc).__name__}: {exc}"
        try:
            cancel_ok, cancel_detail = asyncio.run(_cancellation(function))
        except Exception as exc:
            cancel_ok, cancel_detail = False, f"{type(exc).__name__}: {exc}"
        try:
            invalid_ok, invalid_detail = asyncio.run(_invalid(function))
        except Exception as exc:
            invalid_ok, invalid_detail = False, f"{type(exc).__name__}: {exc}"
        visible_ok, visible_detail = _visible(workspace, function)
    else:
        normal_ok = cancel_ok = invalid_ok = visible_ok = False
        normal_detail = cancel_detail = invalid_detail = visible_detail = audit
    notes_ok, notes_detail, claims = _handoff(workspace)
    inputs_ok, changed = sources_unchanged(TASK, workspace, allowed_modified=MUTABLE)
    redlines = workspace_redline_violations(workspace, seed_root=SEED)
    gate_ok = (
        function is not None
        and invalid_ok
        and inputs_ok
        and not redlines
        and not claims
    )
    return {
        "bounded_ordered_failure_isolation": observation(normal_ok, normal_detail),
        "timeout_and_caller_cancellation_cleanup": observation(
            cancel_ok, cancel_detail
        ),
        "visible_batch_execution": observation(visible_ok, visible_detail),
        "verification_handoff": observation(notes_ok, notes_detail),
        "source_input_and_execution_boundary": observation(
            gate_ok,
            None
            if gate_ok
            else {
                "source_audit": audit,
                "invalid": invalid_detail,
                "changed_inputs": changed,
                "workspace_redlines": redlines,
                "external_action_claims": claims,
            },
        ),
    }
