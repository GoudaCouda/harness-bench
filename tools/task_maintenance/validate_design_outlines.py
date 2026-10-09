#!/usr/bin/env python3
"""Read-only admission checks for retained per-task design outlines.

The validator deliberately checks semantic anchors instead of whole-document
uniqueness. Shared headings and isolation boilerplate are expected; core
workflow, state, failure, and pilot sections must not collapse into identical
cross-family templates.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

import yaml


ROOT = Path(__file__).resolve().parents[2]
TASKS = ROOT / "tasks"
TASK_DIR = re.compile(r"^(?P<number>\d{3})-")
SECTION = re.compile(
    r"^## (?P<number>\d+)\. (?P<title>[^\n]+)\n",
    re.MULTILINE,
)
REQUIRED_SECTIONS = {
    1: "Workflow identity",
    2: "Idea provenance",
    3: "Real-workflow justification",
    4: "Agent-visible inputs",
    5: "Hidden ground truth",
    6: "Expected workflow",
    7: "Harness demands",
    8: "Stressors and difficulty",
    9: "Oracle design",
    10: "Leakage, isolation, and safety review",
    11: "Pilot plan",
    12: "Human validation status",
}
CORE_CROSS_FAMILY_SECTIONS = (3, 5, 6, 8, 11)
CORE_VARIANT_SECTIONS = (5, 6, 8)
STATE_ANCHOR = re.compile(
    r"\b(?:state|status|field|key|version|event|priority|precedence|"
    r"invariant|count|set|ledger|graph|revision|checkpoint|checksum|sha|"
    r"queue|decision|record)\b",
    re.IGNORECASE,
)
MARKDOWN_CODE = re.compile(r"`([^`\n]+)`")
NUMBERED_STEP = re.compile(r"^\d+\.\s+(.+)$", re.MULTILINE)
ADAPTATION_LINE = re.compile(
    r"^- \*\*Adaptation:\*\*\s*(?P<value>.+)$",
    re.MULTILINE,
)
PSEUDO_PATH_SUFFIX = re.compile(
    r"(?:"
    r"\.(?:json|jsonl|csv|md|txt|yaml|yml|py|sql|html?)"
    r"(?:\.\s+|\s+(?:and|or|apply|continue|create|update|produce|the)\b)"
    r"|/\s+(?:for|and|or)\b"
    r"|/\.\s+"
    r")",
    re.IGNORECASE,
)
GENERIC_ADAPTATIONS = {
    (
        "the public source supplied the workflow pattern only. rules, files, "
        "identities, organizations, dates, and records were newly synthesized "
        "for an offline deterministic task."
    ),
    ("the source workflow was abstracted into an offline deterministic scenario."),
}


def _normalize_body(value: str) -> str:
    return "\n".join(line.rstrip() for line in value.strip().splitlines())


def _number_token(value: object) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"oracle weight must be numeric, got {value!r}")
    return json.dumps(value, ensure_ascii=False)


def _adaptation_text(section: str) -> str:
    match = ADAPTATION_LINE.search(section)
    return match.group("value").strip() if match else ""


def _parse_sections(text: str) -> tuple[dict[int, str], dict[int, str], list[str]]:
    matches = list(SECTION.finditer(text))
    titles: dict[int, str] = {}
    bodies: dict[int, str] = {}
    errors: list[str] = []
    for index, match in enumerate(matches):
        number = int(match.group("number"))
        if number in bodies:
            errors.append(f"duplicate section number {number}")
            continue
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        titles[number] = match.group("title").strip()
        bodies[number] = _normalize_body(text[match.end() : end])
    return titles, bodies, errors


def _task_dirs(
    *,
    start: int | None,
    end: int | None,
    requested: set[str],
) -> list[Path]:
    selected: list[Path] = []
    for task_dir in sorted(TASKS.iterdir()):
        match = TASK_DIR.match(task_dir.name)
        if not task_dir.is_dir() or match is None:
            continue
        number = int(match.group("number"))
        if requested and task_dir.name not in requested:
            continue
        if start is not None and number < start:
            continue
        if end is not None and number > end:
            continue
        selected.append(task_dir)
    missing = requested - {path.name for path in selected}
    if missing:
        raise ValueError(f"unknown or filtered task IDs: {sorted(missing)}")
    return selected


def _read_runtime_declarations(task_dir: Path, metadata: Mapping[str, Any]) -> str:
    paths = [
        task_dir / str(metadata.get("hooks_module") or "hooks.py"),
        task_dir / "hooks.py",
    ]
    return "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in dict.fromkeys(paths)
        if path.is_file()
    )


def _table_code_paths(section: str) -> list[str]:
    """Return code-formatted paths from the first column of Markdown rows."""

    paths: list[str] = []
    for line in section.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if not cells:
            continue
        match = re.fullmatch(r"`([^`\n]+)`", cells[0])
        if match is not None:
            paths.append(match.group(1))
    return paths


def _normalized_relative_path(raw_path: str) -> str | None:
    normalized = raw_path.strip().replace("\\", "/").rstrip("/")
    if (
        not normalized
        or normalized.startswith("/")
        or normalized in {".", ".."}
        or any(part in {"", ".", ".."} for part in normalized.split("/"))
    ):
        return None
    return normalized


def _input_path_errors(
    task_dir: Path,
    section: str,
    metadata: Mapping[str, Any],
) -> list[str]:
    errors: list[str] = []
    runtime_text = _read_runtime_declarations(task_dir, metadata)
    workspace_dir = task_dir / str(metadata.get("workspace_dir") or "workspace")
    for raw_path in _table_code_paths(section):
        if raw_path != raw_path.strip():
            errors.append(f"pseudo input path has surrounding whitespace: {raw_path!r}")
            continue
        if PSEUDO_PATH_SUFFIX.search(raw_path):
            errors.append(f"pseudo input path contains prompt prose: {raw_path!r}")
            continue
        normalized = _normalized_relative_path(raw_path)
        if normalized is None:
            errors.append(
                f"agent-visible input is not a safe workspace-relative path: "
                f"{raw_path!r}"
            )
            continue
        workspace_path = workspace_dir / normalized
        if workspace_path.exists():
            continue
        runtime_needles = {
            normalized,
            Path(normalized).name,
        }
        if runtime_text and any(needle in runtime_text for needle in runtime_needles):
            continue
        errors.append(
            f"input path is neither in workspace/ nor hook-declared at runtime: "
            f"{raw_path!r}"
        )
    return errors


def _oracle_spec_errors(task_dir: Path, section: str) -> list[str]:
    spec_path = task_dir / "oracle_spec.json"
    if not spec_path.is_file():
        return []
    try:
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"cannot parse oracle_spec.json: {type(exc).__name__}: {exc}"]
    errors: list[str] = []
    for check in spec.get("checks", []):
        if not isinstance(check, dict):
            continue
        check_id = str(check.get("id") or "").strip()
        if check_id and f"`{check_id}`" not in section:
            errors.append(f"Section 9 omits oracle check ID {check_id!r}")
        try:
            weight = _number_token(check.get("weight"))
        except TypeError as exc:
            errors.append(str(exc))
            continue
        if f"raw=`{weight}`" not in section:
            errors.append(f"Section 9 omits raw weight {weight} for check {check_id!r}")
        cap = check.get("score_cap_on_fail")
        if cap is not None:
            cap_token = _number_token(cap)
            cap_markers = (
                f"score_cap_on_fail={cap_token}",
                f"fail-cap=`{cap_token}`",
            )
            if not any(marker in section for marker in cap_markers):
                errors.append(
                    f"Section 9 omits fail cap {cap_token} for check {check_id!r}"
                )
    if "`required_artifact_contract`" not in section:
        errors.append("Section 9 omits the shared required_artifact_contract gate")
    return errors


def _validate_one(
    task_dir: Path,
) -> tuple[dict[str, Any], dict[int, str], list[str]]:
    errors: list[str] = []
    task_yaml = task_dir / "task.yaml"
    design_path = task_dir / "design.md"
    if not task_yaml.is_file():
        return {}, {}, ["missing task.yaml"]
    metadata = yaml.safe_load(task_yaml.read_text(encoding="utf-8")) or {}
    if not design_path.is_file():
        return metadata, {}, ["missing design.md"]
    text = design_path.read_text(encoding="utf-8", errors="replace")
    titles, bodies, parse_errors = _parse_sections(text)
    errors.extend(parse_errors)
    for number, expected_title in REQUIRED_SECTIONS.items():
        if number not in bodies:
            errors.append(f"missing Section {number}: {expected_title}")
        elif titles[number] != expected_title:
            errors.append(
                f"Section {number} title is {titles[number]!r}, "
                f"expected {expected_title!r}"
            )
        elif not bodies[number]:
            errors.append(f"Section {number} is empty")
    if errors and not all(number in bodies for number in REQUIRED_SECTIONS):
        return metadata, bodies, errors

    human = bodies[12]
    if not re.search(r"\*\*Status:\*\*\s*`(?:pending|not_required)`", human):
        errors.append(
            "Section 12 must record human validation status `pending` or "
            "project-policy status `not_required`"
        )
    if re.search(r"\b(?:approved|complete)\b", human, re.IGNORECASE) and not re.search(
        r"\bnot complete\b|\bdoes not claim human approval\b",
        human,
        re.IGNORECASE,
    ):
        errors.append("Section 12 makes an unsupported approval/completion claim")

    adaptation = _adaptation_text(bodies[2])
    if not adaptation:
        errors.append("Section 2 omits the source-to-task adaptation statement")
    elif adaptation.casefold() in GENERIC_ADAPTATIONS:
        errors.append(
            "Section 2 uses a generic adaptation template instead of naming "
            "the task/family transformation"
        )

    hidden = bodies[5]
    hidden_tokens = MARKDOWN_CODE.findall(hidden)
    visible_inputs = {
        normalized
        for token in _table_code_paths(bodies[4])
        if (normalized := _normalized_relative_path(token)) is not None
    }
    hidden_paths = {
        normalized
        for token in hidden_tokens
        if (normalized := _normalized_relative_path(token)) is not None
    }
    if visible_inputs and visible_inputs.isdisjoint(hidden_paths):
        errors.append(
            "Section 5 must name at least one concrete agent-visible workspace input"
        )
    final_paths = {
        normalized
        for value in metadata.get("required_artifacts", []) or []
        if (
            normalized := _normalized_relative_path(
                str(value).strip().replace("\\", "/")
            )
        )
        is not None
    }
    if final_paths and final_paths.isdisjoint(hidden_paths):
        errors.append(
            "Section 5 must name at least one concrete required final workspace state"
        )
    if STATE_ANCHOR.search(hidden) is None:
        errors.append(
            "Section 5 must name a key, state, version/event priority, or invariant"
        )

    steps = NUMBERED_STEP.findall(bodies[6])
    if len(steps) < 3:
        errors.append("Section 6 must contain at least three numbered steps")
    anchored_steps = [
        step
        for step in steps
        if MARKDOWN_CODE.search(step)
        or re.search(r"\b(?:state|key|event|version)\b", step)
    ]
    if len(anchored_steps) < 3:
        errors.append(
            "Section 6 needs at least three steps with concrete files, "
            "entities, or state anchors"
        )

    oracle = bodies[9]
    if "`task-specific`" in oracle.casefold() or re.search(
        r"\|\s*task-specific\s*\|", oracle, re.IGNORECASE
    ):
        errors.append("Section 9 may not use placeholder weight `task-specific`")
    required_artifacts = [
        str(value).strip().replace("\\", "/").rstrip("/")
        for value in metadata.get("required_artifacts", []) or []
    ]
    for artifact in required_artifacts:
        if f"`{artifact}`" not in oracle:
            errors.append(
                f"Section 9 does not explicitly cover required artifact {artifact!r}"
            )
    errors.extend(_oracle_spec_errors(task_dir, oracle))
    errors.extend(_input_path_errors(task_dir, bodies[4], metadata))

    if "**Plausible failure mode:**" not in bodies[8]:
        errors.append("Section 8 omits a plausible failure mode")
    if "**Difficulty rationale:**" not in bodies[8]:
        errors.append("Section 8 omits a difficulty rationale")
    if "**Expected Gemma/OpenClaw failure modes:**" not in bodies[11]:
        errors.append("Section 11 omits expected model/harness failure modes")
    return metadata, bodies, errors


def _duplicate_errors(
    records: Iterable[tuple[Path, Mapping[str, Any], Mapping[int, str]]],
) -> list[str]:
    records = list(records)
    errors: list[str] = []
    by_adaptation: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for task_dir, metadata, bodies in records:
        adaptation = _normalize_body(_adaptation_text(str(bodies.get(2, ""))))
        family = str(metadata.get("task_family") or task_dir.name)
        if adaptation:
            by_adaptation[adaptation.casefold()].append((task_dir.name, family))
    for matches in by_adaptation.values():
        families = {family for _, family in matches}
        if len(families) > 1:
            errors.append(
                "Adaptation is identical across task families: "
                + ", ".join(task for task, _ in matches)
            )

    for section_number in CORE_CROSS_FAMILY_SECTIONS:
        by_body: dict[str, list[tuple[str, str]]] = defaultdict(list)
        for task_dir, metadata, bodies in records:
            body = _normalize_body(str(bodies.get(section_number, "")))
            family = str(metadata.get("task_family") or task_dir.name)
            if body:
                by_body[body].append((task_dir.name, family))
        for matches in by_body.values():
            families = {family for _, family in matches}
            if len(families) > 1:
                errors.append(
                    f"Section {section_number} is identical across task "
                    f"families: {', '.join(task for task, _ in matches)}"
                )

    by_family: dict[
        str,
        list[tuple[Path, Mapping[str, Any], Mapping[int, str]]],
    ] = defaultdict(list)
    for record in records:
        task_dir, metadata, _ = record
        family = str(metadata.get("task_family") or task_dir.name)
        by_family[family].append(record)
    for family, family_records in by_family.items():
        variants = {
            str(metadata.get("variant") or "standalone")
            for _, metadata, _ in family_records
        }
        if "base" not in variants or not any("stress" in value for value in variants):
            continue
        for section_number in CORE_VARIANT_SECTIONS:
            by_body: dict[str, list[str]] = defaultdict(list)
            for task_dir, _, bodies in family_records:
                body = _normalize_body(str(bodies.get(section_number, "")))
                if body:
                    by_body[body].append(task_dir.name)
            for matches in by_body.values():
                if len(matches) > 1:
                    errors.append(
                        f"family {family!r} base/stress variants share identical "
                        f"Section {section_number}: {', '.join(matches)}"
                    )
    return errors


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=int, help="first numeric task ID, inclusive")
    parser.add_argument("--end", type=int, help="last numeric task ID, inclusive")
    parser.add_argument(
        "--tasks",
        action="append",
        default=[],
        help="comma-separated exact task IDs; may be repeated",
    )
    args = parser.parse_args()
    if args.start is not None and args.end is not None and args.start > args.end:
        parser.error("--start must be <= --end")
    requested = {
        task_id.strip()
        for raw in args.tasks
        for task_id in raw.split(",")
        if task_id.strip()
    }
    try:
        task_dirs = _task_dirs(
            start=args.start,
            end=args.end,
            requested=requested,
        )
    except ValueError as exc:
        parser.error(str(exc))
    if not task_dirs:
        parser.error("no task directories selected")

    records: list[tuple[Path, Mapping[str, Any], Mapping[int, str]]] = []
    failures: list[str] = []
    for task_dir in task_dirs:
        metadata, bodies, errors = _validate_one(task_dir)
        records.append((task_dir, metadata, bodies))
        failures.extend(f"{task_dir.name}: {error}" for error in errors)
    failures.extend(_duplicate_errors(records))

    print(f"validated_designs={len(task_dirs)}")
    print(f"errors={len(failures)}")
    for failure in failures:
        print(f"FAIL {failure}")
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
