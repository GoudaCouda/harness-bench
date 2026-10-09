#!/usr/bin/env bash
set -euo pipefail

: "${HARNESSBENCH_PROMPT:?}"
: "${HARNESSBENCH_CONFIG:?}"
: "${HARNESSBENCH_STATE:?}"
: "${HARNESSBENCH_TRACE:?}"

export HERMES_HOME="${HARNESSBENCH_STATE}"
export HOME="${HARNESSBENCH_STATE}/home"
export HERMES_WRITE_SAFE_ROOT="${HARNESSBENCH_WORKSPACE:-/workspace}"
mkdir -p "${HOME}" "${HARNESSBENCH_TRACE}"
cp "${HARNESSBENCH_CONFIG}" "${HERMES_HOME}/config.yaml"
printf 'LOCAL_VLLM_API_KEY=local-vllm-no-auth\n' > "${HERMES_HOME}/.env"

prompt="$(<"${HARNESSBENCH_PROMPT}")"
set +e
/opt/hermes/.venv/bin/hermes chat \
  -q "${prompt}" \
  --toolsets "terminal,file" \
  > >(tee "${HARNESSBENCH_TRACE}/events.log") \
  2> >(tee "${HARNESSBENCH_TRACE}/stderr.log" >&2)
status=$?
set -e

if [[ -d "${HERMES_HOME}/sessions" ]]; then
  cp -a "${HERMES_HOME}/sessions" "${HARNESSBENCH_TRACE}/native-sessions"
fi
chmod -R a+rX "${HARNESSBENCH_WORKSPACE}" "${HARNESSBENCH_TRACE}" \
  2>/dev/null || true
exit "${status}"
