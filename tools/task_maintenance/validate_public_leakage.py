#!/usr/bin/env python3
"""Reject public task material that encodes instance-specific hidden answers."""

from __future__ import annotations

import argparse
import ast
import json
import re
from pathlib import Path
from typing import Any, Iterable

from common import iter_task_yamls, load_task_metadata


ROOT = Path(__file__).resolve().parents[2]
PROHIBITED_PUBLIC_KEYS = {
    "answer_by_key",
    "answer_by_id",
    "gold_by_key",
    "gold_by_id",
    "required_reference_by_key",
}
ANSWER_FIELD_NAMES = {
    "decision",
    "reason_code",
    "owner",
    "next_action",
    "status",
    "action",
    "approval",
}
ANSWER_FUNCTION_NAMES = {
    "build_plan",
    "expected_plan",
    "expected_plan_core",
    "expected_results",
    "gold_plan",
    "reference_plan",
    "target_plan",
}
COMPLETE_DERIVATION_KEYS = {
    "actions",
    "decisions",
    "final_records",
    "final_rows",
    "final_samples",
    "plan",
}
ID_LIKE_KEY = re.compile(r"(?=.*\d)(?:[A-Z]{2,}[-_:]|.*[-_:].*)")


def walk_json(
    value: Any, path: tuple[str, ...] = ()
) -> Iterable[tuple[tuple[str, ...], Any]]:
    yield path, value
    if isinstance(value, dict):
        for key, child in value.items():
            yield from walk_json(child, (*path, str(key)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from walk_json(child, (*path, str(index)))


def literal_containers(source: str) -> list[tuple[str, Any]]:
    """Extract safely evaluable Python literal containers with their owner name."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    containers: list[tuple[str, Any]] = []
    for node in ast.walk(tree):
        owner = ""
        value_node: ast.AST | None = None
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            value_node = node.value
            target = node.targets[0] if isinstance(node, ast.Assign) else node.target
            if isinstance(target, ast.Name):
                owner = target.id
        if value_node is None or not isinstance(
            value_node,
            (ast.Dict, ast.List, ast.Tuple, ast.Set),
        ):
            continue
        try:
            value = ast.literal_eval(value_node)
        except (TypeError, ValueError):
            continue
        containers.append((owner, value))
    return containers


def canonical(value: Any) -> str:
    def json_value(child: Any) -> Any:
        if isinstance(child, dict):
            return {str(key): json_value(item) for key, item in child.items()}
        if isinstance(child, (list, tuple)):
            return [json_value(item) for item in child]
        if isinstance(child, set):
            return sorted(
                (json_value(item) for item in child),
                key=lambda item: repr(item),
            )
        return child

    return json.dumps(
        json_value(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def hidden_json_containers(task_dir: Path) -> set[str]:
    fingerprints: set[str] = set()
    paths = [
        task_dir / "ground_truth.json",
        *sorted((task_dir / "reference").rglob("*.json")),
        *sorted((task_dir / "tests" / "ground_truth").rglob("*.json")),
        *sorted((task_dir / "tests" / "reference").rglob("*.json")),
    ]
    for path in paths:
        if not path.is_file():
            continue
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue
        for _, child in walk_json(value):
            if isinstance(child, dict) and len(child) >= 2:
                fingerprints.add(canonical(child))
    return fingerprints


def hidden_item_ids(task_dir: Path) -> set[str]:
    ids: set[str] = set()
    paths = [
        task_dir / "ground_truth.json",
        *sorted((task_dir / "tests" / "ground_truth").rglob("*.json")),
    ]
    for path in paths:
        if not path.is_file():
            continue
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue
        for _, child in walk_json(value):
            if isinstance(child, dict):
                for key in ("item_id", "record_id", "case_id"):
                    if child.get(key):
                        ids.add(str(child[key]))
    return ids


def public_json_findings(
    *,
    task_number: int,
    task_dir: Path,
    path: Path,
) -> list[str]:
    findings: list[str] = []
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return findings
    relative = path.relative_to(task_dir).as_posix()
    item_ids = hidden_item_ids(task_dir)
    for location, child in walk_json(value):
        if not location:
            continue
        key = location[-1]
        rendered = ".".join(location)
        if key in PROHIBITED_PUBLIC_KEYS:
            findings.append(f"{relative}:{rendered}: prohibited keyed answer map")
        if 69 <= task_number <= 109 and key == "canonical_value_vocabulary":
            findings.append(
                f"{relative}:{rendered}: instance-derived canonical answer pool"
            )
        if (
            isinstance(child, dict)
            and len(child) >= 2
            and all(isinstance(value, dict) for value in child.values())
            and len(set(map(str, child)) & item_ids) >= 2
        ):
            answer_fields = {
                field
                for row in child.values()
                for field in row
                if field in ANSWER_FIELD_NAMES
            }
            if answer_fields:
                findings.append(
                    f"{relative}:{rendered}: public item-keyed map contains "
                    f"answer fields {sorted(answer_fields)}"
                )
    return findings


def public_python_findings(task_dir: Path, path: Path) -> list[str]:
    findings: list[str] = []
    relative = path.relative_to(task_dir).as_posix()
    source = path.read_text(encoding="utf-8")
    hidden = hidden_json_containers(task_dir)
    for owner, value in literal_containers(source):
        normalized_owner = owner.casefold()
        if (
            owner
            and any(
                token in normalized_owner
                for token in ("expected", "ground_truth", "gold", "answer_key")
            )
            and isinstance(value, (dict, list, tuple))
            and len(value) >= 2
        ):
            findings.append(f"{relative}:{owner}: literal expected-answer container")
        if isinstance(value, dict) and canonical(value) in hidden:
            findings.append(
                f"{relative}:{owner or '<literal>'}: duplicates a hidden "
                "ground-truth/reference JSON container"
            )
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return findings

    def returned_dict_keys(function: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
        assigned: dict[str, ast.Dict] = {}
        for node in ast.walk(function):
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Dict):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        assigned[target.id] = node.value
        keys: set[str] = set()
        for node in ast.walk(function):
            if not isinstance(node, ast.Return) or node.value is None:
                continue
            returned = node.value
            if isinstance(returned, ast.Name):
                returned = assigned.get(returned.id, returned)
            if not isinstance(returned, ast.Dict):
                continue
            keys.update(
                key.value
                for key in returned.keys
                if isinstance(key, ast.Constant) and isinstance(key.value, str)
            )
        return keys

    for function in (
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ):
        normalized_function_name = function.name.casefold().lstrip("_")
        if normalized_function_name in ANSWER_FUNCTION_NAMES:
            findings.append(
                f"{relative}:{function.name}: public expected/gold/target plan "
                "constructor is an answer container"
            )
        if "derive" in normalized_function_name:
            leaked = sorted(returned_dict_keys(function) & COMPLETE_DERIVATION_KEYS)
            if leaked:
                findings.append(
                    f"{relative}:{function.name}: public derivation returns "
                    f"complete candidate state fields {leaked}"
                )
        for comparison in (
            node for node in ast.walk(function) if isinstance(node, ast.Compare)
        ):
            candidates = [comparison.left, *comparison.comparators]
            for candidate in candidates:
                if not isinstance(candidate, ast.Dict) or len(candidate.keys) < 3:
                    continue
                try:
                    value = ast.literal_eval(candidate)
                except (TypeError, ValueError):
                    continue
                if not isinstance(value, dict):
                    continue
                keys = [str(key) for key in value]
                if sum(bool(ID_LIKE_KEY.match(key)) for key in keys) < 3:
                    continue
                findings.append(
                    f"{relative}:{function.name}: verifier compares against a "
                    "literal item-ID final-state map"
                )
    return findings


def audit_task(task_dir: Path, metadata: dict[str, Any]) -> dict[str, Any]:
    number = int(task_dir.name.split("-", 1)[0])
    findings: list[str] = []
    prompt_names = metadata.get("prompt_files") or [
        metadata.get("prompt_file", "prompt.txt")
    ]
    for name in prompt_names:
        prompt = task_dir / str(name)
        if prompt.is_file():
            lowered = prompt.read_text(encoding="utf-8").casefold()
            if (
                "ground_truth.json" in lowered
                or "/reference/" in lowered
                or "tests/ground_truth" in lowered
                or "tests/reference" in lowered
            ):
                findings.append(f"{prompt.name}: references a grader-only answer path")

    workspace = task_dir / str(metadata.get("workspace_dir") or "workspace")
    if workspace.is_dir():
        for path in sorted(workspace.rglob("*")):
            if (
                not path.is_file()
                or "__pycache__" in path.parts
                or path.suffix == ".pyc"
            ):
                continue
            lowered_name = path.name.casefold()
            if any(
                token in lowered_name
                for token in ("ground_truth", "answer_key", "reference_answer")
            ):
                findings.append(
                    f"{path.relative_to(task_dir)}: answer-like public filename"
                )
            if path.suffix == ".json":
                findings.extend(
                    public_json_findings(
                        task_number=number,
                        task_dir=task_dir,
                        path=path,
                    )
                )
            elif path.suffix == ".py":
                findings.extend(public_python_findings(task_dir, path))
    return {
        "task_id": metadata["task_id"],
        "findings": sorted(set(findings)),
        "pass": not findings,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-task-number", type=int, default=1)
    parser.add_argument(
        "--max-task-number",
        type=int,
        help="optional inclusive upper bound (default: audit the full suite)",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        default=ROOT / "artifacts" / "audits" / "public-leakage.json",
    )
    args = parser.parse_args()

    rows: list[dict[str, Any]] = []
    for task_yaml in iter_task_yamls():
        number = int(task_yaml.parent.name.split("-", 1)[0])
        if number < args.min_task_number or (
            args.max_task_number is not None and number > args.max_task_number
        ):
            continue
        row = audit_task(task_yaml.parent, load_task_metadata(task_yaml))
        rows.append(row)
        status = "PASS" if row["pass"] else "FAIL"
        print(f"{status} {row['task_id']}")
        for finding in row["findings"]:
            print(f"  - {finding}")

    payload = {
        "schema_version": 1,
        "task_count": len(rows),
        "passed": sum(row["pass"] for row in rows),
        "failed": sum(not row["pass"] for row in rows),
        "tasks": rows,
    }
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"tasks={payload['task_count']} passed={payload['passed']} "
        f"failed={payload['failed']}"
    )
    print(f"report={args.json_out}")
    raise SystemExit(1 if payload["failed"] else 0)


if __name__ == "__main__":
    main()
