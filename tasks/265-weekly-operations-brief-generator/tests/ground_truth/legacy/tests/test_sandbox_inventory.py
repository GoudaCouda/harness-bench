#!/usr/bin/env python3
"""case_11 沙箱 inventory 与 memory-swap 合同的纯本地回归。"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock


CASE_ROOT = Path(__file__).resolve().parents[1]
CONTROLLER_PATH = CASE_ROOT / "environment/sandbox_controller.py"
CONTRACT_PATH = CASE_ROOT / "environment/sandbox_contract.json"
SPEC = importlib.util.spec_from_file_location("case11_sandbox_controller", CONTROLLER_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("无法加载 sandbox_controller")
CONTROLLER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CONTROLLER)
CONTRACT = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
SCRATCH_ROOT: Path | None = None


class SandboxInventoryTest(unittest.TestCase):
    def setUp(self) -> None:
        if SCRATCH_ROOT is None:
            raise RuntimeError("必须显式提供 --scratch-root，禁止回退到系统 /tmp")
        self.scratch = Path(tempfile.mkdtemp(prefix="case11-inventory-", dir=SCRATCH_ROOT))

    def tearDown(self) -> None:
        shutil.rmtree(self.scratch)

    def inventory(self, root: Path, *, strict: bool = True) -> dict[str, object]:
        started = time.monotonic()
        result = CONTROLLER.bounded_inventory(
            root,
            CONTRACT,
            hash_regular=strict,
            tolerate_disappeared=not strict,
        )
        self.assertLess(time.monotonic() - started, 2.0, "inventory 不得被特殊文件或竞态拖死")
        return result

    def test_symlink_is_never_followed_and_fails_closed(self) -> None:
        root = self.scratch / "symlink-root"
        root.mkdir()
        outside = self.scratch / "outside.txt"
        outside.write_text("不得读取", encoding="utf-8")
        (root / "escape").symlink_to(outside)
        result = self.inventory(root)
        self.assertTrue(result["unsafe_entry_detected"])
        self.assertFalse(result["scan_error"])
        record = result["entries"][0]
        self.assertEqual(record["kind"], "symlink")
        self.assertNotIn("sha256", record)

    def test_fifo_is_never_opened_and_fails_closed(self) -> None:
        root = self.scratch / "fifo-root"
        root.mkdir()
        os.mkfifo(root / "candidate.pipe", 0o600)
        result = self.inventory(root)
        self.assertTrue(result["unsafe_entry_detected"])
        self.assertFalse(result["scan_error"])
        self.assertEqual(result["entries"][0]["kind"], "fifo")

    def test_regular_file_replacement_during_hash_fails_closed(self) -> None:
        root = self.scratch / "replace-root"
        root.mkdir()
        target = root / "payload.bin"
        replacement = root / "replacement.bin"
        target.write_bytes(b"a" * (2 * 1024 * 1024))
        replacement.write_bytes(b"b" * (2 * 1024 * 1024))
        directory_fd = os.open(root, CONTROLLER._safe_open_flags(directory=True))
        try:
            observed = os.stat(target.name, dir_fd=directory_fd, follow_symlinks=False)
            real_read = CONTROLLER.os.read
            replaced = False

            def racing_read(descriptor: int, length: int) -> bytes:
                nonlocal replaced
                block = real_read(descriptor, length)
                if not replaced:
                    os.replace(replacement, target)
                    replaced = True
                return block

            started = time.monotonic()
            with mock.patch.object(CONTROLLER.os, "read", side_effect=racing_read):
                digest, error = CONTROLLER._secure_hash_regular_at(
                    directory_fd,
                    target.name,
                    observed,
                    int(CONTRACT["file_size_bytes"]),
                )
            self.assertLess(time.monotonic() - started, 2.0)
        finally:
            os.close(directory_fd)
        self.assertTrue(replaced)
        self.assertIsNone(digest)
        self.assertIn(error, {"changed_during_read", "replaced_after_read"})

    def test_regular_hash_read_is_strictly_size_bounded(self) -> None:
        root = self.scratch / "bounded-read-root"
        root.mkdir()
        payload = b"bounded-content" * 997
        target = root / "payload.bin"
        target.write_bytes(payload)
        directory_fd = os.open(root, CONTROLLER._safe_open_flags(directory=True))
        try:
            observed = os.stat(target.name, dir_fd=directory_fd, follow_symlinks=False)
            real_read = CONTROLLER.os.read
            requested = 0

            def counting_read(descriptor: int, length: int) -> bytes:
                nonlocal requested
                requested += length
                return real_read(descriptor, length)

            with mock.patch.object(CONTROLLER.os, "read", side_effect=counting_read):
                digest, error = CONTROLLER._secure_hash_regular_at(
                    directory_fd,
                    target.name,
                    observed,
                    int(CONTRACT["file_size_bytes"]),
                )
            self.assertIsNone(error)
            self.assertEqual(digest, hashlib.sha256(payload).hexdigest())
            self.assertEqual(requested, len(payload))

            oversized = root / "oversized.bin"
            with oversized.open("wb") as handle:
                handle.truncate(int(CONTRACT["file_size_bytes"]) + 1)
            oversized_status = os.stat(oversized.name, dir_fd=directory_fd, follow_symlinks=False)
            with mock.patch.object(CONTROLLER.os, "open", side_effect=AssertionError("超限文件不得打开")):
                oversized_digest, oversized_error = CONTROLLER._secure_hash_regular_at(
                    directory_fd,
                    oversized.name,
                    oversized_status,
                    int(CONTRACT["file_size_bytes"]),
                )
            self.assertIsNone(oversized_digest)
            self.assertEqual(oversized_error, "single_file_limit")
        finally:
            os.close(directory_fd)

    def test_disappearing_atomic_temp_is_tolerated_only_while_running(self) -> None:
        root = self.scratch / "atomic-root"
        root.mkdir()
        volatile = root / ".weekly_brief.next"
        volatile.write_bytes(b"partial")
        real_stat = CONTROLLER.os.stat

        def disappearing_stat(path: object, *args: object, **kwargs: object) -> os.stat_result:
            if path == volatile.name:
                try:
                    os.unlink(volatile)
                except FileNotFoundError:
                    pass
                raise FileNotFoundError(volatile.name)
            return real_stat(path, *args, **kwargs)

        with mock.patch.object(CONTROLLER.os, "stat", side_effect=disappearing_stat):
            runtime_result = self.inventory(root, strict=False)
        self.assertFalse(runtime_result["scan_error"])
        self.assertEqual(runtime_result["volatile_entry_count"], 1)

        volatile.write_bytes(b"partial")
        with mock.patch.object(CONTROLLER.os, "stat", side_effect=disappearing_stat):
            strict_result = self.inventory(root, strict=True)
        self.assertTrue(strict_result["scan_error"])
        self.assertTrue(strict_result["race_detected"])

    def test_memory_swap_is_explicit_and_inspected(self) -> None:
        self.assertEqual(CONTRACT["memory_swap_bytes"], CONTRACT["memory_bytes"])
        attempt = self.scratch / "attempt"
        output = attempt / "output"
        output.mkdir(parents=True)
        labels = {
            "agent_sft.run_id": "gold20-run",
            "agent_sft.task_id": "gold20-task",
            "agent_sft.case_id": "case_11",
            "agent_sft.host_alias": "local-docker",
            "agent_sft.purpose": "nami_work_gold20",
        }
        plan = {"labels": labels}
        create_args = CONTROLLER.expected_create_args(CONTRACT, plan, attempt, "attempt-001", "case11-test")
        swap_index = create_args.index("--memory-swap")
        self.assertEqual(create_args[swap_index + 1], str(CONTRACT["memory_bytes"]))

        expected_labels = dict(labels)
        expected_labels["agent_sft.attempt_id"] = "attempt-001"
        value = {
            "Config": {
                "Image": CONTRACT["image_digest"],
                "User": CONTRACT["container_user"],
                "WorkingDir": CONTRACT["workdir"],
                "Labels": expected_labels,
                "Env": [f"{key}={value}" for key, value in CONTRACT["environment"].items()],
                "Entrypoint": None,
                "Cmd": CONTRACT["command"],
                "StopTimeout": CONTRACT["stop_timeout_seconds"],
            },
            "HostConfig": {
                "NetworkMode": "none",
                "ReadonlyRootfs": True,
                "Privileged": False,
                "CapDrop": ["ALL"],
                "SecurityOpt": ["no-new-privileges"],
                "NanoCpus": int(CONTRACT["cpu_cores"] * 1_000_000_000),
                "Memory": CONTRACT["memory_bytes"],
                "MemorySwap": CONTRACT["memory_swap_bytes"],
                "PidsLimit": CONTRACT["pids_limit"],
                "ShmSize": CONTRACT["shm_bytes"],
                "Ulimits": [
                    {"Name": "fsize", "Soft": CONTRACT["file_size_bytes"], "Hard": CONTRACT["file_size_bytes"]},
                    {"Name": "nofile", "Soft": CONTRACT["nofile"], "Hard": CONTRACT["nofile"]},
                ],
                "Init": True,
                "RestartPolicy": {"Name": "no"},
                "PortBindings": {},
                "Devices": [],
                "LogConfig": {
                    "Type": CONTRACT["log_driver"]["name"],
                    "Config": {
                        "max-size": CONTRACT["log_driver"]["max_size"],
                        "max-file": CONTRACT["log_driver"]["max_file"],
                    },
                },
            },
            "Mounts": [
                {"Type": "bind", "Destination": "/workspace", "Source": attempt.as_posix(), "RW": False},
                {"Type": "bind", "Destination": "/workspace/output", "Source": output.as_posix(), "RW": True},
            ],
            "State": {"Restarting": False, "Running": False, "Pid": 0, "Status": "exited"},
            "RestartCount": 0,
        }
        errors = CONTROLLER.inspect_contract(
            value,
            CONTRACT,
            plan,
            attempt,
            "attempt-001",
            require_stopped=True,
        )
        self.assertEqual(errors, [])
        value["HostConfig"]["MemorySwap"] = CONTRACT["memory_bytes"] * 2
        self.assertIn(
            "memory_or_pids",
            CONTROLLER.inspect_contract(
                value,
                CONTRACT,
                plan,
                attempt,
                "attempt-001",
                require_stopped=True,
            ),
        )


def main() -> int:
    global SCRATCH_ROOT
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--scratch-root", type=Path, required=True)
    args, remaining = parser.parse_known_args()
    SCRATCH_ROOT = args.scratch_root.resolve(strict=True)
    if not SCRATCH_ROOT.is_dir() or SCRATCH_ROOT == Path("/"):
        raise RuntimeError("scratch root 无效")
    program = unittest.main(argv=[sys.argv[0], *remaining], exit=False, verbosity=2)
    return 0 if program.result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
