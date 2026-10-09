from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from freeze_model_service_pool import PoolFreezeError, build_pool_manifest  # noqa: E402
from probe_model_service import load_frozen_manifest  # noqa: E402


def canonical(payload: object) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


def write_member(path: Path, *, suffix: str, max_num_seqs: int = 4) -> Path:
    hostname = f"worker-{suffix}"
    identity = {
        "schema_version": 2,
        "deployment_source": {"provider": "slurm", "job_id": f"job-{suffix}"},
        "deployment_artifacts": {
            name: {
                "pod_path": f"/assets/{name}",
                "sha256": character * 64,
                "size_bytes": 1,
            }
            for name, character in (
                ("model_config", "a"),
                ("model_safetensors_index", "b"),
                ("chat_template", "c"),
                ("inner_script", "d"),
            )
        },
        "runtime_observation": {
            "expected_vllm_version": "0.24.0",
            "observed_versions": {
                "torch": "2.11.0+cu129",
                "transformers": "5.12.1",
                "vllm": "0.24.0",
            },
            "replicas": [{"hostname": hostname, "log_file": f"{hostname}.log"}],
        },
        "semantic_config": {
            "served_model_name": "gemma-4-31b-it",
            "dp_size": 1,
            "max_num_seqs": max_num_seqs,
            "gpu_per_replica": 4,
            "replica_count": 1,
            "total_gpu_count": 4,
        },
        "replicas": [
            {"endpoint": f"http://10.0.0.{suffix}:8000/v1", "hostname": hostname}
        ],
    }
    service_id = f"sha256:{hashlib.sha256(canonical(identity)).hexdigest()}"
    path.write_bytes(canonical({**identity, "model_service_id": service_id}) + b"\n")
    return path


def test_pool_is_probe_compatible_and_counts_all_replicas(tmp_path: Path) -> None:
    first = write_member(tmp_path / "first.json", suffix="1")
    second = write_member(tmp_path / "second.json", suffix="2")

    pool = build_pool_manifest([first, second])
    output = tmp_path / "pool.json"
    output.write_bytes(canonical(pool) + b"\n")

    loaded = load_frozen_manifest(output)
    assert loaded["semantic_config"]["replica_count"] == 2
    assert loaded["semantic_config"]["total_gpu_count"] == 8
    assert len(loaded["deployment_source"]["members"]) == 2


def test_pool_rejects_semantic_mismatch(tmp_path: Path) -> None:
    first = write_member(tmp_path / "first.json", suffix="1")
    second = write_member(tmp_path / "second.json", suffix="2", max_num_seqs=8)

    with pytest.raises(PoolFreezeError, match="semantic configurations"):
        build_pool_manifest([first, second])


def test_pool_requires_distinct_members(tmp_path: Path) -> None:
    member = write_member(tmp_path / "member.json", suffix="1")

    with pytest.raises(PoolFreezeError, match="duplicate manifest path"):
        build_pool_manifest([member, member])
