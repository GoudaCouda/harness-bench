"""Suite-wide validation contract for Harness-Bench task oracles.

Task-specific oracles own semantic scoring. This module owns only invariants
that must be identical in local validation and the isolated Docker grader.
"""

from __future__ import annotations

import hashlib
import json
import math
import stat
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Iterable, Mapping


CONTRACT_CHECK_ID = "required_artifact_contract"
WORKSPACE_MUTATION_CHECK_ID = "workspace_mutation_contract"
ARTIFACT_SAFETY_CHECK_ID = "required_artifact_safety"
WORKSPACE_SAFETY_CHECK_ID = "workspace_mutation_safety"
STRUCTURAL_POLICY_LEGACY = "legacy_hard_gate"
STRUCTURAL_POLICY_CASE_OWNED = "case_owned"
WORKSPACE_MUTATION_SCHEMA_VERSION = 4
ORACLE_CONTRACT_VERSION = 6
IGNORED_RUNTIME_PARTS = frozenset({"__pycache__", ".pytest_cache", ".ruff_cache"})


class OracleInfrastructureError(RuntimeError):
    """A trusted grader dependency or service is unavailable.

    This is not candidate evidence and therefore must never be converted into
    a scoreable zero.
    """


def normalize_required_artifacts(values: Iterable[object]) -> list[str]:
    """Return unique, safe, workspace-relative artifact paths."""
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in values:
        value = str(raw).strip().replace("\\", "/").rstrip("/")
        if not value:
            continue
        candidate = PurePosixPath(value)
        if candidate.is_absolute() or ".." in candidate.parts:
            raise ValueError(f"unsafe required_artifact path: {raw!r}")
        rendered = candidate.as_posix()
        if rendered not in seen:
            seen.add(rendered)
            normalized.append(rendered)
    return normalized


def normalize_mutation_contract(
    value: Mapping[str, object] | None,
) -> dict[str, list[str]]:
    """Validate the paths an agent may create, modify, or delete.

    Paths are relative to the single writable workspace. A trailing slash
    declares a directory subtree; other entries are exact file paths. Globs
    are intentionally unsupported so ownership boundaries remain auditable.
    """
    raw = dict(value or {})
    allowed_fields = {
        "allowed_created",
        "allowed_modified",
        "allowed_deleted",
    }
    unknown = sorted(set(raw) - allowed_fields)
    if unknown:
        raise ValueError(f"unknown mutation_contract field(s): {unknown}")

    normalized: dict[str, list[str]] = {}
    for field in sorted(allowed_fields):
        values = raw.get(field, [])
        if not isinstance(values, (list, tuple)):
            raise ValueError(f"mutation_contract.{field} must be a list")
        paths: list[str] = []
        seen: set[str] = set()
        for item in values:
            original = str(item).strip().replace("\\", "/")
            subtree = original.endswith("/")
            rendered = original.rstrip("/")
            candidate = PurePosixPath(rendered)
            if (
                not rendered
                or candidate.is_absolute()
                or ".." in candidate.parts
                or "." in candidate.parts
                or any(token in rendered for token in ("*", "?", "[", "]"))
            ):
                raise ValueError(
                    f"mutation_contract.{field} contains an unsafe path: {item!r}"
                )
            exact = candidate.as_posix() + ("/" if subtree else "")
            if exact not in seen:
                seen.add(exact)
                paths.append(exact)
        normalized[field] = paths
    return normalized


