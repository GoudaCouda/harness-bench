#!/usr/bin/env bash
set -euo pipefail

: "${HARNESSBENCH_PROMPT:?}"
: "${HARNESSBENCH_CONFIG:?}"
: "${HARNESSBENCH_WORKSPACE:?}"
: "${HARNESSBENCH_STATE:?}"
: "${HARNESSBENCH_TRACE:?}"

read_config() {
  python3 -c \
    'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))[sys.argv[2]])' \
    "${HARNESSBENCH_CONFIG}" "$1"
}

export HOME="${HARNESSBENCH_STATE}/home"
export XDG_CONFIG_HOME="${HARNESSBENCH_STATE}/xdg/config"
export XDG_DATA_HOME="${HARNESSBENCH_STATE}/xdg/data"
export XDG_STATE_HOME="${HARNESSBENCH_STATE}/xdg/state"
export GOOSE_PROVIDER="openai"
export GOOSE_MODEL="$(read_config model)"
export GOOSE_CONTEXT_LIMIT="$(read_config context_window)"
export GOOSE_MAX_TOKENS="$(read_config max_tokens)"
export GOOSE_TEMPERATURE="$(read_config temperature)"
export GOOSE_MAX_TURNS="$(read_config max_turns)"
export OPENAI_HOST="$(read_config base_url | sed 's#/v1$##')"
export OPENAI_BASE_PATH="v1/chat/completions"
export OPENAI_API_KEY="local-vllm-no-auth"
export GOOSE_TELEMETRY_ENABLED="false"
export GOOSE_DISABLE_SESSION_NAMING="true"
export GOOSE_DISABLE_TOOL_CALL_SUMMARY="true"
mkdir -p "${HOME}" "${XDG_CONFIG_HOME}" "${XDG_DATA_HOME}" \
  "${XDG_STATE_HOME}" "${HARNESSBENCH_TRACE}"
prompt="$(<"${HARNESSBENCH_PROMPT}")"

set +e
goose run \
  --output-format stream-json \
  --max-turns "$(read_config max_turns)" \
  --no-session \
  --no-profile \
  --with-builtin "developer" \
  -t "${prompt}" \
  > >(tee "${HARNESSBENCH_TRACE}/events.jsonl") \
  2> >(tee "${HARNESSBENCH_TRACE}/stderr.log" >&2)
status=$?
set -e
chmod -R a+rX "${HARNESSBENCH_WORKSPACE}" "${HARNESSBENCH_TRACE}" \
  2>/dev/null || true
exit "${status}"
