#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TIMECODE = re.compile(r"^(\d\d):(\d\d):(\d\d),(\d\d\d)$")


def load(name: str) -> dict:
    return json.loads((ROOT / name).read_text())


def ms_to_code(value: int) -> str:
    hours, rem = divmod(value, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    seconds, millis = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def code_to_ms(value: str) -> int:
    match = TIMECODE.fullmatch(value)
    if not match:
        raise ValueError(value)
    hours, minutes, seconds, millis = map(int, match.groups())
    return ((hours * 60 + minutes) * 60 + seconds) * 1000 + millis


def parse_srt(name: str) -> list[dict]:
    blocks = re.split(r"\n\s*\n", (ROOT / name).read_text().strip())
    cues = []
    for block in blocks:
        lines = block.splitlines()
        start, end = lines[1].split(" --> ")
        cues.append({"number": int(lines[0]), "start_ms": code_to_ms(start), "end_ms": code_to_ms(end), "text": "\n".join(lines[2:])})
    return cues


def checks(cues: list[dict]) -> dict[str, bool]:
    transcript = [row["text"] for row in load("transcript.json")["segments"]]
    cuts = load("shot_boundaries.json")["cuts_ms"]
    return {
        "numbering": [row.get("number") for row in cues] == list(range(1, len(transcript) + 1)),
        "transcript": [row.get("text") for row in cues] == transcript,
        "duration": all(1000 <= row.get("end_ms", 0) - row.get("start_ms", 0) <= 3000 for row in cues),
        "minimum_gap": all(cues[index + 1].get("start_ms", 0) - cues[index].get("end_ms", 0) >= 100 for index in range(len(cues) - 1)),
        "shot_boundaries": len(cues) == len(cuts)
        and all(
            row.get("end_ms", 0) < cut and row.get("start_ms", 0) < cut
            for row, cut in zip(cues, cuts, strict=True)
        ),
        "cut_safe_windows": bool(cues)
        and cues[0].get("start_ms") == 1000
        and all(
            cues[index].get("start_ms", 0) > cuts[index - 1]
            for index in range(1, len(cues))
        ),
    }


def analyze(name: str) -> int:
    try:
        cues = parse_srt(name)
        result = checks(cues)
    except (OSError, ValueError, IndexError):
        result = {"parseable": False}
    print(json.dumps({"status": "pass" if all(result.values()) else "fail", "checks": result}, indent=2))
    return 0


def preview(name: str) -> int:
    cues = load(name).get("cues", [])
    result = checks(cues)
    print(json.dumps({"status": "pass" if all(result.values()) else "fail", "checks": result}, indent=2))
    return 0 if all(result.values()) else 2


def render(name: str) -> int:
    cues = load(name).get("cues", [])
    result = checks(cues)
    if not all(result.values()):
        print(json.dumps({"status": "rejected", "checks": result}, indent=2))
        return 2
    blocks = [f"{row['number']}\n{ms_to_code(row['start_ms'])} --> {ms_to_code(row['end_ms'])}\n{row['text']}" for row in cues]
    payload = "\n\n".join(blocks) + "\n"
    prior = (ROOT / "repaired.srt").read_text() if (ROOT / "repaired.srt").is_file() else None
    (ROOT / "repaired.srt").write_text(payload)
    status = "idempotent" if prior == payload else "rendered"
    print(json.dumps({"status": status, "sha256": hashlib.sha256(payload.encode()).hexdigest()}, indent=2))
    return 0


def verify(name: str) -> int:
    try:
        cues = parse_srt(name)
        result = checks(cues)
        raw = (ROOT / name).read_bytes()
    except (OSError, ValueError, IndexError):
        cues, result, raw = [], {"parseable": False}, b""
    report = {"tool": "subctl/1", "status": "pass" if all(result.values()) else "fail", "checks": result, "cue_count": len(cues), "srt_sha256": hashlib.sha256(raw).hexdigest()}
    (ROOT / "qc_report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "pass" else 2


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("analyze", "preview", "render", "verify"):
        child = sub.add_parser(command)
        child.add_argument("file")
    args = parser.parse_args()
    return {"analyze": lambda: analyze(args.file), "preview": lambda: preview(args.file), "render": lambda: render(args.file), "verify": lambda: verify(args.file)}[args.command]()


if __name__ == "__main__":
    raise SystemExit(main())
