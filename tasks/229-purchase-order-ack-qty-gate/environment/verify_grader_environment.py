#!/usr/bin/env python3
"""Verify the shared grader runtime for 229-purchase-order-ack-qty-gate."""

import json
import sys

import yaml
from harnessbench.grading.deterministic_oracle import score_workspace_from_spec
from harnessbench.grading.outcome_cases import score_workspace_from_cases
from harnessbench.grading.task_checks import (
    observation,
    sources_unchanged,
    workspace_redline_violations,
)


def main() -> None:
    if sys.version_info[:2] != (3, 10):
        raise SystemExit(f"expected grader CPython 3.10, found {sys.version}")
    if not str(yaml.__version__).startswith("6."):
        raise SystemExit(f"expected PyYAML 6.x, found {yaml.__version__}")
    if yaml.safe_load("pass_threshold: 0.8\n")["pass_threshold"] != 0.8:
        raise SystemExit("grader YAML probe failed")
    apis = (
        score_workspace_from_spec,
        score_workspace_from_cases,
        observation,
        sources_unchanged,
        workspace_redline_violations,
    )
    if not all(callable(value) for value in apis):
        raise SystemExit("grader API import probe failed")
    print(json.dumps({"grader": "passed", "task_id": "229-purchase-order-ack-qty-gate"}, sort_keys=True))


if __name__ == "__main__":
    main()
