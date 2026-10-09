FROM python:3.12-slim-bookworm@sha256:d50fb7611f86d04a3b0471b46d7557818d88983fc3136726336b2a4c657aa30b AS task-toolchain

ARG PIP_INDEX_URL
ARG PIP_EXTRA_INDEX_URL
ARG PIP_TRUSTED_HOST
COPY docker/openclaw/requirements.lock /tmp/harnessbench-requirements.lock
RUN python -m pip install --disable-pip-version-check --no-cache-dir \
      --requirement /tmp/harnessbench-requirements.lock \
    && rm /tmp/harnessbench-requirements.lock

FROM node:22-bookworm-slim@sha256:6c74791e557ce11fc957704f6d4fe134a7bc8d6f5ca4403205b2966bd488f6b3

ARG CLAUDE_CODE_VERSION=2.1.220
RUN apt-get update \
    && apt-get install -y --no-install-recommends bash git libsqlite3-0 ripgrep sqlite3 \
    && rm -rf /var/lib/apt/lists/*
RUN npm install --global "@anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}" \
    && npm cache clean --force

# BEGIN MULTIMODAL FRONTEND AGENT TOOLCHAIN
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    NODE_PATH=/usr/local/lib/node_modules:/opt/frontend-deps/node_modules \
    npm_config_cache=/opt/npm-cache
RUN npm install --global playwright@1.55.0 \
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
    && chown -R 1000:1000 /opt/frontend-deps /opt/npm-cache /ms-playwright /home/node/.cache \
    && npm cache verify \
    && rm -rf /var/lib/apt/lists/*
COPY docker/harnesses/multimodal-npm /opt/harnessbench/frontend-bin/npm
RUN chmod 0755 /opt/harnessbench/frontend-bin/npm
ENV PATH="/opt/harnessbench/frontend-bin:${PATH}"
# END MULTIMODAL FRONTEND AGENT TOOLCHAIN

COPY --from=task-toolchain /usr/local/ /usr/local/
COPY docker/openclaw/verify_toolchain.py /opt/harnessbench/verify_toolchain.py
COPY docker/harnesses/claude-code/entrypoint.sh /opt/harness/bin/run
RUN ln -sf /usr/local/bin/python3 /usr/bin/python3 \
    && python /opt/harnessbench/verify_toolchain.py --python-only \
    && chmod 0755 /opt/harness/bin/run

# BEGIN CLAUDE CODE LOGIN-SHELL FRONTEND PATH
RUN printf '%s\n' \
    'export PATH="/opt/harnessbench/frontend-bin:/usr/local/bin:$PATH"' \
    > /etc/profile.d/harnessbench-path.sh \
    && chmod 0644 /etc/profile.d/harnessbench-path.sh
# END CLAUDE CODE LOGIN-SHELL FRONTEND PATH

USER 1000:1000
ENTRYPOINT ["/opt/harness/bin/run"]
