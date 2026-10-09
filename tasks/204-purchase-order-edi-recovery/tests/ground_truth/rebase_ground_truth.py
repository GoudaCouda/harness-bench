#!/usr/bin/env python3
"""Rebase the existing adjudicated plan after reducing redundant 850 traffic."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


TASK = Path(__file__).resolve().parents[2]
WORKSPACE = TASK / "workspace"
GROUND_TRUTH = TASK / "tests/ground_truth/ground_truth.json"


def controller():
    spec = importlib.util.spec_from_file_location("poedictl_rebase", WORKSPACE / "poedictl.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot import controller")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    module = controller()
    truth = json.loads(GROUND_TRUTH.read_text(encoding="utf-8"))
    plan = truth["plan"]
    deliveries = module.load_deliveries()
    retained_ids = {str(row["delivery_id"]) for row in deliveries}
    plan["event_dispositions"] = [
        row for row in plan["event_dispositions"] if str(row["delivery_id"]) in retained_ids
    ]
    for decision in plan["po_decisions"]:
        decision["evidence_refs"] = [
            ref
            for ref in decision["evidence_refs"]
            if not ref.startswith("evidence/edi_deliveries.jsonl#")
            or ref.rsplit("#", 1)[-1] in retained_ids
        ]
    _, facts = module.validation_report(plan)
    plan["source_checkpoint"] = facts["source_checkpoint"]
    problems, _ = module.validation_report(plan)
    if problems:
        raise SystemExit(json.dumps(problems, indent=2, sort_keys=True))
    GROUND_TRUTH.write_text(
        json.dumps({"schema_version": 1, "plan": plan}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
