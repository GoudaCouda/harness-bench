#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sys
from urllib.parse import urldefrag, urljoin

import yaml

from harnessbench.grading.task_checks import (
    observation,
    sources_unchanged,
    substantive_prose,
    workspace_redline_violations,
)


if sys.version_info[:2] != (3, 10):
    raise SystemExit(f"expected grader CPython 3.10, found {sys.version}")

resolved = urljoin("https://schemas.example/catalog/orders/order.json", "../common/address.json#address")
target, fragment = urldefrag(resolved)
if (target, fragment) != ("https://schemas.example/catalog/common/address.json", "address"):
    raise SystemExit("grader JSON Schema URI-resolution probe failed")
schema = json.loads('{"$id":"order.json","required":["ship_to"]}')
if schema["required"] != ["ship_to"]:
    raise SystemExit("grader JSON Schema parser probe failed")
if len(hashlib.sha256(json.dumps(schema, sort_keys=True).encode()).hexdigest()) != 64:
    raise SystemExit("grader schema-graph hash probe failed")
if yaml.safe_load("pass_threshold: 0.8\n")["pass_threshold"] != 0.8:
    raise SystemExit("grader YAML probe failed")
if not all(
    callable(value)
    for value in (
        observation,
        sources_unchanged,
        substantive_prose,
        workspace_redline_violations,
    )
):
    raise SystemExit("grader schema oracle API import probe failed")

print(json.dumps({"python3": "3.10", "uri_resolution": "passed", "json": "passed", "sha256": "passed", "yaml": "passed"}, sort_keys=True))
