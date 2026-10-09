#!/usr/bin/env bash
set -euo pipefail

: "${HARNESSBENCH_PROMPT:?}"
: "${HARNESSBENCH_CONFIG:?}"
: "${HARNESSBENCH_WORKSPACE:?}"
: "${HARNESSBENCH_STATE:?}"
: "${HARNESSBENCH_TRACE:?}"

export HOME="${HARNESSBENCH_STATE}/home"
export XDG_CONFIG_HOME="${HARNESSBENCH_STATE}/xdg/config"
export XDG_DATA_HOME="${HARNESSBENCH_STATE}/xdg/data"
export XDG_STATE_HOME="${HARNESSBENCH_STATE}/xdg/state"
export XDG_CACHE_HOME="${HARNESSBENCH_STATE}/xdg/cache"
export OPENCODE_CONFIG="${HARNESSBENCH_CONFIG}"
export OPENCODE_DISABLE_AUTOUPDATE="true"
mkdir -p "${HOME}" "${XDG_CONFIG_HOME}" "${XDG_DATA_HOME}" \
  "${XDG_STATE_HOME}" "${XDG_CACHE_HOME}" "${HARNESSBENCH_TRACE}"
prompt="$(<"${HARNESSBENCH_PROMPT}")"

set +e
opencode run \
  --format json \
  --auto \
  --agent build \
  --dir /workspace \
  --model "$(python3 -c \
    'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["model"])' \
    "${HARNESSBENCH_CONFIG}")" \
  "${prompt}" \
  > >(tee "${HARNESSBENCH_TRACE}/events.jsonl") \
  2> >(tee "${HARNESSBENCH_TRACE}/stderr.log" >&2)
status=$?
set -e
chmod -R a+rX "${HARNESSBENCH_WORKSPACE}" "${HARNESSBENCH_TRACE}" \
  2>/dev/null || true
exit "${status}"
