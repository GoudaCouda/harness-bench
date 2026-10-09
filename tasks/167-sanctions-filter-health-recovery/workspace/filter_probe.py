#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "filter_config.json"


def main() -> int:
    raw = CONFIG.read_bytes()
    config = json.loads(raw)
    normalized = unicodedata.normalize("NFKC", "ＡЛЬФА").casefold()
    checks = {
        "current_filter_revision": config.get("config_version") == "FILTER-8",
        "current_list_snapshot": config.get("list_version") == "LIST-2026-07-15",
        "non_latin_alias_normalization": config.get("alias_normalization")
        == "nfkc_casefold"
        and normalized == "aльфа",
        "probe_error_fails_closed": config.get("fail_closed_on_probe_error") is True,
        "clearance_role_is_least_privilege": config.get("authorized_clearance_roles")
        == ["compliance_officer"],
    }
    report = {
        "tool": "filter_probe/1",
        "config_sha256": hashlib.sha256(raw).hexdigest(),
        "checks": checks,
        "status": "pass" if all(checks.values()) else "fail",
    }
    (ROOT / "filter_probe_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
