#!/usr/bin/env python3
"""Create one admissible reference output without exposing byte equality."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--ffmpeg", default="/usr/bin/ffmpeg")
    args = parser.parse_args()

    source = args.workspace / "input/source.mp4"
    output = args.workspace / "output/compressed.mp4"
    if source.is_symlink() or not source.is_file():
        raise SystemExit("source fixture is missing or unsafe")
    if output.exists() or output.is_symlink():
        output.unlink()
    output.parent.mkdir(parents=True, exist_ok=True)

    command = [
        args.ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-i",
        str(source),
        "-map",
        "0:v:0",
        "-map",
        "0:a:0",
        "-vf",
        "scale=640:360:flags=lanczos,fps=24",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-b:v",
        "420k",
        "-maxrate",
        "480k",
        "-bufsize",
        "960k",
        "-g",
        "48",
        "-keyint_min",
        "48",
        "-sc_threshold",
        "0",
        "-pix_fmt",
        "yuv420p",
        "-threads",
        "1",
        "-c:a",
        "aac",
        "-b:a",
        "64k",
        "-ar",
        "48000",
        "-ac",
        "2",
        "-map_metadata",
        "-1",
        "-metadata",
        "creation_time=2025-01-01T00:00:00Z",
        "-movflags",
        "+faststart",
        "-shortest",
        "-y",
        str(output),
    ]
    completed = subprocess.run(command, text=True, capture_output=True)
    if completed.returncode != 0:
        raise SystemExit("reference transcode failed")
    print(json.dumps({"output": "output/compressed.mp4", "size_bytes": output.stat().st_size}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
