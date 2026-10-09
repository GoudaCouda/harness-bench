FROM agent-sft-base-python-case01:sha256-4cd0841b3c1b7c

LABEL agent_sft.run_id="nami_work_gold20_v1" \
      agent_sft.case_id="case_01" \
      agent_sft.host_alias="cpu-v16-mechine-97" \
      agent_sft.purpose="nami_work_gold20" \
      agent_sft.task_id="20260719_nami_work_gold20_v1"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONHASHSEED=0 \
    TZ=Asia/Shanghai \
    LANG=C.UTF-8

WORKDIR /case
USER 2050:4007
CMD ["python3", "--version"]
