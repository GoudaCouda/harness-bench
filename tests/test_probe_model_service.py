from __future__ import annotations

import collections
import hashlib
import json
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Iterator


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import probe_model_service as probe  # noqa: E402


def frozen_manifest(endpoint: str) -> dict[str, Any]:
    artifact = {
        "pod_path": "/models/test",
        "sha256": "0" * 64,
        "size_bytes": 1,
    }
    identity = {
        "schema_version": 2,
        "deployment_source": {
            "provider": "test",
            "job_id": "job-1",
        },
        "deployment_artifacts": {
            "model_config": dict(artifact),
            "model_safetensors_index": dict(artifact),
            "chat_template": dict(artifact),
            "inner_script": dict(artifact),
        },
        "runtime_observation": {
            "expected_vllm_version": "0.24.0",
            "observed_versions": {
                "torch": "2.11.0+cu129",
                "transformers": "5.12.1",
                "vllm": "0.24.0",
            },
            "replicas": [
                {
                    "hostname": "replica-a",
                    "log_file": "server.replica-a.log",
                    "versions": {
                        "torch": "2.11.0+cu129",
                        "transformers": "5.12.1",
                        "vllm": "0.24.0",
                    },
                }
            ],
        },
        "semantic_config": {
            "served_model_name": "gemma-4-31b-it",
            "dp_size": 2,
            "replica_count": 1,
            "enable_thinking": True,
        },
        "replicas": [
            {
                "endpoint": endpoint,
                "hostname": "replica-a",
            }
        ],
    }
    digest = hashlib.sha256(probe._canonical_bytes(identity)).hexdigest()
    return {**identity, "model_service_id": f"sha256:{digest}"}


class ServerState:
    def __init__(self) -> None:
        self.version = "0.24.0"
        self.model = "gemma-4-31b-it"
        self.protocol_fault: str | None = None
        self.requests: list[dict[str, Any]] = []
        self.counter = 0
        self.lock = threading.Lock()


class ProbeHandler(BaseHTTPRequestHandler):
    server: ThreadingHTTPServer

    @property
    def state(self) -> ServerState:
        return self.server.state  # type: ignore[attr-defined]

    def log_message(self, _format: str, *args: object) -> None:
        del args

    def _send_json(self, payload: dict[str, Any]) -> None:
        encoded = json.dumps(payload, separators=(",", ":")).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Length", "0")
            self.end_headers()
        elif self.path == "/version":
            self._send_json({"version": self.state.version})
        elif self.path == "/v1/models":
            self._send_json(
                {
                    "object": "list",
                    "data": [{"id": self.state.model, "object": "model"}],
                }
            )
        else:
            self.send_error(404)

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/v1/chat/completions":
            self.send_error(404)
            return
        length = int(self.headers["Content-Length"])
        payload = json.loads(self.rfile.read(length))
        rank = self.headers.get("X-data-parallel-rank")
        with self.state.lock:
            self.state.requests.append(
                {
                    "rank": rank,
                    "payload": payload,
                }
            )
            self.state.counter += 1
            counter = self.state.counter

        messages = payload["messages"]
        if messages[-1]["role"] == "tool":
            tool_message = messages[-1]
            assistant_message = messages[-2]
            if tool_message["tool_call_id"] != assistant_message["tool_calls"][0]["id"]:
                self.send_error(400)
                return
            tool_result = json.loads(tool_message["content"])
            content = f"PROBE_COMPLETE:{tool_result['nonce']}"
            self._send_json(
                {
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": content,
                                "tool_calls": None,
                            }
                        }
                    ]
                }
            )
            return

        arguments = json.loads(messages[-1]["content"].split("object: ", 1)[1])
        call_id = f"call-{rank}-{counter}"
        name = probe.TOOL_NAME
        arguments_raw = json.dumps(arguments, sort_keys=True, separators=(",", ":"))
        content = None
        fault = self.state.protocol_fault
        if fault == "wrong_name":
            name = "wrong_tool"
        elif fault == "malformed_args":
            arguments_raw = "{not-json"
        elif fault == "wrong_args":
            arguments_raw = json.dumps({**arguments, "rank": 99})
        elif fault == "bad_id":
            call_id = "id with spaces"
        elif fault == "raw_marker":
            content = "<tool_call>"
        self._send_json(
            {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": content,
                            "tool_calls": [
                                {
                                    "id": call_id,
                                    "type": "function",
                                    "function": {
                                        "name": name,
                                        "arguments": arguments_raw,
                                    },
                                }
                            ],
                        }
                    }
                ]
            }
        )


@contextmanager
def mock_vllm() -> Iterator[tuple[ServerState, str]]:
    state = ServerState()
    server = ThreadingHTTPServer(("127.0.0.1", 0), ProbeHandler)
    server.state = state  # type: ignore[attr-defined]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        yield state, f"http://{host}:{port}/v1"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


