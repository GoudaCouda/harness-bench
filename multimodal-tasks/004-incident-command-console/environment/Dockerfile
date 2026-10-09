FROM python:3.10-bookworm@sha256:be77ec026cf35f6adf5f4f02015d50b7aadaac98659a02be1fc8ce18c396f652

ENV DEBIAN_FRONTEND=noninteractive \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    npm_config_cache=/opt/npm-cache

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       ca-certificates \
       curl \
       git \
       nodejs \
       npm \
       ripgrep \
    && npm install --global playwright@1.48.2 \
    && playwright install --with-deps chromium \
    && mkdir -p /opt/frontend-deps \
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
    && npm cache verify \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid 1000 agent \
    && useradd --uid 1000 --gid 1000 --create-home \
       --home-dir /home/agent --shell /bin/sh --no-log-init agent \
    && install -d -o agent -g agent /workspace \
    && install -d -o agent -g agent /home/agent/.cache \
    && chown -R agent:agent /opt/frontend-deps /opt/npm-cache /ms-playwright

ENV HOME=/home/agent \
    CI=1 \
    NODE_PATH=/usr/local/lib/node_modules \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    npm_config_cache=/opt/npm-cache \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /workspace
USER agent:agent
