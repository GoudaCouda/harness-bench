#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import multiprocessing
import re
import sys

from harnessbench.grading.pure_function import audit_pure_function, run_pure_function

if sys.version_info[:2] != (3, 10):
    raise SystemExit(f"expected grader CPython 3.10, found {sys.version}")

source = """import re

def canonical_archive_manifest(entries, source_date_epoch, build_root):
    if not re.fullmatch(r"[a-z]+", build_root):
        raise ValueError("root")
    return sorted(entries, key=lambda row: row["path"])
"""
tree = ast.parse(source)
if not any(isinstance(node, ast.Import) for node in ast.walk(tree)):
    raise SystemExit("AST import probe failed")
safe, detail = audit_pure_function(
    source,
    "canonical_archive_manifest",
    allowed_imports=("re",),
    allowed_methods=("fullmatch",),
    max_nodes=7000,
)
if not safe:
    raise SystemExit(f"pure-function audit probe failed: {detail}")
result, detail = run_pure_function(
    source,
    "canonical_archive_manifest",
    [{"entries": [{"path": "b"}, {"path": "a"}], "source_date_epoch": 0, "build_root": "root"}],
    ("entries", "source_date_epoch", "build_root"),
    allowed_imports=("re",),
)
if not result or result[0].get("value") != [{"path": "a"}, {"path": "b"}]:
    raise SystemExit(f"isolated pure-function replay probe failed: {detail}")
if multiprocessing.get_context("spawn").get_start_method() != "spawn":
    raise SystemExit("spawn worker probe failed")

print(json.dumps({"python3": "3.10", "ast": "passed", "pure_function": "passed", "isolated_replay": "passed"}, sort_keys=True))
