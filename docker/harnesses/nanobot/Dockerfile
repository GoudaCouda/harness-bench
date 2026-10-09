FROM python:3.12-slim-bookworm@sha256:d50fb7611f86d04a3b0471b46d7557818d88983fc3136726336b2a4c657aa30b AS task-toolchain

ARG PIP_INDEX_URL
ARG PIP_EXTRA_INDEX_URL
ARG PIP_TRUSTED_HOST
COPY docker/openclaw/requirements.lock /tmp/harnessbench-requirements.lock
RUN python -m pip install --disable-pip-version-check --no-cache-dir \
      --requirement /tmp/harnessbench-requirements.lock \
    && rm /tmp/harnessbench-requirements.lock

FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de

ARG NANOBOT_VERSION=0.3.0
ARG PYPI_INDEX_URL=https://pypi.org/simple
RUN apt-get update \
    && apt-get install -y --no-install-recommends bash git ripgrep sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# BEGIN MULTIMODAL FRONTEND AGENT TOOLCHAIN
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    NODE_PATH=/usr/local/lib/node_modules:/opt/frontend-deps/node_modules \
    npm_config_cache=/opt/npm-cache
RUN apt-get update \
    && apt-get install -y --no-install-recommends nodejs npm \
    && npm install --global playwright@1.55.0 \
    && playwright install --with-deps chromium \
    && mkdir -p /opt/frontend-deps /opt/npm-cache /ms-playwright \
    && cd /opt/frontend-deps \
    && npm init -y \
    && npm install --package-lock=false \
       @vitejs/plugin-react@4.3.4 \
       vite@5.4.11 \
       typescript@5.6.3 \
       react@18.3.1 \
       react-dom@18.3.1 \
       lucide-react@0.468.0 \
       @types/react@18.3.12 \
       @types/react-dom@18.3.1 \
    && chromium_path="$(find /ms-playwright -path '*/chrome-linux/chrome' -type f -print -quit)" \
    && ln -sf "$chromium_path" /usr/local/bin/chromium \
    && chown -R 1000:1000 /opt/frontend-deps /opt/npm-cache /ms-playwright \
    && npm cache verify \
    && rm -rf /var/lib/apt/lists/*
COPY docker/harnesses/multimodal-npm /opt/harnessbench/frontend-bin/npm
RUN chmod 0755 /opt/harnessbench/frontend-bin/npm
ENV PATH="/opt/harnessbench/frontend-bin:${PATH}"
# END MULTIMODAL FRONTEND AGENT TOOLCHAIN

RUN useradd --create-home --uid 1000 harness
COPY --from=task-toolchain /usr/local/ /usr/local/
COPY docker/openclaw/verify_toolchain.py /opt/harnessbench/verify_toolchain.py
COPY docker/harnesses/nanobot/entrypoint.sh /opt/harness/bin/run
RUN ln -sf /usr/local/bin/python3 /usr/bin/python3 \
    && python /opt/harnessbench/verify_toolchain.py --python-only \
    && python -m venv /opt/nanobot \
    && /opt/nanobot/bin/python -m pip install --no-cache-dir \
        --index-url "${PYPI_INDEX_URL}" "nanobot-ai==${NANOBOT_VERSION}" \
    && chmod 0755 /opt/harness/bin/run

ENV PATH="/opt/harnessbench/frontend-bin:/usr/local/bin:/opt/nanobot/bin:${PATH}" \
    NANOBOT_STREAM_IDLE_TIMEOUT_S=7200 \
    NANOBOT_OPENAI_COMPAT_TIMEOUT_S=7200 \
    NANOBOT_LLM_TIMEOUT_S=0
# NANOBOT_LLM_TIMEOUT_S=0 disables Nanobot's separate 300-second wall-clock
# cap (600 seconds for streaming). The benchmark controller remains the single
# authoritative task deadline and still terminates attempts at 1800-7200s.

# BEGIN NANOBOT LOGIN-SHELL PATH
RUN printf '%s\n' \
    'export PATH="/opt/harnessbench/frontend-bin:/usr/local/bin:/opt/nanobot/bin:$PATH"' \
    > /etc/profile.d/harnessbench-path.sh \
    && chmod 0644 /etc/profile.d/harnessbench-path.sh
# END NANOBOT LOGIN-SHELL PATH

USER 1000:1000
ENTRYPOINT ["/opt/harness/bin/run"]