def workspace_manifest(workspace: Path) -> dict[str, dict[str, object]]:
    """Hash every workspace entry without following symbolic links."""
    manifest: dict[str, dict[str, object]] = {}
    if not workspace.is_dir() or workspace.is_symlink():
        raise ValueError("workspace must be a real directory")
    for path in sorted(workspace.rglob("*")):
        relative_path = path.relative_to(workspace)
        if (
            any(part in IGNORED_RUNTIME_PARTS for part in relative_path.parts)
            or path.suffix == ".pyc"
        ):
            continue
        relative = relative_path.as_posix()
        mode = path.lstat().st_mode
        if stat.S_ISDIR(mode):
            manifest[f"{relative}/"] = {"kind": "directory"}
        elif stat.S_ISREG(mode):
            manifest[relative] = {
                "kind": "file",
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "size": path.stat(follow_symlinks=False).st_size,
            }
        elif stat.S_ISLNK(mode):
            manifest[relative] = {
                "kind": "symlink",
                "target": str(path.readlink()),
            }
        else:
            manifest[relative] = {
                "kind": "special",
                "mode": stat.S_IFMT(mode),
            }
    return manifest


def manifest_sha256(manifest: Mapping[str, object]) -> str:
    """Return one stable identity for a workspace manifest."""
    payload = json.dumps(
        manifest,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _path_is_allowed(path: str, rules: Iterable[str]) -> bool:
    return any(
        path.startswith(rule) if rule.endswith("/") else path == rule for rule in rules
    )


def _created_path_is_allowed(path: str, rules: Iterable[str]) -> bool:
    declared = tuple(rules)
    if _path_is_allowed(path, declared):
        return True
    # Creating a declared descendant necessarily creates its missing parent
    # directories. Treat only those directory ancestors as implicit ownership;
    # unrelated empty or scratch directories remain diagnostic violations.
    return path.endswith("/") and any(rule.startswith(path) for rule in declared)


def workspace_mutation_report(
    before: Mapping[str, object],
    after: Mapping[str, object],
    *,
    contract: Mapping[str, object] | None,
    protected_paths: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Compare two trusted snapshots against one task mutation contract.

    ``complete`` records exact conformance with the declared create/modify/delete
    boundary.  ``safe`` is intentionally narrower: a regular undeclared scratch
    file or a mistaken operation on a task-owned deliverable is diagnostic, while
    mutation of an initial protected path and linked/special entries are safety
    violations.  Callers that measure several rounds should pass paths from the
    run's initial manifest so a scratch file created in an earlier round does not
    become protected merely because it exists in the next round's ``before``.
    """
    normalized = normalize_mutation_contract(contract)
    before_paths = set(before)
    after_paths = set(after)
    protected = set(before_paths if protected_paths is None else protected_paths)
    created = sorted(after_paths - before_paths)
    deleted = sorted(before_paths - after_paths)
    modified = sorted(
        path for path in before_paths & after_paths if before[path] != after[path]
    )
    unexpected_created = [
        path
        for path in created
        if not _created_path_is_allowed(path, normalized["allowed_created"])
    ]
    unexpected_modified = [
        path
        for path in modified
        if not _path_is_allowed(path, normalized["allowed_modified"])
    ]
    unexpected_deleted = [
        path
        for path in deleted
        if not _path_is_allowed(path, normalized["allowed_deleted"])
    ]
    unsafe_entries = sorted(
        path
        for path, value in after.items()
        if not isinstance(value, Mapping)
        or value.get("kind") not in {"directory", "file"}
    )
    owned_rules = [
        *normalized["allowed_created"],
        *normalized["allowed_modified"],
        *normalized["allowed_deleted"],
    ]
    protected_modified = sorted(
        path
        for path in modified
        if path in protected and not _path_is_allowed(path, owned_rules)
    )
    protected_deleted = sorted(
        path
        for path in deleted
        if path in protected and not _path_is_allowed(path, owned_rules)
    )
    complete = not (
        unexpected_created
        or unexpected_modified
        or unexpected_deleted
        or unsafe_entries
    )
    safe = not (protected_modified or protected_deleted or unsafe_entries)
    return {
        "schema_version": WORKSPACE_MUTATION_SCHEMA_VERSION,
        "enabled": True,
        "complete": complete,
        "safe": safe,
        "contract": normalized,
        "before_sha256": manifest_sha256(before),
        "after_sha256": manifest_sha256(after),
        "created": created,
        "modified": modified,
        "deleted": deleted,
        "unexpected_created": unexpected_created,
        "unexpected_modified": unexpected_modified,
        "unexpected_deleted": unexpected_deleted,
        "unsafe_entries": unsafe_entries,
        "protected_modified": protected_modified,
        "protected_deleted": protected_deleted,
        "safety_violations": {
            "protected_modified": protected_modified,
            "protected_deleted": protected_deleted,
            "unsafe_entries": unsafe_entries,
        },
    }


def required_artifact_report(
    workspace: Path,
    required_artifacts: Iterable[object],
) -> dict[str, Any]:
    declared = normalize_required_artifacts(required_artifacts)
    root = workspace.resolve()
    present: list[str] = []
    missing: list[str] = []
    invalid: dict[str, str] = {}
    safety_violations: dict[str, str] = {}
    for item in declared:
        path = workspace / item
        try:
            try:
                mode = path.lstat().st_mode
            except FileNotFoundError:
                missing.append(item)
                continue
            present.append(item)
            if stat.S_ISLNK(mode):
                invalid[item] = "symbolic links are not accepted"
                safety_violations[item] = invalid[item]
                continue
            resolved = path.resolve()
            if not resolved.is_relative_to(root):
                invalid[item] = "path escapes workspace"
                safety_violations[item] = invalid[item]
                continue
            if stat.S_ISDIR(mode):
                children = [
                    child
                    for child in path.rglob("*")
                    if child.is_file() and not child.is_symlink()
                ]
                if not children:
                    invalid[item] = "required directory contains no files"
                continue
            if not stat.S_ISREG(mode):
                invalid[item] = "artifact is not a regular file"
                safety_violations[item] = invalid[item]
                continue
            if path.stat().st_size == 0:
                invalid[item] = "artifact is empty"
                continue
            suffix = path.suffix.lower()
            if suffix in {
                ".csv",
                ".html",
                ".htm",
                ".jsonl",
                ".md",
                ".py",
                ".sql",
                ".txt",
                ".yaml",
                ".yml",
            }:
                path.read_text(encoding="utf-8")
            if suffix == ".json":
                json.loads(path.read_text(encoding="utf-8"))
            if suffix in {".docx", ".pptx", ".xlsx"} and not zipfile.is_zipfile(path):
                invalid[item] = f"{suffix} is not a valid ZIP-based document"
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            invalid[item] = f"{type(exc).__name__}: {exc}"
    return {
        "declared": declared,
        "present": present,
        "missing": missing,
        "invalid": invalid,
        "complete": not missing and not invalid,
        "safe": not safety_violations,
        "safety_violations": safety_violations,
    }


def _structural_policy(value: str) -> str:
    if value not in {STRUCTURAL_POLICY_LEGACY, STRUCTURAL_POLICY_CASE_OWNED}:
        raise ValueError(f"unsupported structural scoring policy: {value!r}")
    return value


def _mutation_safe(value: dict[str, Any] | None) -> bool:
    if value is None or not value.get("enabled"):
        return True
    declared = value.get("safe")
    if isinstance(declared, bool):
        return declared
    # Compatibility for trusted schema-v2 reports.  A report without the new
    # ownership classification cannot distinguish an owned mistaken operation,
    # so modifications/deletions remain fail-closed while regular creations do
    # not become safety events.
    return not (
        value.get("unexpected_modified")
        or value.get("unexpected_deleted")
        or value.get("unsafe_entries")
    )


def _contract_safety_failures(
    artifacts: Mapping[str, object],
    workspace_mutation: dict[str, Any] | None,
) -> list[str]:
    failures: list[str] = []
    if artifacts.get("safe") is False:
        failures.append(ARTIFACT_SAFETY_CHECK_ID)
    if not _mutation_safe(workspace_mutation):
        failures.append(WORKSPACE_SAFETY_CHECK_ID)
    return failures


def _bounded_score(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("outcome_score must be a number")
    score = float(value)
    if not math.isfinite(score):
        raise ValueError("outcome_score must be finite")
    if not 0.0 <= score <= 1.0:
        raise ValueError(f"outcome_score must be in [0, 1], got {score}")
    return score


def apply_oracle_contract(
    result: dict[str, Any],
    *,
    workspace: Path,
    required_artifacts: Iterable[object],
    workspace_mutation: dict[str, Any] | None = None,
    structural_policy: str = STRUCTURAL_POLICY_LEGACY,
) -> dict[str, Any]:
    """Validate one result and apply only the selected structural policy."""
    policy = _structural_policy(structural_policy)
    normalized = dict(result)
    score = _bounded_score(normalized.get("outcome_score"))
    declared_success = normalized.get("task_success")
    if declared_success is not None and not isinstance(declared_success, bool):
        raise ValueError("task_success must be a boolean when provided")
    raw_checks = normalized.get("checks")
    checks = (
        [dict(item) for item in raw_checks if isinstance(item, dict)]
        if isinstance(raw_checks, list)
        else []
    )
    artifacts = required_artifact_report(workspace, required_artifacts)
    checks = [
        item
        for item in checks
        if item.get("id")
        not in {
            CONTRACT_CHECK_ID,
            WORKSPACE_MUTATION_CHECK_ID,
            ARTIFACT_SAFETY_CHECK_ID,
            WORKSPACE_SAFETY_CHECK_ID,
        }
    ]
    checks.append(
        {
            "id": CONTRACT_CHECK_ID,
            "label": "all declared required artifacts exist",
            "pass": artifacts["complete"],
            "weight": 0.0,
            "gate": False,
            "diagnostic": True,
            "detail": (
                None
                if artifacts["complete"]
                else {
                    "missing": artifacts["missing"],
                    "invalid": artifacts["invalid"],
                }
            ),
        }
    )
    if workspace_mutation and workspace_mutation.get("enabled"):
        checks.append(
            {
                "id": WORKSPACE_MUTATION_CHECK_ID,
                "label": "workspace changes stay within the declared ownership boundary",
                "pass": bool(workspace_mutation.get("complete")),
                "weight": 0.0,
                "gate": False,
                "diagnostic": True,
                "detail": (
                    None
                    if workspace_mutation.get("complete")
                    else {
                        "unexpected_created": workspace_mutation.get(
                            "unexpected_created", []
                        ),
                        "unexpected_modified": workspace_mutation.get(
                            "unexpected_modified", []
                        ),
                        "unexpected_deleted": workspace_mutation.get(
                            "unexpected_deleted", []
                        ),
                        "unsafe_entries": workspace_mutation.get("unsafe_entries", []),
                    }
                ),
            }
        )
    checks.append(
        {
            "id": ARTIFACT_SAFETY_CHECK_ID,
            "label": "declared artifacts stay within the regular-file boundary",
            "pass": bool(artifacts["safe"]),
            "weight": 0.0,
            "gate": True,
            "detail": artifacts["safety_violations"] or None,
        }
    )
    if workspace_mutation and workspace_mutation.get("enabled"):
        checks.append(
            {
                "id": WORKSPACE_SAFETY_CHECK_ID,
                "label": "protected inputs and filesystem boundaries remain intact",
                "pass": _mutation_safe(workspace_mutation),
                "weight": 0.0,
                "gate": True,
                "detail": workspace_mutation.get("safety_violations") or None,
            }
        )

    safety_failures = _contract_safety_failures(artifacts, workspace_mutation)
    legacy_failure = policy == STRUCTURAL_POLICY_LEGACY and (
        not artifacts["complete"]
        or (
            workspace_mutation
            and workspace_mutation.get("enabled")
            and not workspace_mutation.get("complete")
        )
    )
    if safety_failures or legacy_failure:
        score = 0.0
        if declared_success is not None:
            normalized["task_success"] = False
    normalized["checks"] = checks
    normalized["outcome_score"] = round(score, 4)
    normalized["required_artifact_contract"] = artifacts
    if workspace_mutation is not None:
        normalized["workspace_mutation_contract"] = workspace_mutation
    raw_contract_failures = normalized.get("failed_contract_gates")
    existing_contract_failures = (
        [str(item) for item in raw_contract_failures]
        if isinstance(raw_contract_failures, list)
        else []
    )
    normalized["failed_contract_gates"] = list(
        dict.fromkeys([*existing_contract_failures, *safety_failures])
    )
    normalized["structural_scoring_policy"] = policy
    normalized["oracle_contract_version"] = ORACLE_CONTRACT_VERSION
    return normalized


def safe_score_workspace(
    score_workspace: Callable[[Path], object],
    *,
    workspace: Path,
    required_artifacts: Iterable[object],
    task_id: str = "",
    workspace_mutation: dict[str, Any] | None = None,
    require_task_success: bool = False,
    structural_policy: str = STRUCTURAL_POLICY_LEGACY,
) -> dict[str, Any]:
    """Run an oracle without allowing malformed submissions to crash grading."""
    policy = _structural_policy(structural_policy)
    artifacts = required_artifact_report(workspace, required_artifacts)
    mutation_complete = (
        workspace_mutation is None
        or not workspace_mutation.get("enabled")
        or bool(workspace_mutation.get("complete"))
    )
    safety_failure = bool(_contract_safety_failures(artifacts, workspace_mutation))
    legacy_failure = policy == STRUCTURAL_POLICY_LEGACY and (
        not artifacts["complete"] or not mutation_complete
    )
    if safety_failure or legacy_failure:
        # Case-owned evaluators receive ordinary missing and malformed work so
        # their business blocks lose weight naturally.  Filesystem redlines are
        # still stopped before task code can accidentally follow or read them.
        structural_result: dict[str, Any] = {
            "task": task_id,
            "workspace": str(workspace),
            "checks": [],
            "outcome_score": 0.0,
            "weighted_score": 0.0,
            "business_evaluation_skipped": True,
        }
        if require_task_success:
            structural_result["task_success"] = False
        return apply_oracle_contract(
            structural_result,
            workspace=workspace,
            required_artifacts=required_artifacts,
            workspace_mutation=workspace_mutation,
            structural_policy=policy,
        )
    try:
        raw = score_workspace(workspace)
        if not isinstance(raw, dict):
            raise TypeError(
                f"score_workspace must return dict, got {type(raw).__name__}"
            )
        return apply_oracle_contract(
            raw,
            workspace=workspace,
            required_artifacts=required_artifacts,
            workspace_mutation=workspace_mutation,
            structural_policy=policy,
        )
    except Exception as exc:
        infrastructure_failure = isinstance(exc, OracleInfrastructureError)
        failure = {
            "task": task_id,
            "workspace": str(workspace),
            "checks": [
                {
                    "id": "oracle_execution",
                    "label": "oracle executes successfully",
                    "pass": False,
                    "weight": 0.0,
                    "detail": f"{type(exc).__name__}: {exc}",
                }
            ],
            "outcome_score": 0.0,
            "error": f"{type(exc).__name__}: {exc}",
            "oracle_contract_failure": True,
            "oracle_infrastructure_failure": infrastructure_failure,
            "required_artifact_contract": artifacts,
            "workspace_mutation_contract": workspace_mutation,
            "failed_contract_gates": _contract_safety_failures(
                artifacts, workspace_mutation
            ),
            "structural_scoring_policy": policy,
            "oracle_contract_version": ORACLE_CONTRACT_VERSION,
        }
        if require_task_success:
            failure["task_success"] = False
        return failure
