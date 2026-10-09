"""Strict loading for named HarnessBench task subsets."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Iterable

import yaml
from yaml.constructor import ConstructorError
from yaml.nodes import MappingNode


TASK_SET_SCHEMA_VERSION = 1
TASK_SET_SOURCE_SUITE = "main"
TASK_SELECTION_SCHEMA_VERSION = 1
TASK_SET_NAME_PATTERN = re.compile(r"[a-z][a-z0-9_-]{0,63}")
SHA256_ID_PATTERN = re.compile(r"sha256:[0-9a-f]{64}")
TASK_SELECTION_MODES = frozenset({"main", "inline", "named"})
_TASK_SET_FIELDS = frozenset(
    {
        "schema_version",
        "task_set",
        "status",
        "source_suite",
        "source_suite_size",
        "task_count",
        "selection_policy",
        "task_ids",
    }
)
_SELECTION_POLICY_FIELDS = frozenset(
    {
        "selected_at",
        "model_outcomes_used",
        "changes_main_membership",
        "relocates_task_directories",
        "purpose",
    }
)


class TaskSetError(ValueError):
    """Raised when a named task-set manifest is missing or invalid."""


class _UniqueKeySafeLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects duplicate mapping keys."""


def _construct_unique_mapping(
    loader: _UniqueKeySafeLoader,
    node: MappingNode,
    deep: bool = False,
) -> dict[object, object]:
    loader.flatten_mapping(node)
    mapping: dict[object, object] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            duplicate = key in mapping
        except TypeError as exc:
            raise ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                "found an unhashable mapping key",
                key_node.start_mark,
            ) from exc
        if duplicate:
            raise ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"found duplicate key {key!r}",
                key_node.start_mark,
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_UniqueKeySafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


@dataclass(frozen=True)
class TaskSet:
    """One validated named subset of the canonical task suite."""

    schema_version: int
    name: str
    status: str
    source_suite: str
    source_suite_size: int
    task_count: int
    selection_policy: dict[str, Any]
    task_ids: tuple[str, ...]
    source_path: Path
    manifest_sha256: str


