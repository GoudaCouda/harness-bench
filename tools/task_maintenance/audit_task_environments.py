#!/usr/bin/env python3
"""Inventory task runtime needs without pretending static guesses are reviews."""

from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TASKS = ROOT / "tasks"
_COMMAND = re.compile(r"(?:^|[;&|]\s*)([A-Za-z0-9_.+-]+)(?=\s|$)")
_BACKTICK = re.compile(r"`([^`\n]+)`")
_PACKAGE_COMMANDS = {"apt", "apt-get", "pip", "pip3", "npm", "npx", "pnpm", "yarn"}
_COMMON_COMMANDS = {
    "bash", "chmod", "cp", "cut", "date", "diff", "echo", "env", "find", "git",
    "grep", "head", "ls", "make", "mkdir", "mv", "node", "python", "python3",
    "pytest", "sed", "sh", "sha256sum", "sort", "sqlite3", "tail", "tar", "test",
    "touch", "tr", "uniq", "wc",
}


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def tree_identity(root: Path) -> str:
    digest = hashlib.sha256()
    if not root.is_dir():
        return digest.hexdigest()
    for path in sorted(root.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        relative = path.relative_to(root).as_posix()
        payload = path.read_bytes()
        digest.update(relative.encode())
        digest.update(b"\0")
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
    return digest.hexdigest()


def python_evidence(path: Path) -> tuple[set[str], set[str]]:
    imports: set[str] = set()
    commands: set[str] = set()
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return imports, commands
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".")[0])
        elif isinstance(node, ast.Call):
            function = node.func
            name = ""
            if isinstance(function, ast.Attribute):
                name = function.attr
            elif isinstance(function, ast.Name):
                name = function.id
            if name not in {"run", "Popen", "check_call", "check_output"} or not node.args:
                continue
            value = node.args[0]
            if isinstance(value, (ast.List, ast.Tuple)) and value.elts:
                first = value.elts[0]
                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                    commands.add(first.value)
            elif isinstance(value, ast.Constant) and isinstance(value.value, str):
                match = _COMMAND.search(value.value)
                if match:
                    commands.add(match.group(1))
    return imports, commands


def prompt_hints(task_dir: Path, metadata: dict[str, Any]) -> list[str]:
    names = metadata.get("prompt_files") or [metadata.get("prompt_file", "instruction.md")]
    hints: set[str] = set()
    for raw_name in names:
        path = task_dir / str(raw_name)
        if not path.is_file():
            continue
        for value in _BACKTICK.findall(path.read_text(encoding="utf-8", errors="replace")):
            token = value.strip().split()[0] if value.strip() else ""
            if token and "/" not in token and re.fullmatch(r"[A-Za-z0-9_.+-]+", token):
                hints.add(token)
    return sorted(hints)


def docker_facts(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"present": False}
    text = path.read_text(encoding="utf-8", errors="replace")
    from_images = re.findall(r"(?im)^\s*FROM\s+(?:--platform=\S+\s+)?([^\s]+)", text)
    apt_lines = [
        line.strip() for line in text.splitlines()
        if "apt-get install" in line or "apk add" in line
    ]
    return {
        "present": True,
        "sha256": sha256_bytes(path.read_bytes()),
        "from_images": from_images,
        "has_entrypoint": bool(re.search(r"(?im)^\s*ENTRYPOINT\b", text)),
        "has_healthcheck": bool(re.search(r"(?im)^\s*HEALTHCHECK\b", text)),
        "exposed_ports": re.findall(r"(?im)^\s*EXPOSE\s+([^\s#]+)", text),
        "copies_lock": bool(re.search(r"(?im)^\s*COPY\s+.*(?:requirements|lock)", text)),
        "installs_packages": bool(re.search(r"(?i)apt-get\s+install|apk\s+add|pip\s+install", text)),
        "package_lines": apt_lines,
    }


