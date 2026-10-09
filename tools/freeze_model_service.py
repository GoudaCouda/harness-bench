#!/usr/bin/env python3
"""Freeze a multi-replica vLLM deployment into one safe identity."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import stat
import tempfile
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit


SCHEMA_VERSION = 2
IDENTITY_FIELDS = frozenset(
    {
        "schema_version",
        "deployment_source",
        "deployment_artifacts",
        "runtime_observation",
        "semantic_config",
        "replicas",
    }
)
FROZEN_MANIFEST_FIELDS = IDENTITY_FIELDS | {"model_service_id"}
ENV_KEY_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
VERSION_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9.+_-]*\Z")
PROVIDER_RE = re.compile(r"[a-z0-9][a-z0-9._-]*\Z")
SMOKE_VERSION_PATTERNS = {
    "torch": re.compile(r"^torch\s+(\S+)(?:\s+cuda\s+\S+)?\s*$", re.MULTILINE),
    "transformers": re.compile(r"^transformers\s+(\S+)\s*$", re.MULTILINE),
    "vllm": re.compile(r"^vllm\s+(\S+)\s*$", re.MULTILINE),
}
ASSET_SIZE_LIMITS = {
    "model_config": 16 * 1024 * 1024,
    "model_safetensors_index": 64 * 1024 * 1024,
    "chat_template": 16 * 1024 * 1024,
    "inner_script": 16 * 1024 * 1024,
}
MAX_SERVER_LOG_BYTES = 64 * 1024 * 1024

INT_FIELDS = {
    "max_model_len",
    "max_num_seqs",
    "max_num_batched_tokens",
    "tp_size",
    "dp_size",
}
BOOL_FIELDS = {
    "vllm_env_dereference",
    "copy_runtime_to_shm",
    "enable_thinking",
    "enable_prefix_caching",
    "enforce_eager",
}
STRING_FIELDS = {
    "served_model_name",
    "model_dir",
    "runtime_source",
    "vllm_env_subdir",
    "tool_call_parser",
    "reasoning_parser",
}
OPTIONAL_STRING_FIELDS = {"overlay_site"}
SEMANTIC_ENDPOINT_FIELDS = tuple(
    sorted(
        INT_FIELDS
        | BOOL_FIELDS
        | STRING_FIELDS
        | OPTIONAL_STRING_FIELDS
        | {"gpu_memory_utilization"}
    )
)
RUNTIME_MATERIALIZING_LAUNCHERS = {
    "serve_gemma4_vllm024_tar_multinode_a800.sh",
}


class FreezeError(ValueError):
    """The deployment cannot be assigned a trustworthy service identity."""


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise FreezeError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise FreezeError(f"non-finite JSON value is not allowed: {value}")


def _load_manifest(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise FreezeError(f"submit manifest is not a regular non-symlink file: {path}")
    try:
        payload = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_pairs,
            parse_constant=_reject_json_constant,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise FreezeError(f"cannot read submit manifest {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise FreezeError("submit manifest must contain one JSON object")
    return payload


def _validated_absolute_path(path: Path, *, field: str) -> Path:
    if not path.is_absolute():
        raise FreezeError(f"{field} must be an absolute path: {path}")
    if ".." in path.parts:
        raise FreezeError(f"{field} must not contain parent traversal: {path}")
    return path


def _map_pod_path(
    pod_path: str,
    *,
    pod_path_prefix: Path | None,
    host_path_prefix: Path | None,
    field: str,
) -> Path:
    if (pod_path_prefix is None) != (host_path_prefix is None):
        raise FreezeError(
            "pod_path_prefix and host_path_prefix must be supplied together"
        )
    source = _validated_absolute_path(Path(pod_path), field=field)
    if pod_path_prefix is None:
        return source

    pod_prefix = _validated_absolute_path(
        pod_path_prefix,
        field="pod_path_prefix",
    )
    host_prefix = _validated_absolute_path(
        host_path_prefix,
        field="host_path_prefix",
    )
    try:
        relative = source.relative_to(pod_prefix)
    except ValueError as exc:
        raise FreezeError(f"{field} is outside pod_path_prefix: {source}") from exc
    try:
        resolved_host_prefix = host_prefix.resolve(strict=True)
    except OSError as exc:
        raise FreezeError(
            f"host_path_prefix cannot be resolved: {host_prefix}"
        ) from exc
    if not resolved_host_prefix.is_dir():
        raise FreezeError(f"host_path_prefix is not a directory: {host_prefix}")

    mapped = resolved_host_prefix / relative
    try:
        resolved_parent = mapped.parent.resolve(strict=True)
        resolved_parent.relative_to(resolved_host_prefix)
    except (OSError, ValueError) as exc:
        raise FreezeError(
            f"mapped host parent escapes or is missing for {field}"
        ) from exc
    return resolved_parent / mapped.name


def _read_hashed_regular_file(
    path: Path,
    *,
    label: str,
    max_bytes: int,
) -> tuple[bytes, str]:
    if path.is_symlink():
        raise FreezeError(f"required {label} must not be a symlink: {path}")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        file_descriptor = os.open(path, flags)
    except OSError as exc:
        raise FreezeError(f"cannot open required {label}: {path}") from exc

    try:
        before = os.fstat(file_descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise FreezeError(f"required {label} is not a regular file: {path}")
        if before.st_size <= 0:
            raise FreezeError(f"required {label} is empty: {path}")
        if before.st_size > max_bytes:
            raise FreezeError(f"required {label} exceeds the safe size limit: {path}")

        content = bytearray()
        digest = hashlib.sha256()
        while True:
            chunk = os.read(file_descriptor, 1024 * 1024)
            if not chunk:
                break
            content.extend(chunk)
            digest.update(chunk)
            if len(content) > max_bytes:
                raise FreezeError(
                    f"required {label} changed beyond the safe size limit: {path}"
                )
        after = os.fstat(file_descriptor)
    except OSError as exc:
        raise FreezeError(f"cannot read required {label}: {path}") from exc
    finally:
        os.close(file_descriptor)

    stable_fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns")
    if any(getattr(before, key) != getattr(after, key) for key in stable_fields):
        raise FreezeError(f"required {label} changed while hashing: {path}")
    try:
        current = os.stat(path, follow_symlinks=False)
    except OSError as exc:
        raise FreezeError(
            f"required {label} disappeared after hashing: {path}"
        ) from exc
    if any(getattr(after, key) != getattr(current, key) for key in stable_fields):
        raise FreezeError(f"required {label} path changed while hashing: {path}")
    return bytes(content), digest.hexdigest()


def _validate_json_asset(content: bytes, *, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(
            content.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_pairs,
            parse_constant=_reject_json_constant,
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise FreezeError(f"required {label} is not valid UTF-8 JSON") from exc
    if not isinstance(payload, dict):
        raise FreezeError(f"required {label} must contain one JSON object")
    return payload


def _deployment_asset_specs(
    manifest: dict[str, Any],
    *,
    pod_path_prefix: Path | None,
    host_path_prefix: Path | None,
) -> dict[str, tuple[str, Path]]:
    model_dir = _required_string(manifest, "model_dir", source="submit manifest")
    pod_paths = {
        "model_config": str(Path(model_dir) / "config.json"),
        "model_safetensors_index": str(
            Path(model_dir) / "model.safetensors.index.json"
        ),
        "chat_template": _required_string(
            manifest,
            "chat_template",
            source="submit manifest",
        ),
        "inner_script": _required_string(
            manifest,
            "inner_script",
            source="submit manifest",
        ),
    }
    if len(set(pod_paths.values())) != len(pod_paths):
        raise FreezeError("deployment artifact paths must be distinct")
    return {
        label: (
            pod_path,
            _map_pod_path(
                pod_path,
                pod_path_prefix=pod_path_prefix,
                host_path_prefix=host_path_prefix,
                field=label,
            ),
        )
        for label, pod_path in pod_paths.items()
    }


def _freeze_deployment_artifacts(
    manifest: dict[str, Any],
    *,
    pod_path_prefix: Path | None,
    host_path_prefix: Path | None,
) -> tuple[dict[str, Any], set[Path]]:
    specs = _deployment_asset_specs(
        manifest,
        pod_path_prefix=pod_path_prefix,
        host_path_prefix=host_path_prefix,
    )
    frozen: dict[str, Any] = {}
    host_paths: set[Path] = set()
    for label, (pod_path, host_path) in specs.items():
        content, digest = _read_hashed_regular_file(
            host_path,
            label=label,
            max_bytes=ASSET_SIZE_LIMITS[label],
        )
        if label in {"model_config", "model_safetensors_index"}:
            json_payload = _validate_json_asset(content, label=label)
            if label == "model_safetensors_index":
                weight_map = json_payload.get("weight_map")
                if (
                    not isinstance(weight_map, dict)
                    or not weight_map
                    or not all(
                        isinstance(key, str)
                        and key
                        and isinstance(value, str)
                        and value
                        for key, value in weight_map.items()
                    )
                ):
                    raise FreezeError(
                        "model_safetensors_index requires a non-empty weight_map"
                    )
        frozen[label] = {
            "pod_path": pod_path,
            "sha256": digest,
            "size_bytes": len(content),
        }
        host_paths.add(host_path)
    return frozen, host_paths


def _parse_env_value(raw: str, *, path: Path, line_number: int) -> str:
    if not raw:
        return ""
    try:
        parts = shlex.split(raw, comments=False, posix=True)
    except ValueError as exc:
        raise FreezeError(
            f"invalid env value in {path} at line {line_number}: {exc}"
        ) from exc
    if len(parts) != 1:
        raise FreezeError(
            f"env value in {path} at line {line_number} must be one shell word"
        )
    return parts[0]


def _load_env(path: Path) -> dict[str, str]:
    if path.is_symlink() or not path.is_file():
        raise FreezeError(f"endpoint env is not a regular non-symlink file: {path}")
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise FreezeError(f"cannot read endpoint env {path}: {exc}") from exc

    result: dict[str, str] = {}
    for line_number, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("export "):
            stripped = stripped[7:].lstrip()
        key, separator, raw_value = stripped.partition("=")
        key = key.strip()
        if not separator or not ENV_KEY_RE.fullmatch(key):
            raise FreezeError(f"invalid env assignment in {path} at line {line_number}")
        if key in result:
            raise FreezeError(f"duplicate env key in {path}: {key}")
        result[key] = _parse_env_value(
            raw_value.strip(),
            path=path,
            line_number=line_number,
        )
    return result


def _required_string(mapping: dict[str, Any], key: str, *, source: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise FreezeError(f"{source} requires a non-empty string field: {key}")
    if any(ord(character) < 32 for character in value):
        raise FreezeError(f"{source} field contains control characters: {key}")
    return value.strip()


def _deployment_provider(
    manifest: dict[str, Any],
    requested: str | None,
) -> str:
    manifest_value = manifest.get("provider")
    if manifest_value is not None and (
        not isinstance(manifest_value, str) or not manifest_value.strip()
    ):
        raise FreezeError("submit manifest provider must be a non-empty string")
    manifest_provider = (
        manifest_value.strip().lower() if isinstance(manifest_value, str) else None
    )
    requested_provider = requested.strip().lower() if requested is not None else None
    for source, value in (
        ("submit manifest", manifest_provider),
        ("--provider", requested_provider),
    ):
        if value is not None and not PROVIDER_RE.fullmatch(value):
            raise FreezeError(f"{source} provider is not a valid identifier")
    if (
        manifest_provider is not None
        and requested_provider is not None
        and manifest_provider != requested_provider
    ):
        raise FreezeError("submit manifest provider disagrees with --provider")
    return requested_provider or manifest_provider or "generic"


def _parse_int(value: Any, *, field: str, source: str) -> int:
    if isinstance(value, bool):
        raise FreezeError(f"{source} field must be an integer: {field}")
    try:
        parsed = int(str(value), 10)
    except (TypeError, ValueError) as exc:
        raise FreezeError(f"{source} field must be an integer: {field}") from exc
    if str(value).strip() not in {str(parsed), f"+{parsed}"}:
        raise FreezeError(f"{source} field is not a canonical integer: {field}")
    if parsed <= 0:
        raise FreezeError(f"{source} field must be positive: {field}")
    return parsed


def _parse_bool(value: Any, *, field: str, source: str) -> bool:
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"1", "true"}:
        return True
    if normalized in {"0", "false"}:
        return False
    raise FreezeError(f"{source} field must be one of 0, 1, false, true: {field}")


def _parse_utilization(value: Any, *, source: str) -> str:
    try:
        parsed = Decimal(str(value).strip())
    except (InvalidOperation, ValueError) as exc:
        raise FreezeError(
            f"{source} field must be decimal: gpu_memory_utilization"
        ) from exc
    if not parsed.is_finite() or parsed <= 0 or parsed > 1:
        raise FreezeError(
            f"{source} gpu_memory_utilization must be in the interval (0, 1]"
        )
    normalized = format(parsed.normalize(), "f")
    if "." not in normalized:
        normalized += ".0"
    return normalized


def _canonical_endpoint(value: str, *, source: str) -> str:
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as exc:
        raise FreezeError(f"{source} has an invalid endpoint URL") from exc
    if parsed.scheme.lower() not in {"http", "https"}:
        raise FreezeError(f"{source} endpoint must use http or https")
    if not parsed.hostname:
        raise FreezeError(f"{source} endpoint requires a hostname")
    if parsed.username is not None or parsed.password is not None:
        raise FreezeError(f"{source} endpoint must not contain credentials")
    if parsed.query or parsed.fragment:
        raise FreezeError(f"{source} endpoint must not contain query or fragment")

    hostname = parsed.hostname.lower()
    rendered_host = f"[{hostname}]" if ":" in hostname else hostname
    if port is not None:
        rendered_host = f"{rendered_host}:{port}"
    path = parsed.path.rstrip("/") or "/"
    return urlunsplit((parsed.scheme.lower(), rendered_host, path, "", ""))


def _normalize_endpoint_semantics(
    values: dict[str, str],
    *,
    source: str,
) -> dict[str, Any]:
    missing = sorted(set(SEMANTIC_ENDPOINT_FIELDS) - set(values))
    if missing:
        raise FreezeError(f"{source} is missing semantic fields: {missing}")

    normalized: dict[str, Any] = {}
    for field in sorted(STRING_FIELDS):
        normalized[field] = _required_string(values, field, source=source)
    for field in sorted(OPTIONAL_STRING_FIELDS):
        value = values[field]
        if any(ord(character) < 32 for character in value):
            raise FreezeError(f"{source} field contains control characters: {field}")
        normalized[field] = value.strip()
    for field in sorted(INT_FIELDS):
        normalized[field] = _parse_int(
            values[field],
            field=field,
            source=source,
        )
    for field in sorted(BOOL_FIELDS):
        normalized[field] = _parse_bool(
            values[field],
            field=field,
            source=source,
        )
    normalized["gpu_memory_utilization"] = _parse_utilization(
        values["gpu_memory_utilization"],
        source=source,
    )
    return normalized


def _manifest_command_env(manifest: dict[str, Any]) -> dict[str, Any]:
    command_env = manifest.get("command_env")
    if not isinstance(command_env, dict):
        raise FreezeError("submit manifest requires an object field: command_env")
    return command_env


def _manifest_pair(
    manifest: dict[str, Any],
    command_env: dict[str, Any],
    *,
    top_key: str,
    env_key: str,
    kind: str,
) -> Any:
    if top_key not in manifest:
        raise FreezeError(f"submit manifest is missing field: {top_key}")
    if env_key not in command_env:
        raise FreezeError(f"submit manifest command_env is missing field: {env_key}")
    source = "submit manifest"
    if kind == "string":
        top_value = _required_string(manifest, top_key, source=source)
        env_value = _required_string(command_env, env_key, source="command_env")
    elif kind == "int":
        top_value = _parse_int(manifest[top_key], field=top_key, source=source)
        env_value = _parse_int(
            command_env[env_key], field=env_key, source="command_env"
        )
    elif kind == "bool":
        top_value = _parse_bool(manifest[top_key], field=top_key, source=source)
        env_value = _parse_bool(
            command_env[env_key], field=env_key, source="command_env"
        )
    else:
        raise AssertionError(f"unsupported manifest pair kind: {kind}")
    if top_value != env_value:
        raise FreezeError(
            f"submit manifest fields disagree: {top_key} vs command_env.{env_key}"
        )
    return top_value


def _manifest_only(
    command_env: dict[str, Any],
    env_key: str,
    *,
    field: str,
    kind: str,
) -> Any:
    if env_key not in command_env:
        raise FreezeError(f"submit manifest command_env is missing field: {env_key}")
    if kind == "string":
        return _required_string(command_env, env_key, source="command_env")
    if kind == "int":
        return _parse_int(command_env[env_key], field=field, source="command_env")
    if kind == "bool":
        return _parse_bool(command_env[env_key], field=field, source="command_env")
    if kind == "utilization":
        return _parse_utilization(command_env[env_key], source="command_env")
    raise AssertionError(f"unsupported manifest value kind: {kind}")


def _normalize_manifest(
    manifest: dict[str, Any],
    *,
    expected_replicas: int,
    deployment_provider: str | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    command_env = _manifest_command_env(manifest)

    num_nodes = _manifest_pair(
        manifest,
        command_env,
        top_key="num_nodes",
        env_key="NUM_NODES",
        kind="int",
    )
    if num_nodes != expected_replicas:
        raise FreezeError(
            "expected replica count disagrees with submit manifest num_nodes: "
            f"expected={expected_replicas}, manifest={num_nodes}"
        )

    semantic = {
        "served_model_name": _manifest_pair(
            manifest,
            command_env,
            top_key="served_model_name",
            env_key="SERVED_MODEL_NAME",
            kind="string",
        ),
        "model_dir": _manifest_pair(
            manifest,
            command_env,
            top_key="model_dir",
            env_key="MODEL_DIR",
            kind="string",
        ),
        "max_model_len": _manifest_pair(
            manifest,
            command_env,
            top_key="max_model_len",
            env_key="MAX_MODEL_LEN",
            kind="int",
        ),
        "tp_size": _manifest_pair(
            manifest,
            command_env,
            top_key="tp_size",
            env_key="TP_SIZE",
            kind="int",
        ),
        "dp_size": _manifest_only(
            command_env,
            "DP_SIZE",
            field="dp_size",
            kind="int",
        ),
        "gpu_memory_utilization": _manifest_only(
            command_env,
            "GPU_MEM_UTIL",
            field="gpu_memory_utilization",
            kind="utilization",
        ),
        "max_num_seqs": _manifest_only(
            command_env,
            "MAX_NUM_SEQS",
            field="max_num_seqs",
            kind="int",
        ),
        "max_num_batched_tokens": _manifest_only(
            command_env,
            "MAX_NUM_BATCHED_TOKENS",
            field="max_num_batched_tokens",
            kind="int",
        ),
        "runtime_source": _manifest_pair(
            manifest,
            command_env,
            top_key="runtime_base",
            env_key="VLLM_RUNTIME_BASE",
            kind="string",
        ),
        "vllm_env_subdir": _manifest_pair(
            manifest,
            command_env,
            top_key="vllm_env_subdir",
            env_key="VLLM_ENV_SUBDIR",
            kind="string",
        ),
        "vllm_env_dereference": _manifest_pair(
            manifest,
            command_env,
            top_key="vllm_env_dereference",
            env_key="VLLM_ENV_DEREFERENCE",
            kind="bool",
        ),
        "copy_runtime_to_shm": _manifest_only(
            command_env,
            "COPY_RUNTIME_TO_SHM",
            field="copy_runtime_to_shm",
            kind="bool",
        ),
        "enable_thinking": _manifest_only(
            command_env,
            "ENABLE_THINKING",
            field="enable_thinking",
            kind="bool",
        ),
        "enable_prefix_caching": _manifest_only(
            command_env,
            "ENABLE_PREFIX_CACHING",
            field="enable_prefix_caching",
            kind="bool",
        ),
        "enforce_eager": _manifest_only(
            command_env,
            "ENFORCE_EAGER",
            field="enforce_eager",
            kind="bool",
        ),
        "vllm_overlay_subdir": _manifest_pair(
            manifest,
            command_env,
            top_key="vllm_overlay_subdir",
            env_key="VLLM_OVERLAY_SUBDIR",
            kind="string",
        ),
        "chat_template": _manifest_pair(
            manifest,
            command_env,
            top_key="chat_template",
            env_key="CHAT_TEMPLATE",
            kind="string",
        ),
    }

    # This pinned launcher materializes the archived runtime into node-local
    # /dev/shm before delegating to the common server launcher. Its effective
    # runtime path and copy flag therefore differ from the Ceph preflight
    # values recorded by the generic submitter. Model only this exact,
    # source-hashed launcher; every other semantic mismatch remains
    # fail-closed when endpoint observations are compared below.
    inner_script = _required_string(
        manifest,
        "inner_script",
        source="submit manifest",
    )
    if Path(inner_script).name in RUNTIME_MATERIALIZING_LAUNCHERS:
        materialized_root = str(
            command_env.get("SHM_ENV_ROOT") or "/dev/shm/gemma4_vllm024_cu129"
        ).strip()
        if not materialized_root or not Path(materialized_root).is_absolute():
            raise FreezeError(
                "materializing launcher requires an absolute SHM_ENV_ROOT"
            )
        semantic["runtime_source"] = materialized_root
        semantic["vllm_env_subdir"] = "vllm024"
        semantic["vllm_overlay_subdir"] = "none"
        semantic["copy_runtime_to_shm"] = False

    gpu_per_replica = _parse_int(
        manifest.get("gpu_per_node"),
        field="gpu_per_node",
        source="submit manifest",
    )
    topology_gpu_count = semantic["tp_size"] * semantic["dp_size"]
    if gpu_per_replica != topology_gpu_count:
        raise FreezeError(
            "gpu_per_node must equal tp_size * dp_size: "
            f"gpu_per_node={gpu_per_replica}, topology={topology_gpu_count}"
        )
    semantic["gpu_per_replica"] = gpu_per_replica
    semantic["replica_count"] = expected_replicas
    semantic["total_gpu_count"] = expected_replicas * gpu_per_replica

    job_id = _required_string(manifest, "job_id", source="submit manifest")
    if job_id.lower() == "dry-run":
        raise FreezeError("submit manifest job_id=dry-run is not a deployment")

    deployment_source = {
        "provider": _deployment_provider(manifest, deployment_provider),
        "job_id": job_id,
        "job_name": _required_string(manifest, "job_name", source="submit manifest"),
        "run_name": _required_string(manifest, "run_name", source="submit manifest"),
        "serve_root": _required_string(
            manifest,
            "serve_root",
            source="submit manifest",
        ),
        "submitted_at": _required_string(
            manifest,
            "submitted_at",
            source="submit manifest",
        ),
        "image": _required_string(manifest, "image", source="submit manifest"),
        "inner_script": _required_string(
            manifest,
            "inner_script",
            source="submit manifest",
        ),
    }
    return semantic, deployment_source


def _check_endpoint_identity(
    values: dict[str, str],
    *,
    source: str,
) -> tuple[str, str]:
    hostname = _required_string(values, "hostname", source=source)
    if any(character.isspace() for character in hostname):
        raise FreezeError(f"{source} hostname must not contain whitespace")

    endpoint = _canonical_endpoint(
        _required_string(values, "endpoint", source=source),
        source=source,
    )
    openai_base_url = _canonical_endpoint(
        _required_string(values, "OPENAI_BASE_URL", source=source),
        source=source,
    )
    if endpoint != openai_base_url:
        raise FreezeError(f"{source} endpoint disagrees with OPENAI_BASE_URL")

    parsed = urlsplit(endpoint)
    ip = _required_string(values, "ip", source=source)
    if parsed.hostname != ip.lower():
        raise FreezeError(f"{source} endpoint hostname disagrees with ip")
    endpoint_port = parsed.port
    port = _parse_int(values.get("port"), field="port", source=source)
    if endpoint_port != port:
        raise FreezeError(f"{source} endpoint port disagrees with port")

    model_name = _required_string(values, "MODEL_NAME", source=source)
    served_model_name = _required_string(
        values,
        "served_model_name",
        source=source,
    )
    if model_name != served_model_name:
        raise FreezeError(f"{source} MODEL_NAME disagrees with served_model_name")
    return hostname, endpoint


def _validate_overlay(
    semantic: dict[str, Any],
    *,
    source: str,
) -> None:
    overlay_subdir = str(semantic["vllm_overlay_subdir"])
    overlay_site = str(semantic["overlay_site"])
    if overlay_subdir in {"none", "__none__"}:
        if overlay_site:
            raise FreezeError(
                f"{source} overlay_site must be empty when overlay is disabled"
            )
        return
    if not overlay_site or Path(overlay_site).name != overlay_subdir:
        raise FreezeError(f"{source} overlay_site does not match vllm_overlay_subdir")


def _parse_smoke_versions(path: Path) -> dict[str, str]:
    content, _ = _read_hashed_regular_file(
        path,
        label=f"server smoke log {path.name}",
        max_bytes=MAX_SERVER_LOG_BYTES,
    )
    try:
        text = content.decode("utf-8")
    except UnicodeError as exc:
        raise FreezeError(f"server smoke log is not UTF-8: {path.name}") from exc

    versions: dict[str, str] = {}
    for package, pattern in SMOKE_VERSION_PATTERNS.items():
        observed = pattern.findall(text)
        if not observed:
            raise FreezeError(
                f"server smoke log is missing observed {package} version: {path.name}"
            )
        unique = set(observed)
        if len(unique) != 1:
            raise FreezeError(
                f"server smoke log has conflicting {package} versions: {path.name}"
            )
        version = unique.pop()
        if not VERSION_RE.fullmatch(version):
            raise FreezeError(
                f"server smoke log has an invalid {package} version: {path.name}"
            )
        versions[package] = version
    return versions


def _freeze_runtime_observation(
    *,
    logs_dir: Path,
    replica_logs: list[dict[str, str]],
    expected_replicas: int,
    expected_vllm_version: str,
) -> tuple[dict[str, Any], set[Path]]:
    if not VERSION_RE.fullmatch(expected_vllm_version):
        raise FreezeError("expected_vllm_version is not a valid version token")
    if logs_dir.is_symlink() or not logs_dir.is_dir():
        raise FreezeError(f"logs directory is not a non-symlink directory: {logs_dir}")

    log_paths = sorted(logs_dir.glob("server.*.log"))
    singleton_log = logs_dir / "server.log"
    if singleton_log.exists() or singleton_log.is_symlink():
        log_paths.append(singleton_log)
        log_paths.sort()
    if len(log_paths) != expected_replicas:
        raise FreezeError(
            "server smoke log count mismatch: "
            f"expected={expected_replicas}, actual={len(log_paths)}"
        )
    actual_by_name = {path.name: path for path in log_paths}
    if len(actual_by_name) != len(log_paths):
        raise FreezeError("server smoke log basenames must be unique")
    declared_names = [row["log_file"] for row in replica_logs]
    if len(set(declared_names)) != len(declared_names):
        raise FreezeError("endpoint envs declare duplicate server_log files")
    if set(declared_names) != set(actual_by_name):
        raise FreezeError(
            "endpoint env server_log declarations do not match logs directory"
        )

    baseline: dict[str, str] | None = None
    observed_replicas: list[dict[str, Any]] = []
    for replica in sorted(replica_logs, key=lambda row: row["hostname"]):
        log_name = replica["log_file"]
        versions = _parse_smoke_versions(actual_by_name[log_name])
        if baseline is None:
            baseline = versions
        elif versions != baseline:
            mismatches = sorted(
                package
                for package in set(baseline) | set(versions)
                if baseline.get(package) != versions.get(package)
            )
            raise FreezeError(
                f"observed runtime versions differ across replicas: {mismatches}"
            )
        observed_replicas.append(
            {
                "hostname": replica["hostname"],
                "log_file": log_name,
                "versions": versions,
            }
        )

    if baseline is None:
        raise FreezeError("no server smoke logs were observed")
    if baseline["vllm"] != expected_vllm_version:
        raise FreezeError(
            "observed vllm version disagrees with expected version: "
            f"expected={expected_vllm_version}, observed={baseline['vllm']}"
        )
    return (
        {
            "expected_vllm_version": expected_vllm_version,
            "observed_versions": baseline,
            "replicas": observed_replicas,
        },
        set(log_paths),
    )


def _canonical_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def build_frozen_manifest(
    *,
    submit_manifest: Path,
    endpoints_dir: Path,
    expected_replicas: int,
    logs_dir: Path | None = None,
    pod_path_prefix: Path | None = None,
    host_path_prefix: Path | None = None,
    expected_vllm_version: str = "0.24.0",
    deployment_provider: str | None = None,
) -> dict[str, Any]:
    """Validate and return a credential-free canonical service manifest."""
    if isinstance(expected_replicas, bool) or expected_replicas <= 0:
        raise FreezeError("expected_replicas must be a positive integer")

    manifest = _load_manifest(submit_manifest)
    manifest_semantic, deployment_source = _normalize_manifest(
        manifest,
        expected_replicas=expected_replicas,
        deployment_provider=deployment_provider,
    )
    deployment_artifacts, _ = _freeze_deployment_artifacts(
        manifest,
        pod_path_prefix=pod_path_prefix,
        host_path_prefix=host_path_prefix,
    )
    effective_logs_dir = (
        logs_dir if logs_dir is not None else submit_manifest.parent / "logs"
    )

    if endpoints_dir.is_symlink() or not endpoints_dir.is_dir():
        raise FreezeError(
            f"endpoints directory is not a non-symlink directory: {endpoints_dir}"
        )
    endpoint_paths = sorted(endpoints_dir.glob("*.env"))
    if len(endpoint_paths) != expected_replicas:
        raise FreezeError(
            "endpoint replica count mismatch: "
            f"expected={expected_replicas}, actual={len(endpoint_paths)}"
        )

    baseline: dict[str, Any] | None = None
    replicas: list[dict[str, str]] = []
    replica_logs: list[dict[str, str]] = []
    seen_hostnames: set[str] = set()
    seen_endpoints: set[str] = set()
    for path in endpoint_paths:
        source = f"endpoint env {path.name}"
        values = _load_env(path)
        hostname, endpoint = _check_endpoint_identity(values, source=source)
        semantic = _normalize_endpoint_semantics(values, source=source)
        semantic["vllm_overlay_subdir"] = manifest_semantic["vllm_overlay_subdir"]
        semantic["chat_template"] = manifest_semantic["chat_template"]
        _validate_overlay(semantic, source=source)

        endpoint_num_nodes = _parse_int(
            values.get("num_nodes"),
            field="num_nodes",
            source=source,
        )
        if endpoint_num_nodes != expected_replicas:
            raise FreezeError(
                f"{source} num_nodes disagrees with expected replica count"
            )
        if hostname in seen_hostnames:
            raise FreezeError(f"duplicate replica hostname: {hostname}")
        if endpoint in seen_endpoints:
            raise FreezeError(f"duplicate replica endpoint: {endpoint}")
        seen_hostnames.add(hostname)
        seen_endpoints.add(endpoint)

        server_log = Path(_required_string(values, "server_log", source=source))
        if not server_log.is_absolute():
            raise FreezeError(f"{source} server_log must be an absolute path")
        expected_log_parent = Path(deployment_source["serve_root"]) / "logs"
        if server_log.parent != expected_log_parent:
            raise FreezeError(
                f"{source} server_log is outside submit manifest serve_root/logs"
            )
        log_name = server_log.name
        if not log_name.startswith("server.") or not log_name.endswith(".log"):
            raise FreezeError(f"{source} server_log has an invalid basename")
        replica_logs.append({"hostname": hostname, "log_file": log_name})

        if baseline is None:
            baseline = semantic
        elif semantic != baseline:
            mismatched_fields = sorted(
                field
                for field in set(baseline) | set(semantic)
                if baseline.get(field) != semantic.get(field)
            )
            raise FreezeError(
                f"{source} semantic configuration differs across replicas: "
                f"{mismatched_fields}"
            )
        replicas.append({"endpoint": endpoint, "hostname": hostname})

    if baseline is None:
        raise FreezeError("no endpoint replicas were found")
    for field, expected in manifest_semantic.items():
        if field in {"gpu_per_replica", "replica_count", "total_gpu_count"}:
            continue
        if baseline.get(field) != expected:
            raise FreezeError(
                f"endpoint semantic field disagrees with submit manifest: {field}"
            )
    baseline.update(
        {
            "gpu_per_replica": manifest_semantic["gpu_per_replica"],
            "replica_count": manifest_semantic["replica_count"],
            "total_gpu_count": manifest_semantic["total_gpu_count"],
        }
    )
    runtime_observation, _ = _freeze_runtime_observation(
        logs_dir=effective_logs_dir,
        replica_logs=replica_logs,
        expected_replicas=expected_replicas,
        expected_vllm_version=expected_vllm_version,
    )

    replicas.sort(key=lambda row: (row["hostname"], row["endpoint"]))
    identity_payload = {
        "schema_version": SCHEMA_VERSION,
        "deployment_source": deployment_source,
        "deployment_artifacts": deployment_artifacts,
        "runtime_observation": runtime_observation,
        "semantic_config": baseline,
        "replicas": replicas,
    }
    digest = hashlib.sha256(_canonical_bytes(identity_payload)).hexdigest()
    return {
        **identity_payload,
        "model_service_id": f"sha256:{digest}",
    }


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    """Atomically replace *path* with canonical JSON after a complete fsync."""
    encoded = _canonical_bytes(payload) + b"\n"
    parent = path.parent
    parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.is_dir():
        raise FreezeError(f"output path is a directory: {path}")

    file_descriptor, temporary_name = tempfile.mkstemp(
        dir=parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(file_descriptor, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary_path, 0o644)
        os.replace(temporary_path, path)
        directory_descriptor = os.open(parent, os.O_RDONLY)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate vLLM replicas and atomically freeze a credential-free "
            "model_service_id manifest."
        )
    )
    parser.add_argument(
        "--submit-manifest",
        type=Path,
        required=True,
        help="Path to the deployment submit_manifest.json.",
    )
    parser.add_argument(
        "--provider",
        help=(
            "Stable deployment-provider identifier. It must match a provider "
            "field in the submit manifest when both are present; default: generic."
        ),
    )
    parser.add_argument(
        "--endpoints-dir",
        type=Path,
        help="Directory containing one *.env file per replica.",
    )
    parser.add_argument(
        "--logs-dir",
        type=Path,
        help="Directory containing one server.*.log smoke log per replica.",
    )
    parser.add_argument(
        "--pod-path-prefix",
        type=Path,
        help=(
            "Pod-visible absolute prefix for model/script paths; must be paired "
            "with --host-path-prefix for formal runs."
        ),
    )
    parser.add_argument(
        "--host-path-prefix",
        type=Path,
        help="Host-visible absolute prefix corresponding to --pod-path-prefix.",
    )
    parser.add_argument(
        "--expected-replicas",
        type=int,
        required=True,
        help="Exact number of independent vLLM replicas.",
    )
    parser.add_argument(
        "--expected-vllm-version",
        default="0.24.0",
        help="Exact vLLM version required in every server smoke log.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Canonical JSON file to atomically create or replace.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    submit_manifest = args.submit_manifest.expanduser().resolve()
    endpoints_dir = (
        args.endpoints_dir.expanduser().resolve()
        if args.endpoints_dir
        else submit_manifest.parent / "endpoints"
    )
    logs_dir = (
        args.logs_dir.expanduser().resolve()
        if args.logs_dir
        else submit_manifest.parent / "logs"
    )
    pod_path_prefix = (
        args.pod_path_prefix.expanduser() if args.pod_path_prefix else None
    )
    host_path_prefix = (
        args.host_path_prefix.expanduser().resolve() if args.host_path_prefix else None
    )
    output = args.output.expanduser().resolve()
    manifest = _load_manifest(submit_manifest)
    asset_specs = _deployment_asset_specs(
        manifest,
        pod_path_prefix=pod_path_prefix,
        host_path_prefix=host_path_prefix,
    )
    protected_inputs = {
        submit_manifest,
        *endpoints_dir.glob("*.env"),
        *logs_dir.glob("server.*.log"),
        *(path for path in (logs_dir / "server.log",) if path.exists()),
        *(host_path for _, host_path in asset_specs.values()),
    }
    if output in protected_inputs:
        raise FreezeError("output path must not overwrite an input file")

    payload = build_frozen_manifest(
        submit_manifest=submit_manifest,
        endpoints_dir=endpoints_dir,
        expected_replicas=args.expected_replicas,
        logs_dir=logs_dir,
        pod_path_prefix=pod_path_prefix,
        host_path_prefix=host_path_prefix,
        expected_vllm_version=args.expected_vllm_version,
        deployment_provider=args.provider,
    )
    atomic_write_json(output, payload)
    print(payload["model_service_id"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
