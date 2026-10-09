#!/usr/bin/env bash
set -euo pipefail

: "${HARNESSBENCH_PROMPT:?}"
: "${HARNESSBENCH_CONFIG:?}"
: "${HARNESSBENCH_WORKSPACE:?}"
: "${HARNESSBENCH_STATE:?}"
: "${HARNESSBENCH_TRACE:?}"

export HOME="${HARNESSBENCH_STATE}/home"
export CODEX_HOME="${HARNESSBENCH_STATE}/codex"
export VLLM_API_KEY="local-vllm-no-auth"
mkdir -p "${HOME}" "${CODEX_HOME}" "${HARNESSBENCH_TRACE}"
cp "${HARNESSBENCH_CONFIG}" "${CODEX_HOME}/config.toml"
prompt="$(<"${HARNESSBENCH_PROMPT}")"

set +e
printf '%s' "${prompt}" | codex exec \
  --json \
  --ephemeral \
  --skip-git-repo-check \
  --ignore-rules \
  --cd /workspace \
  --sandbox danger-full-access \
  - \
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
