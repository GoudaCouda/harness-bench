#!/usr/bin/env sh
set -eu

export DEBIAN_FRONTEND=noninteractive
before=/opt/case18-dpkg-before-python3.txt
after=/opt/case18-dpkg-after-python3.txt
added=/opt/case18-python3-added-versions.txt

dpkg-query -W -f='${Package}=${Version}\n' | LC_ALL=C sort > "${before}"
apt-get \
  -o Acquire::Languages=none \
  -o Acquire::Retries=1 \
  -o Acquire::http::Timeout=20 \
  update
apt-get install -y --no-install-recommends python3
dpkg-query -W -f='${Package}=${Version}\n' | LC_ALL=C sort > "${after}"
comm -13 "${before}" "${after}" > "${added}"
dpkg-query -W -f='${Package}=${Version}\n' \
  ffmpeg python3 python3-minimal python3.12 python3.12-minimal \
  > /opt/case18-package-versions.txt
rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/*
