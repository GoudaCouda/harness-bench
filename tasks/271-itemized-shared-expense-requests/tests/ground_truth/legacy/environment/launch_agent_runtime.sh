#!/usr/bin/env bash
set -euo pipefail

# 正式 Agent 运行器只暴露工作区和两个 Agent 可见工具文件；不挂载 case 根。
if [[ $# -ne 4 ]]; then
  echo "usage: $0 IMAGE_ID WORKSPACE CASE_ROOT CONTAINER_NAME" >&2
  exit 2
fi

IMAGE_ID=$1
WORKSPACE=$2
CASE_ROOT=$3
CONTAINER_NAME=$4

case "$IMAGE_ID" in
  sha256:[0-9a-f][0-9a-f]*) ;;
  *) echo "IMAGE_ID must be an immutable sha256 digest" >&2; exit 2 ;;
esac

docker run --detach \
  --name "$CONTAINER_NAME" \
  --label agent_sft.run_id=nami_work_gold20_v1 \
  --label agent_sft.case_id=case_17 \
  --label agent_sft.host_alias=local-docker \
  --label agent_sft.purpose=nami_work_gold20 \
  --label agent_sft.task_id=20260719_nami_work_gold20_v1 \
  --network none \
  --cpus 2 \
  --memory 1024m \
  --pids-limit 128 \
  --read-only \
  --tmpfs /run:rw,nosuid,nodev,noexec,size=32m \
  --user 2050:4007 \
  --mount "type=bind,src=${WORKSPACE},dst=/work" \
  --mount "type=bind,src=${CASE_ROOT}/environment/tools.py,dst=/opt/agent-tools/tools.py,readonly" \
  --mount "type=bind,src=${CASE_ROOT}/environment/tool_contract.json,dst=/opt/agent-tools/tool_contract.json,readonly" \
  --workdir /work \
  "$IMAGE_ID" \
  python3 -c 'import time; time.sleep(86400)'
