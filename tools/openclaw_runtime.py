"""Pinned OpenClaw image and generated per-run configuration."""

from __future__ import annotations

from typing import Any

from openclaw_image import OPENCLAW_RUNTIME_IMAGE


OFFICIAL_OPENCLAW_IMAGE = (
    "ghcr.io/openclaw/openclaw:2026.5.26-slim@sha256:"
    "ae7ff536446f1bbb57ea51b9b21097d8f299d30d683dcd72644973bc0522f3b3"
)
DEFAULT_OPENCLAW_IMAGE = OPENCLAW_RUNTIME_IMAGE

# ``docker save``/``docker load`` preserves the image configuration but can
# lose RepoDigests.  This verified linux/amd64 configuration ID lets an
# air-gapped CPU worker use the official 2026.5.26 image archive without
# silently falling back to an unpinned mutable tag.  Connected workers still
# resolve the manifest digest above.
OPENCLAW_OFFLINE_IMAGE_ALIASES = {
    "ghcr.io/openclaw/openclaw:2026.5.26-slim": (
        "sha256:50d6bf051ad36b1acd1443326d1cf15f5c49457a3141b0918a1549a427e51888"
    ),
}


def openclaw_config(
    base_url: str,
    model: str,
    max_tokens: int,
    temperature: float = 1.0,
    data_parallel_rank: int | None = None,
    provider_timeout_sec: int = 600,
    context_window: int = 200000,
    thinking: str = "high",
) -> dict[str, Any]:
    if provider_timeout_sec <= 0:
        raise ValueError("provider_timeout_sec must be positive")
    if context_window <= 0:
        raise ValueError("context_window must be positive")
    full_model = f"vllm/{model}"
    model_name = model.casefold()
    effort = "none" if thinking == "off" else thinking
    provider_api = "openai-responses" if "gpt-" in model_name else "openai-completions"
    compat: dict[str, Any] = {
        "supportsTools": True,
        "supportsUsageInStreaming": True,
    }
    model_params: dict[str, Any] = {
        "temperature": temperature,
        "reasoningEffort": effort,
    }
    if "qwen" in model_name:
        compat["thinkingFormat"] = "qwen-chat-template"
    if any(name in model_name for name in ("qwen", "gemma")):
        model_params["chat_template_kwargs"] = {
            "enable_thinking": effort != "none",
        }
    return {
        "models": {
            "mode": "replace",
            "providers": {
                "vllm": {
                    "baseUrl": base_url.rstrip("/"),
                    "apiKey": "local-vllm-no-auth",
                    "api": provider_api,
                    "timeoutSeconds": provider_timeout_sec,
                    **(
                        {"headers": {"X-data-parallel-rank": str(data_parallel_rank)}}
                        if data_parallel_rank is not None
                        else {}
                    ),
                    "models": [
                        {
                            "id": model,
                            "name": model,
                            "reasoning": True,
                            "input": ["text"],
                            "contextWindow": context_window,
                            "maxTokens": max_tokens,
                            "agentRuntime": {"id": "pi"},
                            "compat": compat,
                        }
                    ],
                }
            },
        },
        "agents": {
            "defaults": {
                "workspace": "/workspace",
                "skipBootstrap": True,
                "skills": [],
                "model": {"primary": full_model},
                "models": {
                    full_model: {
                        "params": model_params,
                    }
                },
            }
        },
        "tools": {
            "allow": ["read", "write", "edit", "exec", "process"],
        },
        "channels": {},
        "plugins": {"allow": [], "entries": {}, "installs": {}},
    }
