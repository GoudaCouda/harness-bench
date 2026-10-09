#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timezone
import json
import multiprocessing
import sys
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml

from harnessbench.grading.pure_function import (
    audit_pure_function,
    expected_results,
    run_pure_function,
)
from harnessbench.grading.task_checks import (
    explicit_external_action_claims,
    observation,
    sources_unchanged,
    workspace_redline_violations,
)


if sys.version_info[:2] != (3, 10):
    raise SystemExit(f"expected grader CPython 3.10, found {sys.version}")

try:
    zone = ZoneInfo("America/New_York")
except ZoneInfoNotFoundError as exc:
    raise SystemExit(f"grader IANA timezone database is incomplete: {exc}") from exc
early = datetime(2026, 11, 1, 1, 30, tzinfo=zone, fold=0).astimezone(timezone.utc)
late = datetime(2026, 11, 1, 1, 30, tzinfo=zone, fold=1).astimezone(timezone.utc)
if early == late:
    raise SystemExit("grader PEP 495 fold probe failed")
if multiprocessing.get_context("fork").get_start_method() != "fork":
    raise SystemExit("grader pure worker requires POSIX fork")
if yaml.safe_load("pass_threshold: 0.8\n")["pass_threshold"] != 0.8:
    raise SystemExit("grader YAML probe failed")
if not all(
    callable(value)
    for value in (
        audit_pure_function,
        expected_results,
        run_pure_function,
        explicit_external_action_claims,
        observation,
        sources_unchanged,
        workspace_redline_violations,
    )
):
    raise SystemExit("grader API import probe failed")

print(
    json.dumps(
        {
            "python3": "3.10",
            "zoneinfo": "passed",
            "pep495_fold": "passed",
            "fork": "passed",
        },
        sort_keys=True,
    )
)