def bytes_sha256(payload: bytes) -> str:
    """Return the repository's canonical prefixed SHA-256 representation."""
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def task_ids_sha256(task_ids: Iterable[str]) -> str:
    """Hash one task membership set independently of manifest/list ordering."""
    ids = tuple(task_ids)
    if any(not isinstance(task_id, str) or not task_id for task_id in ids):
        raise TaskSetError("task identity IDs must be non-empty strings")
    canonical_ids = sorted(ids)
    payload = json.dumps(
        canonical_ids,
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return bytes_sha256(payload)


def make_task_selection_identity(
    *,
    mode: str,
    task_ids: Iterable[str],
    task_set: str | None = None,
    manifest_sha256: str | None = None,
) -> dict[str, Any]:
    """Build and validate the global, pre-shard task selection identity."""
    ids = tuple(task_ids)
    if not ids or any(not isinstance(task_id, str) or not task_id for task_id in ids):
        raise TaskSetError("task selection IDs must be non-empty strings")
    if len(ids) != len(set(ids)):
        raise TaskSetError("task selection IDs must be non-empty and unique")
    identity = {
        "schema_version": TASK_SELECTION_SCHEMA_VERSION,
        "mode": mode,
        "task_set": task_set,
        "declared_count": len(ids),
        "task_ids_sha256": task_ids_sha256(ids),
        "manifest_sha256": manifest_sha256,
    }
    validate_task_selection_identity(identity)
    return identity


def validate_task_selection_identity(identity: object) -> dict[str, Any]:
    """Strictly validate a summary-level task selection identity."""
    if not isinstance(identity, dict):
        raise TaskSetError("task selection identity must be one mapping")
    required = {
        "schema_version",
        "mode",
        "task_set",
        "declared_count",
        "task_ids_sha256",
        "manifest_sha256",
    }
    actual = set(identity)
    if actual != required:
        missing = sorted(required - actual)
        unknown = sorted(str(field) for field in actual - required)
        details = []
        if missing:
            details.append("missing=" + ",".join(missing))
        if unknown:
            details.append("unknown=" + ",".join(unknown))
        raise TaskSetError("invalid task selection fields: " + " ".join(details))
    schema_version = identity["schema_version"]
    if (
        isinstance(schema_version, bool)
        or not isinstance(schema_version, int)
        or schema_version != TASK_SELECTION_SCHEMA_VERSION
    ):
        raise TaskSetError(
            f"task selection schema_version must be {TASK_SELECTION_SCHEMA_VERSION}"
        )
    mode = identity["mode"]
    if not isinstance(mode, str) or mode not in TASK_SELECTION_MODES:
        raise TaskSetError("task selection mode must be main, inline, or named")
    count = identity["declared_count"]
    if isinstance(count, bool) or not isinstance(count, int) or count < 1:
        raise TaskSetError("task selection declared_count must be a positive integer")
    ids_hash = identity["task_ids_sha256"]
    if not isinstance(ids_hash, str) or SHA256_ID_PATTERN.fullmatch(ids_hash) is None:
        raise TaskSetError("task selection task_ids_sha256 must be sha256:<hex>")

    task_set = identity["task_set"]
    manifest_hash = identity["manifest_sha256"]
    if mode == "named":
        validate_task_set_name(task_set)
        if (
            not isinstance(manifest_hash, str)
            or SHA256_ID_PATTERN.fullmatch(manifest_hash) is None
        ):
            raise TaskSetError("named task selection requires manifest_sha256")
    elif task_set is not None or manifest_hash is not None:
        raise TaskSetError(
            "main/inline task selection requires null task_set and manifest_sha256"
        )
    return dict(identity)


def validate_task_set_name(name: str) -> str:
    """Validate a CLI/manifest name before using it in a filesystem path."""
    if not isinstance(name, str) or TASK_SET_NAME_PATTERN.fullmatch(name) is None:
        raise TaskSetError("task-set name must match [a-z][a-z0-9_-]{0,63}")
    return name


def load_task_set(
    catalog_dir: Path,
    name: str,
    *,
    known_task_ids: Iterable[str],
) -> TaskSet:
    """Load ``catalog/<name>.yaml`` and validate it against the main suite."""
    safe_name = validate_task_set_name(name)
    source_path = catalog_dir / f"{safe_name}.yaml"
    if source_path.is_symlink():
        raise TaskSetError(f"task-set manifest must not be a symlink: {source_path}")
    if not source_path.is_file():
        raise TaskSetError(f"task-set manifest does not exist: {source_path}")
    try:
        manifest_bytes = source_path.read_bytes()
        manifest_text = manifest_bytes.decode("utf-8")
        raw = yaml.load(manifest_text, Loader=_UniqueKeySafeLoader)
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise TaskSetError(
            f"cannot load task-set manifest {source_path}: {exc}"
        ) from exc

    if not isinstance(raw, dict):
        raise TaskSetError("task-set manifest must be one YAML mapping")
    actual_fields = set(raw)
    missing = sorted(_TASK_SET_FIELDS - actual_fields)
    unknown = sorted(str(field) for field in actual_fields - _TASK_SET_FIELDS)
    if missing:
        raise TaskSetError("task-set manifest missing field(s): " + ", ".join(missing))
    if unknown:
        raise TaskSetError(
            "task-set manifest has unknown field(s): " + ", ".join(unknown)
        )

    schema_version = raw["schema_version"]
    if (
        isinstance(schema_version, bool)
        or not isinstance(schema_version, int)
        or schema_version != TASK_SET_SCHEMA_VERSION
    ):
        raise TaskSetError(f"task-set schema_version must be {TASK_SET_SCHEMA_VERSION}")

    manifest_name = raw["task_set"]
    if not isinstance(manifest_name, str):
        raise TaskSetError("task-set task_set must be a string")
    validate_task_set_name(manifest_name)
    if manifest_name != safe_name:
        raise TaskSetError(
            f"task-set name/file mismatch: {manifest_name!r} != {safe_name!r}"
        )

    status = raw["status"]
    if not isinstance(status, str) or not status.strip() or status.strip() != status:
        raise TaskSetError("task-set status must be a non-empty, trimmed string")
    source_suite = raw["source_suite"]
    if (
        not isinstance(source_suite, str)
        or not source_suite.strip()
        or source_suite.strip() != source_suite
    ):
        raise TaskSetError("task-set source_suite must be a non-empty, trimmed string")
    if source_suite != TASK_SET_SOURCE_SUITE:
        raise TaskSetError(f"task-set source_suite must be {TASK_SET_SOURCE_SUITE!r}")
    source_suite_size = raw["source_suite_size"]
    if (
        isinstance(source_suite_size, bool)
        or not isinstance(source_suite_size, int)
        or source_suite_size < 1
    ):
        raise TaskSetError("task-set source_suite_size must be a positive integer")

    task_count = raw["task_count"]
    if (
        isinstance(task_count, bool)
        or not isinstance(task_count, int)
        or task_count < 1
    ):
        raise TaskSetError("task-set task_count must be a positive integer")

    raw_policy = raw["selection_policy"]
    if not isinstance(raw_policy, dict):
        raise TaskSetError("task-set selection_policy must be one YAML mapping")
    policy_fields = set(raw_policy)
    missing_policy_fields = sorted(_SELECTION_POLICY_FIELDS - policy_fields)
    unknown_policy_fields = sorted(
        str(field) for field in policy_fields - _SELECTION_POLICY_FIELDS
    )
    if missing_policy_fields:
        raise TaskSetError(
            "task-set selection_policy missing field(s): "
            + ", ".join(missing_policy_fields)
        )
    if unknown_policy_fields:
        raise TaskSetError(
            "task-set selection_policy has unknown field(s): "
            + ", ".join(unknown_policy_fields)
        )
    selected_at = raw_policy["selected_at"]
    if not isinstance(selected_at, str):
        raise TaskSetError("task-set selection_policy.selected_at must be YYYY-MM-DD")
    try:
        parsed_selected_at = date.fromisoformat(selected_at)
    except ValueError as exc:
        raise TaskSetError(
            "task-set selection_policy.selected_at must be YYYY-MM-DD"
        ) from exc
    if parsed_selected_at.isoformat() != selected_at:
        raise TaskSetError("task-set selection_policy.selected_at must be YYYY-MM-DD")
    for key in (
        "model_outcomes_used",
        "changes_main_membership",
        "relocates_task_directories",
    ):
        if not isinstance(raw_policy[key], bool):
            raise TaskSetError(f"task-set selection_policy.{key} must be boolean")
    for key in ("changes_main_membership", "relocates_task_directories"):
        if raw_policy[key]:
            raise TaskSetError(f"task-set selection_policy.{key} must be false")
    purpose = raw_policy["purpose"]
    if (
        not isinstance(purpose, str)
        or not purpose.strip()
        or purpose.strip() != purpose
    ):
        raise TaskSetError(
            "task-set selection_policy.purpose must be a non-empty, trimmed string"
        )

    raw_task_ids = raw["task_ids"]
    if not isinstance(raw_task_ids, list):
        raise TaskSetError("task-set task_ids must be a YAML list")
    task_ids: list[str] = []
    seen: set[str] = set()
    duplicates: set[str] = set()
    for index, task_id in enumerate(raw_task_ids):
        if not isinstance(task_id, str) or not task_id or task_id.strip() != task_id:
            raise TaskSetError(
                f"task-set task_ids[{index}] must be a non-empty, trimmed string"
            )
        if task_id in seen:
            duplicates.add(task_id)
        seen.add(task_id)
        task_ids.append(task_id)
    if duplicates:
        raise TaskSetError(
            "task-set contains duplicate task ID(s): " + ", ".join(sorted(duplicates))
        )
    if task_count != len(task_ids):
        raise TaskSetError(
            "task-set task_count mismatch: "
            f"declared {task_count}, found {len(task_ids)} task_ids"
        )

    known = set(known_task_ids)
    historical_frozen_subset = (
        status.startswith("frozen_")
        and source_suite_size < len(known)
        and set(task_ids).issubset(known)
    )
    if source_suite_size != len(known) and not historical_frozen_subset:
        raise TaskSetError(
            "task-set source_suite_size mismatch: "
            f"declared {source_suite_size}, found {len(known)} known task IDs"
        )
    unknown_task_ids = sorted(set(task_ids) - known)
    if unknown_task_ids:
        raise TaskSetError(
            "task-set contains unknown task ID(s): " + ", ".join(unknown_task_ids)
        )

    return TaskSet(
        schema_version=schema_version,
        name=manifest_name,
        status=status,
        source_suite=source_suite,
        source_suite_size=source_suite_size,
        task_count=task_count,
        selection_policy=dict(raw_policy),
        task_ids=tuple(task_ids),
        source_path=source_path.resolve(),
        manifest_sha256=bytes_sha256(manifest_bytes),
    )
