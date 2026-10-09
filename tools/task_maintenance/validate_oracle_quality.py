#!/usr/bin/env python3
"""Exercise every formal oracle against common adversarial cases.

The task-specific reference case lives in ``<task>/tests/reference`` for a
formal task (legacy tasks use ``<task>/reference``). That directory mirrors
final workspace-relative artifact paths and is never exposed to agents.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from pathlib import Path
from typing import Any

from common import (
    iter_task_yamls,
    load_oracle,
    load_task_metadata,
    score_task_workspace,
)
from harnessbench.grading.oracle_contract import normalize_required_artifacts


ROOT = Path(__file__).resolve().parents[2]
GRADER_BASE_IMAGE = (
    "python:3.10-bookworm@sha256:"
    "be77ec026cf35f6adf5f4f02015d50b7aadaac98659a02be1fc8ce18c396f652"
)


def tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    if not root.exists():
        return digest.hexdigest()
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        digest.update(relative.encode())
        digest.update(b"\0d\0" if path.is_dir() else b"\0f\0")
        if path.is_file():
            digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def copy_tree(source: Path, destination: Path) -> None:
    if not source.is_dir():
        return
    shutil.copytree(
        source,
        destination,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns(
            "__pycache__",
            "*.pyc",
            ".DS_Store",
        ),
    )


def reference_root(task_dir: Path, metadata: dict[str, Any]) -> Path:
    if str(metadata.get("outcome_test") or "").strip():
        return task_dir / "tests" / "reference"
    return task_dir / "reference"


def copy_reference_artifacts(
    task_dir: Path,
    metadata: dict[str, Any],
    destination: Path,
) -> None:
    reference = reference_root(task_dir, metadata)
    for source in sorted(reference.rglob("*")):
        relative = source.relative_to(reference)
        if (
            not source.is_file()
            or "__pycache__" in relative.parts
            or source.suffix == ".pyc"
            or source.name in {"setup_reference.py", ".DS_Store"}
        ):
            continue
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def reference_helper(
    workspace: Path,
    runtime: Path,
) -> Any:
    """Use local Git when present, otherwise the same pinned Docker helper."""
    if shutil.which("git"):

        def run_local(command: list[str]) -> subprocess.CompletedProcess[str]:
            local_command = list(command)
            if local_command and local_command[0] == "python3":
                local_command[0] = sys.executable
            environment = {
                **os.environ,
                "HB_WORKSPACE": str(workspace),
                "HB_RUNTIME": str(runtime),
            }
            completed = subprocess.run(
                local_command,
                text=True,
                capture_output=True,
                check=False,
                env=environment,
            )
            if completed.returncode != 0:
                raise RuntimeError(completed.stderr.strip() or completed.stdout.strip())
            return completed

        return run_local
    if not shutil.which("docker"):
        raise RuntimeError(
            "reference setup requires either Git or Docker on the maintainer host"
        )

    def run_docker(command: list[str]) -> subprocess.CompletedProcess[str]:
        completed = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "--network",
                "none",
                "--read-only",
                "--cap-drop",
                "ALL",
                "--security-opt",
                "no-new-privileges:true",
                "--user",
                "1000:1000",
                "--env",
                "HOME=/tmp",
                "--env",
                "HB_WORKSPACE=/workspace",
                "--env",
                "HB_RUNTIME=/runtime",
                "--tmpfs",
                "/tmp:rw,noexec,nosuid,size=64m",
                "--mount",
                f"type=bind,src={workspace.resolve()},dst=/workspace",
                "--mount",
                f"type=bind,src={runtime.resolve()},dst=/runtime",
                GRADER_BASE_IMAGE,
                *command,
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or completed.stdout.strip())
        return completed

    return run_docker


def make_workspace(
    task_dir: Path,
    metadata: dict[str, Any],
    mode: str,
) -> tuple[Path, list[Path]]:
    root = Path(tempfile.mkdtemp(prefix=f"hb-oracle-{mode}-"))
    if mode != "empty":
        copy_tree(
            task_dir / str(metadata.get("workspace_dir") or "workspace"),
            root,
        )
    cleanup_roots = [root]
    setup_path = reference_root(task_dir, metadata) / "setup_reference.py"
    hooks_name = str(metadata.get("hooks_module") or "")
    if mode == "reference":
        runtime_state: dict[str, Any] = {}
        runtime: Path | None = None
        if setup_path.is_file():
            runtime = Path(tempfile.mkdtemp(prefix="hb-oracle-reference-runtime-"))
            cleanup_roots.append(runtime)
        if hooks_name:
            if runtime is None:
                runtime = Path(tempfile.mkdtemp(prefix="hb-oracle-reference-runtime-"))
                cleanup_roots.append(runtime)
            hooks = load_oracle(
                task_dir / hooks_name,
                metadata["task_id"] + "-reference-hooks",
            )
            prepare = getattr(hooks, "prepare_runtime", None)
            if not callable(prepare):
                raise RuntimeError(
                    f"{metadata['task_id']}: reference setup requires prepare_runtime"
                )
            runtime_state = dict(prepare(
                {
                    "task": SimpleNamespace(
                        task_id=metadata["task_id"],
                        task_dir=task_dir,
                        title=metadata.get("title", metadata["task_id"]),
                    ),
                    "sandbox": runtime,
                    "workspace": root,
                    "service_bind_host": "127.0.0.1",
                    "service_public_host": "127.0.0.1",
                    "reference_mode": True,
                    "run_trusted_helper": reference_helper(root, runtime),
                }
            ) or {})
        copy_reference_artifacts(task_dir, metadata, root)
        if setup_path.is_file():
            assert runtime is not None
            setup = load_oracle(setup_path, metadata["task_id"] + "-reference")
            apply_reference = getattr(setup, "apply_reference", None)
            if not callable(apply_reference):
                raise RuntimeError(
                    f"{metadata['task_id']}: setup_reference.py lacks apply_reference"
                )
            apply_reference(root, runtime, runtime_state)
    elif mode == "malformed":
        raw_artifacts = [
            str(value).strip().replace("\\", "/")
            for value in metadata.get("required_artifacts", [])
        ]
        artifacts = normalize_required_artifacts(raw_artifacts)
        directory_paths = {
            value.rstrip("/") for value in raw_artifacts if value.endswith("/")
        }
        directory_paths.update(
            artifact
            for artifact in artifacts
            if any(other.startswith(artifact + "/") for other in artifacts)
        )
        for artifact in artifacts:
            path = root / artifact
            if artifact in directory_paths:
                path.mkdir(parents=True, exist_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"\x00not-valid-json,csv,markdown,or-code\xff")
    return root, cleanup_roots


def run_case(
    task_dir: Path,
    metadata: dict[str, Any],
    mode: str,
) -> dict[str, Any]:
    workspace, cleanup_roots = make_workspace(task_dir, metadata, mode)
    try:
        before = tree_digest(workspace)
        first = score_task_workspace(task_dir, metadata, workspace)
        after_first = tree_digest(workspace)
        second = score_task_workspace(task_dir, metadata, workspace)
        after_second = tree_digest(workspace)
        score = first.get("outcome_score")
        return {
            "score": score,
            "task_success": first.get("task_success"),
            "error": first.get("error", ""),
            "oracle_contract_failure": bool(first.get("oracle_contract_failure")),
            "oracle_infrastructure_failure": bool(
                first.get("oracle_infrastructure_failure")
            ),
            "deterministic": (
                first.get("outcome_score") == second.get("outcome_score")
                and first.get("checks") == second.get("checks")
            ),
            "workspace_unchanged": before == after_first == after_second,
            "artifact_contract": first.get("required_artifact_contract", {}),
        }
    finally:
        for root in cleanup_roots:
            shutil.rmtree(root, ignore_errors=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--require-reference",
        action="store_true",
        help="fail tasks that do not contain a reference workspace",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        default=ROOT / "artifacts" / "audits" / "oracle-quality.json",
    )
    args = parser.parse_args()

    rows: list[dict[str, Any]] = []
    for task_yaml in iter_task_yamls():
        task_dir = task_yaml.parent
        metadata = load_task_metadata(task_yaml)
        reference_exists = reference_root(task_dir, metadata).is_dir()
        cases = {
            mode: run_case(task_dir, metadata, mode)
            for mode in ("empty", "untouched", "malformed")
        }
        if reference_exists:
            cases["reference"] = run_case(task_dir, metadata, "reference")

        failures: list[str] = []
        blocked_modes = [
            mode
            for mode, result in cases.items()
            if result["oracle_infrastructure_failure"]
        ]
        for mode in blocked_modes:
            failures.append(f"{mode}_trusted_dependency_unavailable")
        for mode in ("empty", "untouched"):
            if cases[mode]["score"] != 0.0:
                failures.append(f"{mode}_score={cases[mode]['score']}")
            if cases[mode]["oracle_contract_failure"]:
                failures.append(f"{mode}_oracle_error")
            if (
                str(metadata.get("outcome_test") or "").strip()
                and cases[mode]["task_success"] is not False
            ):
                failures.append(f"{mode}_task_success={cases[mode]['task_success']}")
        if cases["malformed"]["oracle_contract_failure"]:
            failures.append("malformed_oracle_error")
        if cases["malformed"]["score"] != 0.0:
            failures.append(f"malformed_score={cases['malformed']['score']}")
        for mode, result in cases.items():
            if not result["deterministic"]:
                failures.append(f"{mode}_nondeterministic")
            if not result["workspace_unchanged"]:
                failures.append(f"{mode}_oracle_mutated_workspace")
        if reference_exists and cases["reference"]["score"] != 1.0:
            failures.append(f"reference_score={cases['reference']['score']}")
        if (
            reference_exists
            and str(metadata.get("outcome_test") or "").strip()
            and cases["reference"]["task_success"] is not True
        ):
            failures.append(
                f"reference_task_success={cases['reference']['task_success']}"
            )
        if args.require_reference and not reference_exists:
            failures.append("missing_reference")

        row = {
            "task_id": metadata["task_id"],
            "reference_exists": reference_exists,
            "cases": cases,
            "failures": failures,
            "blocked": bool(blocked_modes),
            "pass": not failures,
        }
        rows.append(row)
        state = "PASS" if row["pass"] else ("BLOCKED" if row["blocked"] else "FAIL")
        scores = ", ".join(
            f"{name}={result['score']}" for name, result in cases.items()
        )
        suffix = "" if not failures else " [" + ", ".join(failures) + "]"
        print(f"{state} {metadata['task_id']}: {scores}{suffix}")

    payload = {
        "schema_version": 1,
        "task_count": len(rows),
        "passed": sum(row["pass"] for row in rows),
        "blocked": sum(row["blocked"] for row in rows),
        "failed": sum(not row["pass"] for row in rows),
        "reference_count": sum(row["reference_exists"] for row in rows),
        "tasks": rows,
    }
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"tasks={payload['task_count']} passed={payload['passed']} "
        f"failed={payload['failed']} references={payload['reference_count']}"
    )
    print(f"report={args.json_out}")
    if payload["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
