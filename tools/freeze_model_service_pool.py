#!/usr/bin/env python3
"""Freeze independently submitted, equivalent vLLM services into one pool ID."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from freeze_model_service import SCHEMA_VERSION
from probe_model_service import ProbeError, load_frozen_manifest


class PoolFreezeError(ValueError):
    """The member deployments cannot form one trustworthy service pool."""


def _canonical_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _semantic_signature(manifest: dict[str, Any]) -> dict[str, Any]:
    semantic = dict(manifest["semantic_config"])
    semantic.pop("replica_count", None)
    semantic.pop("total_gpu_count", None)
    return semantic


def _runtime_signature(manifest: dict[str, Any]) -> dict[str, Any]:
    observation = manifest["runtime_observation"]
    return {
        "expected_vllm_version": observation["expected_vllm_version"],
        "observed_versions": observation["observed_versions"],
    }


def build_pool_manifest(paths: list[Path]) -> dict[str, Any]:
    """Validate frozen members and return a probe-compatible frozen pool."""

    if len(paths) < 2:
        raise PoolFreezeError("a model service pool requires at least two manifests")
    resolved = [path.expanduser().resolve() for path in paths]
    if len(set(resolved)) != len(resolved):
        raise PoolFreezeError("model service pool contains a duplicate manifest path")

    members: list[dict[str, Any]] = []
    for path in resolved:
        try:
            member = load_frozen_manifest(path)
        except (OSError, ProbeError) as exc:
            raise PoolFreezeError(f"invalid frozen member {path}: {exc}") from exc
        members.append(member)

    baseline = members[0]
    semantic_signature = _semantic_signature(baseline)
    runtime_signature = _runtime_signature(baseline)
    artifacts = baseline["deployment_artifacts"]
    for member in members[1:]:
        if _semantic_signature(member) != semantic_signature:
            raise PoolFreezeError("member semantic configurations are not equivalent")
        if _runtime_signature(member) != runtime_signature:
            raise PoolFreezeError("member runtime versions are not equivalent")
        if member["deployment_artifacts"] != artifacts:
            raise PoolFreezeError("member deployment artifacts are not identical")

    replicas: list[dict[str, str]] = []
    runtime_replicas: list[dict[str, str]] = []
    member_sources: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_endpoints: set[str] = set()
    seen_hostnames: set[str] = set()
    total_gpu_count = 0
    for member in members:
        member_id = member["model_service_id"]
        if member_id in seen_ids:
            raise PoolFreezeError("model service pool contains a duplicate member ID")
        seen_ids.add(member_id)
        total_gpu_count += int(member["semantic_config"]["total_gpu_count"])
        member_sources.append(
            {
                "model_service_id": member_id,
                "deployment_source": member["deployment_source"],
            }
        )
        observations = {
            row["hostname"]: row
            for row in member["runtime_observation"]["replicas"]
        }
        for replica in member["replicas"]:
            endpoint = replica["endpoint"]
            hostname = replica["hostname"]
            if endpoint in seen_endpoints or hostname in seen_hostnames:
                raise PoolFreezeError("member deployments contain duplicate replicas")
            seen_endpoints.add(endpoint)
            seen_hostnames.add(hostname)
            replicas.append({"endpoint": endpoint, "hostname": hostname})
            runtime_replicas.append(dict(observations[hostname]))

    replicas.sort(key=lambda row: (row["hostname"], row["endpoint"]))
    runtime_replicas.sort(key=lambda row: row["hostname"])
    member_sources.sort(key=lambda row: row["model_service_id"])
    semantic = dict(baseline["semantic_config"])
    semantic["replica_count"] = len(replicas)
    semantic["total_gpu_count"] = total_gpu_count
    identity = {
        "schema_version": SCHEMA_VERSION,
        "deployment_source": {
            "provider": "model-service-pool",
            "members": member_sources,
        },
        "deployment_artifacts": artifacts,
        "runtime_observation": {
            **runtime_signature,
            "replicas": runtime_replicas,
        },
        "semantic_config": semantic,
        "replicas": replicas,
    }
    digest = hashlib.sha256(_canonical_bytes(identity)).hexdigest()
    return {**identity, "model_service_id": f"sha256:{digest}"}


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(_canonical_bytes(payload) + b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o644)
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        action="append",
        required=True,
        type=Path,
        help="Frozen model_service_manifest.json; repeat for each member.",
    )
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    output = args.output.expanduser().resolve()
    members = [path.expanduser().resolve() for path in args.manifest]
    if output in members:
        raise PoolFreezeError("output path must not overwrite a member manifest")
    payload = build_pool_manifest(members)
    atomic_write_json(output, payload)
    print(payload["model_service_id"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
