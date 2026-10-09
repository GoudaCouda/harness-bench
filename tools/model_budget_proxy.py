"""Per-trial HTTP proxy that enforces provider-side harness budgets."""

from __future__ import annotations

import http.client
import json
import socket
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from provider_trace import ProviderTraceRecorder


MODEL_PATH_SUFFIXES = ("/chat/completions", "/responses", "/messages")
HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}


def _reasoning_effort(thinking: str) -> str:
    return "none" if thinking == "off" else thinking


def apply_reasoning_policy(
    payload: dict[str, object],
    *,
    path: str,
    thinking: str,
) -> None:
    """Map one benchmark reasoning setting onto the active wire protocol."""
    effort = _reasoning_effort(thinking)
    model = str(payload.get("model") or "").casefold()
    if path.endswith("/responses"):
        reasoning = payload.get("reasoning")
        if not isinstance(reasoning, dict):
            reasoning = {}
            payload["reasoning"] = reasoning
        reasoning["effort"] = effort
        include = payload.get("include")
        include = list(include) if isinstance(include, list) else []
        if effort != "none" and "reasoning.encrypted_content" not in include:
            include.append("reasoning.encrypted_content")
        payload["include"] = include
        return

    if path.endswith("/messages"):
        if effort == "none":
            payload["thinking"] = {"type": "disabled"}
            payload.pop("output_config", None)
        else:
            payload["thinking"] = {"type": "adaptive"}
            output_config = payload.get("output_config")
            if not isinstance(output_config, dict):
                output_config = {}
                payload["output_config"] = output_config
            output_config["effort"] = effort
        return

    if not path.endswith("/chat/completions"):
        return
    if any(name in model for name in ("qwen", "gemma")):
        template = payload.get("chat_template_kwargs")
        if not isinstance(template, dict):
            template = {}
            payload["chat_template_kwargs"] = template
        template["enable_thinking"] = effort != "none"
    else:
        payload["reasoning_effort"] = effort


def is_downstream_disconnect(
    exc: BaseException,
    *,
    response_started: bool,
) -> bool:
    """Distinguish a harness closing its response from an upstream failure."""
    # BrokenPipeError is raised by ``wfile`` after the harness has closed its
    # response socket. ConnectionResetError remains an upstream error here
    # because ``http.client`` can raise it while reading a started response.
    return response_started and isinstance(exc, BrokenPipeError)


