#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path


def load_json(root: Path, relative: str):
    return json.loads((root / relative).read_text(encoding="utf-8"))


def evaluate(config, root):
    graph = load_json(root, "repo/graph.json")
    sample_rows = load_json(root, "repo/sample_rows.json")
    dependencies = {
        dependency
        for values in graph.values()
        for dependency in values
    }
    branch_heads = sorted(set(graph) - dependencies)
    app = branch_heads[0].split(".", 1)[0]
    migration_numbers = [
        int(re.search(r"\.(\d+)_", name).group(1))
        for name in branch_heads
    ]
    topics = {name.rsplit("_", 1)[-1] for name in branch_heads}
    topic = next(iter(topics)) if len(topics) == 1 else "branches"
    merge_name = f"{app}.{max(migration_numbers) + 1:04d}_merge_{topic}"
    merge = config.get("merge") or {}
    merge_dependencies = merge.get("dependencies") or []

    repaired_graph = dict(graph)
    if merge.get("name"):
        repaired_graph[merge["name"]] = list(merge_dependencies)
    repaired_dependencies = {
        dependency
        for values in repaired_graph.values()
        for dependency in values
    }
    final_heads = sorted(set(repaired_graph) - repaired_dependencies)
    graph_valid = (
        merge.get("name") == merge_name
        and len(merge_dependencies) == len(set(merge_dependencies))
        and set(merge_dependencies) == set(branch_heads)
        and final_heads == [merge_name]
    )

    def forward(rows):
        result = copy.deepcopy(rows)
        for row in result:
            if row.get("region") is None:
                row["region"] = {"CA": "NA", "US": "NA"}.get(
                    row.get("country"),
                    "OTHER",
                )
                row["_migration_owned"] = True
            elif not config.get("idempotent"):
                row["region"] = "OVERWRITTEN"
        return result

    first = forward(sample_rows)
    second = forward(first)
    manual_preserved = next(
        row for row in first if row["id"] == "o2"
    )["region"] == "manual"
    reverse_rows = copy.deepcopy(first)
    if config.get("reverse") == "restore_null_region":
        for row in reverse_rows:
            if row.pop("_migration_owned", False):
                row["region"] = None
    reverse_ok = all(
        row.get("region") == original.get("region")
        for row, original in zip(reverse_rows, sample_rows)
    )
    fresh_ok = graph_valid and bool(config.get("uses_historical_model"))
    upgrade_ok = (
        fresh_ok
        and manual_preserved
        and next(row for row in first if row["id"] == "o1")["region"] == "NA"
    )
    idempotent_ok = config.get("idempotent") is True and first == second

    return {
        "heads": config.get("heads") == final_heads and graph_valid,
        "merge": graph_valid,
        "uses_historical_model": config.get("uses_historical_model") is True,
        "idempotent": idempotent_ok,
        "reverse": reverse_ok,
        "fresh_replay": (
            fresh_ok and config.get("fresh_replay") == "pass"
        ),
        "upgrade_replay": (
            upgrade_ok and config.get("upgrade_replay") == "pass"
        ),
    }


if __name__ == "__main__":
    candidate = Path(sys.argv[1])
    fixture_root = Path(__file__).resolve().parents[1]
    config = json.loads(candidate.read_text(encoding="utf-8"))
    print(json.dumps(evaluate(config, fixture_root), sort_keys=True))
