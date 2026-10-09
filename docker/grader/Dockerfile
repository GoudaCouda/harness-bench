FROM quay.io/prometheus/alertmanager:v0.32.1@sha256:51a825c2a40acc3e338fdd00d622e01ec090f72be2b3ea46be0839cd47a4d286 AS alertmanager

FROM python:3.10-bookworm@sha256:be77ec026cf35f6adf5f4f02015d50b7aadaac98659a02be1fc8ce18c396f652

USER root
RUN test "$(git --version)" = "git version 2.39.5"
COPY docker/grader/requirements.lock /opt/harnessbench/requirements.lock
ARG HARNESSBENCH_PYPI_INDEX_URL=https://pypi.org/simple
ARG HARNESSBENCH_PYPI_TRUSTED_HOST=
RUN trusted_host_args="" \
    && if [ -n "$HARNESSBENCH_PYPI_TRUSTED_HOST" ]; then \
         trusted_host_args="--trusted-host $HARNESSBENCH_PYPI_TRUSTED_HOST"; \
       fi \
    && python3 -m pip install \
      --index-url "$HARNESSBENCH_PYPI_INDEX_URL" \
      $trusted_host_args \
      --no-cache-dir \
      --only-binary=:all: \
      --require-hashes \
      --requirement /opt/harnessbench/requirements.lock \
    && python3 -c 'import yaml; assert yaml.__version__ == "6.0.2"'
COPY --from=alertmanager /bin/amtool /usr/local/bin/amtool
RUN /usr/local/bin/amtool --version 2>&1 | grep -F "version 0.32.1"

# BEGIN MULTIMODAL FRONTEND GRADER TOOLCHAIN
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN python3 -m pip install --no-cache-dir playwright==1.48.0 \
    && python3 -m playwright install --with-deps chromium \
    && chmod -R a+rX /ms-playwright
# END MULTIMODAL FRONTEND GRADER TOOLCHAIN

COPY src/harnessbench/__init__.py /opt/harnessbench/harnessbench/__init__.py
COPY src/harnessbench/grading/ /opt/harnessbench/harnessbench/grading/
COPY docker/grader/grade_entrypoint.py /opt/harnessbench/grade_entrypoint.py
RUN find /opt/harnessbench -type d -exec chmod 0755 {} + \
    && find /opt/harnessbench -type f -exec chmod 0644 {} +

ARG HARNESSBENCH_GRADER_SOURCE_SHA256
LABEL org.harnessbench.grader-source-sha256="${HARNESSBENCH_GRADER_SOURCE_SHA256}"

USER 10002:10002
ENV HOME=/tmp PYTHONPATH=/opt/harnessbench
WORKDIR /workspace
ENTRYPOINT ["python3", "/opt/harnessbench/grade_entrypoint.py"]
