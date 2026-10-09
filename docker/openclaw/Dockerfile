FROM python:3.12-slim-bookworm@sha256:d50fb7611f86d04a3b0471b46d7557818d88983fc3136726336b2a4c657aa30b AS alertmanager-fetch

ARG TARGETARCH=amd64
ARG ALERTMANAGER_VERSION=0.32.1
ARG ALERTMANAGER_SHA256_AMD64=e3ba4a543111dd4bbf436838385cbf88108f0b128a723e61fe97d3569294ad4d
ARG ALERTMANAGER_SHA256_ARM64=fff322eae493eabdec5c16dfdfb26b37508aaf3ca3238ab1ed1e5bebf3ff4cd9

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && case "$TARGETARCH" in \
         amd64) archive_arch=amd64; expected="$ALERTMANAGER_SHA256_AMD64" ;; \
         arm64) archive_arch=arm64; expected="$ALERTMANAGER_SHA256_ARM64" ;; \
         *) echo "unsupported TARGETARCH=$TARGETARCH" >&2; exit 1 ;; \
       esac \
    && archive="alertmanager-${ALERTMANAGER_VERSION}.linux-${archive_arch}.tar.gz" \
    && curl -fsSLo "/tmp/$archive" \
       "https://github.com/prometheus/alertmanager/releases/download/v${ALERTMANAGER_VERSION}/$archive" \
    && echo "$expected  /tmp/$archive" | sha256sum -c - \
    && tar -xzf "/tmp/$archive" -C /tmp \
    && install -D -m 0755 "/tmp/alertmanager-${ALERTMANAGER_VERSION}.linux-${archive_arch}/amtool" /out/amtool \
    && rm -rf /var/lib/apt/lists/* "/tmp/$archive" "/tmp/alertmanager-${ALERTMANAGER_VERSION}.linux-${archive_arch}"

FROM python:3.12-slim-bookworm@sha256:d50fb7611f86d04a3b0471b46d7557818d88983fc3136726336b2a4c657aa30b AS task-toolchain

ARG PIP_INDEX_URL
ARG PIP_EXTRA_INDEX_URL
ARG PIP_TRUSTED_HOST
COPY docker/openclaw/requirements.lock /tmp/harnessbench-requirements.lock
RUN python -m pip install \
      --disable-pip-version-check \
      --no-cache-dir \
      --requirement /tmp/harnessbench-requirements.lock \
    && rm /tmp/harnessbench-requirements.lock

FROM ghcr.io/openclaw/openclaw:2026.5.26-slim@sha256:ae7ff536446f1bbb57ea51b9b21097d8f299d30d683dcd72644973bc0522f3b3

USER root
ARG HARNESSBENCH_OPENCLAW_SOURCE_SHA256
LABEL org.harnessbench.openclaw-source-sha256="${HARNESSBENCH_OPENCLAW_SOURCE_SHA256}"
LABEL org.harnessbench.task-toolchain="office-python-alertmanager"

RUN apt-get update \
    && apt-get install -y --no-install-recommends sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Merge a complete, digest-pinned CPython installation into the official
# OpenClaw image. This leaves OpenClaw itself byte-identical to the upstream
# layer while making the task-visible CLI consistent and available offline.
COPY --from=task-toolchain /usr/local/ /usr/local/
COPY --from=alertmanager-fetch /out/amtool /usr/local/bin/amtool

# BEGIN MULTIMODAL FRONTEND AGENT TOOLCHAIN
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    NODE_PATH=/usr/local/lib/node_modules:/opt/frontend-deps/node_modules \
    npm_config_cache=/opt/npm-cache
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl git nodejs npm ripgrep \
    && npm install --global playwright@1.48.2 \
    && playwright install --with-deps chromium \
    && mkdir -p /opt/frontend-deps /opt/npm-cache /ms-playwright /home/node/.cache \
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
    && chown -R node:node /opt/frontend-deps /opt/npm-cache /ms-playwright /home/node/.cache \
    && npm cache verify \
    && rm -rf /var/lib/apt/lists/*
COPY docker/harnesses/multimodal-npm /opt/harnessbench/frontend-bin/npm
RUN chmod 0755 /opt/harnessbench/frontend-bin/npm
ENV PATH="/opt/harnessbench/frontend-bin:${PATH}"
# END MULTIMODAL FRONTEND AGENT TOOLCHAIN

COPY docker/openclaw/verify_toolchain.py /opt/harnessbench/verify_toolchain.py
RUN ln -sf /usr/local/bin/python3 /usr/bin/python3 \
    && python /opt/harnessbench/verify_toolchain.py

USER node
