FROM python:3.11.9-slim-bookworm@sha256:8fb099199b9f2d70342674bd9dbccd3ed03a258f26bbd1d556822c6dfc60c317

ARG SANDBOX_CONTRACT_SHA256

LABEL agent_sft.case_id="case_08" \
      agent_sft.variant="case_08_isolation_v2" \
      agent_sft.role="candidate-sandbox-image" \
      agent_sft.sandbox_contract_sha256="${SANDBOX_CONTRACT_SHA256}"

ENV LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    TZ=UTC \
    PYTHONHASHSEED=0 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    GPG_KEY=""

COPY runtime/ /opt/case08-runtime/
RUN chmod 0555 /opt/case08-runtime \
    && chmod 0444 /opt/case08-runtime/*.py

WORKDIR /workspace
ENTRYPOINT ["python3", "/opt/case08-runtime/idle.py"]
