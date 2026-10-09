#!/usr/bin/env python3
"""Fail-closed preflight and monitoring for a frozen vLLM service."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import signal
import tempfile
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import (
    HTTPRedirectHandler,
    Request,
    build_opener,
)

from freeze_model_service import (
    FROZEN_MANIFEST_FIELDS,
    SCHEMA_VERSION as FROZEN_MANIFEST_SCHEMA_VERSION,
)

SCHEMA_VERSION = 1
DEFAULT_EXPECTED_VERSION = "0.24.0"
DEFAULT_TIMEOUT_SECONDS = 15.0
DEFAULT_PER_RANK_CONCURRENCY = 4
DEFAULT_MONITOR_INTERVAL_SECONDS = 15.0
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
PROTOCOL_PROBE_MAX_TOKENS = 2048
TOOL_NAME = "harnessbench_service_probe"
CALL_ID_RE = re.compile(r"[A-Za-z0-9_.:-]{1,256}\Z")
SHA256_ID_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")
RAW_GEMMA_MARKERS = (
    "<start_of_turn>",
    "<end_of_turn>",
    "<|start_of_turn|>",
    "<|end_of_turn|>",
    "<|tool_call>",
    "<tool_call|>",
    "<tool_call>",
    "</tool_call>",
    "<start_function_call>",
    "<end_function_call>",
    "<function_call>",
    "</function_call>",
    "<function=",
)


class ProbeError(RuntimeError):
    """A service or protocol check failed closed."""


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(  # type: ignore[override]
        self,
        req: Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> None:
        del req, fp, code, msg, headers, newurl
        return None


_OPENER = build_opener(_NoRedirect)


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ProbeError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise ProbeError(f"non-finite JSON value is not allowed: {value}")


def _decode_json(raw: bytes, *, source: str) -> Any:
    try:
        return json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_pairs,
            parse_constant=_reject_json_constant,
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ProbeError(f"{source} returned invalid JSON") from exc


def _canonical_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _required_string(mapping: dict[str, Any], key: str, *, source: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ProbeError(f"{source} requires a non-empty string field: {key}")
    if any(ord(character) < 32 for character in value):
        raise ProbeError(f"{source} field contains control characters: {key}")
    return value.strip()


def _positive_int(value: Any, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ProbeError(f"frozen manifest requires a positive integer: {field}")
    return value


def _api_coordinates(endpoint: str) -> tuple[str, str]:
    try:
        parsed = urlsplit(endpoint)
        port = parsed.port
    except ValueError as exc:
        raise ProbeError("frozen manifest contains an invalid endpoint URL") from exc
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ProbeError("frozen manifest endpoint must use http or https")
    if parsed.username is not None or parsed.password is not None:
        raise ProbeError("frozen manifest endpoint must not contain credentials")
    if parsed.query or parsed.fragment:
        raise ProbeError("frozen manifest endpoint must not contain query or fragment")
    path = parsed.path.rstrip("/")
    if path not in {"", "/v1"}:
        raise ProbeError("frozen manifest endpoint path must be / or /v1")
    host = parsed.hostname.lower()
    rendered_host = f"[{host}]" if ":" in host else host
    if port is not None:
        rendered_host = f"{rendered_host}:{port}"
    origin = urlunsplit((parsed.scheme, rendered_host, "", "", "")).rstrip("/")
    return origin, f"{origin}/v1"


def load_frozen_manifest(path: Path) -> dict[str, Any]:
    """Load and cryptographically validate freeze_model_service.py output."""
    if path.is_symlink() or not path.is_file():
        raise ProbeError(f"manifest is not a regular non-symlink file: {path}")
    try:
        payload = _decode_json(path.read_bytes(), source="frozen manifest")
    except OSError as exc:
        raise ProbeError(f"cannot read frozen manifest: {path}") from exc
    if not isinstance(payload, dict):
        raise ProbeError("frozen manifest must contain one JSON object")
    if set(payload) != FROZEN_MANIFEST_FIELDS:
        raise ProbeError("frozen manifest has unexpected or missing top-level fields")
    if payload["schema_version"] != FROZEN_MANIFEST_SCHEMA_VERSION:
        raise ProbeError("unsupported frozen manifest schema_version")

    model_service_id = _required_string(
        payload,
        "model_service_id",
        source="frozen manifest",
    )
    if not SHA256_ID_RE.fullmatch(model_service_id):
        raise ProbeError("frozen manifest has an invalid model_service_id")
    identity = dict(payload)
    identity.pop("model_service_id")
    expected_id = f"sha256:{hashlib.sha256(_canonical_bytes(identity)).hexdigest()}"
    if model_service_id != expected_id:
        raise ProbeError("frozen manifest model_service_id digest mismatch")

    semantic = payload.get("semantic_config")
    replicas = payload.get("replicas")
    if not isinstance(semantic, dict) or not isinstance(replicas, list):
        raise ProbeError("frozen manifest semantic_config/replicas types are invalid")
    for field in (
        "deployment_source",
        "deployment_artifacts",
        "runtime_observation",
    ):
        if not isinstance(payload.get(field), dict):
            raise ProbeError(f"frozen manifest {field} must be an object")

    artifacts = payload["deployment_artifacts"]
    required_artifacts = {
        "model_config",
        "model_safetensors_index",
        "chat_template",
        "inner_script",
    }
    if set(artifacts) != required_artifacts:
        raise ProbeError("frozen manifest deployment_artifacts shape is invalid")
    for name, artifact in artifacts.items():
        if not isinstance(artifact, dict) or set(artifact) != {
            "pod_path",
            "sha256",
            "size_bytes",
        }:
            raise ProbeError(f"frozen deployment artifact has invalid shape: {name}")
        _required_string(artifact, "pod_path", source=f"artifact {name}")
        artifact_sha = _required_string(
            artifact,
            "sha256",
            source=f"artifact {name}",
        )
        if not re.fullmatch(r"[0-9a-f]{64}", artifact_sha):
            raise ProbeError(f"frozen deployment artifact has invalid sha256: {name}")
        _positive_int(
            artifact.get("size_bytes"),
            field=f"artifact {name}.size_bytes",
        )

    runtime_observation = payload["runtime_observation"]
    expected_vllm = _required_string(
        runtime_observation,
        "expected_vllm_version",
        source="runtime_observation",
    )
    observed_versions = runtime_observation.get("observed_versions")
    observed_replicas = runtime_observation.get("replicas")
    if not isinstance(observed_versions, dict) or not isinstance(
        observed_replicas,
        list,
    ):
        raise ProbeError("frozen runtime_observation shape is invalid")
    observed_vllm = _required_string(
        observed_versions,
        "vllm",
        source="runtime_observation.observed_versions",
    )
    if observed_vllm != expected_vllm:
        raise ProbeError("frozen runtime observation has inconsistent vLLM versions")

    _required_string(semantic, "served_model_name", source="semantic_config")
    _positive_int(semantic.get("dp_size"), field="semantic_config.dp_size")
    replica_count = _positive_int(
        semantic.get("replica_count"),
        field="semantic_config.replica_count",
    )
    if len(replicas) != replica_count:
        raise ProbeError("frozen manifest replica_count does not match replicas")

    seen_hostnames: set[str] = set()
    seen_endpoints: set[str] = set()
    for index, replica in enumerate(replicas):
        if not isinstance(replica, dict) or set(replica) != {"endpoint", "hostname"}:
            raise ProbeError(f"frozen manifest replica {index} has an invalid shape")
        hostname = _required_string(
            replica,
            "hostname",
            source=f"replica {index}",
        )
        endpoint = _required_string(
            replica,
            "endpoint",
            source=f"replica {index}",
        )
        _api_coordinates(endpoint)
        if hostname in seen_hostnames or endpoint in seen_endpoints:
            raise ProbeError("frozen manifest contains duplicate replicas")
        seen_hostnames.add(hostname)
        seen_endpoints.add(endpoint)
    observed_hostnames = {
        _required_string(
            row,
            "hostname",
            source=f"runtime observation replica {index}",
        )
        for index, row in enumerate(observed_replicas)
        if isinstance(row, dict)
    }
    if (
        len(observed_replicas) != replica_count
        or len(observed_hostnames) != replica_count
        or observed_hostnames != seen_hostnames
    ):
        raise ProbeError("frozen runtime observation does not match endpoint replicas")
    return payload


def _request(
    *,
    method: str,
    url: str,
    timeout: float,
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[bytes, float]:
    body = _canonical_bytes(payload) if payload is not None else None
    request_headers = {
        "Accept": "application/json",
        "User-Agent": "HarnessBench-vLLM-probe/1",
    }
    if payload is not None:
        request_headers["Content-Type"] = "application/json"
    if headers:
        request_headers.update(headers)
    request = Request(
        url,
        data=body,
        headers=request_headers,
        method=method,
    )
    started = time.monotonic()
    try:
        with _OPENER.open(request, timeout=timeout) as response:
            status = response.status
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except HTTPError as exc:
        raise ProbeError(f"{method} endpoint returned HTTP {exc.code}") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise ProbeError(f"{method} endpoint was unreachable") from exc
    latency_ms = round((time.monotonic() - started) * 1000, 3)
    if status != 200:
        raise ProbeError(f"{method} endpoint returned HTTP {status}")
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ProbeError(f"{method} endpoint response exceeded size limit")
    return raw, latency_ms


def _request_json(
    *,
    method: str,
    url: str,
    timeout: float,
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[Any, float]:
    raw, latency_ms = _request(
        method=method,
        url=url,
        timeout=timeout,
        payload=payload,
        headers=headers,
    )
    return _decode_json(raw, source=method), latency_ms


def preflight_endpoint(
    replica: dict[str, str],
    *,
    model: str,
    expected_version: str,
    timeout: float,
) -> dict[str, Any]:
    """Check health, exact vLLM version, and served-model visibility."""
    origin, api_base = _api_coordinates(replica["endpoint"])
    started = time.monotonic()
    _, health_latency = _request(
        method="GET",
        url=f"{origin}/health",
        timeout=timeout,
    )
    version_payload, version_latency = _request_json(
        method="GET",
        url=f"{origin}/version",
        timeout=timeout,
    )
    if not isinstance(version_payload, dict) or version_payload.get("version") != (
        expected_version
    ):
        raise ProbeError(f"vLLM version is not exactly {expected_version}")
    models_payload, models_latency = _request_json(
        method="GET",
        url=f"{api_base}/models",
        timeout=timeout,
    )
    model_rows = (
        models_payload.get("data") if isinstance(models_payload, dict) else None
    )
    if not isinstance(model_rows, list) or not any(
        isinstance(row, dict) and row.get("id") == model for row in model_rows
    ):
        raise ProbeError("served model is absent from /v1/models")
    return {
        "status": "pass",
        "latency_ms": round((time.monotonic() - started) * 1000, 3),
        "checks": {
            "health_latency_ms": health_latency,
            "version_latency_ms": version_latency,
            "models_latency_ms": models_latency,
        },
    }


def _preflight_result(
    replica: dict[str, str],
    *,
    model: str,
    expected_version: str,
    timeout: float,
) -> dict[str, Any]:
    started = time.monotonic()
    try:
        return preflight_endpoint(
            replica,
            model=model,
            expected_version=expected_version,
            timeout=timeout,
        )
    except BaseException as exc:
        return {
            "status": "fail",
            "latency_ms": round((time.monotonic() - started) * 1000, 3),
            "checks": {},
            "error": _error_result(exc),
        }


def _assert_no_raw_markers(payload: Any) -> None:
    rendered = json.dumps(payload, ensure_ascii=False).casefold()
    marker = next(
        (candidate for candidate in RAW_GEMMA_MARKERS if candidate in rendered),
        None,
    )
    if marker is not None:
        raise ProbeError(f"raw Gemma protocol marker leaked: {marker}")


def _assistant_message(payload: Any, *, phase: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ProbeError(f"{phase} response is not a JSON object")
    _assert_no_raw_markers(payload)
    choices = payload.get("choices")
    if not isinstance(choices, list) or len(choices) != 1:
        raise ProbeError(f"{phase} response must contain exactly one choice")
    choice = choices[0]
    message = choice.get("message") if isinstance(choice, dict) else None
    if not isinstance(message, dict) or message.get("role") != "assistant":
        raise ProbeError(f"{phase} response has no assistant message")
    return message


def _first_turn_message(
    payload: Any,
    *,
    nonce: str,
    rank: int,
    hostname: str,
) -> tuple[dict[str, Any], str]:
    message = _assistant_message(payload, phase="first tool-call")
    tool_calls = message.get("tool_calls")
    if not isinstance(tool_calls, list) or len(tool_calls) != 1:
        raise ProbeError("first response must contain exactly one tool call")
    tool_call = tool_calls[0]
    if not isinstance(tool_call, dict) or tool_call.get("type") != "function":
        raise ProbeError("first response tool call must have type=function")
    call_id = tool_call.get("id")
    if not isinstance(call_id, str) or not CALL_ID_RE.fullmatch(call_id):
        raise ProbeError("first response has an invalid tool-call id")
    function = tool_call.get("function")
    if not isinstance(function, dict) or function.get("name") != TOOL_NAME:
        raise ProbeError("first response has the wrong tool name")
    arguments_raw = function.get("arguments")
    if not isinstance(arguments_raw, str):
        raise ProbeError("tool arguments must be a JSON string")
    arguments = _decode_json(arguments_raw.encode(), source="tool arguments")
    expected_arguments = {
        "endpoint_hostname": hostname,
        "nonce": nonce,
        "rank": rank,
    }
    if arguments != expected_arguments:
        raise ProbeError(
            "tool arguments do not exactly match the probe request: "
            f"expected={_canonical_bytes(expected_arguments).decode('utf-8')}, "
            f"observed={_canonical_bytes(arguments).decode('utf-8')}"
        )
    return message, call_id


def _completion_message(payload: Any, *, nonce: str) -> None:
    message = _assistant_message(payload, phase="tool-result continuation")
    if message.get("tool_calls") not in (None, []):
        raise ProbeError("second response unexpectedly contains tool calls")
    content = message.get("content")
    if not isinstance(content, str) or content.strip() != f"PROBE_COMPLETE:{nonce}":
        raise ProbeError("second response did not acknowledge the tool result exactly")


def protocol_probe(
    replica: dict[str, str],
    *,
    model: str,
    rank: int,
    sample: int,
    timeout: float,
    enable_thinking: bool,
) -> dict[str, Any]:
    """Perform a two-turn structured tool-call check against one DP rank."""
    _, api_base = _api_coordinates(replica["endpoint"])
    nonce = uuid.uuid4().hex
    completion = f"PROBE_COMPLETE:{nonce}"
    system_text = (
        "You are a deterministic API protocol probe. Call the required function "
        "exactly once on the first turn. After its tool result, answer with exactly "
        f"{completion} and no other text."
    )
    desired_arguments = {
        "endpoint_hostname": replica["hostname"],
        "nonce": nonce,
        "rank": rank,
    }
    tools = [
        {
            "type": "function",
            "function": {
                "name": TOOL_NAME,
                "description": "Record a deterministic vLLM protocol probe.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "endpoint_hostname": {"type": "string"},
                        "nonce": {"type": "string"},
                        "rank": {"type": "integer"},
                    },
                    "required": ["endpoint_hostname", "nonce", "rank"],
                    "additionalProperties": False,
                },
            },
        }
    ]
    common = {
        "model": model,
        "stream": False,
        "temperature": 0,
        # Gemma's thinking tokens share the completion budget.  A 256-token
        # canary can stop while copying the nonce/hostname JSON even though
        # the tool protocol itself is healthy.
        "max_tokens": PROTOCOL_PROBE_MAX_TOKENS,
        "tools": tools,
        "chat_template_kwargs": {"enable_thinking": enable_thinking},
    }
    headers = {"X-data-parallel-rank": str(rank)}
    started = time.monotonic()
    first_payload, first_latency = _request_json(
        method="POST",
        url=f"{api_base}/chat/completions",
        timeout=timeout,
        headers=headers,
        payload={
            **common,
            "tool_choice": {
                "type": "function",
                "function": {"name": TOOL_NAME},
            },
            "messages": [
                {"role": "system", "content": system_text},
                {
                    "role": "user",
                    "content": (
                        "Invoke the required function with exactly this JSON object: "
                        + json.dumps(
                            desired_arguments,
                            ensure_ascii=False,
                            sort_keys=True,
                            separators=(",", ":"),
                        )
                    ),
                },
            ],
        },
    )
    assistant_message, call_id = _first_turn_message(
        first_payload,
        nonce=nonce,
        rank=rank,
        hostname=replica["hostname"],
    )
    second_payload, second_latency = _request_json(
        method="POST",
        url=f"{api_base}/chat/completions",
        timeout=timeout,
        headers=headers,
        payload={
            **common,
            "tool_choice": "none",
            "messages": [
                {"role": "system", "content": system_text},
                {
                    "role": "user",
                    "content": (
                        "Invoke the required function with exactly this JSON object: "
                        + json.dumps(
                            desired_arguments,
                            ensure_ascii=False,
                            sort_keys=True,
                            separators=(",", ":"),
                        )
                    ),
                },
                {
                    "role": "assistant",
                    "content": assistant_message.get("content"),
                    "tool_calls": assistant_message["tool_calls"],
                },
                {
                    "role": "tool",
                    "tool_call_id": call_id,
                    "name": TOOL_NAME,
                    "content": json.dumps(
                        {"accepted": True, "nonce": nonce},
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                },
            ],
        },
    )
    _completion_message(second_payload, nonce=nonce)
    return {
        "rank": rank,
        "sample": sample,
        "status": "pass",
        "latency_ms": round((time.monotonic() - started) * 1000, 3),
        "first_turn_latency_ms": first_latency,
        "second_turn_latency_ms": second_latency,
        "error": None,
    }


def _error_result(error: BaseException) -> str:
    if isinstance(error, ProbeError):
        return str(error)
    return f"unexpected {type(error).__name__}"


def run_one_shot(
    manifest: dict[str, Any],
    *,
    expected_version: str = DEFAULT_EXPECTED_VERSION,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    per_rank_concurrency: int = DEFAULT_PER_RANK_CONCURRENCY,
) -> dict[str, Any]:
    """Run all preflight and per-rank protocol probes, returning one report."""
    if timeout <= 0:
        raise ProbeError("timeout must be positive")
    if per_rank_concurrency <= 0:
        raise ProbeError("per-rank concurrency must be positive")
    started_epoch = time.time()
    semantic = manifest["semantic_config"]
    model = semantic["served_model_name"]
    dp_size = semantic["dp_size"]
    replicas = manifest["replicas"]
    endpoint_results: dict[str, dict[str, Any]] = {}

    with ThreadPoolExecutor(max_workers=len(replicas)) as executor:
        futures = {
            executor.submit(
                _preflight_result,
                replica,
                model=model,
                expected_version=expected_version,
                timeout=timeout,
            ): replica
            for replica in replicas
        }
        for future in as_completed(futures):
            replica = futures[future]
            preflight = future.result()
            endpoint_results[replica["hostname"]] = {
                **replica,
                "status": preflight["status"],
                "preflight": preflight,
                "rank_probes": [],
            }

    workflow_count = len(replicas) * dp_size * per_rank_concurrency
    with ThreadPoolExecutor(max_workers=max(1, workflow_count)) as executor:
        futures = {}
        for replica in replicas:
            endpoint_result = endpoint_results[replica["hostname"]]
            if endpoint_result["preflight"]["status"] != "pass":
                continue
            for rank in range(dp_size):
                for sample in range(per_rank_concurrency):
                    future = executor.submit(
                        protocol_probe,
                        replica,
                        model=model,
                        rank=rank,
                        sample=sample,
                        timeout=timeout,
                        enable_thinking=bool(semantic.get("enable_thinking")),
                    )
                    futures[future] = (replica["hostname"], rank, sample)
        for future in as_completed(futures):
            hostname, rank, sample = futures[future]
            try:
                result = future.result()
            except BaseException as exc:
                result = {
                    "rank": rank,
                    "sample": sample,
                    "status": "fail",
                    "latency_ms": None,
                    "first_turn_latency_ms": None,
                    "second_turn_latency_ms": None,
                    "error": _error_result(exc),
                }
            endpoint_results[hostname]["rank_probes"].append(result)

    ordered_results = []
    for replica in replicas:
        result = endpoint_results[replica["hostname"]]
        result["rank_probes"].sort(key=lambda row: (row["rank"], row["sample"]))
        expected_count = dp_size * per_rank_concurrency
        if (
            result["preflight"]["status"] != "pass"
            or len(result["rank_probes"]) != expected_count
            or any(row["status"] != "pass" for row in result["rank_probes"])
        ):
            result["status"] = "fail"
        ordered_results.append(result)
    overall_status = (
        "pass"
        if ordered_results and all(row["status"] == "pass" for row in ordered_results)
        else "fail"
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "mode": "one-shot",
        "model_service_id": manifest["model_service_id"],
        "expected_vllm_version": expected_version,
        "started_epoch": started_epoch,
        "finished_epoch": time.time(),
        "status": overall_status,
        "configuration": {
            "endpoint_count": len(replicas),
            "dp_size": dp_size,
            "per_rank_concurrency": per_rank_concurrency,
            "request_timeout_seconds": timeout,
            "protocol_probe_max_tokens": PROTOCOL_PROBE_MAX_TOKENS,
            "enable_thinking": bool(semantic.get("enable_thinking")),
        },
        "endpoints": ordered_results,
    }


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    """Atomically replace a complete one-shot report."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise ProbeError(f"output is not a regular non-symlink file: {path}")
    encoded = _canonical_bytes(payload) + b"\n"
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary_path, 0o644)
        os.replace(temporary_path, path)
        directory_descriptor = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def append_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    """Append one complete monitoring epoch without truncating prior rows."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise ProbeError(f"monitor output is not a regular non-symlink file: {path}")
    encoded = b"".join(_canonical_bytes(row) + b"\n" for row in rows)
    flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, 0o644)
    try:
        view = memoryview(encoded)
        while view:
            written = os.write(descriptor, view)
            view = view[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def monitor_service(
    manifest: dict[str, Any],
    *,
    output: Path,
    expected_version: str = DEFAULT_EXPECTED_VERSION,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    interval: float = DEFAULT_MONITOR_INTERVAL_SECONDS,
    stop_event: threading.Event | None = None,
    max_polls: int | None = None,
) -> int:
    """Append preflight status per endpoint until stopped."""
    if timeout <= 0:
        raise ProbeError("timeout must be positive")
    if not 10 <= interval <= 30:
        raise ProbeError("monitor interval must be between 10 and 30 seconds")
    if max_polls is not None and max_polls <= 0:
        raise ProbeError("max_polls must be positive when provided")
    stop_event = stop_event or threading.Event()
    semantic = manifest["semantic_config"]
    model = semantic["served_model_name"]
    replicas = manifest["replicas"]
    poll_index = 0
    while not stop_event.is_set():
        poll_index += 1
        epoch = time.time()
        rows_by_hostname: dict[str, dict[str, Any]] = {}
        with ThreadPoolExecutor(max_workers=len(replicas)) as executor:
            futures = {
                executor.submit(
                    _preflight_result,
                    replica,
                    model=model,
                    expected_version=expected_version,
                    timeout=timeout,
                ): replica
                for replica in replicas
            }
            for future in as_completed(futures):
                replica = futures[future]
                result = future.result()
                rows_by_hostname[replica["hostname"]] = {
                    "schema_version": SCHEMA_VERSION,
                    "mode": "monitor",
                    "model_service_id": manifest["model_service_id"],
                    "poll_index": poll_index,
                    "epoch": epoch,
                    "endpoint": replica["endpoint"],
                    "hostname": replica["hostname"],
                    "status": result["status"],
                    "latency_ms": result["latency_ms"],
                    "error": result.get("error"),
                }
        append_jsonl(
            output,
            [rows_by_hostname[replica["hostname"]] for replica in replicas],
        )
        if max_polls is not None and poll_index >= max_polls:
            break
        stop_event.wait(interval)
    return poll_index


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Probe or monitor a frozen multi-replica vLLM service."
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        required=True,
        help="Credential-free JSON produced by tools/freeze_model_service.py.",
    )
    parser.add_argument(
        "--expected-version",
        default=DEFAULT_EXPECTED_VERSION,
        help="Exact vLLM /version value (default: 0.24.0).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="Per-request timeout in seconds.",
    )
    subparsers = parser.add_subparsers(dest="mode", required=True)
    one_shot = subparsers.add_parser(
        "probe",
        help="Run one preflight plus concurrent two-turn protocol probes.",
    )
    one_shot.add_argument("--output", type=Path, required=True)
    one_shot.add_argument(
        "--per-rank-concurrency",
        type=int,
        default=DEFAULT_PER_RANK_CONCURRENCY,
    )
    monitor = subparsers.add_parser(
        "monitor",
        help="Append endpoint status to JSONL until SIGINT or SIGTERM.",
    )
    monitor.add_argument("--output", type=Path, required=True)
    monitor.add_argument(
        "--interval",
        type=float,
        default=DEFAULT_MONITOR_INTERVAL_SECONDS,
        help="Polling interval from 10 through 30 seconds.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    manifest_path = args.manifest.expanduser().resolve()
    output = args.output.expanduser().resolve()
    if output == manifest_path:
        raise ProbeError("output path must not overwrite the frozen manifest")
    manifest = load_frozen_manifest(manifest_path)
    if args.mode == "probe":
        report = run_one_shot(
            manifest,
            expected_version=args.expected_version,
            timeout=args.timeout,
            per_rank_concurrency=args.per_rank_concurrency,
        )
        atomic_write_json(output, report)
        print(report["status"])
        return 0 if report["status"] == "pass" else 1

    stop_event = threading.Event()

    def stop(_signum: int, _frame: Any) -> None:
        stop_event.set()

    previous_sigint = signal.signal(signal.SIGINT, stop)
    previous_sigterm = signal.signal(signal.SIGTERM, stop)
    try:
        monitor_service(
            manifest,
            output=output,
            expected_version=args.expected_version,
            timeout=args.timeout,
            interval=args.interval,
            stop_event=stop_event,
        )
    finally:
        signal.signal(signal.SIGINT, previous_sigint)
        signal.signal(signal.SIGTERM, previous_sigterm)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
