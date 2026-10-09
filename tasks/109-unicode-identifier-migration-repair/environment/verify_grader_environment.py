#!/usr/bin/env python3
from __future__ import annotations

import json
import multiprocessing
import sys
import unicodedata

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

canonical = unicodedata.normalize(
    "NFKC",
    unicodedata.normalize("NFKC", "Straße").casefold(),
)
if canonical != "strasse" or not canonical.isidentifier():
    raise SystemExit("grader Unicode profile probe failed")
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
            "unicode_version": unicodedata.unidata_version,
            "nfkc_casefold": "passed",
            "fork": "passed",
        },
        sort_keys=True,
    )
)
