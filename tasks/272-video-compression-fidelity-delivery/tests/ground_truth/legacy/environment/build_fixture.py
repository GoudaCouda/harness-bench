#!/usr/bin/env python3
"""Build the project-owned deterministic audiovisual input fixture."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=True, text=True, capture_output=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ffmpeg", default="/usr/bin/ffmpeg")
    parser.add_argument("--ffprobe", default="/usr/bin/ffprobe")
    args = parser.parse_args()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists() or args.output.is_symlink():
        raise SystemExit("refusing to overwrite an existing fixture")

    command = [
        args.ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "lavfi",
        "-i",
        "testsrc2=size=1280x720:rate=30:duration=12",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=880:sample_rate=48000:duration=12",
        "-filter_complex",
        "[1:a]volume=0.12,pan=stereo|c0=c0|c1=c0[a]",
        "-map",
        "0:v:0",
        "-map",
        "[a]",
        "-c:v",
        "mpeg4",
        "-q:v",
        "2",
        "-pix_fmt",
        "yuv420p",
        "-r",
        "30",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-ar",
        "48000",
        "-ac",
        "2",
        "-movflags",
        "+faststart",
        "-metadata",
        "creation_time=2025-01-01T00:00:00Z",
        "-metadata",
        "title=Agent SFT synthetic fixture",
        "-threads",
        "1",
        "-y",
        str(args.output),
    ]
    run(command)
    probe = run(
        [
            args.ffprobe,
            "-v",
            "error",
            "-show_streams",
            "-show_format",
            "-of",
            "json",
            str(args.output),
        ]
    )
    metadata = json.loads(probe.stdout)
    print(
        json.dumps(
            {
                "sha256": sha256_file(args.output),
                "size_bytes": args.output.stat().st_size,
                "stream_count": len(metadata.get("streams", [])),
                "format_name": metadata.get("format", {}).get("format_name"),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
