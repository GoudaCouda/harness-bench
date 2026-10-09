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

model="$(read_config model)"
export HOME="${HARNESSBENCH_STATE}/home"
export ANTHROPIC_BASE_URL="$(read_config base_url)"
export ANTHROPIC_API_KEY="local-vllm-no-auth"
export ANTHROPIC_AUTH_TOKEN="local-vllm-no-auth"
export ANTHROPIC_DEFAULT_OPUS_MODEL="${model}"
export ANTHROPIC_DEFAULT_SONNET_MODEL="${model}"
export ANTHROPIC_DEFAULT_HAIKU_MODEL="${model}"
export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC="1"
export DISABLE_TELEMETRY="1"
export CLAUDE_CODE_EFFORT_LEVEL="$(read_config thinking)"
mkdir -p "${HOME}" "${HARNESSBENCH_TRACE}"
prompt="$(<"${HARNESSBENCH_PROMPT}")"

set +e
claude --bare \
  --print "${prompt}" \
  --output-format stream-json \
  --verbose \
  --no-session-persistence \
  --permission-mode bypassPermissions \
  --allowedTools "Bash,Read,Write,Edit,Glob,Grep" \
  > >(tee "${HARNESSBENCH_TRACE}/events.jsonl") \
  2> >(tee "${HARNESSBENCH_TRACE}/stderr.log" >&2)
status=$?
set -e
# Remove offline npm dependencies before the trusted workspace safety check.
rm -rf -- "${HARNESSBENCH_WORKSPACE}/web/node_modules" \
  2>/dev/null || true
chmod -R a+rX "${HARNESSBENCH_WORKSPACE}" "${HARNESSBENCH_TRACE}" \
  2>/dev/null || true
exit "${status}"
