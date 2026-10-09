#!/usr/bin/env python3
from __future__ import annotations

import fnmatch
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY = json.loads((ROOT / "policy/context_policy.json").read_text())


def rules():
    result = []
    for raw in (ROOT / ".dockerignore").read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        negated = line.startswith("!")
        pattern = line[1:] if negated else line
        result.append((negated, pattern.lstrip("/")))
    return result


def matched(path, pattern):
    path = path.as_posix()
    pattern = pattern.rstrip("/")
    if "/" not in pattern:
        return any(fnmatch.fnmatch(part, pattern) for part in path.split("/"))
    return fnmatch.fnmatch(path, pattern) or path.startswith(pattern + "/")


def included(relative, parsed):
    keep = True
    for negated, pattern in parsed:
        if matched(relative, pattern):
            keep = negated
    return keep


def main():
    parsed = rules()
    files = []
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(ROOT)
        if relative.parts[0] in {"out"} or relative.as_posix() == "BUILD_CONTEXT_HANDOFF.md":
            continue
        if relative.as_posix().startswith("tools/") or relative.as_posix().startswith("policy/"):
            continue
        if included(relative, parsed):
            files.append(relative.as_posix())
    hashes = {
        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        for name in files
    }
    required = set(POLICY["required"])
    protected = set(POLICY["protected_excluded"])
    prefix_leaks = [
        name for name in files
        if any(name.startswith(prefix) for prefix in POLICY["excluded_prefixes"])
    ]
    result = {
        "schema_version": 1,
        "included": files,
        "sha256": hashes,
        "total_bytes": sum((ROOT / name).stat().st_size for name in files),
        "missing_required": sorted(required - set(files)),
        "protected_leaks": sorted(protected & set(files)),
        "prefix_leaks": sorted(prefix_leaks),
        "valid": required <= set(files) and not protected.intersection(files) and not prefix_leaks,
    }
    target = ROOT / POLICY["manifest"]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    raise SystemExit(0 if result["valid"] else 1)


if __name__ == "__main__":
    main()
