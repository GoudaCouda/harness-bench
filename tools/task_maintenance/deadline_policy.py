from __future__ import annotations

import argparse
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import yaml


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TASKS_DIR = ROOT / "tasks"
INPUT_BYTES_THRESHOLD = 12 * 1024
INPUT_NEWLINES_THRESHOLD = 300
MINIMUM_ROUND_TIMEOUT = 1800
_TIMEOUT_LINE = re.compile(
    r"^(timeout_sec:[ \t]*)([0-9]+)([^\r\n]*)$",
    flags=re.MULTILINE,
)


@dataclass(frozen=True)
class FixtureMetrics:
    """Byte-level size of every regular, agent-visible fixture file."""

    files: int
    bytes: int
    newlines: int


@dataclass(frozen=True)
class DeadlineDecision:
    """Deterministic deadline decision for one task."""

    task_id: str
    flags: Mapping[str, bool]
    fixture_metrics: FixtureMetrics
    existing_timeout: int
    floor: int
    effective_timeout: int

    @property
    def flag_count(self) -> int:
        return sum(self.flags.values())

    @property
    def changed(self) -> bool:
        return self.effective_timeout != self.existing_timeout


def _list_size(value: object) -> int:
    return len(value) if isinstance(value, list) else 0


def _workspace_root(task_dir: Path, metadata: Mapping[str, object]) -> Path:
    raw_name = str(metadata.get("workspace_dir") or "workspace")
    relative = Path(raw_name)
    if relative.is_absolute() or ".." in relative.parts or len(relative.parts) != 1:
        raise ValueError("workspace_dir must be one safe task-relative directory")
    return task_dir / relative


def measure_agent_visible_fixtures(
    task_dir: Path,
    metadata: Mapping[str, object],
) -> FixtureMetrics:
    """Count regular agent-visible seed files without following symlinks.

    Newlines are counted as literal ``b"\n"`` bytes, so this measurement is
    encoding-independent and reproducible for text and binary fixtures alike.
    """

    workspace_root = _workspace_root(task_dir, metadata)
    if not workspace_root.is_dir():
        return FixtureMetrics(files=0, bytes=0, newlines=0)

    files = 0
    total_bytes = 0
    total_newlines = 0
    for path in sorted(workspace_root.rglob("*")):
        if path.is_symlink() or not path.is_file():
            continue
        payload = path.read_bytes()
        files += 1
        total_bytes += len(payload)
        total_newlines += payload.count(b"\n")
    return FixtureMetrics(
        files=files,
        bytes=total_bytes,
        newlines=total_newlines,
    )


def deadline_flags(
    metadata: Mapping[str, object],
    fixture_metrics: FixtureMetrics,
) -> dict[str, bool]:
    """Return the four policy flags in their stable H/A/I/S order."""

    demands = _list_size(metadata.get("harness_demands"))
    stressors = _list_size(metadata.get("stressors"))
    return {
        "H": str(metadata.get("difficulty") or "").strip().casefold() == "hard",
        "A": _list_size(metadata.get("required_artifacts")) >= 4,
        "I": (
            fixture_metrics.bytes >= INPUT_BYTES_THRESHOLD
            or fixture_metrics.newlines >= INPUT_NEWLINES_THRESHOLD
        ),
        "S": stressors >= 4 or demands >= 6,
    }


def deadline_floor(flags: Mapping[str, bool]) -> int:
    """Return the model-independent minimum budget for every agent round.

    H/A/I/S remain useful workload descriptors, but they must not reduce the
    execution budget. A task that looks small statically can still require a
    long model turn, and applying shorter deadlines to those tasks creates a
    harness-dependent censoring boundary rather than a difficulty signal.
    Existing longer, manually reviewed deadlines are preserved by
    :func:`evaluate_deadline`.
    """

    # Touch every known key so a partial mapping cannot accidentally become a
    # second policy path.
    tuple(bool(flags.get(name, False)) for name in ("H", "A", "I", "S"))
    return MINIMUM_ROUND_TIMEOUT


def _existing_timeout(metadata: Mapping[str, object]) -> int:
    value = metadata.get("timeout_sec")
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError("timeout_sec must be a positive integer")
    return value