class ProbeModelServiceTests(unittest.TestCase):
    def test_one_shot_checks_each_rank_with_requested_concurrency(self) -> None:
        with mock_vllm() as (state, endpoint):
            report = probe.run_one_shot(
                frozen_manifest(endpoint),
                timeout=2,
                per_rank_concurrency=3,
            )

        self.assertEqual(report["status"], "pass")
        self.assertEqual(
            report["configuration"],
            {
                "endpoint_count": 1,
                "dp_size": 2,
                "per_rank_concurrency": 3,
                "request_timeout_seconds": 2,
                "protocol_probe_max_tokens": probe.PROTOCOL_PROBE_MAX_TOKENS,
                "enable_thinking": True,
            },
        )
        endpoint_report = report["endpoints"][0]
        self.assertEqual(endpoint_report["preflight"]["status"], "pass")
        self.assertEqual(len(endpoint_report["rank_probes"]), 6)
        self.assertTrue(
            all(row["status"] == "pass" for row in endpoint_report["rank_probes"])
        )
        rank_counts = collections.Counter(
            row["rank"]
            for row in state.requests
            if row["payload"]["messages"][-1]["role"] == "user"
        )
        self.assertEqual(rank_counts, {"0": 3, "1": 3})
        second_turns = [
            row
            for row in state.requests
            if row["payload"]["messages"][-1]["role"] == "tool"
        ]
        self.assertEqual(len(second_turns), 6)
        self.assertTrue(
            all(
                row["payload"]["stream"] is False
                and row["payload"]["tool_choice"] == "none"
                and row["payload"]["max_tokens"] == probe.PROTOCOL_PROBE_MAX_TOKENS
                for row in second_turns
            )
        )

    def test_preflight_requires_exact_version_and_served_model(self) -> None:
        for mutation, expected_error in (
            ({"version": "0.23.0"}, "version is not exactly"),
            ({"model": "different-model"}, "absent from /v1/models"),
        ):
            with self.subTest(mutation=mutation), mock_vllm() as (state, endpoint):
                for key, value in mutation.items():
                    setattr(state, key, value)
                report = probe.run_one_shot(
                    frozen_manifest(endpoint),
                    timeout=2,
                    per_rank_concurrency=1,
                )
                endpoint_report = report["endpoints"][0]
                self.assertEqual(report["status"], "fail")
                self.assertEqual(endpoint_report["rank_probes"], [])
                self.assertIn(
                    expected_error,
                    endpoint_report["preflight"]["error"],
                )

    def test_tool_protocol_failures_are_not_accepted(self) -> None:
        cases = {
            "wrong_name": "wrong tool name",
            "malformed_args": "invalid JSON",
            "wrong_args": "do not exactly match",
            "bad_id": "invalid tool-call id",
            "raw_marker": "raw Gemma protocol marker",
        }
        for fault, expected_error in cases.items():
            with self.subTest(fault=fault), mock_vllm() as (state, endpoint):
                state.protocol_fault = fault
                report = probe.run_one_shot(
                    frozen_manifest(endpoint),
                    timeout=2,
                    per_rank_concurrency=1,
                )
                errors = [row["error"] for row in report["endpoints"][0]["rank_probes"]]
                self.assertEqual(report["status"], "fail")
                self.assertEqual(len(errors), 2)
                self.assertTrue(all(expected_error in error for error in errors))

    def test_manifest_digest_shape_and_credential_checks_fail_closed(self) -> None:
        with mock_vllm() as (_state, endpoint), tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = frozen_manifest(endpoint)
            path = root / "frozen.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            self.assertEqual(probe.load_frozen_manifest(path), payload)

            payload["semantic_config"]["dp_size"] = 3
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(probe.ProbeError, "digest mismatch"):
                probe.load_frozen_manifest(path)

            credential_payload = frozen_manifest(
                endpoint.replace("http://", "http://user:secret@")
            )
            path.write_text(json.dumps(credential_payload), encoding="utf-8")
            with self.assertRaisesRegex(probe.ProbeError, "credentials"):
                probe.load_frozen_manifest(path)

    def test_one_shot_output_is_atomic_and_monitor_is_append_only(self) -> None:
        with mock_vllm() as (state, endpoint), tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = frozen_manifest(endpoint)
            report_path = root / "report.json"
            report = probe.run_one_shot(
                manifest,
                timeout=2,
                per_rank_concurrency=1,
            )
            probe.atomic_write_json(report_path, report)
            parsed = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(parsed["status"], "pass")

            monitor_path = root / "monitor.jsonl"
            for _ in range(2):
                polls = probe.monitor_service(
                    manifest,
                    output=monitor_path,
                    timeout=2,
                    interval=10,
                    max_polls=1,
                )
                self.assertEqual(polls, 1)
            state.version = "0.23.0"
            probe.monitor_service(
                manifest,
                output=monitor_path,
                timeout=2,
                interval=10,
                max_polls=1,
            )
            rows = [
                json.loads(line)
                for line in monitor_path.read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual(len(rows), 3)
            self.assertEqual([row["status"] for row in rows], ["pass", "pass", "fail"])
            self.assertEqual(
                set(rows[-1]),
                {
                    "schema_version",
                    "mode",
                    "model_service_id",
                    "poll_index",
                    "epoch",
                    "endpoint",
                    "hostname",
                    "status",
                    "latency_ms",
                    "error",
                },
            )

    def test_monitor_sigterm_exits_cleanly_without_truncating(self) -> None:
        with mock_vllm() as (_state, endpoint), tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_path = root / "frozen.json"
            manifest_path.write_text(
                json.dumps(frozen_manifest(endpoint)),
                encoding="utf-8",
            )
            output = root / "monitor.jsonl"
            process = subprocess.Popen(
                [
                    sys.executable,
                    str(TOOLS / "probe_model_service.py"),
                    "--manifest",
                    str(manifest_path),
                    "--timeout",
                    "2",
                    "monitor",
                    "--output",
                    str(output),
                    "--interval",
                    "10",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                if output.exists() and output.stat().st_size:
                    break
                time.sleep(0.05)
            else:
                process.kill()
                self.fail("monitor did not append its first poll")
            before = output.read_bytes()
            process.send_signal(signal.SIGTERM)
            stdout, stderr = process.communicate(timeout=3)
            self.assertEqual((process.returncode, stdout, stderr), (0, "", ""))
            self.assertEqual(output.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
