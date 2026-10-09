#!/usr/bin/env python3
"""Fail-closed, deterministic media verifier for case_18."""

from __future__ import annotations

import argparse
import array
import hashlib
import json
import math
import os
import re
import stat
import subprocess
import sys
from fractions import Fraction
from pathlib import Path
from typing import Any


EXPECTED_DIRECTORIES = {"input", "output", "task"}
EXPECTED_FILES = {
    "input/source.mp4",
    "output/compressed.mp4",
    "task/instruction.md",
    "task/target_spec.json",
    "task/tool_contract.json",
}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inventory(root: Path) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        mode = path.lstat().st_mode
        if stat.S_ISLNK(mode):
            item = {"path": relative, "kind": "symlink", "target": os.readlink(path)}
        elif stat.S_ISDIR(mode):
            item = {"path": relative, "kind": "directory"}
        elif stat.S_ISREG(mode):
            item = {
                "path": relative,
                "kind": "file",
                "size_bytes": path.stat().st_size,
                "sha256": file_sha256(path),
            }
        else:
            item = {"path": relative, "kind": "special"}
        values.append(item)
    return values


def state_sha256(root: Path) -> str:
    payload = json.dumps(
        inventory(root), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def add_check(checks: dict[str, Any], check_id: str, passed: bool, **details: Any) -> None:
    checks[check_id] = {"passed": bool(passed), "details": details}


def probe(path: Path, ffprobe: str) -> tuple[dict[str, Any] | None, str | None]:
    command = [
        ffprobe,
        "-v",
        "error",
        "-show_entries",
        "stream=index,codec_type,codec_name,pix_fmt,width,height,avg_frame_rate,r_frame_rate,sample_rate,channels,duration:format=format_name,format_long_name,duration,size",
        "-of",
        "json",
        str(path),
    ]
    completed = subprocess.run(command, text=True, capture_output=True, timeout=30)
    if completed.returncode != 0:
        return None, "ffprobe_failed"
    try:
        value = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return None, "ffprobe_invalid_json"
    if not isinstance(value, dict):
        return None, "ffprobe_invalid_shape"
    return value, None


def decode_ok(path: Path, ffmpeg: str) -> bool:
    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-xerror",
        "-nostdin",
        "-i",
        str(path),
        "-map",
        "0:v:0",
        "-map",
        "0:a:0",
        "-f",
        "null",
        "-",
    ]
    completed = subprocess.run(command, text=True, capture_output=True, timeout=90)
    return completed.returncode == 0


def video_ssim(source: Path, output: Path, ffmpeg: str) -> float | None:
    """Compare decoded pictures after the required scale/fps conversion."""

    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "info",
        "-nostdin",
        "-threads",
        "1",
        "-filter_complex_threads",
        "1",
        "-i",
        str(source),
        "-i",
        str(output),
        "-filter_complex",
        "[0:v:0]scale=640:360:flags=bilinear,fps=24,setpts=PTS-STARTPTS[reference];"
        "[1:v:0]scale=640:360:flags=bilinear,fps=24,setpts=PTS-STARTPTS[candidate];"
        "[reference][candidate]ssim[compared]",
        "-map",
        "[compared]",
        "-an",
        "-f",
        "null",
        "-",
    ]
    completed = subprocess.run(command, text=True, capture_output=True, timeout=90)
    if completed.returncode != 0:
        return None
    matches = re.findall(r"\bAll:([0-9]+(?:\.[0-9]+)?)", completed.stderr)
    return float(matches[-1]) if matches else None


def decode_audio_pcm(path: Path, ffmpeg: str) -> array.array[int] | None:
    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-threads",
        "1",
        "-i",
        str(path),
        "-map",
        "0:a:0",
        "-ac",
        "1",
        "-ar",
        "8000",
        "-f",
        "s16le",
        "-",
    ]
    completed = subprocess.run(command, capture_output=True, timeout=90)
    if completed.returncode != 0 or not completed.stdout:
        return None
    values = array.array("h")
    values.frombytes(completed.stdout)
    if sys.byteorder != "little":
        values.byteswap()
    return values


def audio_snr(source: Path, output: Path, ffmpeg: str) -> float | None:
    """Measure decoded waveform fidelity; silence and unrelated audio score low."""

    reference = decode_audio_pcm(source, ffmpeg)
    candidate = decode_audio_pcm(output, ffmpeg)
    if reference is None or candidate is None:
        return None
    sample_count = min(len(reference), len(candidate))
    if sample_count < 8000:
        return None
    signal_energy = 0.0
    error_energy = 0.0
    for expected, actual in zip(reference[:sample_count], candidate[:sample_count]):
        signal_energy += float(expected) * expected
        delta = expected - actual
        error_energy += float(delta) * delta
    if signal_energy <= 0.0:
        return None
    if error_energy == 0.0:
        return 300.0
    return 10.0 * math.log10(signal_energy / error_energy)