def evaluate_deadline(
    task_dir: Path,
    metadata: Mapping[str, object],
) -> DeadlineDecision:
    """Evaluate one task; the effective timeout can only increase."""

    metrics = measure_agent_visible_fixtures(task_dir, metadata)
    flags = deadline_flags(metadata, metrics)
    floor = deadline_floor(flags)
    existing = _existing_timeout(metadata)
    return DeadlineDecision(
        task_id=str(metadata.get("task_id") or task_dir.name),
        flags=flags,
        fixture_metrics=metrics,
        existing_timeout=existing,
        floor=floor,
        effective_timeout=max(existing, floor),
    )


def iter_task_yamls(tasks_dir: Path) -> Iterable[Path]:
    yield from sorted(tasks_dir.glob("*/task.yaml"))


def load_decision(task_yaml: Path) -> DeadlineDecision:
    metadata = yaml.safe_load(task_yaml.read_text(encoding="utf-8")) or {}
    if not isinstance(metadata, dict):
        raise ValueError("task.yaml must contain a mapping")
    return evaluate_deadline(task_yaml.parent, metadata)


def rewrite_timeout_text(text: str, effective_timeout: int) -> str:
    """Replace exactly one scalar timeout while preserving YAML formatting."""

    rewritten, replacements = _TIMEOUT_LINE.subn(
        rf"\g<1>{effective_timeout}\g<3>",
        text,
    )
    if replacements != 1:
        raise ValueError(
            "task.yaml must contain exactly one unquoted integer timeout_sec"
        )
    return rewritten


def _format_distribution(decisions: Sequence[DeadlineDecision]) -> str:
    counts = Counter(item.effective_timeout for item in decisions)
    return ",".join(f"{timeout}:{counts[timeout]}" for timeout in sorted(counts))


def _format_flags(flags: Mapping[str, bool]) -> str:
    return "".join(name for name in ("H", "A", "I", "S") if flags[name]) or "-"


def run(tasks_dir: Path, *, write: bool) -> int:
    task_yamls = list(iter_task_yamls(tasks_dir))
    if not task_yamls:
        print(f"ERROR no task.yaml files found below {tasks_dir}")
        return 2

    loaded: list[tuple[Path, DeadlineDecision]] = []
    failures: list[str] = []
    for task_yaml in task_yamls:
        try:
            loaded.append((task_yaml, load_decision(task_yaml)))
        except (OSError, ValueError, yaml.YAMLError) as exc:
            failures.append(f"{task_yaml}: {exc}")

    for failure in failures:
        print(f"ERROR {failure}")
    if failures:
        return 2

    decisions = [item for _, item in loaded]
    changed = [(task_yaml, item) for task_yaml, item in loaded if item.changed]
    rewrites: dict[Path, str] = {}
    if write:
        for task_yaml, item in changed:
            try:
                original = task_yaml.read_text(encoding="utf-8")
                rewrites[task_yaml] = rewrite_timeout_text(
                    original,
                    item.effective_timeout,
                )
            except (OSError, ValueError) as exc:
                failures.append(f"{task_yaml}: {exc}")
        for failure in failures:
            print(f"ERROR {failure}")
        if failures:
            return 2

    all_flags = [
        item.task_id.split("-", 1)[0] for item in decisions if item.flag_count == 4
    ]
    for task_yaml, item in changed:
        print(
            f"{'WRITE' if write else 'NEEDS_UPDATE'} {item.task_id}: "
            f"{item.existing_timeout}->{item.effective_timeout} "
            f"floor={item.floor} flags={_format_flags(item.flags)}"
        )
        if write:
            task_yaml.write_text(rewrites[task_yaml], encoding="utf-8")

    print(f"tasks={len(decisions)}")
    print(f"changed={len(changed)}")
    print(f"all_flags={','.join(all_flags)}")
    print(f"effective_distribution={_format_distribution(decisions)}")
    return 0 if write or not changed else 1


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Check or normalize deterministic HarnessBench deadlines."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--check",
        action="store_true",
        help="exit nonzero when a task timeout is below its policy floor",
    )
    mode.add_argument(
        "--write",
        action="store_true",
        help="raise noncompliant timeouts to their policy floor",
    )
    parser.add_argument(
        "--tasks-dir",
        type=Path,
        default=DEFAULT_TASKS_DIR,
        help=f"task suite root (default: {DEFAULT_TASKS_DIR})",
    )
    args = parser.parse_args()
    raise SystemExit(run(args.tasks_dir.resolve(), write=args.write))


if __name__ == "__main__":
    main()
