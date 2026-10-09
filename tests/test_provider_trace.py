from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from provider_trace import (  # noqa: E402
    ProviderTraceRecorder,
    normalize_request,
    normalize_response,
    normalize_usage,
)


def sse_objects(*payloads: dict[str, object]) -> list[dict[str, object]]:
    return list(payloads)


def test_normalizes_chat_request_role_and_tool_sequence() -> None:
    events = normalize_request(
        {
            "messages": [
                {"role": "user", "content": "inspect"},
                {
                    "role": "assistant",
                    "content": "working",
                    "tool_calls": [
                        {
                            "id": "call-1",
                            "type": "function",
                            "function": {"name": "shell", "arguments": "{}"},
                        }
                    ],
                },
                {
                    "role": "tool",
                    "tool_call_id": "call-1",
                    "content": "done",
                },
            ]
        },
        "chat_completions",
    )
    assert [event["type"] for event in events] == [
        "user",
        "assistant",
        "tool_call",
        "tool_result",
    ]
    assert events[2]["name"] == "shell"
    assert events[3]["tool_call_id"] == "call-1"


def test_normalizes_anthropic_tool_blocks() -> None:
    events = normalize_request(
        {
            "messages": [
                {
                    "role": "assistant",
                    "content": [
                        {"type": "text", "text": "checking"},
                        {
                            "type": "tool_use",
                            "id": "tool-1",
                            "name": "Bash",
                            "input": {"command": "pwd"},
                        },
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "tool-1",
                            "content": "/workspace",
                        }
                    ],
                },
            ]
        },
        "anthropic_messages",
    )
    assert [event["type"] for event in events] == [
        "assistant",
        "tool_call",
        "tool_result",
    ]
    assert events[1]["arguments"] == {"command": "pwd"}


def test_normalizes_responses_input_items() -> None:
    events = normalize_request(
        {
            "input": [
                {"type": "message", "role": "user", "content": "go"},
                {
                    "type": "function_call",
                    "call_id": "call-1",
                    "name": "exec",
                    "arguments": "{\"cmd\":\"ls\"}",
                },
                {
                    "type": "function_call_output",
                    "call_id": "call-1",
                    "output": "file.txt",
                },
            ]
        },
        "responses",
    )
    assert [event["type"] for event in events] == [
        "user",
        "tool_call",
        "tool_result",
    ]


def test_normalizes_responses_custom_tool_items() -> None:
    events = normalize_request(
        {
            "input": [
                {
                    "type": "custom_tool_call",
                    "call_id": "call-2",
                    "name": "apply_patch",
                    "arguments": "*** Begin Patch",
                },
                {
                    "type": "custom_tool_call_output",
                    "call_id": "call-2",
                    "output": "Done!",
                },
            ]
        },
        "responses",
    )
    assert [event["type"] for event in events] == ["tool_call", "tool_result"]


def test_normalizes_streaming_chat_response_and_usage() -> None:
    objects = sse_objects(
        {
            "choices": [
                {
                    "delta": {
                        "role": "assistant",
                        "content": "hello ",
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": "call-1",
                                "function": {"name": "exec", "arguments": "{\""},
                            }
                        ],
                    }
                }
            ]
        },
        {
            "choices": [
                {
                    "delta": {
                        "content": "world",
                        "tool_calls": [
                            {
                                "index": 0,
                                "function": {"arguments": "cmd\":\"ls\"}"},
                            }
                        ],
                    }
                }
            ]
        },
        {
            "choices": [],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 4,
                "total_tokens": 14,
            },
        },
    )
    events = normalize_response(objects, "chat_completions")
    assert events[0]["text"] == "hello world"
    assert events[1] == {
        "type": "tool_call",
        "id": "call-1",
        "name": "exec",
        "arguments": "{\"cmd\":\"ls\"}",
    }
    assert normalize_usage(objects, "chat_completions") == {
        "input_tokens": 10,
        "cached_input_tokens": 0,
        "cache_write_input_tokens": 0,
        "output_tokens": 4,
        "reasoning_output_tokens": 0,
        "total_tokens": 14,
    }


