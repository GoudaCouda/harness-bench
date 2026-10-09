FROM python:3.11.9-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

WORKDIR /work
LABEL agent_sft.run_id="nami_work_gold20_v1" \
      agent_sft.case_id="case_17" \
      agent_sft.host_alias="local-docker" \
      agent_sft.purpose="nami_work_gold20" \
      agent_sft.task_id="20260719_nami_work_gold20_v1"
USER 2050:4007
CMD ["python3", "-c", "import time; time.sleep(86400)"]
