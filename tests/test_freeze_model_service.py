from __future__ import annotations

import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import freeze_model_service as freeze  # noqa: E402
import probe_model_service as probe  # noqa: E402


class FreezeModelServiceTests(unittest.TestCase):
    def smoke_log(
        self,
        *,
        torch: str = "2.8.0+cu129",
        transformers: str = "4.57.1",
        vllm: str = "0.24.0",
    ) -> str:
        return "\n".join(
            [
                "python 3.12.10",
                f"torch {torch} cuda 12.9",
                f"transformers {transformers}",
                f"vllm {vllm}",
                "credential=this-log-secret-must-not-leak",
                "",
            ]
        )

    def manifest(self) -> dict[str, object]:
        command_env = {
            "MODEL_DIR": "/pod/models/gemma",
            "SERVED_MODEL_NAME": "gemma-4-31b-it",
            "MAX_MODEL_LEN": "131072",
            "TP_SIZE": "4",
            "NUM_NODES": "4",
            "DP_SIZE": "2",
            "VLLM_RUNTIME_BASE": "/runtime/vllm024",
            "VLLM_ENV_SUBDIR": "vllm024",
            "VLLM_OVERLAY_SUBDIR": "none",
            "VLLM_ENV_DEREFERENCE": "1",
            "CHAT_TEMPLATE": "/pod/scripts/gemma4.jinja",
            "GPU_MEM_UTIL": "0.920",
            "MAX_NUM_SEQS": "8",
            "MAX_NUM_BATCHED_TOKENS": "65536",
            "ENABLE_THINKING": "true",
            "ENABLE_PREFIX_CACHING": "0",
            "ENFORCE_EAGER": "1",
            "COPY_RUNTIME_TO_SHM": "1",
            "OPENAI_API_KEY": "manifest-secret-must-not-leak",
        }
        return {
            "job_id": "test-job-1",
            "job_name": "vllm-gemma4",
            "run_name": "gemma4-4n",
            "submitted_at": "2026-07-29T00:00:00+00:00",
            "image": "registry/vllm:0.24",
            "serve_root": "/pod/artifacts/run",
            "inner_script": "/pod/scripts/serve.sh",
            "model_dir": "/pod/models/gemma",
            "served_model_name": "gemma-4-31b-it",
            "max_model_len": 131072,
            "tp_size": 4,
            "gpu_per_node": 8,
            "num_nodes": 4,
            "runtime_base": "/runtime/vllm024",
            "vllm_env_subdir": "vllm024",
            "vllm_overlay_subdir": "none",
            "vllm_env_dereference": "1",
            "chat_template": "/pod/scripts/gemma4.jinja",
            "command_env": command_env,
            "api_key": "top-level-secret-must-not-leak",
        }

    def endpoint(self, index: int) -> dict[str, str]:
        ip = f"10.1.0.{index + 10}"
        endpoint = f"http://{ip}:8000/v1"
        return {
            "OPENAI_BASE_URL": endpoint,
            "MODEL_NAME": "gemma-4-31b-it",
            "endpoint": endpoint,
            "hostname": f"replica-{index}",
            "ip": ip,
            "port": "8000",
            "served_model_name": "gemma-4-31b-it",
            "model_dir": "/pod/models/gemma",
            "max_model_len": "131072",
            "max_num_seqs": "8",
            "max_num_batched_tokens": "65536",
            "tp_size": "4",
            "dp_size": "2",
            "gpu_memory_utilization": "0.92",
            "runtime_source": "/runtime/vllm024",
            "vllm_env_subdir": "vllm024",
            "vllm_env_dereference": "true",
            "copy_runtime_to_shm": "1",
            "overlay_site": "",
            "tool_call_parser": "gemma4",
            "reasoning_parser": "gemma4",
            "enable_thinking": "1",
            "enable_prefix_caching": "false",
            "enforce_eager": "true",
            "num_nodes": "4",
            "server_log": f"/pod/artifacts/run/logs/server.replica-{index}.log",
            "OPENAI_API_KEY": "endpoint-secret-must-not-leak",
        }

    def write_fixture(
        self,
        root: Path,
        *,
        manifest: dict[str, object] | None = None,
        endpoints: list[dict[str, str]] | None = None,
        logs: list[str] | None = None,
    ) -> tuple[Path, Path, Path, Path]:
        host_root = root / "host"
        model_root = host_root / "models" / "gemma"
        scripts_root = host_root / "scripts"
        model_root.mkdir(parents=True)
        scripts_root.mkdir(parents=True)
        (model_root / "config.json").write_text(
            '{"model_type":"gemma4"}\n',
            encoding="utf-8",
        )
        (model_root / "model.safetensors.index.json").write_text(
            json.dumps(
                {
                    "metadata": {"total_size": 1},
                    "weight_map": {
                        "model.layers.0.weight": "model-00001-of-00001.safetensors"
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )
        (scripts_root / "gemma4.jinja").write_text(
            "{% for message in messages %}{{ message.content }}{% endfor %}\n",
            encoding="utf-8",
        )
        (scripts_root / "serve.sh").write_text(
            "#!/usr/bin/env bash\nexec python -m vllm.entrypoints.openai.api_server\n",
            encoding="utf-8",
        )

        manifest_path = root / "submit_manifest.json"
        manifest_path.write_text(
            json.dumps(manifest or self.manifest()),
            encoding="utf-8",
        )
        endpoints_dir = root / "endpoints"
        endpoints_dir.mkdir()
        for index, values in enumerate(
            endpoints or [self.endpoint(index) for index in range(4)]
        ):
            lines = [f"{key}={value}" for key, value in values.items()]
            (endpoints_dir / f"replica-{index}.env").write_text(
                "\n".join(lines) + "\n",
                encoding="utf-8",
            )
        logs_dir = root / "logs"
        logs_dir.mkdir()
        smoke_logs = logs or [self.smoke_log() for _ in range(4)]
        for index, content in enumerate(smoke_logs):
            (logs_dir / f"server.replica-{index}.log").write_text(
                content,
                encoding="utf-8",
            )
        return manifest_path, endpoints_dir, logs_dir, host_root

    def freeze_fixture(
        self,
        root: Path,
        *,
        manifest: dict[str, object] | None = None,
        endpoints: list[dict[str, str]] | None = None,
        logs: list[str] | None = None,
        expected_replicas: int = 4,
        expected_vllm_version: str = "0.24.0",
    ) -> dict[str, object]:
        manifest_path, endpoints_dir, logs_dir, host_root = self.write_fixture(
            root,
            manifest=manifest,
            endpoints=endpoints,
            logs=logs,
        )
        return freeze.build_frozen_manifest(
            submit_manifest=manifest_path,
            endpoints_dir=endpoints_dir,
            expected_replicas=expected_replicas,
            logs_dir=logs_dir,
            pod_path_prefix=Path("/pod"),
            host_path_prefix=host_root,
            expected_vllm_version=expected_vllm_version,
        )

    def test_success_is_canonical_deterministic_and_credential_free(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            payload = self.freeze_fixture(root)
            output = root / "frozen.json"
            freeze.atomic_write_json(output, payload)
            raw = output.read_bytes()
            self.assertEqual(probe.load_frozen_manifest(output), payload)

        self.assertTrue(raw.endswith(b"\n"))
        self.assertNotIn(b"secret-must-not-leak", raw)
        self.assertNotIn(b"api_key", raw.lower())
        self.assertNotIn(b"this-log-secret", raw)
        self.assertEqual(payload["semantic_config"]["total_gpu_count"], 32)
        self.assertEqual(payload["semantic_config"]["replica_count"], 4)
        self.assertEqual(
            payload["runtime_observation"]["observed_versions"],
            {
                "torch": "2.8.0+cu129",
                "transformers": "4.57.1",
                "vllm": "0.24.0",
            },
        )
        self.assertEqual(
            set(payload["deployment_artifacts"]),
            {
                "model_config",
                "model_safetensors_index",
                "chat_template",
                "inner_script",
            },
        )
        for artifact in payload["deployment_artifacts"].values():
            self.assertRegex(artifact["sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(
            [row["hostname"] for row in payload["replicas"]],
            [f"replica-{index}" for index in range(4)],
        )

        identity = dict(payload)
        model_service_id = identity.pop("model_service_id")
        expected_digest = hashlib.sha256(freeze._canonical_bytes(identity)).hexdigest()
        self.assertEqual(model_service_id, f"sha256:{expected_digest}")
        self.assertEqual(
            raw,
            freeze._canonical_bytes(payload) + b"\n",
        )
        self.assertEqual(payload["deployment_source"]["provider"], "generic")

    def test_provider_is_portable_canonical_and_conflict_checked(self) -> None:
        manifest = self.manifest()
        manifest["provider"] = "SLURM"
        self.assertEqual(freeze._deployment_provider(manifest, None), "slurm")
        self.assertEqual(
            freeze._deployment_provider(self.manifest(), "Kubernetes"), "kubernetes"
        )
        self.assertEqual(freeze._deployment_provider(manifest, "slurm"), "slurm")

        with self.assertRaisesRegex(
            freeze.FreezeError,
            "disagrees",
        ):
            freeze._deployment_provider(manifest, "kubernetes")
        with self.assertRaisesRegex(
            freeze.FreezeError,
            "valid identifier",
        ):
            freeze._deployment_provider(self.manifest(), "cluster provider")

    def test_file_order_does_not_change_service_id(self) -> None:
        endpoints = [self.endpoint(index) for index in range(4)]
        with tempfile.TemporaryDirectory() as first_tmp:
            first = self.freeze_fixture(Path(first_tmp), endpoints=endpoints)
        with tempfile.TemporaryDirectory() as second_tmp:
            second = self.freeze_fixture(
                Path(second_tmp),
                endpoints=list(reversed(endpoints)),
            )
        self.assertEqual(first, second)

    def test_replica_count_must_match_cli_manifest_and_endpoint_envs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaisesRegex(
                freeze.FreezeError,
                "num_nodes",
            ):
                self.freeze_fixture(root, expected_replicas=3)

    def test_cross_replica_semantic_mismatch_fails_closed(self) -> None:
        endpoints = [self.endpoint(index) for index in range(4)]
        endpoints[2]["reasoning_parser"] = "different-parser"
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(
                freeze.FreezeError,
                "differs across replicas",
            ):
                self.freeze_fixture(Path(temporary), endpoints=endpoints)

    def test_manifest_endpoint_semantic_mismatch_fails_closed(self) -> None:
        manifest = self.manifest()
        command_env = manifest["command_env"]
        assert isinstance(command_env, dict)
        command_env["MAX_NUM_SEQS"] = "16"
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(
                freeze.FreezeError,
                "max_num_seqs",
            ):
                self.freeze_fixture(Path(temporary), manifest=manifest)

    def test_pinned_tar_launcher_models_effective_node_local_runtime(self) -> None:
        manifest = self.manifest()
        manifest["inner_script"] = (
            "/pod/scripts/serve_gemma4_vllm024_tar_multinode_a800.sh"
        )
        semantic, _ = freeze._normalize_manifest(
            manifest,
            expected_replicas=4,
            deployment_provider=None,
        )
        self.assertEqual(
            semantic["runtime_source"],
            "/dev/shm/gemma4_vllm024_cu129",
        )
        self.assertEqual(semantic["vllm_env_subdir"], "vllm024")
        self.assertEqual(semantic["vllm_overlay_subdir"], "none")
        self.assertIs(semantic["copy_runtime_to_shm"], False)

        command_env = manifest["command_env"]
        assert isinstance(command_env, dict)
        command_env["SHM_ENV_ROOT"] = "/dev/shm/custom-vllm"
        semantic, _ = freeze._normalize_manifest(
            manifest,
            expected_replicas=4,
            deployment_provider=None,
        )
        self.assertEqual(semantic["runtime_source"], "/dev/shm/custom-vllm")

    def test_duplicate_endpoint_and_hostname_are_rejected(self) -> None:
        for duplicated_field in ("endpoint", "hostname"):
            endpoints = [self.endpoint(index) for index in range(4)]
            if duplicated_field == "endpoint":
                for key in ("endpoint", "OPENAI_BASE_URL", "ip"):
                    endpoints[1][key] = endpoints[0][key]
            else:
                endpoints[1]["hostname"] = endpoints[0]["hostname"]
            with self.subTest(field=duplicated_field):
                with tempfile.TemporaryDirectory() as temporary:
                    with self.assertRaisesRegex(
                        freeze.FreezeError,
                        f"duplicate replica {duplicated_field}",
                    ):
                        self.freeze_fixture(Path(temporary), endpoints=endpoints)

    def test_endpoint_url_credentials_are_rejected(self) -> None:
        endpoints = [self.endpoint(index) for index in range(4)]
        endpoints[0]["endpoint"] = "http://user:password@10.1.0.10:8000/v1"
        endpoints[0]["OPENAI_BASE_URL"] = endpoints[0]["endpoint"]
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(
                freeze.FreezeError,
                "must not contain credentials",
            ):
                self.freeze_fixture(Path(temporary), endpoints=endpoints)

    def test_failed_validation_leaves_existing_output_unchanged(self) -> None:
        endpoints = [self.endpoint(index) for index in range(4)]
        endpoints[3]["tool_call_parser"] = "broken"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (
                manifest_path,
                endpoints_dir,
                logs_dir,
                host_root,
            ) = self.write_fixture(root, endpoints=endpoints)
            output = root / "frozen.json"
            output.write_text("previous-good-manifest\n", encoding="utf-8")
            with self.assertRaises(freeze.FreezeError):
                payload = freeze.build_frozen_manifest(
                    submit_manifest=manifest_path,
                    endpoints_dir=endpoints_dir,
                    expected_replicas=4,
                    logs_dir=logs_dir,
                    pod_path_prefix=Path("/pod"),
                    host_path_prefix=host_root,
                )
                freeze.atomic_write_json(output, payload)
            self.assertEqual(
                output.read_text(encoding="utf-8"),
                "previous-good-manifest\n",
            )

    def test_dry_run_manifest_is_rejected(self) -> None:
        manifest = self.manifest()
        manifest["job_id"] = "dry-run"
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(
                freeze.FreezeError,
                "job_id=dry-run",
            ):
                self.freeze_fixture(Path(temporary), manifest=manifest)

    def test_path_prefixes_must_be_paired(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (
                manifest_path,
                endpoints_dir,
                logs_dir,
                _,
            ) = self.write_fixture(root)
            with self.assertRaisesRegex(
                freeze.FreezeError,
                "must be supplied together",
            ):
                freeze.build_frozen_manifest(
                    submit_manifest=manifest_path,
                    endpoints_dir=endpoints_dir,
                    logs_dir=logs_dir,
                    expected_replicas=4,
                    pod_path_prefix=Path("/pod"),
                )

    def test_missing_or_symlinked_artifact_is_rejected(self) -> None:
        for artifact_relative in (
            Path("models/gemma/config.json"),
            Path("scripts/serve.sh"),
        ):
            with self.subTest(artifact=str(artifact_relative)):
                with tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary)
                    (
                        manifest_path,
                        endpoints_dir,
                        logs_dir,
                        host_root,
                    ) = self.write_fixture(root)
                    artifact = host_root / artifact_relative
                    artifact.unlink()
                    if artifact.name == "serve.sh":
                        artifact.symlink_to(host_root / "scripts/gemma4.jinja")
                    with self.assertRaisesRegex(
                        freeze.FreezeError,
                        "required (model_config|inner_script)",
                    ):
                        freeze.build_frozen_manifest(
                            submit_manifest=manifest_path,
                            endpoints_dir=endpoints_dir,
                            logs_dir=logs_dir,
                            expected_replicas=4,
                            pod_path_prefix=Path("/pod"),
                            host_path_prefix=host_root,
                        )

    def test_invalid_model_index_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (
                manifest_path,
                endpoints_dir,
                logs_dir,
                host_root,
            ) = self.write_fixture(root)
            (host_root / "models/gemma/model.safetensors.index.json").write_text(
                '{"metadata":{}}\n',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                freeze.FreezeError,
                "non-empty weight_map",
            ):
                freeze.build_frozen_manifest(
                    submit_manifest=manifest_path,
                    endpoints_dir=endpoints_dir,
                    logs_dir=logs_dir,
                    expected_replicas=4,
                    pod_path_prefix=Path("/pod"),
                    host_path_prefix=host_root,
                )

    def test_identity_hashes_metadata_but_not_weight_shards(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (
                manifest_path,
                endpoints_dir,
                logs_dir,
                host_root,
            ) = self.write_fixture(root)
            weight = host_root / "models/gemma/model-00001-of-00001.safetensors"
            weight.write_bytes(b"first weight content")
            kwargs = {
                "submit_manifest": manifest_path,
                "endpoints_dir": endpoints_dir,
                "logs_dir": logs_dir,
                "expected_replicas": 4,
                "pod_path_prefix": Path("/pod"),
                "host_path_prefix": host_root,
            }
            first = freeze.build_frozen_manifest(**kwargs)
            weight.write_bytes(b"different weight content")
            after_weight_change = freeze.build_frozen_manifest(**kwargs)
            self.assertEqual(
                first["model_service_id"],
                after_weight_change["model_service_id"],
            )

            (host_root / "models/gemma/config.json").write_text(
                '{"model_type":"gemma4","revision":2}\n',
                encoding="utf-8",
            )
            after_config_change = freeze.build_frozen_manifest(**kwargs)
            self.assertNotEqual(
                first["model_service_id"],
                after_config_change["model_service_id"],
            )

    def test_server_log_count_and_declarations_are_exact(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(
                freeze.FreezeError,
                "server smoke log count mismatch",
            ):
                self.freeze_fixture(
                    Path(temporary),
                    logs=[self.smoke_log() for _ in range(3)],
                )

        endpoints = [self.endpoint(index) for index in range(4)]
        endpoints[0]["server_log"] = "/pod/artifacts/run/logs/server.not-a-replica.log"
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(
                freeze.FreezeError,
                "declarations do not match",
            ):
                self.freeze_fixture(Path(temporary), endpoints=endpoints)

    def test_single_replica_accepts_launcher_server_log_name(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            logs_dir = Path(temporary)
            (logs_dir / "server.log").write_text(
                self.smoke_log(),
                encoding="utf-8",
            )

            observation, paths = freeze._freeze_runtime_observation(
                logs_dir=logs_dir,
                replica_logs=[{"hostname": "replica-0", "log_file": "server.log"}],
                expected_replicas=1,
                expected_vllm_version="0.24.0",
            )

            self.assertEqual(observation["observed_versions"]["vllm"], "0.24.0")
            self.assertEqual(paths, {logs_dir / "server.log"})

    def test_server_log_requires_complete_consistent_smoke_versions(self) -> None:
        missing_transformers = [
            self.smoke_log().replace("transformers 4.57.1\n", "") for _ in range(4)
        ]
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(
                freeze.FreezeError,
                "missing observed transformers",
            ):
                self.freeze_fixture(
                    Path(temporary),
                    logs=missing_transformers,
                )

        cross_node_mismatch = [self.smoke_log() for _ in range(4)]
        cross_node_mismatch[2] = self.smoke_log(torch="2.9.0+cu129")
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(
                freeze.FreezeError,
                "versions differ across replicas",
            ):
                self.freeze_fixture(
                    Path(temporary),
                    logs=cross_node_mismatch,
                )

        conflicting_restart = [self.smoke_log() for _ in range(4)]
        conflicting_restart[1] += "vllm 0.23.0\n"
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(
                freeze.FreezeError,
                "conflicting vllm versions",
            ):
                self.freeze_fixture(
                    Path(temporary),
                    logs=conflicting_restart,
                )

    def test_expected_vllm_version_is_enforced_and_overridable(self) -> None:
        logs = [self.smoke_log(vllm="0.25.0") for _ in range(4)]
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(
                freeze.FreezeError,
                "disagrees with expected version",
            ):
                self.freeze_fixture(Path(temporary), logs=logs)
        with tempfile.TemporaryDirectory() as temporary:
            payload = self.freeze_fixture(
                Path(temporary),
                logs=logs,
                expected_vllm_version="0.25.0",
            )
        self.assertEqual(
            payload["runtime_observation"]["observed_versions"]["vllm"],
            "0.25.0",
        )

    def test_raw_json_duplicate_key_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "submit_manifest.json"
            path.write_text('{"job_id":"first","job_id":"second"}', encoding="utf-8")
            with self.assertRaisesRegex(freeze.FreezeError, "duplicate JSON key"):
                freeze._load_manifest(path)

    def test_atomic_writer_replaces_complete_document(self) -> None:
        payload = {"z": 1, "a": {"value": True}}
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "nested" / "frozen.json"
            freeze.atomic_write_json(output, payload)
            first = output.read_bytes()
            modified = copy.deepcopy(payload)
            modified["z"] = 2
            freeze.atomic_write_json(output, modified)
            second = output.read_bytes()
        self.assertEqual(first, b'{"a":{"value":true},"z":1}\n')
        self.assertEqual(second, b'{"a":{"value":true},"z":2}\n')


if __name__ == "__main__":
    unittest.main()