def duration(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if result <= 0:
        return None
    return result


def media_streams(metadata: dict[str, Any], kind: str) -> list[dict[str, Any]]:
    streams = metadata.get("streams")
    if not isinstance(streams, list):
        return []
    return [item for item in streams if isinstance(item, dict) and item.get("codec_type") == kind]


def exact_fraction(value: Any) -> Fraction | None:
    try:
        return Fraction(str(value))
    except (ValueError, ZeroDivisionError):
        return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-root", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--ffmpeg", default="/usr/bin/ffmpeg")
    parser.add_argument("--ffprobe", default="/usr/bin/ffprobe")
    args = parser.parse_args()

    case_root = args.case_root.resolve(strict=True)
    workspace = args.workspace.resolve(strict=True)
    before = state_sha256(workspace)
    checks: dict[str, Any] = {}

    try:
        expected_manifest = json.loads(
            (case_root / "fixtures/workspace_manifest.json").read_text(encoding="utf-8")
        )
        target = json.loads(
            (case_root / "fixtures/task/target_spec.json").read_text(encoding="utf-8")
        )
        expected_hashes = expected_manifest["protected_file_sha256"]
    except (OSError, KeyError, TypeError, json.JSONDecodeError):
        expected_hashes = {}
        target = {}

    actual_inventory = inventory(workspace)
    actual_dirs = {item["path"] for item in actual_inventory if item["kind"] == "directory"}
    actual_files = {item["path"] for item in actual_inventory if item["kind"] == "file"}
    unsafe_entries = [item["path"] for item in actual_inventory if item["kind"] not in {"file", "directory"}]
    add_check(
        checks,
        "workspace_scope",
        actual_dirs == EXPECTED_DIRECTORIES and actual_files == EXPECTED_FILES and not unsafe_entries,
        directory_count=len(actual_dirs),
        file_count=len(actual_files),
        unsafe_entry_count=len(unsafe_entries),
    )

    protected_ok = isinstance(expected_hashes, dict)
    protected_checked = 0
    if protected_ok:
        for relative, expected_hash in expected_hashes.items():
            path = workspace / relative
            if path.is_symlink() or not path.is_file() or file_sha256(path) != expected_hash:
                protected_ok = False
            protected_checked += 1
    add_check(checks, "protected_files", protected_ok, checked_count=protected_checked)

    source = workspace / "input/source.mp4"
    output = workspace / "output/compressed.mp4"
    output_regular = output.is_file() and not output.is_symlink()
    add_check(checks, "output_exists", output_regular, logical_path="output/compressed.mp4")

    input_meta: dict[str, Any] | None = None
    output_meta: dict[str, Any] | None = None
    input_error = "missing_input"
    output_error = "missing_output"
    if source.is_file() and not source.is_symlink():
        input_meta, input_error = probe(source, args.ffprobe)
    if output_regular:
        output_meta, output_error = probe(output, args.ffprobe)
    add_check(
        checks,
        "media_parse",
        input_meta is not None and output_meta is not None,
        input_error=input_error,
        output_error=output_error,
    )

    if output_meta is None:
        output_meta = {}
    if input_meta is None:
        input_meta = {}
    video_streams = media_streams(output_meta, "video")
    audio_streams = media_streams(output_meta, "audio")
    all_streams = output_meta.get("streams") if isinstance(output_meta.get("streams"), list) else []
    add_check(
        checks,
        "stream_layout",
        len(video_streams) == 1 and len(audio_streams) == 1 and len(all_streams) == 2,
        video_stream_count=len(video_streams),
        audio_stream_count=len(audio_streams),
        total_stream_count=len(all_streams),
    )

    format_info = output_meta.get("format") if isinstance(output_meta.get("format"), dict) else {}
    format_names = set(str(format_info.get("format_name", "")).split(","))
    add_check(
        checks,
        "container_spec",
        "mp4" in format_names and str(output).endswith(".mp4"),
        detected_format_count=len(format_names),
    )

    expected_video = target.get("video") if isinstance(target.get("video"), dict) else {}
    video = video_streams[0] if len(video_streams) == 1 else {}
    expected_fps = exact_fraction(expected_video.get("fps"))
    actual_fps = exact_fraction(video.get("avg_frame_rate"))
    video_ok = (
        video.get("codec_name") == expected_video.get("codec_name")
        and video.get("pix_fmt") == expected_video.get("pixel_format")
        and video.get("width") == expected_video.get("width")
        and video.get("height") == expected_video.get("height")
        and actual_fps is not None
        and expected_fps is not None
        and actual_fps == expected_fps
    )
    add_check(
        checks,
        "video_spec",
        video_ok,
        codec_name=video.get("codec_name"),
        width=video.get("width"),
        height=video.get("height"),
        pixel_format=video.get("pix_fmt"),
        average_frame_rate=video.get("avg_frame_rate"),
    )

    expected_audio = target.get("audio") if isinstance(target.get("audio"), dict) else {}
    audio = audio_streams[0] if len(audio_streams) == 1 else {}
    audio_ok = (
        audio.get("codec_name") == expected_audio.get("codec_name")
        and str(audio.get("sample_rate")) == str(expected_audio.get("sample_rate_hz"))
        and audio.get("channels") == expected_audio.get("channels")
    )
    add_check(
        checks,
        "audio_spec",
        audio_ok,
        codec_name=audio.get("codec_name"),
        sample_rate=audio.get("sample_rate"),
        channels=audio.get("channels"),
    )

    input_format = input_meta.get("format") if isinstance(input_meta.get("format"), dict) else {}
    input_duration = duration(input_format.get("duration"))
    output_duration = duration(format_info.get("duration"))
    video_duration = duration(video.get("duration"))
    audio_duration = duration(audio.get("duration"))
    tolerance = target.get("duration_tolerance_seconds")
    duration_ok = isinstance(tolerance, (int, float)) and input_duration is not None
    for candidate in (output_duration, video_duration, audio_duration):
        if candidate is None or not duration_ok or abs(candidate - input_duration) > float(tolerance):
            duration_ok = False
    add_check(
        checks,
        "duration_spec",
        duration_ok,
        input_duration_seconds=input_duration,
        output_duration_seconds=output_duration,
        video_duration_seconds=video_duration,
        audio_duration_seconds=audio_duration,
    )

    input_size = source.stat().st_size if source.is_file() else 0
    output_size = output.stat().st_size if output_regular else 0
    max_size = target.get("max_output_size_bytes")
    minimum_reduction = target.get("minimum_size_reduction_ratio")
    reduction = (input_size - output_size) / input_size if input_size > 0 else -1.0
    size_ok = (
        isinstance(max_size, int)
        and isinstance(minimum_reduction, (int, float))
        and 0 < output_size <= max_size
        and reduction >= float(minimum_reduction)
    )
    add_check(
        checks,
        "size_spec",
        size_ok,
        input_size_bytes=input_size,
        output_size_bytes=output_size,
        reduction_ratio=round(reduction, 6),
    )

    decoded = output_regular and decode_ok(output, args.ffmpeg)
    add_check(checks, "decodable", decoded, complete_decode=decoded)

    minimum_ssim = target.get("minimum_video_ssim")
    minimum_audio_snr = target.get("minimum_audio_snr_db")
    measured_ssim = None
    measured_audio_snr = None
    if output_regular and decoded:
        measured_ssim = video_ssim(source, output, args.ffmpeg)
        measured_audio_snr = audio_snr(source, output, args.ffmpeg)
    content_fidelity_ok = (
        isinstance(minimum_ssim, (int, float))
        and isinstance(minimum_audio_snr, (int, float))
        and measured_ssim is not None
        and measured_audio_snr is not None
        and measured_ssim >= float(minimum_ssim)
        and measured_audio_snr >= float(minimum_audio_snr)
    )
    add_check(
        checks,
        "content_fidelity",
        content_fidelity_ok,
        video_ssim=measured_ssim,
        minimum_video_ssim=minimum_ssim,
        audio_snr_db=measured_audio_snr,
        minimum_audio_snr_db=minimum_audio_snr,
    )

    after = state_sha256(workspace)
    add_check(checks, "verifier_non_mutation", before == after, state_unchanged=before == after)
    passed = all(item.get("passed") is True for item in checks.values())
    result = {
        "schema_version": "nami_work_case18_verdict_v1",
        "verdict": "accept" if passed else "reject",
        "checks": checks,
        "workspace_state_sha256_before": before,
        "workspace_state_sha256_after": after,
    }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        fallback = {
            "schema_version": "nami_work_case18_verdict_v1",
            "verdict": "invalid",
            "checks": {"verifier_runtime": {"passed": False, "details": {"error_type": type(exc).__name__}}},
            "workspace_state_sha256_before": "0" * 64,
            "workspace_state_sha256_after": "0" * 64,
        }
        print(json.dumps(fallback, sort_keys=True))
        raise SystemExit(2)