def test_normalizes_responses_and_anthropic_usage() -> None:
    response_objects = [
        {
            "type": "response.completed",
            "response": {
                "output": [
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": [{"type": "output_text", "text": "done"}],
                    }
                ],
                "usage": {
                    "input_tokens": 20,
                    "output_tokens": 5,
                    "total_tokens": 25,
                    "output_tokens_details": {"reasoning_tokens": 2},
                },
            },
        }
    ]
    assert normalize_response(response_objects, "responses")[0]["text"] == "done"
    assert normalize_usage(response_objects, "responses")["reasoning_output_tokens"] == 2

    anthropic_objects = [
        {
            "type": "message_start",
            "message": {"usage": {"input_tokens": 30, "output_tokens": 0}},
        },
        {"type": "message_delta", "usage": {"output_tokens": 7}},
    ]
    usage = normalize_usage(anthropic_objects, "anthropic_messages")
    assert usage is not None
    assert usage["input_tokens"] == 30
    assert usage["output_tokens"] == 7
    assert usage["total_tokens"] == 37


def test_recorder_persists_raw_transaction_and_session_summary(
    tmp_path: Path,
) -> None:
    recorder = ProviderTraceRecorder(tmp_path, session_id="session-1")
    request = json.dumps(
        {"messages": [{"role": "user", "content": "hello"}]}
    ).encode()
    response = (
        'data: {"choices":[{"delta":{"content":"hi"}}]}\n\n'
        'data: {"choices":[],"usage":{"prompt_tokens":10,'
        '"completion_tokens":2,"total_tokens":12}}\n\n'
        "data: [DONE]\n\n"
    ).encode()
    recorder.record(
        request_index=recorder.next_request_index(),
        path="/v1/chat/completions",
        request_body=request,
        started_epoch=10.0,
        response_status=200,
        response_content_type="text/event-stream",
        response_body=response,
        finished_epoch=11.0,
        complete=True,
        outcome="upstream_response",
    )
    summary = recorder.summary()
    assert summary["status"] == "complete"
    assert summary["token_coverage"] == 1.0
    assert summary["token_usage"]["total_tokens"] == 12
    assert summary["trajectory_length"]["provider_transactions"] == 1
    assert summary["trajectory_length"]["user_events"] == 1
    assert summary["trajectory_length"]["assistant_events"] == 1
    persisted = json.loads((tmp_path / "transactions.jsonl").read_text())
    assert persisted["request"]["body"]["value"]["messages"][0]["content"] == "hello"
    assert persisted["response"]["sha256"]
    trajectory = [
        json.loads(line)
        for line in (tmp_path / "trajectory.jsonl").read_text().splitlines()
    ]
    assert [item["event"]["type"] for item in trajectory] == ["user", "assistant"]
    assert [item["source"] for item in trajectory] == [
        "request_context",
        "response",
    ]
    assert json.loads((tmp_path / "session-summary.json").read_text()) == summary


def test_local_turn_limit_rejection_does_not_reduce_token_coverage(
    tmp_path: Path,
) -> None:
    recorder = ProviderTraceRecorder(tmp_path, session_id="session-1")
    recorder.record(
        request_index=recorder.next_request_index(),
        path="/v1/messages",
        request_body=b"{}",
        started_epoch=10.0,
        response_status=400,
        response_content_type="application/json",
        response_body=b'{"error":{"type":"max_agent_turns_exceeded"}}',
        finished_epoch=10.1,
        complete=True,
        outcome="local_turn_limit_rejection",
    )
    summary = recorder.summary()
    assert summary["requests_eligible_for_usage"] == 0
    assert summary["requests_with_usage"] == 0
    assert summary["token_coverage"] == 1.0


