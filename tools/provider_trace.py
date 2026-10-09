"""Trusted provider-boundary recording for complete harness sessions.

The recorder deliberately lives outside every harness container.  It persists
the exact rewritten model request and the exact upstream response, then adds a
small protocol-neutral view for ordinary trajectory analysis.  The raw record
remains authoritative whenever a native protocol adds a field that the
normalizer does not yet understand.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import threading
from pathlib import Path
from typing import Any


TRACE_SCHEMA_VERSION = 1


def _expected_effort(thinking: str) -> str:
    return "none" if thinking == "off" else thinking


def _request_reasoning_control(
    payload: dict[str, Any] | None,
    protocol: str,
) -> dict[str, Any]:
    """Describe the actual model-side reasoning control on one request."""
    if payload is None:
        return {"kind": "unparseable"}
    if protocol == "responses":
        reasoning = payload.get("reasoning")
        reasoning = reasoning if isinstance(reasoning, dict) else {}
        return {
            "kind": "effort",
            "effort": reasoning.get("effort"),
            "encrypted_content_requested": "reasoning.encrypted_content"
            in (payload.get("include") or []),
        }
    if protocol == "anthropic_messages":
        thinking = payload.get("thinking")
        thinking = thinking if isinstance(thinking, dict) else {}
        output_config = payload.get("output_config")
        output_config = output_config if isinstance(output_config, dict) else {}
        return {
            "kind": "adaptive",
            "thinking_type": thinking.get("type"),
            "effort": output_config.get("effort"),
        }
    if protocol == "chat_completions":
        template = payload.get("chat_template_kwargs")
        template = template if isinstance(template, dict) else {}
        return {
            "kind": "chat",
            "effort": payload.get("reasoning_effort"),
            "thinking_enabled": template.get("enable_thinking"),
        }
    return {"kind": "unknown"}


def _control_matches_requested(control: dict[str, Any], requested: str) -> bool:
    expected = _expected_effort(requested)
    kind = control.get("kind")
    if kind == "effort":
        return control.get("effort") == expected and (
            expected == "none" or control.get("encrypted_content_requested") is True
        )
    if kind == "adaptive":
        if expected == "none":
            return control.get("thinking_type") in {None, "disabled"}
        return (
            control.get("thinking_type") == "adaptive"
            and control.get("effort") == expected
        )
    if kind == "chat":
        if control.get("effort") == expected:
            return True
        return control.get("thinking_enabled") is (expected != "none")
    return False


def _response_reasoning_state(
    objects: list[dict[str, Any]], protocol: str
) -> set[str]:
    """Return opaque replay keys without storing extra copies of reasoning text."""
    states: set[str] = set()
    if protocol == "responses":
        output: list[Any] = []
        for item in objects:
            response = item.get("response")
            if isinstance(response, dict) and isinstance(response.get("output"), list):
                output.extend(response["output"])
            if isinstance(item.get("output"), list):
                output.extend(item["output"])
            streamed_item = item.get("item")
            if isinstance(streamed_item, dict):
                output.append(streamed_item)
        for item in output:
            if not isinstance(item, dict) or item.get("type") != "reasoning":
                continue
            encrypted = item.get("encrypted_content")
            if isinstance(encrypted, str) and encrypted:
                states.add("encrypted:" + hashlib.sha256(encrypted.encode()).hexdigest())
        return states

    if protocol == "anthropic_messages":
        blocks: list[dict[str, Any]] = []
        for item in objects:
            content = item.get("content")
            if isinstance(content, list):
                blocks = [block for block in content if isinstance(block, dict)]
            block = item.get("content_block")
            if isinstance(block, dict):
                blocks.append(block)
            delta = item.get("delta")
            if isinstance(delta, dict):
                signature = delta.get("signature")
                if isinstance(signature, str) and signature:
                    states.add(
                        "signature:" + hashlib.sha256(signature.encode()).hexdigest()
                    )
        for block in blocks:
            for key, prefix in (("signature", "signature:"), ("data", "redacted:")):
                value = block.get(key)
                if isinstance(value, str) and value:
                    states.add(prefix + hashlib.sha256(value.encode()).hexdigest())
        return states

    if protocol == "chat_completions":
        reasoning: list[str] = []
        for item in objects:
            choices = item.get("choices")
            if not isinstance(choices, list):
                continue
            for choice in choices:
                if not isinstance(choice, dict):
                    continue
                message = choice.get("message")
                delta = choice.get("delta")
                for container in (message, delta):
                    if not isinstance(container, dict):
                        continue
                    for key in ("reasoning_content", "reasoning"):
                        value = container.get(key)
                        if isinstance(value, str) and value:
                            reasoning.append(value)
        if reasoning:
            value = "".join(reasoning)
            states.add("reasoning:" + hashlib.sha256(value.encode()).hexdigest())
        return states
    return states


def _request_reasoning_state(
    payload: dict[str, Any] | None, protocol: str
) -> set[str]:
    if payload is None:
        return set()
    states: set[str] = set()
    if protocol == "responses":
        inputs = payload.get("input")
        if not isinstance(inputs, list):
            return states
        for item in inputs:
            if not isinstance(item, dict) or item.get("type") != "reasoning":
                continue
            encrypted = item.get("encrypted_content")
            if isinstance(encrypted, str) and encrypted:
                states.add("encrypted:" + hashlib.sha256(encrypted.encode()).hexdigest())
        return states

    messages = payload.get("messages")
    if not isinstance(messages, list):
        return states
    reasoning: list[str] = []
    for message in messages:
        if not isinstance(message, dict) or message.get("role") != "assistant":
            continue
        for key in ("reasoning_content", "reasoning"):
            value = message.get(key)
            if isinstance(value, str) and value:
                reasoning.append(value)
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            for key, prefix in (("signature", "signature:"), ("data", "redacted:")):
                value = block.get(key)
                if isinstance(value, str) and value:
                    states.add(prefix + hashlib.sha256(value.encode()).hexdigest())
    if reasoning:
        states.add("reasoning:" + hashlib.sha256("".join(reasoning).encode()).hexdigest())
    return states


def protocol_for_path(path: str) -> str:
    clean = path.split("?", 1)[0]
    if clean.endswith("/responses"):
        return "responses"
    if clean.endswith("/messages"):
        return "anthropic_messages"
    if clean.endswith("/chat/completions"):
        return "chat_completions"
    return "unknown"


def _json_object(payload: bytes) -> dict[str, Any] | None:
    try:
        loaded = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return loaded if isinstance(loaded, dict) else None


def _body_record(payload: bytes) -> dict[str, Any]:
    decoded = _json_object(payload)
    if decoded is not None:
        return {"encoding": "json", "value": decoded}
    try:
        return {"encoding": "utf-8", "value": payload.decode("utf-8")}
    except UnicodeDecodeError:
        return {
            "encoding": "base64",
            "value": base64.b64encode(payload).decode("ascii"),
        }


def _sse_objects(payload: bytes) -> list[dict[str, Any]]:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        return []
    objects: list[dict[str, Any]] = []
    for line in text.splitlines():
        if not line.startswith("data:"):
            continue
        value = line[5:].strip()
        if not value or value == "[DONE]":
            continue
        try:
            loaded = json.loads(value)
        except json.JSONDecodeError:
            continue
        if isinstance(loaded, dict):
            objects.append(loaded)
    return objects


def _response_objects(payload: bytes, content_type: str) -> list[dict[str, Any]]:
    if "text/event-stream" in content_type.casefold() or payload.lstrip().startswith(
        b"data:"
    ):
        return _sse_objects(payload)
    loaded = _json_object(payload)
    return [loaded] if loaded is not None else []


def _text_from_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        for key in ("text", "thinking", "output_text"):
            value = block.get(key)
            if isinstance(value, str):
                parts.append(value)
                break
    return "".join(parts)


def _tool_calls_from_message(message: dict[str, Any]) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    native = message.get("tool_calls")
    if isinstance(native, list):
        for item in native:
            if not isinstance(item, dict):
                continue
            function = item.get("function")
            function = function if isinstance(function, dict) else {}
            calls.append(
                {
                    "type": "tool_call",
                    "id": item.get("id"),
                    "name": function.get("name") or item.get("name"),
                    "arguments": function.get("arguments", item.get("arguments")),
                }
            )
    content = message.get("content")
    if isinstance(content, list):
        for block in content:
            if not isinstance(block, dict) or block.get("type") not in {
                "tool_use",
                "function_call",
            }:
                continue
            calls.append(
                {
                    "type": "tool_call",
                    "id": block.get("id") or block.get("call_id"),
                    "name": block.get("name"),
                    "arguments": block.get("input", block.get("arguments")),
                }
            )
    return calls


def _events_from_message(message: dict[str, Any]) -> list[dict[str, Any]]:
    role = str(message.get("role") or "unknown")
    content = message.get("content")
    events: list[dict[str, Any]] = []
    if role == "tool":
        return [
            {
                "type": "tool_result",
                "tool_call_id": message.get("tool_call_id"),
                "content": content,
            }
        ]
    if role == "user" and isinstance(content, list):
        ordinary: list[Any] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_result":
                events.append(
                    {
                        "type": "tool_result",
                        "tool_call_id": block.get("tool_use_id"),
                        "content": block.get("content"),
                        "is_error": block.get("is_error"),
                    }
                )
            else:
                ordinary.append(block)
        if ordinary:
            events.insert(0, {"type": "user", "content": ordinary})
        return events
    event = {"type": role, "content": content}
    if role == "assistant":
        event["text"] = _text_from_content(content)
    events.append(event)
    if role == "assistant":
        events.extend(_tool_calls_from_message(message))
    return events


def normalize_request(payload: dict[str, Any], protocol: str) -> list[dict[str, Any]]:
    """Return ordered role/tool observations from one provider request."""
    events: list[dict[str, Any]] = []
    if protocol in {"chat_completions", "anthropic_messages"}:
        if protocol == "anthropic_messages" and payload.get("system") is not None:
            events.append({"type": "system", "content": payload["system"]})
        messages = payload.get("messages")
        if isinstance(messages, list):
            for message in messages:
                if isinstance(message, dict):
                    events.extend(_events_from_message(message))
        return events

    if protocol != "responses":
        return events
    if payload.get("instructions") is not None:
        events.append({"type": "developer", "content": payload["instructions"]})
    inputs = payload.get("input")
    if isinstance(inputs, str):
        events.append({"type": "user", "content": inputs})
        return events
    if not isinstance(inputs, list):
        return events
    for item in inputs:
        if not isinstance(item, dict):
            continue
        item_type = item.get("type")
        if item_type in {"function_call", "custom_tool_call", "computer_call"}:
            events.append(
                {
                    "type": "tool_call",
                    "id": item.get("call_id") or item.get("id"),
                    "name": item.get("name"),
                    "arguments": item.get("arguments"),
                }
            )
        elif item_type in {
            "function_call_output",
            "custom_tool_call_output",
            "computer_call_output",
        }:
            events.append(
                {
                    "type": "tool_result",
                    "tool_call_id": item.get("call_id"),
                    "content": item.get("output"),
                }
            )
        elif item_type == "message" or "role" in item:
            events.extend(_events_from_message(item))
    return events


def _events_from_response_output(output: Any) -> list[dict[str, Any]]:
    if not isinstance(output, list):
        return []
    events: list[dict[str, Any]] = []
    for item in output:
        if not isinstance(item, dict):
            continue
        item_type = item.get("type")
        if item_type in {"function_call", "custom_tool_call", "computer_call"}:
            events.append(
                {
                    "type": "tool_call",
                    "id": item.get("call_id") or item.get("id"),
                    "name": item.get("name"),
                    "arguments": item.get("arguments"),
                }
            )
        elif item_type == "message" or item.get("role") == "assistant":
            events.extend(_events_from_message(item))
        elif item_type in {"reasoning", "analysis"}:
            events.append({"type": "assistant_reasoning", "content": item})
    return events


def normalize_response(
    objects: list[dict[str, Any]], protocol: str
) -> list[dict[str, Any]]:
    """Normalize the assistant/tool-call portion of a provider response."""
    if not objects:
        return []
    if protocol == "chat_completions":
        nonstream = objects[-1].get("choices")
        if isinstance(nonstream, list) and nonstream:
            message = nonstream[0].get("message")
            if isinstance(message, dict):
                return _events_from_message({"role": "assistant", **message})
        text: list[str] = []
        reasoning: list[str] = []
        calls: dict[int, dict[str, Any]] = {}
        for item in objects:
            choices = item.get("choices")
            if not isinstance(choices, list):
                continue
            for choice in choices:
                delta = choice.get("delta") if isinstance(choice, dict) else None
                if not isinstance(delta, dict):
                    continue
                if isinstance(delta.get("content"), str):
                    text.append(delta["content"])
                for key in ("reasoning", "reasoning_content"):
                    if isinstance(delta.get(key), str):
                        reasoning.append(delta[key])
                tool_calls = delta.get("tool_calls")
                if isinstance(tool_calls, list):
                    for raw in tool_calls:
                        if not isinstance(raw, dict):
                            continue
                        index = int(raw.get("index") or 0)
                        call = calls.setdefault(
                            index,
                            {"type": "tool_call", "id": "", "name": "", "arguments": ""},
                        )
                        if isinstance(raw.get("id"), str):
                            call["id"] += raw["id"]
                        function = raw.get("function")
                        if isinstance(function, dict):
                            if isinstance(function.get("name"), str):
                                call["name"] += function["name"]
                            if isinstance(function.get("arguments"), str):
                                call["arguments"] += function["arguments"]
        events: list[dict[str, Any]] = []
        if text or reasoning:
            events.append(
                {
                    "type": "assistant",
                    "text": "".join(text),
                    "reasoning": "".join(reasoning),
                }
            )
        events.extend(calls[index] for index in sorted(calls))
        return events

    if protocol == "responses":
        for item in reversed(objects):
            response = item.get("response")
            if isinstance(response, dict) and isinstance(response.get("output"), list):
                return _events_from_response_output(response["output"])
            if isinstance(item.get("output"), list):
                return _events_from_response_output(item["output"])
        text = "".join(
            str(item.get("delta"))
            for item in objects
            if item.get("type") in {"response.output_text.delta", "response.refusal.delta"}
            and isinstance(item.get("delta"), str)
        )
        return [{"type": "assistant", "text": text}] if text else []

    if protocol == "anthropic_messages":
        for item in reversed(objects):
            content = item.get("content")
            if isinstance(content, list):
                return _events_from_message({"role": "assistant", "content": content})
        text: list[str] = []
        thinking: list[str] = []
        calls: dict[int, dict[str, Any]] = {}
        for item in objects:
            item_type = item.get("type")
            index = int(item.get("index") or 0)
            block = item.get("content_block")
            if item_type == "content_block_start" and isinstance(block, dict):
                if block.get("type") == "tool_use":
                    calls[index] = {
                        "type": "tool_call",
                        "id": block.get("id"),
                        "name": block.get("name"),
                        "arguments": block.get("input", ""),
                    }
            delta = item.get("delta")
            if not isinstance(delta, dict):
                continue
            if isinstance(delta.get("text"), str):
                text.append(delta["text"])
            if isinstance(delta.get("thinking"), str):
                thinking.append(delta["thinking"])
            if isinstance(delta.get("partial_json"), str) and index in calls:
                prior = calls[index].get("arguments")
                calls[index]["arguments"] = (
                    (prior if isinstance(prior, str) else "") + delta["partial_json"]
                )
        events = []
        if text or thinking:
            events.append(
                {
                    "type": "assistant",
                    "text": "".join(text),
                    "reasoning": "".join(thinking),
                }
            )
        events.extend(calls[index] for index in sorted(calls))
        return events
    return []


def _usage_candidates(
    objects: list[dict[str, Any]], protocol: str
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for item in objects:
        if isinstance(item.get("usage"), dict):
            candidates.append(item["usage"])
        response = item.get("response")
        if isinstance(response, dict) and isinstance(response.get("usage"), dict):
            candidates.append(response["usage"])
        message = item.get("message")
        if protocol == "anthropic_messages" and isinstance(message, dict):
            if isinstance(message.get("usage"), dict):
                candidates.append(message["usage"])
    return candidates


def normalize_usage(
    objects: list[dict[str, Any]], protocol: str
) -> dict[str, Any] | None:
    candidates = _usage_candidates(objects, protocol)
    if not candidates:
        return None
    input_tokens = 0
    output_tokens = 0
    cached_input_tokens = 0
    cache_write_input_tokens = 0
    reasoning_output_tokens = 0
    provided_total = 0
    for usage in candidates:
        input_tokens = max(
            input_tokens,
            int(usage.get("input_tokens", usage.get("prompt_tokens", 0)) or 0),
        )
        output_tokens = max(
            output_tokens,
            int(usage.get("output_tokens", usage.get("completion_tokens", 0)) or 0),
        )
        cached_input_tokens = max(
            cached_input_tokens,
            int(usage.get("cache_read_input_tokens", 0) or 0),
        )
        cache_write_input_tokens = max(
            cache_write_input_tokens,
            int(usage.get("cache_creation_input_tokens", 0) or 0),
        )
        input_details = usage.get("input_tokens_details") or usage.get(
            "prompt_tokens_details"
        )
        if isinstance(input_details, dict):
            cached_input_tokens = max(
                cached_input_tokens,
                int(input_details.get("cached_tokens", 0) or 0),
            )
        output_details = usage.get("output_tokens_details") or usage.get(
            "completion_tokens_details"
        )
        if isinstance(output_details, dict):
            reasoning_output_tokens = max(
                reasoning_output_tokens,
                int(output_details.get("reasoning_tokens", 0) or 0),
            )
        reasoning_output_tokens = max(
            reasoning_output_tokens,
            int(usage.get("reasoning_output_tokens", 0) or 0),
        )
        provided_total = max(provided_total, int(usage.get("total_tokens", 0) or 0))
    computed_total = (
        input_tokens
        + cached_input_tokens
        + cache_write_input_tokens
        + output_tokens
    )
    return {
        "input_tokens": input_tokens,
        "cached_input_tokens": cached_input_tokens,
        "cache_write_input_tokens": cache_write_input_tokens,
        "output_tokens": output_tokens,
        "reasoning_output_tokens": reasoning_output_tokens,
        "total_tokens": provided_total or computed_total,
    }


class ProviderTraceRecorder:
    """Append-only provider transactions plus an atomic session summary."""

    def __init__(
        self,
        trace_dir: Path,
        *,
        session_id: str,
        requested_thinking: str = "high",
    ) -> None:
        self.trace_dir = trace_dir
        self.session_id = session_id
        self.requested_thinking = requested_thinking
        self.transactions_path = trace_dir / "transactions.jsonl"
        self.trajectory_path = trace_dir / "trajectory.jsonl"
        self.summary_path = trace_dir / "session-summary.json"
        self._lock = threading.Lock()
        self._next_request_index = 0
        self._records: list[dict[str, Any]] = []
        trace_dir.mkdir(parents=True, exist_ok=True)
        self.transactions_path.touch(exist_ok=True)
        self.trajectory_path.touch(exist_ok=True)
        self._write_summary_locked()

    def next_request_index(self) -> int:
        with self._lock:
            self._next_request_index += 1
            return self._next_request_index

    def record(
        self,
        *,
        request_index: int,
        path: str,
        request_body: bytes,
        started_epoch: float,
        response_status: int | None,
        response_content_type: str,
        response_body: bytes,
        finished_epoch: float,
        complete: bool,
        outcome: str,
        error: str = "",
    ) -> None:
        protocol = protocol_for_path(path)
        request_json = _json_object(request_body)
        response_objects = _response_objects(response_body, response_content_type)
        request_events = (
            normalize_request(request_json, protocol)
            if request_json is not None
            else []
        )
        reasoning_control = _request_reasoning_control(request_json, protocol)
        response_events = normalize_response(response_objects, protocol)
        returned_reasoning_state = sorted(
            _response_reasoning_state(response_objects, protocol)
        )
        usage = normalize_usage(response_objects, protocol)
        record = {
            "schema_version": TRACE_SCHEMA_VERSION,
            "session_id": self.session_id,
            "request_index": request_index,
            "protocol": protocol,
            "path": path,
            "started_epoch": started_epoch,
            "finished_epoch": finished_epoch,
            "elapsed_sec": round(max(0.0, finished_epoch - started_epoch), 6),
            "outcome": outcome,
            "complete": complete,
            "error": error,
            "request": {
                "byte_count": len(request_body),
                "sha256": hashlib.sha256(request_body).hexdigest(),
                "body": _body_record(request_body),
            },
            "response": {
                "status": response_status,
                "content_type": response_content_type,
                "byte_count": len(response_body),
                "sha256": hashlib.sha256(response_body).hexdigest(),
                "body": _body_record(response_body),
            },
            "normalized": {
                "request_events": request_events,
                "response_events": response_events,
                "reasoning_control": reasoning_control,
                "returned_reasoning_state": returned_reasoning_state,
                "request_reasoning_state": sorted(
                    _request_reasoning_state(request_json, protocol)
                ),
            },
            "usage": usage,
        }
        line = json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
        trajectory_lines: list[str] = []
        observation_index = 0
        for source, events in (
            ("request_context", request_events),
            ("response", response_events),
        ):
            for event in events:
                observation_index += 1
                trajectory_lines.append(
                    json.dumps(
                        {
                            "schema_version": TRACE_SCHEMA_VERSION,
                            "session_id": self.session_id,
                            "request_index": request_index,
                            "observation_index": observation_index,
                            "source": source,
                            "event": event,
                        },
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                    + "\n"
                )
        with self._lock:
            with self.transactions_path.open("a", encoding="utf-8") as stream:
                stream.write(line)
                stream.flush()
                os.fsync(stream.fileno())
            if trajectory_lines:
                with self.trajectory_path.open("a", encoding="utf-8") as stream:
                    stream.writelines(trajectory_lines)
                    stream.flush()
                    os.fsync(stream.fileno())
            self._records.append(record)
            self._write_summary_locked()

    def _summary_locked(self) -> dict[str, Any]:
        usage_keys = (
            "input_tokens",
            "cached_input_tokens",
            "cache_write_input_tokens",
            "output_tokens",
            "reasoning_output_tokens",
            "total_tokens",
        )
        token_usage = {key: 0 for key in usage_keys}
        lengths = {
            "provider_transactions": len(self._records),
            "completed_transactions": 0,
            "request_context_events": 0,
            "response_events": 0,
            "user_events": 0,
            "assistant_events": 0,
            "tool_calls": 0,
            "tool_results": 0,
            "raw_request_bytes": 0,
            "raw_response_bytes": 0,
        }
        requests_with_usage = 0
        requests_eligible_for_usage = 0
        controlled_requests = 0
        reasoning_observed_requests = 0
        protocol_counts: dict[str, int] = {}
        for record in self._records:
            protocol = str(record.get("protocol") or "unknown")
            protocol_counts[protocol] = protocol_counts.get(protocol, 0) + 1
            lengths["completed_transactions"] += record["complete"] is True
            request_events = record["normalized"]["request_events"]
            response_events = record["normalized"]["response_events"]
            lengths["request_context_events"] += len(request_events)
            lengths["response_events"] += len(response_events)
            for event in [*request_events, *response_events]:
                event_type = event.get("type")
                if event_type == "user":
                    lengths["user_events"] += 1
                elif event_type in {"assistant", "assistant_reasoning"}:
                    lengths["assistant_events"] += 1
                elif event_type == "tool_call":
                    lengths["tool_calls"] += 1
                elif event_type == "tool_result":
                    lengths["tool_results"] += 1
            lengths["raw_request_bytes"] += record["request"]["byte_count"]
            lengths["raw_response_bytes"] += record["response"]["byte_count"]
            if record["outcome"] != "local_turn_limit_rejection":
                requests_eligible_for_usage += 1
            usage = record.get("usage")
            if isinstance(usage, dict):
                requests_with_usage += 1
                if int(usage.get("reasoning_output_tokens", 0) or 0) > 0:
                    reasoning_observed_requests += 1
                for key in usage_keys:
                    token_usage[key] += int(usage.get(key, 0) or 0)
            if record["normalized"].get("returned_reasoning_state"):
                reasoning_observed_requests += not (
                    isinstance(usage, dict)
                    and int(usage.get("reasoning_output_tokens", 0) or 0) > 0
                )
            controlled_requests += _control_matches_requested(
                record["normalized"].get("reasoning_control") or {},
                self.requested_thinking,
            )
        transaction_count = len(self._records)
        replay_required = 0
        replay_eligible = 0
        replayed = 0
        lost = 0
        state_not_exposed = 0
        for index, record in enumerate(self._records[:-1]):
            tool_call_ids = {
                event.get("id")
                for event in record["normalized"].get("response_events") or []
                if event.get("type") == "tool_call" and event.get("id")
            }
            if not tool_call_ids:
                continue
            following_record: dict[str, Any] | None = None
            for candidate in self._records[index + 1 :]:
                result_ids = {
                    event.get("tool_call_id")
                    for event in candidate["normalized"].get("request_events") or []
                    if event.get("type") == "tool_result"
                    and event.get("tool_call_id")
                }
                if tool_call_ids & result_ids:
                    following_record = candidate
                    break
            if following_record is None:
                continue
            replay_required += 1
            returned = set(
                record["normalized"].get("returned_reasoning_state") or []
            )
            if not returned:
                state_not_exposed += 1
                continue
            replay_eligible += 1
            following = set(
                following_record["normalized"].get(
                    "request_reasoning_state"
                )
                or []
            )
            if not returned.isdisjoint(following):
                replayed += 1
            else:
                lost += 1
        control_coverage = (
            round(controlled_requests / transaction_count, 6)
            if transaction_count
            else 1.0
        )
        strict_reasoning_eligible = (
            transaction_count > 0
            and controlled_requests == transaction_count
            and lost == 0
            and replay_required > 0
            and replay_eligible > 0
        )
        return {
            "schema_version": TRACE_SCHEMA_VERSION,
            "session_id": self.session_id,
            "status": (
                "complete"
                if transaction_count > 0
                and lengths["completed_transactions"] == transaction_count
                else "partial"
            ),
            "requests_with_usage": requests_with_usage,
            "requests_eligible_for_usage": requests_eligible_for_usage,
            "token_coverage": (
                round(requests_with_usage / requests_eligible_for_usage, 6)
                if requests_eligible_for_usage
                else 1.0
            ),
            "token_usage": token_usage,
            "reasoning": {
                "requested": self.requested_thinking,
                "controlled_requests": controlled_requests,
                "control_coverage": control_coverage,
                "observed_requests": reasoning_observed_requests,
                "replay_required_transitions": replay_required,
                "replay_eligible_transitions": replay_eligible,
                "replayed_transitions": replayed,
                "lost_transitions": lost,
                "state_not_exposed_transitions": state_not_exposed,
                "strict_eligible": strict_reasoning_eligible,
            },
            "protocol_counts": protocol_counts,
            "trajectory_length": lengths,
            "files": {
                "transactions": self.transactions_path.name,
                "trajectory": self.trajectory_path.name,
                "summary": self.summary_path.name,
            },
        }

    def _write_summary_locked(self) -> None:
        payload = json.dumps(
            self._summary_locked(), ensure_ascii=False, indent=2
        ) + "\n"
        temporary = self.summary_path.with_suffix(".json.tmp")
        temporary.write_text(payload, encoding="utf-8")
        os.replace(temporary, self.summary_path)

    def summary(self) -> dict[str, Any]:
        with self._lock:
            return self._summary_locked()
