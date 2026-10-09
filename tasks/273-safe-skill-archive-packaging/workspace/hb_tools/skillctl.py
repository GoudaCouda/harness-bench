from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import sys
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


PACKAGE_NAME = "calendar_briefing_skill"
PACKAGE_VERSION = "1.2.0"
ENTRYPOINT = "scripts/main.py"
PAYLOAD_PATHS = ("SKILL.md", "assets/template.txt", "scripts/main.py")
ZIP_PATHS = tuple(f"{PACKAGE_NAME}/{path}" for path in PAYLOAD_PATHS) + (
    f"{PACKAGE_NAME}/manifest.json",
)
FIXED_ZIP_TIME = (2026, 7, 1, 0, 0, 0)


class ContractError(ValueError):
    pass


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def read_regular_file(path: Path, root: Path) -> bytes:
    try:
        relative = path.relative_to(root)
    except ValueError as exc:
        raise ContractError("path_outside_skill_root") from exc
    if not relative.parts or any(part in {"", ".", ".."} for part in relative.parts):
        raise ContractError("unsafe_relative_path")
    current = root
    for part in relative.parts:
        current = current / part
        info = current.lstat()
        if stat.S_ISLNK(info.st_mode):
            raise ContractError("symlink_forbidden")
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode):
        raise ContractError("non_regular_file_forbidden")
    if info.st_size > 131072:
        raise ContractError("file_too_large")
    return path.read_bytes()


def expected_file_records(skill_dir: Path) -> list[dict[str, Any]]:
    root = skill_dir.resolve(strict=True)
    records: list[dict[str, Any]] = []
    for relative in PAYLOAD_PATHS:
        value = read_regular_file(root / PurePosixPath(relative), root)
        records.append(
            {"path": relative, "sha256": sha256_bytes(value), "size_bytes": len(value)}
        )
    return records


def load_manifest(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ContractError("manifest_not_regular")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ContractError("manifest_invalid_json") from exc
    if not isinstance(value, dict):
        raise ContractError("manifest_not_object")
    return value


def validate_manifest(skill_dir: Path, manifest_path: Path) -> dict[str, Any]:
    manifest = load_manifest(manifest_path)
    if set(manifest) != {"schema_version", "package_name", "version", "entrypoint", "files"}:
        raise ContractError("manifest_keys_mismatch")
    expected_scalar = {
        "schema_version": "skill_package_manifest_v1",
        "package_name": PACKAGE_NAME,
        "version": PACKAGE_VERSION,
        "entrypoint": ENTRYPOINT,
    }
    for key, expected in expected_scalar.items():
        if manifest.get(key) != expected:
            raise ContractError(f"manifest_{key}_mismatch")
    expected_records = expected_file_records(skill_dir)
    if manifest.get("files") != expected_records:
        raise ContractError("manifest_files_mismatch")
    return manifest


def canonical_manifest_bytes(manifest: dict[str, Any]) -> bytes:
    return (json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def expected_workspace_root(skill_dir: Path) -> Path:
    if skill_dir.is_symlink():
        raise ContractError("skill_root_symlink_forbidden")
    root = skill_dir.resolve(strict=True)
    if root.name != PACKAGE_NAME or root.parent.name != "input":
        raise ContractError("skill_root_layout_mismatch")
    return root.parent.parent


def safe_output_path(output: Path, skill_dir: Path, manifest_path: Path) -> Path:
    workspace = expected_workspace_root(skill_dir)
    expected_output_dir = workspace / "output"
    if expected_output_dir.is_symlink() or not expected_output_dir.is_dir():
        raise ContractError("output_directory_invalid")
    resolved_parent = output.parent.resolve(strict=True)
    if output.exists() and output.is_symlink():
        raise ContractError("output_symlink_forbidden")
    if resolved_parent != expected_output_dir.resolve(strict=True):
        raise ContractError("output_outside_allowed_directory")
    if output.name != "calendar_briefing_skill.zip":
        raise ContractError("output_name_mismatch")
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise ContractError("manifest_not_regular")
    resolved_manifest = manifest_path.resolve(strict=True)
    if (
        resolved_manifest.parent != workspace
        or resolved_manifest.name != ".manifest.build.json"
    ):
        raise ContractError("manifest_outside_allowed_path")
    return resolved_parent / output.name


def write_zip(skill_dir: Path, manifest_path: Path, output: Path) -> None:
    manifest = validate_manifest(skill_dir, manifest_path)
    output = safe_output_path(output, skill_dir, manifest_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = output.with_name(output.name + ".partial")
    if staging.exists() or staging.is_symlink():
        raise ContractError("staging_path_already_exists")
    root = skill_dir.resolve(strict=True)
    try:
        with zipfile.ZipFile(
            staging, mode="x", compression=zipfile.ZIP_DEFLATED, compresslevel=9
        ) as archive:
            values = {
                f"{PACKAGE_NAME}/{relative}": read_regular_file(
                    root / PurePosixPath(relative), root
                )
                for relative in PAYLOAD_PATHS
            }
            values[f"{PACKAGE_NAME}/manifest.json"] = canonical_manifest_bytes(manifest)
            for name in ZIP_PATHS:
                info = zipfile.ZipInfo(name, FIXED_ZIP_TIME)
                info.create_system = 3
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = (stat.S_IFREG | 0o644) << 16
                info.flag_bits |= 0x800
                archive.writestr(info, values[name])
        os.replace(staging, output)
    except BaseException:
        if staging.exists() and not staging.is_symlink():
            staging.unlink()
        raise


def inspect(skill_dir: Path) -> list[dict[str, Any]]:
    root = skill_dir.resolve(strict=True)
    results: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode):
            kind = "symlink"
            digest = None
        elif stat.S_ISREG(info.st_mode):
            kind = "regular"
            value = read_regular_file(path, root)
            digest = sha256_bytes(value)
        elif stat.S_ISDIR(info.st_mode):
            kind = "directory"
            digest = None
        else:
            kind = "special"
            digest = None
        results.append(
            {"path": relative, "kind": kind, "size_bytes": info.st_size, "sha256": digest}
        )
    return results


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser()
    commands = root.add_subparsers(dest="command", required=True)
    inspect_parser = commands.add_parser("inspect")
    inspect_parser.add_argument("--skill-dir", type=Path, required=True)
    validate_parser = commands.add_parser("validate-manifest")
    validate_parser.add_argument("--skill-dir", type=Path, required=True)
    validate_parser.add_argument("--manifest", type=Path, required=True)
    package_parser = commands.add_parser("package")
    package_parser.add_argument("--skill-dir", type=Path, required=True)
    package_parser.add_argument("--manifest", type=Path, required=True)
    package_parser.add_argument("--output", type=Path, required=True)
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        if args.command == "inspect":
            payload = {"status": "ok", "files": inspect(args.skill_dir)}
        elif args.command == "validate-manifest":
            payload = {"status": "ok", "manifest": validate_manifest(args.skill_dir, args.manifest)}
        else:
            write_zip(args.skill_dir, args.manifest, args.output)
            payload = {"status": "ok", "output": str(args.output)}
    except (ContractError, FileNotFoundError, OSError) as exc:
        payload = {"status": "error", "error": str(exc)}
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 2
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
