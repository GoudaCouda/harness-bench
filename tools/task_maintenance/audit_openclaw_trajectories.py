#!/usr/bin/env python3
"""Summarize task-level OpenClaw traces for human workflow review.

This does not decide task membership or quality. It exposes evidence needed for
the task-only protocol's post-run diagnostic review: tool/result integrity,
ordering, feedback, retries, state verification, errors, and score attribution.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def session_records(task_root: Path) -> list[dict[str, Any]]:
    """Load message records from either legacy state or current trajectories."""

    values = sorted(
        path
        for path in (task_root / "openclaw-state").rglob("*.jsonl")
        if not path.name.endswith(".trajectory.jsonl")
    ) if (task_root / "openclaw-state").is_dir() else []
    if len(values) == 1:
        return [
            json.loads(line)
            for line in values[0].read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    raw_sessions = sorted(
        path
        for path in (task_root / "trace").glob("*.jsonl")
        if not path.name.endswith(".trajectory.jsonl")
    )
    if raw_sessions:
        records: list[dict[str, Any]] = []
        for path in raw_sessions:
            records.extend(
                json.loads(line)
                for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            )
        return records
    trajectories = sorted((task_root / "trace").glob("*.trajectory.jsonl"))
    if len(trajectories) != 1:
        raise ValueError(
            f"expected one legacy session or current trajectory for "
            f"{task_root.name}: {values or trajectories}"
        )
    for line in trajectories[0].read_text(encoding="utf-8").splitlines():
        event = json.loads(line)
        if event.get("type") != "model.completed":
            continue
        data = event.get("data")
        snapshot = data.get("messagesSnapshot") if isinstance(data, dict) else None
        if isinstance(snapshot, list):
            return [record for record in snapshot if isinstance(record, dict)]
    raise ValueError(f"trajectory has no messagesSnapshot: {trajectories[0]}")


def content_blocks(record: dict[str, Any]) -> list[dict[str, Any]]:
    message = record.get("message") if record.get("type") == "message" else record
    if not isinstance(message, dict):
        return []
    content = message.get("content")
    return [block for block in content if isinstance(block, dict)] if isinstance(content, list) else []


def command_text(block: dict[str, Any]) -> str:
    arguments = block.get("arguments")
    if not isinstance(arguments, dict):
        return ""
    return str(arguments.get("command") or arguments.get("path") or arguments.get("file_path") or "")


def audit_task(task_root: Path) -> dict[str, Any]:
    if (task_root / "result.json").is_file():
        result = load_json(task_root / "result.json")
        grade = result
        run = result
        integrity = result.get("trace_integrity")
        if not isinstance(integrity, dict):
            integrity = {}
    else:
        grade = load_json(task_root / "grade.json")
        run = load_json(task_root / "run.json")
        integrity = load_json(task_root / "trace_integrity.json")
    calls: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []
    for index, record in enumerate(session_records(task_root)):
        message = record.get("message") if record.get("type") == "message" else record
        role = message.get("role") if isinstance(message, dict) else None
        for block in content_blocks(record):
            if block.get("type") == "toolCall":
                calls.append(
                    {
                        "index": index,
                        "id": block.get("id"),
                        "tool": block.get("name"),
                        "command": command_text(block),
                    }
                )
        if role == "toolResult":
            details = message.get("details") if isinstance(message, dict) else {}
            results.append(
                {
                    "index": index,
                    "id": message.get("toolCallId"),
                    "tool": message.get("toolName"),
                    "is_error": bool(message.get("isError"))
                    or (isinstance(details, dict) and details.get("status") not in (None, "completed")),
                    "exit_code": details.get("exitCode") if isinstance(details, dict) else None,
                }
            )
    commands = [row["command"] for row in calls if row["command"]]
    read_pattern = re.compile(r"(?:^|\s)(?:cat|sed|head|tail|less|rg|grep|find|ls|sqlite3\b.*select|python3\s+\S+\s+(?:status|query|requirements|graph|impact|candidates|analyze))", re.I)
    write_pattern = re.compile(r"(?:>|\b(?:write|edit|apply|stage|merge|commit|render|finalize|decide)\b)", re.I)
    verify_pattern = re.compile(r"\b(?:verify|validate|preview|replay|pytest|test)\b", re.I)
    retry_pattern = re.compile(r"\b(?:idempot|retry|reapply|replay|render|finalize|commit|merge|stage|apply)\b", re.I)
    read_indexes = [
        row["index"]
        for row in calls
        if row["tool"] == "read" or read_pattern.search(row["command"])
    ]
    write_indexes = [
        row["index"]
        for row in calls
        if row["tool"] in {"write", "edit"} or write_pattern.search(row["command"])
    ]
    first_write = min(write_indexes) if write_indexes else None
    reads_before_first_write = sum(
        index < first_write for index in read_indexes
    ) if first_write is not None else len(read_indexes)
    normalized_commands = [re.sub(r"\s+", " ", command.strip()) for command in commands]
    duplicates = sorted(command for command, count in Counter(normalized_commands).items() if count > 1)
    oracle = grade.get("oracle") if isinstance(grade.get("oracle"), dict) else {}
    case_results = grade.get("checks") if isinstance(grade.get("checks"), list) else oracle.get("checks", [])
    failed_cases = [
        str(row.get("id")).removeprefix("case:")
        for row in case_results
        if isinstance(row, dict)
        and str(row.get("id", "")).startswith("case:")
        and row.get("pass") is not True
    ]
    return {
        "task_id": task_root.name,
        "status": run.get("status"),
        "outcome_score": grade.get("outcome_score"),
        "task_success": grade.get("task_success"),
        "failed_cases": failed_cases,
        "elapsed_sec": run.get("elapsed_sec"),
        "trace_integrity": integrity.get("status"),
        "tool_calls": len(calls),
        "tool_results": len(results),
        "tool_distribution": dict(sorted(Counter(row["tool"] for row in calls).items())),
        "tool_errors": sum(row["is_error"] or row["exit_code"] not in (None, 0) for row in results),
        "read_like_calls": len(read_indexes),
        "reads_before_first_write": reads_before_first_write,
        "write_like_calls": len(write_indexes),
        "verification_like_calls": sum(bool(verify_pattern.search(command)) for command in commands),
        "retry_like_calls": sum(bool(retry_pattern.search(command)) for command in commands),
        "duplicate_exact_commands": duplicates,
        "commands": commands,
        "human_review": {
            "surface_realism": "pending",
            "dependency_depth": "pending",
            "feedback_used": "pending",
            "score_attribution": "pending",
            "disposition": "pending",
            "notes": "",
        },
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = [
        "task_id",
        "status",
        "outcome_score",
        "task_success",
        "tool_calls",
        "tool_results",
        "tool_errors",
        "read_like_calls",
        "reads_before_first_write",
        "write_like_calls",
        "verification_like_calls",
        "retry_like_calls",
        "failed_cases",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: json.dumps(row[key]) if isinstance(row[key], list) else row[key] for key in fields})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_root", type=Path)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--csv-out", type=Path)
    args = parser.parse_args()
    run_root = args.run_root.resolve()
    rows = [
        audit_task(path)
        for path in sorted((run_root / "tasks").iterdir())
        if (path / "run.json").is_file() or (path / "result.json").is_file()
    ]
    payload = {
        "schema_version": 1,
        "evaluation_id": run_root.name,
        "task_count": len(rows),
        "all_trace_integrity_pass": all(row["trace_integrity"] == "pass" for row in rows),
        "total_tool_calls": sum(row["tool_calls"] for row in rows),
        "total_tool_results": sum(row["tool_results"] for row in rows),
        "tasks": rows,
    }
    json_out = args.json_out or run_root / "trajectory_audit.json"
    csv_out = args.csv_out or run_root / "trajectory_audit.csv"
    json_out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_csv(csv_out, rows)
    print(json.dumps({key: payload[key] for key in ("task_count", "all_trace_integrity_pass", "total_tool_calls", "total_tool_results")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
