FROM node@sha256:e21fc383b50d5347dc7a9f1cae45b8f4e2f0d39f7ade28e4eef7d2934522b752 AS gold20-node

FROM python:3.12-slim-bookworm@sha256:d50fb7611f86d04a3b0471b46d7557818d88983fc3136726336b2a4c657aa30b
COPY --from=gold20-node /usr/local/bin/node /usr/local/bin/node
RUN node --version | grep -Fx v22.22.3
RUN groupadd --gid 1000 agent \
    && useradd --uid 1000 --gid 1000 --create-home \
       --home-dir /home/agent --shell /bin/sh --no-log-init agent \
    && install -d -o agent -g agent /workspace
ENV HOME=/home/agent PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /workspace
USER agent:agent