def test_partial_provider_response_is_retained_without_estimating_usage(
    tmp_path: Path,
) -> None:
    recorder = ProviderTraceRecorder(tmp_path, session_id="session-1")
    partial_response = (
        'data: {"choices":[{"delta":{"content":"unfinished"}}]}\n\n'
    ).encode()
    recorder.record(
        request_index=recorder.next_request_index(),
        path="/v1/chat/completions",
        request_body=json.dumps(
            {"messages": [{"role": "user", "content": "hello"}]}
        ).encode(),
        started_epoch=10.0,
        response_status=200,
        response_content_type="text/event-stream",
        response_body=partial_response,
        finished_epoch=11.0,
        complete=False,
        outcome="upstream_error",
        error="TimeoutError: provider stalled",
    )

    summary = recorder.summary()
    assert summary["status"] == "partial"
    assert summary["requests_eligible_for_usage"] == 1
    assert summary["requests_with_usage"] == 0
    assert summary["token_coverage"] == 0.0
    assert summary["token_usage"]["total_tokens"] == 0
    assert summary["trajectory_length"]["assistant_events"] == 1
    transaction = json.loads((tmp_path / "transactions.jsonl").read_text())
    assert transaction["complete"] is False
    assert transaction["response"]["body"]["value"] == partial_response.decode()


def test_reasoning_control_and_responses_replay_are_audited(tmp_path: Path) -> None:
    recorder = ProviderTraceRecorder(
        tmp_path,
        session_id="reasoning-session",
        requested_thinking="high",
    )
    encrypted = "opaque-reasoning-state"
    recorder.record(
        request_index=recorder.next_request_index(),
        path="/v1/responses",
        request_body=json.dumps(
            {
                "model": "openai/gpt-5.6-luna",
                "reasoning": {"effort": "high"},
                "include": ["reasoning.encrypted_content"],
                "input": [{"role": "user", "content": "first"}],
            }
        ).encode(),
        started_epoch=1.0,
        response_status=200,
        response_content_type="application/json",
        response_body=json.dumps(
            {
                "output": [
                    {
                        "type": "reasoning",
                        "encrypted_content": "alternate-stream-copy",
                        "summary": [],
                    },
                    {
                        "type": "reasoning",
                        "encrypted_content": encrypted,
                        "summary": [],
                    },
                    {
                        "type": "function_call",
                        "call_id": "call-1",
                        "name": "shell",
                        "arguments": "{}",
                    },
                ],
                "usage": {"input_tokens": 2, "output_tokens": 3},
            }
        ).encode(),
        finished_epoch=2.0,
        complete=True,
        outcome="upstream_response",
    )
    recorder.record(
        request_index=recorder.next_request_index(),
        path="/v1/responses",
        request_body=json.dumps(
            {
                "model": "openai/gpt-5.6-luna",
                "reasoning": {"effort": "high"},
                "include": ["reasoning.encrypted_content"],
                "input": [
                    {
                        "type": "reasoning",
                        "encrypted_content": encrypted,
                        "summary": [],
                    },
                    {
                        "type": "function_call_output",
                        "call_id": "call-1",
                        "output": "ok",
                    },
                ],
            }
        ).encode(),
        started_epoch=3.0,
        response_status=200,
        response_content_type="application/json",
        response_body=json.dumps(
            {
                "output": [
                    {"type": "message", "role": "assistant", "content": []}
                ],
                "usage": {"input_tokens": 4, "output_tokens": 1},
            }
        ).encode(),
        finished_epoch=4.0,
        complete=True,
        outcome="upstream_response",
    )

    reasoning = recorder.summary()["reasoning"]
    assert reasoning["controlled_requests"] == 2
    assert reasoning["control_coverage"] == 1.0
    assert reasoning["replay_required_transitions"] == 1
    assert reasoning["replay_eligible_transitions"] == 1
    assert reasoning["replayed_transitions"] == 1
    assert reasoning["lost_transitions"] == 0
    assert reasoning["strict_eligible"] is True