class ModelBudgetProxy:
    """Forward one trial to vLLM while bounding requests and sampling knobs."""

    def __init__(
        self,
        upstream_base_url: str,
        *,
        max_agent_turns: int,
        temperature: float,
        max_output_tokens: int,
        timeout_sec: int = 7200,
        thinking: str = "high",
        trace_dir: Path | None = None,
        session_id: str | None = None,
        upstream_api_key: str | None = None,
    ) -> None:
        upstream = urlsplit(upstream_base_url.rstrip("/"))
        if upstream.scheme not in {"http", "https"} or not upstream.hostname:
            raise ValueError("model upstream must be one HTTP(S) base URL")
        if max_agent_turns < 1 or max_output_tokens < 1 or timeout_sec < 1:
            raise ValueError("model request budgets must be positive")
        self.upstream = upstream
        self.max_agent_turns = max_agent_turns
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens
        self.timeout_sec = timeout_sec
        self.thinking = thinking
        if upstream_api_key is not None:
            upstream_api_key = upstream_api_key.strip()
            if not upstream_api_key:
                raise ValueError("upstream API key must not be empty")
            if "\r" in upstream_api_key or "\n" in upstream_api_key:
                raise ValueError("upstream API key must be one line")
        self.upstream_api_key = upstream_api_key
        self.path_prefix = "/_harnessbench/" + secrets.token_urlsafe(24)
        self._lock = threading.Lock()
        self._model_requests = 0
        self._rejected_requests = 0
        self._forward_errors = 0
        self._downstream_disconnects = 0
        self._last_error = ""
        self._last_downstream_disconnect = ""
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._active_connections: set[object] = set()
        self._active_handlers = 0
        self._active_condition = threading.Condition(self._lock)
        if (trace_dir is None) != (session_id is None):
            raise ValueError("trace_dir and session_id must be provided together")
        self.trace_recorder = (
            ProviderTraceRecorder(
                trace_dir,
                session_id=session_id,
                requested_thinking=thinking,
            )
            if trace_dir is not None and session_id is not None
            else None
        )

    @property
    def model_requests(self) -> int:
        with self._lock:
            return self._model_requests

    @property
    def rejected_requests(self) -> int:
        with self._lock:
            return self._rejected_requests

    @property
    def forward_errors(self) -> int:
        with self._lock:
            return self._forward_errors

    @property
    def last_error(self) -> str:
        with self._lock:
            return self._last_error

    @property
    def downstream_disconnects(self) -> int:
        with self._lock:
            return self._downstream_disconnects

    @property
    def last_downstream_disconnect(self) -> str:
        with self._lock:
            return self._last_downstream_disconnect

    @property
    def trace_summary(self) -> dict[str, object] | None:
        if self.trace_recorder is None:
            return None
        return self.trace_recorder.summary()

    def _record_forward_error(self, exc: BaseException) -> None:
        with self._lock:
            self._forward_errors += 1
            self._last_error = f"{type(exc).__name__}: {exc}"

    def _record_downstream_disconnect(self, exc: BaseException) -> None:
        with self._lock:
            self._downstream_disconnects += 1
            self._last_downstream_disconnect = f"{type(exc).__name__}: {exc}"

    def _register_connection(self, connection: object) -> None:
        with self._active_condition:
            self._active_connections.add(connection)
            self._active_condition.notify_all()

    def _unregister_connection(self, connection: object) -> None:
        with self._active_condition:
            self._active_connections.discard(connection)
            self._active_condition.notify_all()

    def _register_handler(self) -> None:
        with self._active_condition:
            self._active_handlers += 1

    def _unregister_handler(self) -> None:
        with self._active_condition:
            self._active_handlers -= 1
            self._active_condition.notify_all()

    def _claim_model_request(self) -> bool:
        with self._lock:
            if self._model_requests >= self.max_agent_turns:
                self._rejected_requests += 1
                return False
            self._model_requests += 1
            return True

    def _release_model_request(self) -> None:
        with self._lock:
            if self._model_requests < 1:
                raise RuntimeError("cannot release an unclaimed model request")
            self._model_requests -= 1


    def _rewrite_body(self, path: str, body: bytes) -> bytes:
        if not path.endswith(MODEL_PATH_SUFFIXES):
            return body
        try:
            payload = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return body
        if not isinstance(payload, dict):
            return body
        apply_reasoning_policy(payload, path=path, thinking=self.thinking)
        payload["temperature"] = self.temperature
        if path.endswith("/responses"):
            token_key = "max_output_tokens"
        elif path.endswith("/chat/completions") and "max_completion_tokens" in payload:
            token_key = "max_completion_tokens"
        else:
            token_key = "max_tokens"
        requested = payload.get(token_key)
        if not isinstance(requested, int) or isinstance(requested, bool):
            payload[token_key] = self.max_output_tokens
        else:
            payload[token_key] = min(requested, self.max_output_tokens)
        if path.endswith("/chat/completions") and payload.get("stream") is True:
            stream_options = payload.get("stream_options")
            if not isinstance(stream_options, dict):
                stream_options = {}
                payload["stream_options"] = stream_options
            stream_options["include_usage"] = True
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode(
            "utf-8"
        )

    def start(self) -> str:
        if self._server is not None:
            raise RuntimeError("model budget proxy is already running")
        owner = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.0"

            def handle(self) -> None:
                # Track the handler before it can claim a model request. A
                # request can otherwise increment the budget and be between
                # claim and upstream-connection registration when close()
                # snapshots active connections, leaving its final trace row
                # out of the task summary.
                owner._register_handler()
                owner._register_connection(self.connection)
                try:
                    super().handle()
                finally:
                    owner._unregister_connection(self.connection)
                    owner._unregister_handler()

            def log_message(self, _format: str, *_args: object) -> None:
                return

            def do_GET(self) -> None:  # noqa: N802
                upstream_path = self._upstream_path()
                if upstream_path is None:
                    self.send_error(404)
                    return
                self._forward(upstream_path)

            def do_POST(self) -> None:  # noqa: N802
                upstream_path = self._upstream_path()
                if upstream_path is None:
                    self.send_error(404)
                    return
                model_request = upstream_path.split("?", 1)[0].endswith(
                    MODEL_PATH_SUFFIXES
                )
                if model_request:
                    if not owner._claim_model_request():
                        started_epoch = time.time()
                        length = int(self.headers.get("Content-Length") or 0)
                        body = self.rfile.read(length) if length else b""
                        body = owner._rewrite_body(upstream_path.split("?", 1)[0], body)
                        payload = json.dumps(
                            {
                                "error": {
                                    "type": "max_agent_turns_exceeded",
                                    "message": (
                                        "HarnessBench maximum provider request budget "
                                        f"of {owner.max_agent_turns} was reached"
                                    ),
                                }
                            }
                        ).encode("utf-8")
                        self.send_response(400)
                        self.send_header("Content-Type", "application/json")
                        self.send_header("Content-Length", str(len(payload)))
                        self.end_headers()
                        self.wfile.write(payload)
                        if owner.trace_recorder is not None:
                            owner.trace_recorder.record(
                                request_index=owner.trace_recorder.next_request_index(),
                                path=upstream_path,
                                request_body=body,
                                started_epoch=started_epoch,
                                response_status=400,
                                response_content_type="application/json",
                                response_body=payload,
                                finished_epoch=time.time(),
                                complete=True,
                                outcome="local_turn_limit_rejection",
                            )
                        return
                self._forward(upstream_path, trace_model_request=model_request)

            def _upstream_path(self) -> str | None:
                path, separator, query = self.path.partition("?")
                if path != owner.path_prefix and not path.startswith(
                    owner.path_prefix + "/"
                ):
                    return None
                mapped = path[len(owner.path_prefix) :] or "/"
                return mapped + (separator + query if separator else "")

            def _forward(
                self,
                upstream_path: str,
                *,
                trace_model_request: bool = False,
            ) -> None:
                length = int(self.headers.get("Content-Length") or 0)
                try:
                    body = self.rfile.read(length) if length else b""
                except (ConnectionError, OSError) as exc:
                    if trace_model_request:
                        owner._release_model_request()
                    owner._record_downstream_disconnect(exc)
                    self.close_connection = True
                    return
                if trace_model_request and len(body) != length:
                    owner._release_model_request()
                    owner._record_downstream_disconnect(
                        ConnectionResetError(
                            "downstream closed before request body was complete"
                        )
                    )
                    self.close_connection = True
                    return
                body = owner._rewrite_body(upstream_path.split("?", 1)[0], body)
                started_epoch = time.time()
                request_index = (
                    owner.trace_recorder.next_request_index()
                    if trace_model_request and owner.trace_recorder is not None
                    else None
                )
                connection_cls = (
                    http.client.HTTPSConnection
                    if owner.upstream.scheme == "https"
                    else http.client.HTTPConnection
                )
                connection = connection_cls(
                    owner.upstream.hostname,
                    owner.upstream.port,
                    timeout=owner.timeout_sec,
                )
                owner._register_connection(connection)
                blocked_headers = HOP_BY_HOP_HEADERS | {
                    "host",
                    "content-length",
                    "accept-encoding",
                }
                if owner.upstream_api_key is not None:
                    blocked_headers |= {"authorization", "x-api-key"}
                headers = {
                    name: value
                    for name, value in self.headers.items()
                    if name.casefold() not in blocked_headers
                }
                # Provider traces parse the response body to recover usage and
                # normalized events. Request an identity response so an
                # upstream gzip variant cannot silently erase token coverage.
                headers["Accept-Encoding"] = "identity"
                if owner.upstream_api_key is not None:
                    headers["Authorization"] = f"Bearer {owner.upstream_api_key}"
                    if upstream_path.split("?", 1)[0].endswith("/messages"):
                        headers["x-api-key"] = owner.upstream_api_key
                if body:
                    headers["Content-Length"] = str(len(body))
                response_started = False
                response_status: int | None = None
                response_content_type = ""
                response_body = bytearray()
                trace_complete = False
                trace_outcome = "upstream_error"
                trace_error = ""
                try:
                    connection.request(
                        self.command, upstream_path, body=body, headers=headers
                    )
                    response = connection.getresponse()
                    response_status = response.status
                    response_content_type = response.getheader("Content-Type") or ""
                    self.send_response(response.status, response.reason)
                    for name, value in response.getheaders():
                        if (
                            name.casefold() not in HOP_BY_HOP_HEADERS
                            and name.casefold() != "content-length"
                        ):
                            self.send_header(name, value)
                    self.send_header("Connection", "close")
                    self.end_headers()
                    response_started = True
                    while True:
                        chunk = response.read(64 * 1024)
                        if not chunk:
                            break
                        response_body.extend(chunk)
                        self.wfile.write(chunk)
                        self.wfile.flush()
                    trace_complete = True
                    trace_outcome = "upstream_response"
                except (
                    BrokenPipeError,
                    ConnectionError,
                    OSError,
                    http.client.HTTPException,
                ) as exc:
                    downstream_disconnect = is_downstream_disconnect(
                        exc,
                        response_started=response_started,
                    )
                    if downstream_disconnect:
                        owner._record_downstream_disconnect(exc)
                        trace_outcome = "downstream_disconnect"
                    else:
                        owner._record_forward_error(exc)
                        trace_outcome = "upstream_error"
                    trace_error = f"{type(exc).__name__}: {exc}"
                    if not response_started and not downstream_disconnect:
                        payload = json.dumps(
                            {
                                "error": {
                                    "type": "model_upstream_error",
                                    "message": owner.last_error,
                                }
                            }
                        ).encode("utf-8")
                        try:
                            self.send_response(502)
                            self.send_header("Content-Type", "application/json")
                            self.send_header("Content-Length", str(len(payload)))
                            self.end_headers()
                            self.wfile.write(payload)
                        except (BrokenPipeError, ConnectionError, OSError):
                            pass
                    self.close_connection = True
                finally:
                    connection.close()
                    try:
                        if (
                            request_index is not None
                            and owner.trace_recorder is not None
                        ):
                            owner.trace_recorder.record(
                                request_index=request_index,
                                path=upstream_path,
                                request_body=body,
                                started_epoch=started_epoch,
                                response_status=response_status,
                                response_content_type=response_content_type,
                                response_body=bytes(response_body),
                                finished_epoch=time.time(),
                                complete=trace_complete,
                                outcome=trace_outcome,
                                error=trace_error,
                            )
                    finally:
                        owner._unregister_connection(connection)

        self._server = ThreadingHTTPServer(("0.0.0.0", 0), Handler)
        # server_close() must join request handlers.  Otherwise close() can
        # return while a final harness bookkeeping request is still appending
        # its provider transaction, and the controller snapshots a false
        # observed=request_count-1 trace mismatch.
        self._server.daemon_threads = False
        self._server.block_on_close = True
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name="hb-model-budget-proxy",
            daemon=True,
        )
        self._thread.start()
        port = self._server.server_address[1]
        return (
            f"http://host.docker.internal:{port}{self.path_prefix}"
            f"{self.upstream.path.rstrip('/')}"
        )

    def close(self) -> None:
        if self._server is None:
            return
        self._server.shutdown()
        # A harness may finish its foreground task while a final bookkeeping
        # request is still receiving a model response. Preserve that response
        # and its usage before forcing socket shutdown.
        grace_deadline = time.monotonic() + 120
        with self._active_condition:
            while self._active_connections or self._active_handlers:
                remaining = grace_deadline - time.monotonic()
                if remaining <= 0:
                    break
                self._active_condition.wait(timeout=min(remaining, 0.1))

        deadline = time.monotonic() + 10
        while True:
            with self._active_condition:
                active = list(self._active_connections)
                handlers = self._active_handlers
            if not active and not handlers:
                break
            for connection in active:
                try:
                    shutdown = getattr(connection, "shutdown", None)
                    if callable(shutdown):
                        shutdown(socket.SHUT_RDWR)
                    elif getattr(connection, "sock", None) is not None:
                        connection.sock.shutdown(socket.SHUT_RDWR)
                    connection.close()  # type: ignore[attr-defined]
                except (OSError, http.client.HTTPException):
                    pass
            with self._active_condition:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                # A handler may claim its turn immediately before registering
                # the upstream connection. Recheck so late registration cannot
                # escape shutdown and the provider trace snapshot.
                self._active_condition.wait(timeout=min(remaining, 0.1))
        # ThreadingMixIn.server_close() joins every non-daemon request thread.
        # Forced socket shutdown above makes blocked reads unwind before this
        # method returns, so trace_summary cannot race a late record().
        self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5)
        self._server = None
        self._thread = None
