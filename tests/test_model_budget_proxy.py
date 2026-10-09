from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from model_budget_proxy import (  # noqa: E402
    ModelBudgetProxy,
    is_downstream_disconnect,
)


class ModelBudgetProxyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.received: list[tuple[str, dict[str, object]]] = []
        self.received_headers: list[dict[str, str]] = []
        received = self.received
        received_headers = self.received_headers

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, _format: str, *_args: object) -> None:
                return

            def do_POST(self) -> None:  # noqa: N802
                length = int(self.headers.get("Content-Length") or 0)
                payload = json.loads(self.rfile.read(length))
                received.append((self.path, payload))
                received_headers.append(
                    {name.casefold(): value for name, value in self.headers.items()}
                )
                if payload.get("stream") is True:
                    response = (
                        'data: {"choices":[{"delta":{"content":"ok"}}]}\n\n'
                        'data: {"choices":[],"usage":{"prompt_tokens":11,'
                        '"completion_tokens":3,"total_tokens":14}}\n\n'
                        "data: [DONE]\n\n"
                    ).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.send_header("Content-Length", str(len(response)))
                    self.end_headers()
                    self.wfile.write(response)
                    return
                response = json.dumps({"ok": True}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(response)))
                self.end_headers()
                self.wfile.write(response)

        self.upstream = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.upstream.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self) -> None:
        self.upstream.shutdown()
        self.upstream.server_close()
        self.thread.join(timeout=5)

    def _proxy_url(self, proxy: ModelBudgetProxy) -> str:
        container_url = proxy.start()
        return container_url.replace("host.docker.internal", "127.0.0.1")

    @staticmethod
    def _post(url: str, payload: dict[str, object]) -> tuple[int, dict[str, object]]:
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            response = urllib.request.urlopen(request, timeout=5)
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read())
        with response:
            return response.status, json.loads(response.read())

    def test_rewrites_sampling_parameters_and_caps_output(self) -> None:
        upstream_url = f"http://127.0.0.1:{self.upstream.server_port}/v1"
        proxy = ModelBudgetProxy(
            upstream_url,
            max_agent_turns=150,
            temperature=1.0,
            max_output_tokens=32768,
        )
        proxy_url = self._proxy_url(proxy)
        try:
            status, _ = self._post(
                f"{proxy_url}/chat/completions",
                {"temperature": 0.2, "max_tokens": 99999},
            )
            self.assertEqual(status, 200)
            status, _ = self._post(
                f"{proxy_url}/responses",
                {"temperature": 0.0},
            )
            self.assertEqual(status, 200)
        finally:
            proxy.close()

        self.assertEqual(proxy.model_requests, 2)
        self.assertEqual(self.received[0][0], "/v1/chat/completions")
        self.assertEqual(self.received[1][0], "/v1/responses")
        self.assertEqual(self.received[0][1]["temperature"], 1.0)
        self.assertEqual(self.received[0][1]["max_tokens"], 32768)
        self.assertEqual(self.received[0][1]["reasoning_effort"], "high")
        self.assertEqual(self.received[1][1]["temperature"], 1.0)
        self.assertEqual(self.received[1][1]["max_output_tokens"], 32768)
        self.assertEqual(
            self.received[1][1]["reasoning"],
            {"effort": "high"},
        )
        self.assertIn(
            "reasoning.encrypted_content",
            self.received[1][1]["include"],
        )

    def test_maps_local_thinking_and_anthropic_adaptive_controls(self) -> None:
        upstream_url = f"http://127.0.0.1:{self.upstream.server_port}/v1"
        proxy = ModelBudgetProxy(
            upstream_url,
            max_agent_turns=2,
            temperature=1.0,
            max_output_tokens=32768,
            thinking="high",
        )
        proxy_url = self._proxy_url(proxy)
        try:
            self._post(
                f"{proxy_url}/chat/completions",
                {"model": "Qwen/Qwen3.8-27B"},
            )
            self._post(
                f"{proxy_url}/messages",
                {"model": "openai/gpt-5.6-luna"},
            )
        finally:
            proxy.close()

        self.assertEqual(
            self.received[0][1]["chat_template_kwargs"],
            {"enable_thinking": True},
        )
        self.assertNotIn("reasoning_effort", self.received[0][1])
        self.assertEqual(
            self.received[1][1]["thinking"],
            {"type": "adaptive"},
        )
        self.assertEqual(
            self.received[1][1]["output_config"],
            {"effort": "high"},
        )

    def test_rejects_requests_beyond_turn_budget(self) -> None:
        upstream_url = f"http://127.0.0.1:{self.upstream.server_port}/v1"
        proxy = ModelBudgetProxy(
            upstream_url,
            max_agent_turns=1,
            temperature=1.0,
            max_output_tokens=32768,
        )
        proxy_url = self._proxy_url(proxy)
        try:
            first_status, _ = self._post(f"{proxy_url}/messages", {})
            second_status, second_body = self._post(f"{proxy_url}/messages", {})
        finally:
            proxy.close()

        self.assertEqual(first_status, 200)
        self.assertEqual(second_status, 400)
        self.assertEqual(
            second_body["error"]["type"],
            "max_agent_turns_exceeded",
        )
        self.assertEqual(proxy.model_requests, 1)
        self.assertEqual(proxy.rejected_requests, 1)
        self.assertEqual(len(self.received), 1)

    def test_trusted_upstream_key_replaces_harness_placeholder(self) -> None:
        upstream_url = f"http://127.0.0.1:{self.upstream.server_port}/v1"
        proxy = ModelBudgetProxy(
            upstream_url,
            max_agent_turns=2,
            temperature=1.0,
            max_output_tokens=32768,
            upstream_api_key="trusted-test-key",
        )
        proxy_url = self._proxy_url(proxy)
        request = urllib.request.Request(
            f"{proxy_url}/messages",
            data=b"{}",
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer harness-placeholder",
                "X-Api-Key": "harness-placeholder",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                self.assertEqual(response.status, 200)
        finally:
            proxy.close()
        self.assertEqual(
            self.received_headers[-1]["authorization"], "Bearer trusted-test-key"
        )
        self.assertEqual(self.received_headers[-1]["x-api-key"], "trusted-test-key")

    def test_forces_identity_response_encoding_for_trace_parsing(self) -> None:
        upstream_url = f"http://127.0.0.1:{self.upstream.server_port}/v1"
        proxy = ModelBudgetProxy(
            upstream_url,
            max_agent_turns=2,
            temperature=1.0,
            max_output_tokens=32768,
        )
        proxy_url = self._proxy_url(proxy)
        request = urllib.request.Request(
            f"{proxy_url}/chat/completions",
            data=b"{}",
            headers={
                "Content-Type": "application/json",
                "Accept-Encoding": "gzip",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                self.assertEqual(response.status, 200)
        finally:
            proxy.close()
        self.assertEqual(
            self.received_headers[-1]["accept-encoding"],
            "identity",
        )

    def test_records_streaming_request_response_usage_and_roles(self) -> None:
        upstream_url = f"http://127.0.0.1:{self.upstream.server_port}/v1"
        with tempfile.TemporaryDirectory() as temporary:
            proxy = ModelBudgetProxy(
                upstream_url,
                max_agent_turns=10,
                temperature=1.0,
                max_output_tokens=32768,
                trace_dir=Path(temporary),
                session_id="session-1",
            )
            proxy_url = self._proxy_url(proxy)
            request = urllib.request.Request(
                f"{proxy_url}/chat/completions",
                data=json.dumps(
                    {
                        "stream": True,
                        "messages": [{"role": "user", "content": "hello"}],
                    }
                ).encode(),
                headers={"Content-Type": "application/json"},
            )
            try:
                with urllib.request.urlopen(request, timeout=5) as response:
                    body = response.read()
            finally:
                proxy.close()

            self.assertIn(b"[DONE]", body)
            self.assertEqual(
                self.received[-1][1]["stream_options"], {"include_usage": True}
            )
            summary = proxy.trace_summary
            self.assertIsNotNone(summary)
            assert summary is not None
            self.assertEqual(summary["token_coverage"], 1.0)
            self.assertEqual(summary["token_usage"]["total_tokens"], 14)
            self.assertEqual(summary["trajectory_length"]["user_events"], 1)
            self.assertEqual(summary["trajectory_length"]["assistant_events"], 1)
            records = Path(temporary, "transactions.jsonl").read_text().splitlines()
            self.assertEqual(len(records), 1)
            transaction = json.loads(records[0])
            self.assertEqual(transaction["outcome"], "upstream_response")
            self.assertEqual(
                transaction["normalized"]["request_events"][0]["type"], "user"
            )

    def test_close_waits_for_claimed_request_before_trace_summary(self) -> None:
        upstream_url = f"http://127.0.0.1:{self.upstream.server_port}/v1"
        with tempfile.TemporaryDirectory() as temporary:
            proxy = ModelBudgetProxy(
                upstream_url,
                max_agent_turns=10,
                temperature=1.0,
                max_output_tokens=32768,
                trace_dir=Path(temporary),
                session_id="close-race",
            )
            proxy_url = self._proxy_url(proxy)
            assert proxy._server is not None
            self.assertFalse(proxy._server.daemon_threads)
            self.assertTrue(proxy._server.block_on_close)

            entered_registration = threading.Event()
            release_registration = threading.Event()
            close_finished = threading.Event()
            original_register = proxy._register_connection

            def delayed_register(connection: object) -> None:
                entered_registration.set()
                self.assertTrue(release_registration.wait(timeout=5))
                original_register(connection)

            proxy._register_connection = delayed_register  # type: ignore[method-assign]
            response: list[tuple[int, dict[str, object]]] = []
            client = threading.Thread(
                target=lambda: response.append(
                    self._post(f"{proxy_url}/chat/completions", {})
                )
            )
            client.start()
            self.assertTrue(entered_registration.wait(timeout=5))
            closer = threading.Thread(
                target=lambda: (proxy.close(), close_finished.set())
            )
            closer.start()
            self.assertFalse(close_finished.wait(timeout=0.1))
            release_registration.set()
            client.join(timeout=5)
            closer.join(timeout=5)

            self.assertFalse(client.is_alive())
            self.assertFalse(closer.is_alive())
            self.assertEqual(response[0][0], 200)
            self.assertEqual(proxy.model_requests, 1)
            summary = proxy.trace_summary
            self.assertIsNotNone(summary)
            assert summary is not None
            self.assertEqual(summary["trajectory_length"]["provider_transactions"], 1)

    def test_downstream_broken_pipe_is_not_an_upstream_forward_error(self) -> None:
        self.assertTrue(
            is_downstream_disconnect(
                BrokenPipeError(32, "broken pipe"),
                response_started=True,
            )
        )
        self.assertFalse(
            is_downstream_disconnect(
                BrokenPipeError(32, "broken pipe"),
                response_started=False,
            )
        )
        self.assertFalse(
            is_downstream_disconnect(
                TimeoutError("upstream stalled"),
                response_started=True,
            )
        )


if __name__ == "__main__":
    unittest.main()
