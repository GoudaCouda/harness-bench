#!/usr/bin/env python3
from __future__ import annotations

from collections import defaultdict, deque
import hashlib
import hmac
import json
import sys
from urllib.parse import unquote

import yaml

from harnessbench.grading.outcome_cases import score_workspace_from_cases
from harnessbench.grading.task_checks import (
    explicit_external_action_claims,
    observation,
    read_json_object,
    sources_unchanged,
)


if sys.version_info[:2] != (3, 10):
    raise SystemExit(f"expected grader CPython 3.10, found {sys.version}")

digest = hmac.new(b"k", b"body", hashlib.sha256).hexdigest()
if len(digest) != 64 or unquote("%2e%2e%2f") != "../":
    raise SystemExit("grader WAF replay primitives probe failed")
windows: dict[str, deque[int]] = defaultdict(deque)
windows["client"].append(7)
if windows["client"].popleft() != 7:
    raise SystemExit("grader sliding-window probe failed")
if yaml.safe_load("pass_threshold: 0.8\n")["pass_threshold"] != 0.8:
    raise SystemExit("grader YAML probe failed")
if not all(
    callable(value)
    for value in (
        score_workspace_from_cases,
        explicit_external_action_claims,
        observation,
        read_json_object,
        sources_unchanged,
    )
):
    raise SystemExit("grader API import probe failed")

print(
    json.dumps(
        {"python3": "3.10", "hmac_sha256": "passed", "url_decode": "passed", "yaml": "passed"},
        sort_keys=True,
    )
)
