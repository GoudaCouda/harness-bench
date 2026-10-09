#!/usr/bin/env bash
set -euo pipefail

: "${HARNESSBENCH_PROMPT:?}"
: "${HARNESSBENCH_CONFIG:?}"
: "${HARNESSBENCH_WORKSPACE:?}"
: "${HARNESSBENCH_STATE:?}"
: "${HARNESSBENCH_TRACE:?}"

export HOME="${HARNESSBENCH_STATE}/home"
mkdir -p "${HOME}" "${HARNESSBENCH_TRACE}"
runtime_config="${HARNESSBENCH_STATE}/config.json"
cp "${HARNESSBENCH_CONFIG}" "${runtime_config}"
prompt="$(<"${HARNESSBENCH_PROMPT}")"
nanobot_scaffold=(
  AGENTS.md
  HEARTBEAT.md
  SOUL.md
  USER.md
  memory
  prompts
  sessions
  skills
)
created_scaffold=()
for relative in "${nanobot_scaffold[@]}"; do
  if [[ ! -e "${HARNESSBENCH_WORKSPACE}/${relative}" && ! -L "${HARNESSBENCH_WORKSPACE}/${relative}" ]]; then
    created_scaffold+=("${relative}")
  fi
done

set +e
nanobot agent \
  --config "${runtime_config}" \
  --workspace "${HARNESSBENCH_WORKSPACE}" \
  --no-markdown \
  -m "${prompt}" \
  > >(tee "${HARNESSBENCH_TRACE}/events.log") \
  2> >(tee "${HARNESSBENCH_TRACE}/stderr.log" >&2)
status=$?
set -e

# Nanobot always bootstraps identity, memory, prompt, session and skill files
# into its configured workspace. They are harness state rather than candidate
# task output, so remove only paths that were absent before this invocation.
for relative in "${created_scaffold[@]}"; do
  rm -rf -- "${HARNESSBENCH_WORKSPACE:?}/${relative}"
done

if [[ -d "${HOME}/.nanobot" ]]; then
  cp -a "${HOME}/.nanobot" "${HARNESSBENCH_TRACE}/native-state"
fi
chmod -R a+rX "${HARNESSBENCH_WORKSPACE}" "${HARNESSBENCH_TRACE}" \
  2>/dev/null || true
exit "${status}"
