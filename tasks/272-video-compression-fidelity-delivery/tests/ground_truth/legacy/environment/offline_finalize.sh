#!/usr/bin/env bash
set -euo pipefail

container_id="${1:?container id is required}"
final_tag="${2:-agent-sft/nami-work-gold20-case18:gold20-v1-draft}"

docker exec -u 0 "${container_id}" sh -lc '
set -eu
expected="ffmpeg=7:6.1.1-3ubuntu5
python3=3.12.3-0ubuntu2.1
python3-minimal=3.12.3-0ubuntu2.1
python3.12=3.12.3-1ubuntu0.15
python3.12-minimal=3.12.3-1ubuntu0.15"
actual="$(dpkg-query -W -f="\${Package}=\${Version}\\n" ffmpeg python3 python3-minimal python3.12 python3.12-minimal)"
test "${actual}" = "${expected}"
expected_added="libpython3-stdlib=3.12.3-0ubuntu2.1
libpython3.12-stdlib=3.12.3-1ubuntu0.15
libreadline8t64=8.2-4build1
libsqlite3-0=3.45.1-1ubuntu2.6
media-types=10.1.0
netbase=6.4
python3.12=3.12.3-1ubuntu0.15
python3=3.12.3-0ubuntu2.1
readline-common=8.2-4build1
tzdata=2026b-0ubuntu0.24.04.1"
test "$(cat /opt/case18-python3-added-versions.txt)" = "${expected_added}"
test "$(ffmpeg -version | sed -n "1s/^ffmpeg version \([^ ]*\).*/\1/p")" = "6.1.1-3ubuntu5"
test "$(ffprobe -version | sed -n "1s/^ffprobe version \([^ ]*\).*/\1/p")" = "6.1.1-3ubuntu5"
test "$(python3 -c "import platform; print(platform.python_version())")" = "3.12.3"
python3 -c "import hashlib, json, pathlib, subprocess"
ffmpeg -hide_banner -loglevel error \
  -f lavfi -i testsrc2=size=64x64:rate=10:duration=0.2 \
  -f lavfi -i sine=frequency=440:sample_rate=48000:duration=0.2 \
  -map 0:v:0 -map 1:a:0 -c:v libx264 -pix_fmt yuv420p \
  -c:a aac -threads 1 -y /opt/case18-assertion.mp4
ffprobe -v error -select_streams v:0 -show_entries stream=codec_name \
  -of default=nw=1:nk=1 /opt/case18-assertion.mp4 | grep -qx h264
ffprobe -v error -select_streams a:0 -show_entries stream=codec_name \
  -of default=nw=1:nk=1 /opt/case18-assertion.mp4 | grep -qx aac
rm -f /opt/case18-assertion.mp4
printf "%s\n" \
  "probe_image=sha256:dc988db44edcaff405c310a8c58b9aae8ad9e65c3f609008a5da26ecefd19593" \
  "ffmpeg=7:6.1.1-3ubuntu5" \
  "python3=3.12.3-0ubuntu2.1" \
  "python3-minimal=3.12.3-0ubuntu2.1" \
  "network=none" \
  > /opt/case18-final-assertion.txt
'

docker commit --pause=true \
  --change 'USER 2050:4007' \
  --change 'CMD ["sleep","infinity"]' \
  "${container_id}" "${final_tag}"
