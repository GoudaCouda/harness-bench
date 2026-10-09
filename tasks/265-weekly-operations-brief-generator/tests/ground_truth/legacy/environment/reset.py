#!/usr/bin/env python3
"""从锁定的 case_11 fixture 原子构建一个全新 Agent workspace。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import sys
from pathlib import Path
from typing import Any


STABLE = re.compile(r"^[a-z0-9][a-z0-9._-]{2,80}$")
PLAN_SCHEMA = "case11_execution_ownership_plan_v2"
VARIANT_SCHEMA = "case11_fixture_variants_v2"
CASE_ROOT = Path(__file__).resolve().parents[1]
VARIANT_MANIFEST = CASE_ROOT / "tests/hidden/variant_manifest.json"
INPUT_NAMES = ("weekly_operations.csv", "metric_definitions.json", "brief_template.md")


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_object(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ValueError("JSON 必须是非链接普通文件")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("JSON 根必须是对象")
    return value


def inventory_hash(workspace: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(workspace.rglob("*")):
        if path.is_symlink():
            raise ValueError("初始 workspace 不得含符号链接")
        relative = path.relative_to(workspace).as_posix()
        kind = "d" if path.is_dir() else "f" if path.is_file() else "o"
        mode = stat.S_IMODE(path.lstat().st_mode)
        digest.update(f"{kind}:{mode:o}:{relative}\0".encode("utf-8"))
        if path.is_file():
            digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def validate_plan(plan_path: Path) -> tuple[dict[str, Any], Path, Path]:
    plan = read_object(plan_path)
    if plan.get("schema_version") != PLAN_SCHEMA:
        raise ValueError("ownership plan 版本无效")
    runtime_root = plan_path.parent.parent.resolve(strict=True)
    if Path(str(plan.get("runtime_root", ""))).resolve(strict=True) != runtime_root:
        raise ValueError("runtime root 无效")
    attempts_root = Path(str(plan.get("attempts_root", ""))).resolve(strict=True)
    if attempts_root != runtime_root / "attempts" or attempts_root.is_symlink():
        raise ValueError("attempts root 无效")
    evidence_root = Path(str(plan.get("evidence_root", ""))).resolve(strict=True)
    if evidence_root != runtime_root / "evidence" or evidence_root.is_symlink():
        raise ValueError("evidence root 无效")
    return plan, attempts_root, evidence_root


def variant_sources(variant: str) -> dict[str, Path]:
    manifest = read_object(VARIANT_MANIFEST)
    if manifest.get("schema_version") != VARIANT_SCHEMA:
        raise ValueError("fixture variant manifest 版本无效")
    variants = manifest.get("variants")
    if not isinstance(variants, dict) or variant not in variants:
        raise ValueError("fixture variant 无效")
    record = variants[variant]
    if not isinstance(record, dict) or set(record) != set(INPUT_NAMES):
        raise ValueError("fixture variant 字段无效")
    result: dict[str, Path] = {}
    for destination, item in record.items():
        if not isinstance(item, dict) or set(item) != {"path", "sha256"}:
            raise ValueError("fixture variant 资产记录无效")
        relative = Path(str(item["path"]))
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("fixture 路径越界")
        source = (CASE_ROOT / relative).resolve(strict=True)
        if CASE_ROOT.resolve() not in source.parents or source.is_symlink() or not source.is_file():
            raise ValueError("fixture 必须是 case 内的非链接普通文件")
        if not re.fullmatch(r"[0-9a-f]{64}", str(item["sha256"])):
            raise ValueError("fixture SHA-256 无效")
        if file_hash(source) != item["sha256"]:
            raise ValueError("fixture SHA-256 不匹配")
        result[destination] = source
    return result


def build_workspace(stage: Path, sources: dict[str, Path]) -> dict[str, str]:
    stage.mkdir(mode=0o2770)
    (stage / "input").mkdir(mode=0o2750)
    (stage / "output").mkdir(mode=0o2770)
    (stage / "submission").mkdir(mode=0o2770)
    stage.chmod(0o2770)
    (stage / "input").chmod(0o2750)
    (stage / "output").chmod(0o2770)
    (stage / "submission").chmod(0o2770)
    hashes: dict[str, str] = {}
    for name in INPUT_NAMES:
        target = stage / "input" / name
        shutil.copyfile(sources[name], target)
        target.chmod(0o640)
        hashes[f"input/{name}"] = file_hash(target)
    return hashes


def input_baseline(workspace: Path, variant: str, state_hash: str) -> dict[str, Any]:
    files: dict[str, dict[str, Any]] = {}
    for name in INPUT_NAMES:
        path = workspace / "input" / name
        status = path.lstat()
        files[f"input/{name}"] = {
            "sha256": file_hash(path),
            "size_bytes": status.st_size,
            "mode": stat.S_IMODE(status.st_mode),
            "uid": status.st_uid,
            "gid": status.st_gid,
            "device": status.st_dev,
            "inode": status.st_ino,
            "link_count": status.st_nlink,
        }
    return {
        "schema_version": "case11_reset_baseline_v2",
        "fixture_variant": variant,
        "initial_state_sha256": state_hash,
        "input_files": files,
    }


def write_exclusive_json(path: Path, value: dict[str, Any]) -> None:
    payload = (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o640)
    try:
        os.write(descriptor, payload)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--workspace-id", required=True)
    parser.add_argument("--variant", default="primary")
    args = parser.parse_args()
    stage: Path | None = None
    try:
        if not STABLE.fullmatch(args.workspace_id) or not STABLE.fullmatch(args.variant):
            raise ValueError("workspace ID 或 variant 无效")
        plan_path = args.plan.resolve(strict=True)
        _, attempts_root, evidence_root = validate_plan(plan_path)
        workspace = attempts_root / args.workspace_id
        if workspace.exists() or workspace.is_symlink():
            raise ValueError("不得覆盖已有 workspace")
        stage = attempts_root / f".reset-{args.workspace_id}-{os.getpid()}"
        if stage.exists() or stage.is_symlink():
            raise ValueError("reset staging 路径已存在")
        baselines_root = evidence_root / "reset_baselines"
        baselines_root.mkdir(mode=0o2770, exist_ok=True)
        baseline_path = baselines_root / f"{args.workspace_id}.json"
        if baseline_path.exists() or baseline_path.is_symlink():
            raise ValueError("不得覆盖 reset baseline")
        hashes = build_workspace(stage, variant_sources(args.variant))
        state_hash = inventory_hash(stage)
        os.replace(stage, workspace)
        stage = None
        try:
            write_exclusive_json(
                baseline_path,
                input_baseline(workspace, args.variant, state_hash),
            )
        except Exception:
            shutil.rmtree(workspace, ignore_errors=True)
            raise
        result = {
            "schema_version": "case11_reset_result_v2",
            "workspace_id": args.workspace_id,
            "fixture_variant": args.variant,
            "initial_state_sha256": state_hash,
            "input_sha256": hashes,
            "directories": ["input", "output", "submission"],
            "baseline_path": baseline_path.as_posix(),
        }
        sys.stdout.write(json.dumps(result, ensure_ascii=False, sort_keys=True) + "\n")
        return 0
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        if stage is not None and stage.exists() and stage.name.startswith(".reset-"):
            shutil.rmtree(stage, ignore_errors=True)
        print(f"reset 失败：{type(exc).__name__}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
