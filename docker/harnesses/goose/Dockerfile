FROM python:3.12-slim-bookworm@sha256:d50fb7611f86d04a3b0471b46d7557818d88983fc3136726336b2a4c657aa30b AS task-toolchain

ARG PIP_INDEX_URL
ARG PIP_EXTRA_INDEX_URL
ARG PIP_TRUSTED_HOST
COPY docker/openclaw/requirements.lock /tmp/harnessbench-requirements.lock
RUN python -m pip install --disable-pip-version-check --no-cache-dir \
      --requirement /tmp/harnessbench-requirements.lock \
    && rm /tmp/harnessbench-requirements.lock

FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de

ARG GOOSE_VERSION=1.44.0
ARG GOOSE_SHA256=07febc8b4f73bdfdc3ece3d34d0e21b005f3a4f43008f95b85d6538da8f6bac1
RUN apt-get update \
    && apt-get install -y --no-install-recommends bash ca-certificates curl git ripgrep sqlite3 \
    && rm -rf /var/lib/apt/lists/* \
    && curl -fL \
      "https://github.com/aaif-goose/goose/releases/download/v${GOOSE_VERSION}/goose-x86_64-unknown-linux-gnu.tar.gz" \
      -o /tmp/goose.tar.gz \
    && echo "${GOOSE_SHA256}  /tmp/goose.tar.gz" | sha256sum -c - \
    && tar -xzf /tmp/goose.tar.gz -C /usr/local/bin \
    && rm /tmp/goose.tar.gz \
    && goose --version

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
COPY docker/harnesses/goose/entrypoint.sh /opt/harness/bin/run
RUN ln -sf /usr/local/bin/python3 /usr/bin/python3 \
    && python /opt/harnessbench/verify_toolchain.py --python-only \
    && chmod 0755 /opt/harness/bin/run

# Goose 1.44 otherwise applies its OpenAI-provider default of 600 seconds to
# each model request.  The benchmark controller owns the task deadline, which
# is at most 7200 seconds in the frozen Standard237 release.
ENV OPENAI_TIMEOUT=7200

USER 1000:1000
ENTRYPOINT ["/opt/harness/bin/run"]
