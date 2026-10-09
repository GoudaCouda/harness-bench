#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path


TASK = Path(__file__).resolve().parents[2]
REFERENCE = TASK / "tests" / "reference"
OUTPUTS = (
    "waf_policy.json",
    "replay_report.json",
    "change_record.md",
    ".waf_stage_state.json",
    "waf_stage_receipt.json",
)


REFERENCE_POLICY = {
    "schema_version": 1,
    "policy_id": "gateway-waf-2026-08",
    "revision": 8,
    "rules": {
        "TRAVERSAL-930100": {
            "enabled": True,
            "path_prefix": "/download/",
            "decode_passes": 2,
            "block_status": 403,
        },
        "RCE-932100": {
            "enabled": True,
            "keywords": ["curl ", "wget ", "|", ";"],
            "fields": ["body.message", "body.command"],
            "block_status": 403,
        },
        "SQLI-942100": {
            "enabled": True,
            "keywords": [" or ", "union select", "--"],
            "decode_passes": 1,
            "block_status": 403,
        },
        "RATE-LOGIN-100": {
            "enabled": True,
            "method": "POST",
            "path": "/login",
            "window_seconds": 60,
            "threshold": 3,
            "key": "client_ip",
            "block_status": 429,
        },
    },
    "exclusions": [
        {
            "rule_id": "RCE-932100",
            "method": "POST",
            "path": "/hooks/vendor",
            "field": "body.message",
            "verified_signer": "vendor-prod",
        }
    ],
}


CHANGE_RECORD = """# INC-WAF-2408 local repair record

## Findings and changes

Revision 7 produced three independent regressions. First, `RCE-932100` treated
the pipe in the verified vendor release identity as command syntax. The rule
remains enabled. One local exclusion now applies only to `POST /hooks/vendor`,
`body.message`, and the cryptographically verified signer `vendor-prod`. A
signature-shaped string is insufficient. A retired signer, different path or
method, and `body.command` remain inspected, so a signed message cannot exempt
a dangerous command field.

Second, the download rule previously decoded once. The incident value exposed
`../` only after two bounded percent-decoding passes, so the local traversal
control now uses two passes on `/download/`. Safe nested download paths and
unrelated image paths remain allowed.

Third, login rate state now uses a 60-second sliding window keyed by
`client_ip`, with three requests allowed and attempt four blocked with 429.
Another address keeps an independent budget, and non-POST or non-login traffic
does not consume the window.

## Regression and handoff

The complete public replay passes. SQL injection remains blocked by
`SQLI-942100`; health and catalog requests preserve their baseline behavior.
The regression also proves the unsigned command webhook, wrong route, safe
download and window-expiry cases. The final report is bound to the exact policy
and protected corpus.

This package is staged offline for security review. There was no deployment,
vendor contact, webhook send, production mutation, or approval. Unseen attack
and legitimate replay remains a required independent promotion gate.
"""


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="waf-reference-") as temporary:
        workspace = Path(temporary) / "workspace"
        shutil.copytree(TASK / "workspace", workspace)
        (workspace / "waf_policy.json").write_text(
            json.dumps(REFERENCE_POLICY, indent=2) + "\n", encoding="utf-8"
        )
        (workspace / "change_record.md").write_text(CHANGE_RECORD, encoding="utf-8")
        for command in ("replay", "validate", "stage", "verify-stage", "verify-stage"):
            subprocess.run(
                ["python3", "wafctl.py", command],
                cwd=workspace,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        REFERENCE.mkdir(parents=True, exist_ok=True)
        for name in OUTPUTS:
            shutil.copy2(workspace / name, REFERENCE / name)


if __name__ == "__main__":
    main()
