FROM python:3.12-slim-bookworm@sha256:d50fb7611f86d04a3b0471b46d7557818d88983fc3136726336b2a4c657aa30b
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
RUN groupadd --gid 1000 agent \
    && useradd --uid 1000 --gid 1000 --create-home \
       --home-dir /home/agent --shell /bin/sh --no-log-init agent \
    && install -d -o agent -g agent /workspace
ENV HOME=/home/agent PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /workspace
USER agent:agent
