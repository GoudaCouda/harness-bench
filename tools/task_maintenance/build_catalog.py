from __future__ import annotations

import argparse
import csv
import io
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

from common import (
    TASK_ROOTS,
    is_local_runtime_artifact,
    oracle_definition,
    pre_agent_score,
)


ROOT = Path(__file__).resolve().parents[2]
CATALOG_CSV = ROOT / "catalog" / "task_catalog.csv"
SUITE_YAML = ROOT / "catalog" / "suite.yaml"

SCALAR_STAT_FIELDS = (
    "domain",
    "difficulty",
    "task_family",
    "variant",
)
LIST_STAT_FIELDS = (
    "harness_demands",
    "capability_tags",
    "stressors",
)
UNSPECIFIED = "(unspecified)"


def catalog_workspace_files(workspace_dir: Path) -> list[Path]:
    """Return deterministic agent-visible files, excluding local run caches."""
    if not workspace_dir.exists():
        return []
    return [
        path
        for path in workspace_dir.rglob("*")
        if path.is_file()
        and not is_local_runtime_artifact(path.relative_to(workspace_dir))
    ]


def prompt_text(task_dir: Path, data: dict[str, Any]) -> str:
    names = data.get("prompt_files") or [data.get("prompt_file", "prompt.txt")]
    return "\n".join(
        (task_dir / name).read_text(encoding="utf-8", errors="replace")
        for name in names
        if (task_dir / name).is_file()
    )


def collect_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for collection, task_root in TASK_ROOTS.items():
        for task_yaml in sorted(task_root.glob("*/task.yaml")):
            task_dir = task_yaml.parent
            data = yaml.safe_load(task_yaml.read_text(encoding="utf-8")) or {}
            provenance = data.get("provenance") or {}
            prompt = prompt_text(task_dir, data)
            workspace_dir = task_dir / data.get("workspace_dir", "workspace")
            workspace_files = catalog_workspace_files(workspace_dir)
            oracle_kind, oracle_path = oracle_definition(task_dir, data)
            baseline, _, _, baseline_error = pre_agent_score(task_dir, data)
            rows.append(
                {
                    "task_id": str(data["task_id"]),
                    "title": data.get("title", data["task_id"]),
                    "domain": data.get("domain", ""),
                    "collection": collection,
                    "difficulty": data.get("difficulty", ""),
                    "task_family": data.get("task_family", ""),
                    "variant": data.get("variant", ""),
                    "capability_tags": "|".join(data.get("capability_tags", []) or []),
                    "harness_demands": "|".join(data.get("harness_demands", []) or []),
                    "stressors": "|".join(data.get("stressors", []) or []),
                    "required_artifacts": "|".join(
                        data.get("required_artifacts", []) or []
                    ),
                    "design_file": data.get("design_file")
                    or ("design.md" if (task_dir / "design.md").is_file() else ""),
                    "provenance_origin": provenance.get("origin", ""),
                    "source_ids": "|".join(provenance.get("source_ids", []) or []),
                    "prompt_words": len(prompt.split()),
                    "workspace_files": len(workspace_files),
                    "workspace_bytes": sum(
                        path.stat().st_size for path in workspace_files
                    ),
                    "oracle_lines": len(
                        oracle_path.read_text(
                            encoding="utf-8", errors="replace"
                        ).splitlines()
                    ),
                    "oracle_kind": oracle_kind,
                    "untouched_workspace_score": (
                        "" if baseline is None else f"{baseline:.3f}"
                    ),
                    "baseline_error": baseline_error,
                }
            )
    return sorted(rows, key=lambda row: row["task_id"])


def _scalar_counts(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    counts = Counter(str(row.get(field) or UNSPECIFIED) for row in rows)
    return dict(sorted(counts.items()))


def _list_counts(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in rows:
        values = {
            value.strip()
            for value in str(row.get(field) or "").split("|")
            if value.strip()
        }
        counts.update(values)
    return dict(sorted(counts.items()))


def suite_payload(rows: list[dict[str, Any]]) -> dict[str, Any]:
    main_rows = [row for row in rows if row["collection"] == "main"]
    task_ids = [str(row["task_id"]) for row in main_rows]
    duplicates = sorted(
        task_id for task_id, count in Counter(task_ids).items() if count > 1
    )
    if duplicates:
        raise RuntimeError(f"duplicate main task IDs: {duplicates}")
    return {
        "schema_version": 1,
        "suite": "main",
        "suite_size": len(task_ids),
        "task_ids": task_ids,
        "statistics": {
            **{field: _scalar_counts(main_rows, field) for field in SCALAR_STAT_FIELDS},
            **{field: _list_counts(main_rows, field) for field in LIST_STAT_FIELDS},
        },
    }


def render_catalog(rows: list[dict[str, Any]]) -> tuple[str, str]:
    if not rows:
        raise RuntimeError("no task metadata found")
    csv_buffer = io.StringIO(newline="")
    writer = csv.DictWriter(
        csv_buffer,
        fieldnames=list(rows[0]),
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerows(rows)
    suite_text = yaml.safe_dump(
        suite_payload(rows),
        sort_keys=False,
        allow_unicode=True,
        width=1000,
    )
    return csv_buffer.getvalue(), suite_text


def write_catalog(rows: list[dict[str, Any]]) -> None:
    csv_text, suite_text = render_catalog(rows)
    CATALOG_CSV.parent.mkdir(parents=True, exist_ok=True)
    CATALOG_CSV.write_text(csv_text, encoding="utf-8")
    SUITE_YAML.write_text(suite_text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail without writing if the checked-in catalog is stale",
    )
    args = parser.parse_args()
    rows = collect_rows()
    if args.check:
        csv_text, suite_text = render_catalog(rows)
        stale = [
            path
            for path, expected in (
                (CATALOG_CSV, csv_text),
                (SUITE_YAML, suite_text),
            )
            if not path.is_file() or path.read_text(encoding="utf-8") != expected
        ]
        if stale:
            for path in stale:
                print(f"STALE {path}")
            return 1
        print(f"current {CATALOG_CSV}")
        print(f"current {SUITE_YAML}")
        return 0

    write_catalog(rows)
    print(f"wrote {CATALOG_CSV}")
    print(f"wrote {SUITE_YAML}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
