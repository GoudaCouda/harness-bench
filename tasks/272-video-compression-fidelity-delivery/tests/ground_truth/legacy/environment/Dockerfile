FROM ubuntu@sha256:4fbb8e6a8395de5a7550b33509421a2bafbc0aab6c06ba2cef9ebffbc7092d90

ARG DEBIAN_FRONTEND=noninteractive

LABEL agent_sft.run_id="nami_work_gold20_v1" \
      agent_sft.task_id="20260719_nami_work_gold20_v1" \
      agent_sft.case_id="case_18" \
      agent_sft.host_alias="local-docker" \
      agent_sft.purpose="nami_work_gold20"

RUN printf '%s\n' \
      'deb [signed-by=/usr/share/keyrings/ubuntu-archive-keyring.gpg] http://archive.ubuntu.com/ubuntu noble main universe' \
      'deb [signed-by=/usr/share/keyrings/ubuntu-archive-keyring.gpg] http://archive.ubuntu.com/ubuntu noble-updates main universe' \
      'deb [signed-by=/usr/share/keyrings/ubuntu-archive-keyring.gpg] http://archive.ubuntu.com/ubuntu noble-security main universe' \
      > /etc/apt/sources.list \
    && rm -f /etc/apt/sources.list.d/ubuntu.sources \
    && apt-get \
      -o Acquire::Languages=none \
      -o Acquire::Retries=1 \
      -o Acquire::http::Timeout=20 \
      update \
    && apt-get install -y --no-install-recommends \
      ffmpeg \
      python3-minimal \
    && dpkg-query -W -f='${Package}=${Version}\n' ffmpeg python3-minimal \
      > /opt/case18-package-versions.txt \
    && rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/*

ENV LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    TZ=UTC \
    SOURCE_DATE_EPOCH=1735689600

WORKDIR /workspace

ENTRYPOINT []
CMD ["sleep", "infinity"]
