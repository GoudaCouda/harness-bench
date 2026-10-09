from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import merge_shards as merge_module  # noqa: E402
from harnessbench.task_sets import (  # noqa: E402
    bytes_sha256,
    make_task_selection_identity,
)
from merge_shards import CONSISTENCY_FIELDS, MERGED_SEMANTIC_FIELDS  # noqa: E402


class MergeShardGuardTests(unittest.TestCase):
    task_ids = {"001-test", "002-test", "003-test"}
    service_id = "sha256:" + "a" * 64

    def named_selection(
        self,
        task_ids: set[str],
        *,
        purpose: str = "Test named selection.",
    ) -> tuple[dict, str]:
        rendered_ids = "\n".join(f"- {task_id}" for task_id in sorted(task_ids))
        manifest = f"""\
schema_version: 1
task_set: curated
status: research_subset
source_suite: main
source_suite_size: {len(self.task_ids)}
task_count: {len(task_ids)}
selection_policy:
  selected_at: '2026-07-31'
  model_outcomes_used: false
  changes_main_membership: false
  relocates_task_directories: false
  purpose: {purpose}
task_ids:
{rendered_ids}
"""
        identity = make_task_selection_identity(
            mode="named",
            task_ids=task_ids,
            task_set="curated",
            manifest_sha256=bytes_sha256(manifest.encode("utf-8")),
        )
        return identity, manifest

    @staticmethod
    def runtime_identity(marker: str = "a") -> tuple[dict, str]:
        payload = {
            "schema_version": 1,
            "implementation": "CPython",
            "python_version": "3.10.0",
            "python_executable_sha256": marker * 64,
            "distributions": {
                "PyYAML": {
                    "version": "6.0",
                    "distribution_tree_sha256": marker * 64,
                    "file_count": 1,
                },
                "tomli": {
                    "version": "2.0",
                    "distribution_tree_sha256": marker * 64,
                    "file_count": 1,
                },
            },
            "uv_lock_sha256": marker * 64,
        }
        canonical = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        return payload, f"sha256:{hashlib.sha256(canonical).hexdigest()}"

    def write_shard(
        self,
        root: Path,
        *,
        shard_index: int,
        selected: dict[str, tuple[str, float | None]],
        base_url: str = "http://model/v1",
        model_service_id: str | None = service_id,
        data_parallel_rank: int | None = None,
        workers: int = 1,
        controller_runtime_marker: str = "a",
        selection_identity: dict | None = None,
        task_set_manifest: str | None = None,
    ) -> Path:
        root.mkdir()
        rows = []
        for task_id in sorted(self.task_ids):
            status, score = selected.get(task_id, ("not_selected", None))
            rows.append(
                {
                    "task_id": task_id,
                    "title": task_id,
                    "domain": "Test",
                    "difficulty": "medium",
                    "task_definition_sha256": task_id,
                    "status": status,
                    "outcome_score": score,
                    "elapsed_sec": 1.0 if status != "not_selected" else None,
                    "required_artifacts": (
                        {"complete": True} if status != "not_selected" else None
                    ),
                    "review_flag": "",
                    "error": "",
                }
            )
            if status in merge_module.TERMINAL:
                result_dir = root / "tasks" / task_id
                result_dir.mkdir(parents=True)
                (result_dir / "result.json").write_text(
                    json.dumps(
                        {
                            "task_id": task_id,
                            "status": status,
                            "outcome_score": score,
                        }
                    ),
                    encoding="utf-8",
                )
        controller_runtime, controller_runtime_id = self.runtime_identity(
            controller_runtime_marker
        )
        summary = {
            "schema_version": 1,
            "benchmark": "HarnessBench",
            "suite": "main",
            "suite_size": len(self.task_ids),
            "suite_definition_sha256": "suite",
            "suite_snapshot_sha256": "snapshot",
            "controller_definition_sha256": "controller",
            "controller_runtime": controller_runtime,
            "controller_runtime_id": controller_runtime_id,
            "selected_count": len(selected),
            "shard_index": shard_index,
            "shard_count": 2,
            "grading": "oracle_only",
            "model": "model",
            "harness": "openclaw",
            "harness_version": "1",
            "harness_protocol": "chat_completions",
            "harness_profile": "controlled-core",
            "provider_timeout_policy": "match_round_timeout",
            "base_url": base_url,
            "harness_image": "openclaw@sha256:test",
            "openclaw_image": "openclaw@sha256:test",
            "trace_complete": True,
            "runtime_images": {"grader": "sha256:grader"},
            "isolation": {
                "schema_version": 1,
                "level": "transitional",
                "engine": "docker",
                "server_version": "test",
                "rootless": False,
                "default_runtime": "runc",
                "cgroup_driver": "systemd",
                "security_options": [
                    "name=apparmor",
                    "name=seccomp,profile=builtin",
                ],
                "network_policy": ("direct-no-secret-model-endpoint-over-bridge"),
            },
            "workers": workers,
            "max_tokens": 128,
            "temperature": 0.0,
            "data_parallel_rank": (
                shard_index if data_parallel_rank is None else data_parallel_rank
            ),
            "thinking": "low",
            "timeout_override": 60,
            "tasks": rows,
        }
        if model_service_id is not None:
            summary["model_service_id"] = model_service_id
        if selection_identity is not None:
            summary["selection"] = selection_identity
            summary["task_set"] = selection_identity["task_set"]
            if selection_identity["mode"] == "named":
                if task_set_manifest is None:
                    raise ValueError("named test selection requires a manifest")
                catalog = root / "selection" / "catalog"
                catalog.mkdir(parents=True)
                (catalog / f"{selection_identity['task_set']}.yaml").write_text(
                    task_set_manifest,
                    encoding="utf-8",
                )
        (root / "summary.json").write_text(
            json.dumps(summary),
            encoding="utf-8",
        )
        return root

    def merge(
        self,
        roots: list[Path],
        output: Path,
        *,
        allow_subset: bool = False,
        run_plan: dict | None = None,
    ) -> dict:
        with mock.patch.object(merge_module, "TASK_IDS", self.task_ids):
            return merge_module.merge_shard_runs(
                roots,
                output=output,
                allow_subset=allow_subset,
                run_plan=run_plan,
            )

    def test_harness_execution_identity_is_consistent(self) -> None:
        required = {
            "harness",
            "harness_version",
            "harness_protocol",
            "harness_profile",
            "provider_timeout_policy",
            "harness_image",
            "runtime_images",
            "isolation",
            "trace_complete",
            "controller_runtime",
            "controller_runtime_id",
        }
        self.assertTrue(required.issubset(CONSISTENCY_FIELDS))

    def test_named_subset_merge_preserves_global_identity_and_manifest(self) -> None:
        identity, manifest = self.named_selection({"001-test", "002-test"})
        with tempfile.TemporaryDirectory() as tmp:
            temp = Path(tmp)
            roots = [
                self.write_shard(
                    temp / "shard-0",
                    shard_index=0,
                    selected={"001-test": ("completed", 1.0)},
                    selection_identity=identity,
                    task_set_manifest=manifest,
                ),
                self.write_shard(
                    temp / "shard-1",
                    shard_index=1,
                    selected={"002-test": ("completed", 0.5)},
                    selection_identity=identity,
                    task_set_manifest=manifest,
                ),
            ]
            output = temp / "merged"
            payload = self.merge(roots, output, allow_subset=True)

            self.assertEqual(payload["task_set"], "curated")
            self.assertEqual(payload["selection"], identity)
            self.assertEqual(
                (output / "selection" / "catalog" / "curated.yaml").read_text(
                    encoding="utf-8"
                ),
                manifest,
            )

    def test_main_selection_identity_accepts_complete_canonical_shards(self) -> None:
        identity = make_task_selection_identity(
            mode="main",
            task_ids=self.task_ids,
        )
        with tempfile.TemporaryDirectory() as tmp:
            temp = Path(tmp)
            roots = [
                self.write_shard(
                    temp / "shard-0",
                    shard_index=0,
                    selected={
                        "001-test": ("completed", 1.0),
                        "003-test": ("completed", 1.0),
                    },
                    selection_identity=identity,
                ),
                self.write_shard(
                    temp / "shard-1",
                    shard_index=1,
                    selected={"002-test": ("completed", 0.5)},
                    selection_identity=identity,
                ),
            ]
            payload = self.merge(roots, temp / "merged")

        self.assertEqual(payload["selection"], identity)
        self.assertEqual(payload["selected_count"], 3)

    def test_named_subset_merge_rejects_incomplete_declared_membership(self) -> None:
        identity, manifest = self.named_selection(self.task_ids)
        with tempfile.TemporaryDirectory() as tmp:
            temp = Path(tmp)
            roots = [
                self.write_shard(
                    temp / "shard-0",
                    shard_index=0,
                    selected={"001-test": ("completed", 1.0)},
                    selection_identity=identity,
                    task_set_manifest=manifest,
                ),
                self.write_shard(
                    temp / "shard-1",
                    shard_index=1,
                    selected={"002-test": ("completed", 0.5)},
                    selection_identity=identity,
                    task_set_manifest=manifest,
                ),
            ]
            with self.assertRaisesRegex(ValueError, "global identity"):
                self.merge(roots, temp / "merged", allow_subset=True)

    def test_named_subset_merge_rejects_different_manifest_identities(self) -> None:
        first_identity, first_manifest = self.named_selection(
            {"001-test", "002-test"},
            purpose="First selection.",
        )
        second_identity, second_manifest = self.named_selection(
            {"001-test", "002-test"},
            purpose="Changed selection.",
        )
        with tempfile.TemporaryDirectory() as tmp:
            temp = Path(tmp)
            roots = [
                self.write_shard(
                    temp / "shard-0",
                    shard_index=0,
                    selected={"001-test": ("completed", 1.0)},
                    selection_identity=first_identity,
                    task_set_manifest=first_manifest,
                ),
                self.write_shard(
                    temp / "shard-1",
                    shard_index=1,
                    selected={"002-test": ("completed", 0.5)},
                    selection_identity=second_identity,
                    task_set_manifest=second_manifest,
                ),
            ]
            with self.assertRaisesRegex(ValueError, "incompatible shard"):
                self.merge(roots, temp / "merged", allow_subset=True)

    def test_named_subset_merge_rejects_missing_selection_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp = Path(tmp)
            roots = [
                self.write_shard(
                    temp / "shard-0",
                    shard_index=0,
                    selected={"001-test": ("completed", 1.0)},
                ),
                self.write_shard(
                    temp / "shard-1",
                    shard_index=1,
                    selected={"002-test": ("completed", 0.5)},
                ),
            ]
            for root in roots:
                path = root / "summary.json"
                summary = json.loads(path.read_text(encoding="utf-8"))
                summary["task_set"] = "curated"
                path.write_text(json.dumps(summary), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "no selection identity"):
                self.merge(roots, temp / "merged", allow_subset=True)

    def test_explicit_invalidation_marker_blocks_merge(self) -> None:
        self.assertEqual(
            merge_module.INVALIDATION_MARKERS[0],
            merge_module.INVALIDATION_MARKER,
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            shards = [
                self.write_shard(
                    root / "shard-0",
                    shard_index=0,
                    selected={
                        "001-test": ("completed", 1.0),
                        "003-test": ("completed", 1.0),
                    },
                ),
                self.write_shard(
                    root / "shard-1",
                    shard_index=1,
                    selected={"002-test": ("completed", 1.0)},
                ),
            ]
            (root / merge_module.INVALIDATION_MARKER).write_text(
                '{"reason":"diagnostic task-definition defects"}\n',
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "explicitly invalidated"):
                self.merge(shards, root / "merged")

    def test_both_marker_names_block_shards_parent_and_formal_ancestor(self) -> None:
        sensitive_content = (
            "https://" + "example.invalid/" + "github_" + "pat_" + "synthetic"
        )
        for marker_name in merge_module.INVALIDATION_MARKERS:
            for marker_level in ("shards", "formal"):
                with self.subTest(
                    marker_name=marker_name,
                    marker_level=marker_level,
                ):
                    with tempfile.TemporaryDirectory() as temporary:
                        formal = Path(temporary) / "formal"
                        shards_root = formal / "shards"
                        shards_root.mkdir(parents=True)
                        shards = [
                            self.write_shard(
                                shards_root / "shard-0",
                                shard_index=0,
                                selected={
                                    "001-test": ("completed", 1.0),
                                    "003-test": ("completed", 1.0),
                                },
                            ),
                            self.write_shard(
                                shards_root / "shard-1",
                                shard_index=1,
                                selected={"002-test": ("completed", 1.0)},
                            ),
                        ]
                        marker_root = (
                            shards_root if marker_level == "shards" else formal
                        )
                        (marker_root / marker_name).write_text(
                            json.dumps({"reason": sensitive_content}) + "\n",
                            encoding="utf-8",
                        )

                        with self.assertRaisesRegex(
                            ValueError,
                            "explicitly invalidated",
                        ) as raised:
                            self.merge(shards, formal / "merged")
                        message = str(raised.exception)
                        self.assertNotIn(sensitive_content, message)
                        self.assertNotIn(str(formal), message)

    def test_merged_summary_preserves_harness_execution_identity(self) -> None:
        required = {
            "harness",
            "harness_version",
            "harness_protocol",
            "harness_profile",
            "provider_timeout_policy",
            "harness_image",
            "runtime_images",
            "isolation",
            "trace_complete",
            "controller_runtime",
            "controller_runtime_id",
        }
        self.assertTrue(required.issubset(MERGED_SEMANTIC_FIELDS))

    def test_data_parallel_rank_may_differ_between_shards(self) -> None:
        self.assertNotIn("data_parallel_rank", CONSISTENCY_FIELDS)

    def test_different_controller_runtimes_cannot_merge(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp = Path(tmp)
            roots = [
                self.write_shard(
                    temp / "shard-0",
                    shard_index=0,
                    selected={
                        "001-test": ("completed", 1.0),
                        "003-test": ("completed", 0.0),
                    },
                    controller_runtime_marker="a",
                ),
                self.write_shard(
                    temp / "shard-1",
                    shard_index=1,
                    selected={"002-test": ("completed", 0.5)},
                    controller_runtime_marker="b",
                ),
            ]
            with self.assertRaisesRegex(ValueError, "controller_runtime"):
                self.merge(roots, temp / "merged")

    def test_docker_server_patch_versions_may_differ_between_workers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp = Path(tmp)
            roots = [
                self.write_shard(
                    temp / "shard-0",
                    shard_index=0,
                    selected={
                        "001-test": ("completed", 1.0),
                        "003-test": ("completed", 0.0),
                    },
                ),
                self.write_shard(
                    temp / "shard-1",
                    shard_index=1,
                    selected={"002-test": ("completed", 0.5)},
                ),
            ]
            second_path = roots[1] / "summary.json"
            second = json.loads(second_path.read_text(encoding="utf-8"))
            second["isolation"]["server_version"] = "test-patch-2"
            second_path.write_text(json.dumps(second), encoding="utf-8")

            payload = self.merge(roots, temp / "merged")

        self.assertEqual(payload["docker_server_versions"], ["test", "test-patch-2"])
        self.assertEqual(
            {
                value["server_version"]
                for value in payload["source_isolation"].values()
            },
            {"test", "test-patch-2"},
        )

    def test_meaningful_isolation_differences_still_block_merge(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp = Path(tmp)
            roots = [
                self.write_shard(
                    temp / "shard-0",
                    shard_index=0,
                    selected={
                        "001-test": ("completed", 1.0),
                        "003-test": ("completed", 0.0),
                    },
                ),
                self.write_shard(
                    temp / "shard-1",
                    shard_index=1,
                    selected={"002-test": ("completed", 0.5)},
                ),
            ]
            second_path = roots[1] / "summary.json"
            second = json.loads(second_path.read_text(encoding="utf-8"))
            second["isolation"]["default_runtime"] = "runsc"
            second_path.write_text(json.dumps(second), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "isolation"):
                self.merge(roots, temp / "merged")

    def test_controller_runtime_id_must_match_its_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp = Path(tmp)
            roots = [
                self.write_shard(
                    temp / "shard-0",
                    shard_index=0,
                    selected={
                        "001-test": ("completed", 1.0),
                        "003-test": ("completed", 0.0),
                    },
                ),
                self.write_shard(
                    temp / "shard-1",
                    shard_index=1,
                    selected={"002-test": ("completed", 0.5)},
                ),
            ]
            summary_path = roots[1] / "summary.json"
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            summary["controller_runtime_id"] = "sha256:" + "0" * 64
            summary_path.write_text(json.dumps(summary), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "invalid controller_runtime_id"):
                self.merge(roots, temp / "merged")

    def test_equivalent_replica_urls_merge_with_common_service_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp = Path(tmp)
            roots = [
                self.write_shard(
                    temp / "shard-0",
                    shard_index=0,
                    selected={
                        "001-test": ("completed", 1.0),
                        "003-test": ("completed", 0.0),
                    },
                    base_url="http://replica-a/v1",
                ),
                self.write_shard(
                    temp / "shard-1",
                    shard_index=1,
                    selected={"002-test": ("completed", 0.5)},
                    base_url="http://replica-b/v1",
                ),
            ]
            payload = self.merge(roots, temp / "merged")

        self.assertEqual(payload["model_service_id"], self.service_id)
        self.assertIsNone(payload["base_url"])
        self.assertEqual(
            payload["base_urls"],
            ["http://replica-a/v1", "http://replica-b/v1"],
        )
        self.assertEqual(
            set(payload["source_base_urls"].values()),
            {"http://replica-a/v1", "http://replica-b/v1"},
        )
        expected_runtime, expected_runtime_id = self.runtime_identity()
        self.assertEqual(payload["controller_runtime"], expected_runtime)
        self.assertEqual(payload["controller_runtime_id"], expected_runtime_id)

    def test_different_replica_urls_without_service_id_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp = Path(tmp)
            roots = [
                self.write_shard(
                    temp / "shard-0",
                    shard_index=0,
                    selected={"001-test": ("completed", 1.0)},
                    base_url="http://replica-a/v1",
                    model_service_id=None,
                ),
                self.write_shard(
                    temp / "shard-1",
                    shard_index=1,
                    selected={
                        "002-test": ("completed", 0.5),
                        "003-test": ("completed", 0.0),
                    },
                    base_url="http://replica-b/v1",
                    model_service_id=None,
                ),
            ]
            with self.assertRaisesRegex(ValueError, "model_service_id"):
                self.merge(roots, temp / "merged")

    def test_different_replica_urls_reject_free_form_service_label(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp = Path(tmp)
            roots = [
                self.write_shard(
                    temp / "shard-0",
                    shard_index=0,
                    selected={"001-test": ("completed", 1.0)},
                    base_url="http://replica-a/v1",
                    model_service_id="same-model-name",
                ),
                self.write_shard(
                    temp / "shard-1",
                    shard_index=1,
                    selected={
                        "002-test": ("completed", 0.5),
                        "003-test": ("completed", 0.0),
                    },
                    base_url="http://replica-b/v1",
                    model_service_id="same-model-name",
                ),
            ]
            with self.assertRaisesRegex(ValueError, "frozen sha256"):
                self.merge(roots, temp / "merged")

    def test_default_merge_rejects_noncanonical_task_assignment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp = Path(tmp)
            roots = [
                self.write_shard(
                    temp / "shard-0",
                    shard_index=0,
                    selected={
                        "001-test": ("completed", 1.0),
                        "002-test": ("completed", 0.5),
                    },
                ),
                self.write_shard(
                    temp / "shard-1",
                    shard_index=1,
                    selected={"003-test": ("completed", 0.0)},
                ),
            ]
            with self.assertRaisesRegex(
                ValueError,
                "task assigned to non-canonical shard",
            ):
                self.merge(roots, temp / "merged")

    def test_terminal_task_requires_result_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp = Path(tmp)
            roots = [
                self.write_shard(
                    temp / "shard-0",
                    shard_index=0,
                    selected={"001-test": ("completed", 1.0)},
                ),
                self.write_shard(
                    temp / "shard-1",
                    shard_index=1,
                    selected={"002-test": ("completed", 0.5)},
                ),
            ]
            (roots[0] / "tasks" / "001-test" / "result.json").unlink()
            with self.assertRaisesRegex(
                ValueError,
                "missing terminal task result",
            ):
                self.merge(
                    roots,
                    temp / "merged",
                    allow_subset=True,
                )

    def test_terminal_task_requires_parseable_result_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp = Path(tmp)
            roots = [
                self.write_shard(
                    temp / "shard-0",
                    shard_index=0,
                    selected={"001-test": ("completed", 1.0)},
                ),
                self.write_shard(
                    temp / "shard-1",
                    shard_index=1,
                    selected={"002-test": ("completed", 0.5)},
                ),
            ]
            (roots[0] / "tasks" / "001-test" / "result.json").write_text(
                "{broken", encoding="utf-8"
            )
            with self.assertRaisesRegex(
                ValueError,
                "invalid terminal task result JSON",
            ):
                self.merge(
                    roots,
                    temp / "merged",
                    allow_subset=True,
                )

    def test_terminal_result_identity_must_match_summary(self) -> None:
        for field, wrong_value in (
            ("task_id", "999-wrong"),
            ("status", "timeout"),
        ):
            with self.subTest(field=field):
                with tempfile.TemporaryDirectory() as tmp:
                    temp = Path(tmp)
                    roots = [
                        self.write_shard(
                            temp / "shard-0",
                            shard_index=0,
                            selected={"001-test": ("completed", 1.0)},
                        ),
                        self.write_shard(
                            temp / "shard-1",
                            shard_index=1,
                            selected={"002-test": ("completed", 0.5)},
                        ),
                    ]
                    result_path = roots[0] / "tasks" / "001-test" / "result.json"
                    result = json.loads(result_path.read_text(encoding="utf-8"))
                    result[field] = wrong_value
                    result_path.write_text(
                        json.dumps(result),
                        encoding="utf-8",
                    )
                    with self.assertRaisesRegex(
                        ValueError,
                        "terminal task result disagrees with summary",
                    ):
                        self.merge(
                            roots,
                            temp / "merged",
                            allow_subset=True,
                        )

    def test_terminal_result_score_must_match_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp = Path(tmp)
            roots = [
                self.write_shard(
                    temp / "shard-0",
                    shard_index=0,
                    selected={"001-test": ("completed", 1.0)},
                ),
                self.write_shard(
                    temp / "shard-1",
                    shard_index=1,
                    selected={"002-test": ("completed", 0.5)},
                ),
            ]
            result_path = roots[0] / "tasks" / "001-test" / "result.json"
            result = json.loads(result_path.read_text(encoding="utf-8"))
            result["outcome_score"] = 0.25
            result_path.write_text(json.dumps(result), encoding="utf-8")

            with self.assertRaisesRegex(
                ValueError,
                "terminal task result disagrees with summary",
            ):
                self.merge(
                    roots,
                    temp / "merged",
                    allow_subset=True,
                )

    def test_terminal_result_score_accepts_small_float_rounding_difference(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp = Path(tmp)
            roots = [
                self.write_shard(
                    temp / "shard-0",
                    shard_index=0,
                    selected={"001-test": ("completed", 0.3)},
                ),
                self.write_shard(
                    temp / "shard-1",
                    shard_index=1,
                    selected={"002-test": ("completed", 0.5)},
                ),
            ]
            result_path = roots[0] / "tasks" / "001-test" / "result.json"
            result = json.loads(result_path.read_text(encoding="utf-8"))
            result["outcome_score"] = 0.30000000000000004
            result_path.write_text(json.dumps(result), encoding="utf-8")

            payload = self.merge(
                roots,
                temp / "merged",
                allow_subset=True,
            )

        self.assertEqual(payload["selected_count"], 2)

    def test_terminal_error_allows_null_score_on_both_records(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp = Path(tmp)
            roots = [
                self.write_shard(
                    temp / "shard-0",
                    shard_index=0,
                    selected={"001-test": ("timeout", None)},
                ),
                self.write_shard(
                    temp / "shard-1",
                    shard_index=1,
                    selected={"002-test": ("completed", 0.5)},
                ),
            ]

            payload = self.merge(
                roots,
                temp / "merged",
                allow_subset=True,
            )

        self.assertEqual(payload["counts"]["timeout"], 1)

    def test_completed_terminal_result_rejects_null_score(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp = Path(tmp)
            roots = [
                self.write_shard(
                    temp / "shard-0",
                    shard_index=0,
                    selected={"001-test": ("completed", None)},
                ),
                self.write_shard(
                    temp / "shard-1",
                    shard_index=1,
                    selected={"002-test": ("completed", 0.5)},
                ),
            ]

            with self.assertRaisesRegex(
                ValueError,
                "terminal task result disagrees with summary",
            ):
                self.merge(
                    roots,
                    temp / "merged",
                    allow_subset=True,
                )

    def test_completed_openclaw_result_requires_passing_trace_integrity(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp = Path(tmp)
            roots = [
                self.write_shard(
                    temp / "shard-0",
                    shard_index=0,
                    selected={"001-test": ("completed", 1.0)},
                ),
                self.write_shard(
                    temp / "shard-1",
                    shard_index=1,
                    selected={"002-test": ("completed", 0.5)},
                ),
            ]
            result_path = roots[0] / "tasks" / "001-test" / "result.json"
            result = json.loads(result_path.read_text(encoding="utf-8"))
            result.update(
                {
                    "harness": "openclaw",
                    "trace_integrity": {
                        "status": "fail",
                        "problems": ["dangling tool call"],
                    },
                }
            )
            result_path.write_text(json.dumps(result), encoding="utf-8")

            with self.assertRaisesRegex(
                ValueError,
                "no passing trace integrity report",
            ):
                self.merge(
                    roots,
                    temp / "merged",
                    allow_subset=True,
                )

    def test_run_plan_matches_shards_by_index(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp = Path(tmp)
            roots = [
                self.write_shard(
                    temp / "shard-0",
                    shard_index=0,
                    selected={
                        "001-test": ("completed", 1.0),
                        "003-test": ("completed", 0.0),
                    },
                    base_url="http://replica-a/v1",
                    data_parallel_rank=0,
                    workers=4,
                ),
                self.write_shard(
                    temp / "shard-1",
                    shard_index=1,
                    selected={"002-test": ("completed", 0.5)},
                    base_url="http://replica-b/v1",
                    data_parallel_rank=1,
                    workers=4,
                ),
            ]
            run_plan = {
                "shard_count": 2,
                "controller_runtime_id": self.runtime_identity()[1],
                "shards": [
                    {
                        "shard_index": 1,
                        "base_url": "http://replica-b/v1",
                        "data_parallel_rank": 1,
                        "workers": 4,
                        "model_service_id": self.service_id,
                    },
                    {
                        "shard_index": 0,
                        "base_url": "http://replica-a/v1",
                        "data_parallel_rank": 0,
                        "workers": 4,
                        "model_service_id": self.service_id,
                    },
                ],
            }
            payload = self.merge(
                list(reversed(roots)),
                temp / "merged",
                run_plan=run_plan,
            )

        self.assertEqual(payload["selected_count"], 3)
        self.assertEqual(payload["workers"], 8)

    def test_run_plan_rejects_route_or_identity_mismatch(self) -> None:
        mismatches = (
            ("base_url", "http://wrong/v1"),
            ("data_parallel_rank", 0),
            ("workers", 8),
            ("model_service_id", "sha256:" + "b" * 64),
        )
        for field, wrong_value in mismatches:
            with self.subTest(field=field):
                with tempfile.TemporaryDirectory() as tmp:
                    temp = Path(tmp)
                    roots = [
                        self.write_shard(
                            temp / "shard-0",
                            shard_index=0,
                            selected={
                                "001-test": ("completed", 1.0),
                                "003-test": ("completed", 0.0),
                            },
                            base_url="http://replica-a/v1",
                            data_parallel_rank=0,
                            workers=4,
                        ),
                        self.write_shard(
                            temp / "shard-1",
                            shard_index=1,
                            selected={"002-test": ("completed", 0.5)},
                            base_url="http://replica-b/v1",
                            data_parallel_rank=1,
                            workers=4,
                        ),
                    ]
                    run_plan = {
                        "shards": [
                            {
                                "shard_index": 0,
                                "base_url": "http://replica-a/v1",
                                "data_parallel_rank": 0,
                                "workers": 4,
                                "model_service_id": self.service_id,
                            },
                            {
                                "shard_index": 1,
                                "base_url": "http://replica-b/v1",
                                "data_parallel_rank": 1,
                                "workers": 4,
                                "model_service_id": self.service_id,
                            },
                        ]
                    }
                    run_plan["shards"][1][field] = wrong_value
                    with self.assertRaisesRegex(
                        ValueError,
                        "run plan mismatch for shard 1",
                    ):
                        self.merge(
                            roots,
                            temp / "merged",
                            run_plan=run_plan,
                        )

    def test_run_plan_checks_frozen_top_level_execution_identity(self) -> None:
        mismatches = {
            "suite_definition_sha256": "wrong-suite",
            "suite_snapshot_sha256": "wrong-snapshot",
            "controller_definition_sha256": "wrong-controller",
            "controller_runtime_id": "sha256:" + "b" * 64,
            "model_service_id": "sha256:" + "b" * 64,
            "workers_total": 99,
            "runtime_images": {"grader": "sha256:wrong"},
        }
        for field, wrong_value in mismatches.items():
            with self.subTest(field=field), tempfile.TemporaryDirectory() as tmp:
                temp = Path(tmp)
                roots = [
                    self.write_shard(
                        temp / "shard-0",
                        shard_index=0,
                        selected={
                            "001-test": ("completed", 1.0),
                            "003-test": ("completed", 0.0),
                        },
                    ),
                    self.write_shard(
                        temp / "shard-1",
                        shard_index=1,
                        selected={"002-test": ("completed", 0.5)},
                    ),
                ]
                run_plan = {
                    field: wrong_value,
                    "shards": [
                        {
                            "shard_index": index,
                            "base_url": "http://model/v1",
                            "data_parallel_rank": index,
                            "workers": 1,
                            "model_service_id": self.service_id,
                        }
                        for index in range(2)
                    ],
                }
                with self.assertRaisesRegex(
                    ValueError,
                    "run plan execution identity mismatch",
                ):
                    self.merge(
                        roots,
                        temp / "merged",
                        run_plan=run_plan,
                    )

    def test_run_plan_requires_complete_unique_shard_set(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp = Path(tmp)
            roots = [
                self.write_shard(
                    temp / "shard-0",
                    shard_index=0,
                    selected={
                        "001-test": ("completed", 1.0),
                        "003-test": ("completed", 0.0),
                    },
                ),
                self.write_shard(
                    temp / "shard-1",
                    shard_index=1,
                    selected={"002-test": ("completed", 0.5)},
                ),
            ]
            incomplete_plan = {
                "shards": [
                    {
                        "shard_index": 0,
                        "base_url": "http://model/v1",
                        "data_parallel_rank": 0,
                        "workers": 1,
                        "model_service_id": self.service_id,
                    }
                ]
            }
            with self.assertRaisesRegex(
                ValueError,
                "run plan shard set is not complete and unique",
            ):
                self.merge(
                    roots,
                    temp / "merged",
                    run_plan=incomplete_plan,
                )

    def test_run_plan_rejects_duplicate_shard_index(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp = Path(tmp)
            roots = [
                self.write_shard(
                    temp / "shard-0",
                    shard_index=0,
                    selected={
                        "001-test": ("completed", 1.0),
                        "003-test": ("completed", 0.0),
                    },
                ),
                self.write_shard(
                    temp / "shard-1",
                    shard_index=1,
                    selected={"002-test": ("completed", 0.5)},
                ),
            ]
            duplicate_plan = {
                "shards": [
                    {
                        "shard_index": 0,
                        "base_url": "http://model/v1",
                        "data_parallel_rank": 0,
                        "workers": 1,
                        "model_service_id": self.service_id,
                    },
                    {
                        "shard_index": 0,
                        "base_url": "http://model/v1",
                        "data_parallel_rank": 1,
                        "workers": 1,
                        "model_service_id": self.service_id,
                    },
                ]
            }
            with self.assertRaisesRegex(
                ValueError,
                "duplicate shard_index",
            ):
                self.merge(
                    roots,
                    temp / "merged",
                    run_plan=duplicate_plan,
                )

    def test_explicit_subset_merge_uses_selected_union(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp = Path(tmp)
            roots = [
                self.write_shard(
                    temp / "shard-0",
                    shard_index=0,
                    selected={"001-test": ("completed", 1.0)},
                ),
                self.write_shard(
                    temp / "shard-1",
                    shard_index=1,
                    selected={"002-test": ("completed", 0.5)},
                ),
            ]
            payload = self.merge(
                roots,
                temp / "merged",
                allow_subset=True,
            )

        self.assertEqual(payload["selected_count"], 2)
        self.assertEqual(payload["completed_count"], 2)
        self.assertEqual(payload["progress"], 1.0)
        self.assertEqual(payload["headline_oracle_score"], 0.75)
        self.assertEqual(payload["mean_oracle_completed"], 0.75)
        self.assertEqual(payload["counts"]["not_selected"], 1)
        rows = {row["task_id"]: row for row in payload["tasks"]}
        self.assertEqual(rows["003-test"]["status"], "not_selected")

    def test_default_merge_rejects_missing_formal_task(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp = Path(tmp)
            roots = [
                self.write_shard(
                    temp / "shard-0",
                    shard_index=0,
                    selected={"001-test": ("completed", 1.0)},
                ),
                self.write_shard(
                    temp / "shard-1",
                    shard_index=1,
                    selected={"002-test": ("completed", 0.5)},
                ),
            ]
            with self.assertRaisesRegex(
                ValueError,
                "incomplete full-suite shards",
            ):
                self.merge(roots, temp / "merged")

    def test_subset_merge_rejects_task_selected_by_two_shards(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp = Path(tmp)
            roots = [
                self.write_shard(
                    temp / "shard-0",
                    shard_index=0,
                    selected={"001-test": ("completed", 1.0)},
                ),
                self.write_shard(
                    temp / "shard-1",
                    shard_index=1,
                    selected={"001-test": ("completed", 0.5)},
                ),
            ]
            with self.assertRaisesRegex(
                ValueError,
                "task appears in multiple shards",
            ):
                self.merge(
                    roots,
                    temp / "merged",
                    allow_subset=True,
                )

    def test_subset_merge_rejects_nonterminal_selected_task(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp = Path(tmp)
            roots = [
                self.write_shard(
                    temp / "shard-0",
                    shard_index=0,
                    selected={"001-test": ("running", None)},
                ),
                self.write_shard(
                    temp / "shard-1",
                    shard_index=1,
                    selected={"002-test": ("completed", 0.5)},
                ),
            ]
            with self.assertRaisesRegex(ValueError, "nonterminal"):
                self.merge(
                    roots,
                    temp / "merged",
                    allow_subset=True,
                )

    def test_subset_infrastructure_error_suppresses_headline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp = Path(tmp)
            roots = [
                self.write_shard(
                    temp / "shard-0",
                    shard_index=0,
                    selected={"001-test": ("infrastructure_error", None)},
                ),
                self.write_shard(
                    temp / "shard-1",
                    shard_index=1,
                    selected={"002-test": ("completed", 0.8)},
                ),
            ]
            payload = self.merge(
                roots,
                temp / "merged",
                allow_subset=True,
            )

        self.assertEqual(payload["selected_count"], 2)
        self.assertEqual(payload["completed_count"], 2)
        self.assertEqual(payload["progress"], 1.0)
        self.assertEqual(payload["counts"]["infrastructure_error"], 1)
        self.assertEqual(payload["mean_oracle_completed"], 0.8)
        self.assertIsNone(payload["headline_oracle_score"])

    def test_merge_recomputes_safety_metrics_and_excludes_infrastructure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp = Path(tmp)
            roots = [
                self.write_shard(
                    temp / "shard-0",
                    shard_index=0,
                    selected={
                        "001-test": ("completed", 0.0),
                        "003-test": ("infrastructure_error", None),
                    },
                ),
                self.write_shard(
                    temp / "shard-1",
                    shard_index=1,
                    selected={"002-test": ("completed", 0.49)},
                ),
            ]
            for root, metrics in zip(
                roots,
                (
                    {
                        "001-test": (True, 1, 0),
                        "003-test": (True, 7, 7),
                    },
                    {"002-test": (False, 0, 2)},
                ),
            ):
                path = root / "summary.json"
                summary = json.loads(path.read_text(encoding="utf-8"))
                for row in summary["tasks"]:
                    if row["task_id"] in metrics:
                        failed, gates, critical = metrics[row["task_id"]]
                        row.update(
                            safety_gate_failed=failed,
                            failed_gate_count=gates,
                            failed_core_count=critical,
                        )
                path.write_text(json.dumps(summary), encoding="utf-8")

            payload = self.merge(
                roots,
                temp / "merged",
                allow_subset=True,
            )

        self.assertEqual(payload["safety_gate_evaluated_count"], 2)
        self.assertEqual(payload["safety_gate_failed_count"], 1)
        self.assertEqual(payload["safety_gate_failure_rate"], 0.5)
        self.assertEqual(payload["failed_gate_total"], 1)
        self.assertEqual(payload["failed_core_total"], 2)


if __name__ == "__main__":
    unittest.main()