def inspect_task(task_yaml: Path) -> dict[str, Any]:
    task_dir = task_yaml.parent
    metadata = yaml.safe_load(task_yaml.read_text(encoding="utf-8")) or {}
    workspace = task_dir / str(metadata.get("workspace_dir") or "workspace")
    environment = task_dir / "environment"
    imports: set[str] = set()
    commands: set[str] = set()
    python_roles: dict[str, int] = Counter()
    for path in sorted(task_dir.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        relative = path.relative_to(task_dir)
        role = relative.parts[0] if relative.parts else "task"
        python_roles[role] += 1
        found_imports, found_commands = python_evidence(path)
        imports.update(found_imports)
        commands.update(found_commands)

    suffixes: Counter[str] = Counter()
    workspace_files = 0
    for path in sorted(workspace.rglob("*")) if workspace.is_dir() else []:
        if path.is_file() and "__pycache__" not in path.parts:
            workspace_files += 1
            suffixes[path.suffix.casefold() or "<none>"] += 1

    docker = docker_facts(environment / "Dockerfile")
    hooks = environment / "hooks.py"
    hook_imports, _ = python_evidence(hooks) if hooks.is_file() else (set(), set())
    environment_files = [
        path.relative_to(environment).as_posix()
        for path in sorted(environment.rglob("*"))
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
    ] if environment.is_dir() else []
    package_commands = sorted(commands & _PACKAGE_COMMANDS)
    uncommon_commands = sorted(
        command for command in commands
        if command not in _COMMON_COMMANDS and command not in _PACKAGE_COMMANDS
    )
    if docker.get("has_entrypoint") or docker.get("has_healthcheck") or docker.get("exposed_ports"):
        static_class = "service_candidate"
    elif docker.get("installs_packages") or docker.get("copies_lock"):
        static_class = "dependency_overlay_candidate"
    else:
        static_class = "shared_baseline_candidate"
    if hooks.is_file() and {"socket", "urllib", "http"} & hook_imports:
        static_class = "hook_service_candidate"

    task_id = str(metadata.get("task_id") or task_dir.name)
    return {
        "schema_version": 1,
        "task_id": task_id,
        "title": metadata.get("title"),
        "domain": metadata.get("domain"),
        "task_tree_sha256": tree_identity(task_dir),
        "environment_tree_sha256": tree_identity(environment),
        "dockerfile": docker,
        "environment_files": environment_files,
        "hooks_module": metadata.get("hooks_module"),
        "workspace_file_count": workspace_files,
        "workspace_suffix_counts": dict(sorted(suffixes.items())),
        "python_file_roles": dict(sorted(python_roles.items())),
        "python_imports": sorted(imports),
        "subprocess_commands": sorted(commands),
        "prompt_command_hints": prompt_hints(task_dir, metadata),
        "package_install_commands_in_task_code": package_commands,
        "uncommon_commands": uncommon_commands,
        "static_classification": static_class,
        "manual_review_status": "pending",
        "manual_review_required": True,
        "review_questions": [
            "Which commands and libraries are required by the agent rather than merely mentioned?",
            "Which dependencies are needed only by trusted setup or grading?",
            "Does the task need a stateful sidecar, a hook fixture, or neither?",
            "Can every required dependency be pinned and resolved offline?",
            "Which verifier proves the actual runtime contract for this task?",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks-dir", type=Path, default=DEFAULT_TASKS)
    parser.add_argument("--json-out", type=Path, required=True)
    parser.add_argument("--csv-out", type=Path)
    args = parser.parse_args()
    rows = [inspect_task(path) for path in sorted(args.tasks_dir.glob("*/task.yaml"))]
    payload = {
        "schema_version": 1,
        "task_count": len(rows),
        "manual_reviewed_count": 0,
        "tasks": rows,
    }
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.csv_out:
        args.csv_out.parent.mkdir(parents=True, exist_ok=True)
        with args.csv_out.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=[
                "task_id", "domain", "static_classification", "environment_tree_sha256",
                "hooks_module", "workspace_file_count", "uncommon_commands",
                "manual_review_status",
            ])
            writer.writeheader()
            for row in rows:
                writer.writerow({
                    **{key: row.get(key) for key in writer.fieldnames},
                    "uncommon_commands": ",".join(row["uncommon_commands"]),
                })
    print(json.dumps({
        "task_count": len(rows),
        "classes": dict(sorted(Counter(row["static_classification"] for row in rows).items())),
        "json_out": str(args.json_out),
        "csv_out": str(args.csv_out) if args.csv_out else None,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
