#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urldefrag, urljoin

ROOT = Path(__file__).resolve().parents[1]


def walk(value, key):
    if isinstance(value, dict):
        for name, item in value.items():
            if name == key and isinstance(item, str):
                yield item
            yield from walk(item, key)
    elif isinstance(value, list):
        for item in value:
            yield from walk(item, key)


def required_ok(value, schema):
    if not isinstance(value, dict):
        return False
    if any(name not in value for name in schema.get("required", [])):
        return False
    for name, rule in schema.get("properties", {}).items():
        if name not in value or not isinstance(rule, dict):
            continue
        if rule.get("type") == "string" and not isinstance(value[name], str):
            return False
    return True


def audit():
    registry = json.loads((ROOT / "registry.json").read_text())
    records = []
    resources = {}
    anchors = {}
    documents = {}
    for row in registry["resources"]:
        path = ROOT / row["path"]
        doc = json.loads(path.read_text())
        retrieval = row["retrieval_uri"]
        effective = urljoin(retrieval, doc.get("$id", retrieval))
        base, fragment = urldefrag(effective)
        if fragment or base in resources:
            raise ValueError("duplicate or fragmented effective resource URI")
        resources[base] = row["path"]
        documents[row["path"]] = doc
        for anchor in walk(doc, "$anchor"):
            key = base + "#" + anchor
            if key in anchors:
                raise ValueError("duplicate anchor")
            anchors[key] = row["path"]
        records.append((row, doc, base))

    edges = []
    unresolved = []
    for row, doc, base in records:
        for ref in walk(doc, "$ref"):
            resolved = urljoin(base, ref)
            target_base, fragment = urldefrag(resolved)
            ok = resolved in anchors if fragment else target_base in resources
            item = {"from": row["path"], "ref": ref, "resolved": resolved}
            (edges if ok else unresolved).append(item)

    order = documents["schemas/orders/order.json"]
    address = documents["schemas/common/address.json"]
    classifications = {}
    for row in registry["examples"]:
        value = json.loads((ROOT / row["path"]).read_text())
        order_value = value.get("order") if isinstance(value, dict) else None
        valid = required_ok(order_value, order)
        if valid and isinstance(order_value, dict):
            valid = required_ok(order_value.get("ship_to"), address)
        classifications[row["path"]] = valid

    expected = {row["path"]: bool(row["expected_valid"]) for row in registry["examples"]}
    report = {
        "resources": dict(sorted(resources.items())),
        "anchors": dict(sorted(anchors.items())),
        "edges": sorted(edges, key=lambda item: (item["from"], item["ref"])),
        "unresolved": sorted(unresolved, key=lambda item: (item["from"], item["ref"])),
        "examples": dict(sorted(classifications.items())),
        "valid": not unresolved and classifications == expected,
    }
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    report = audit()
    if args.write:
        out = ROOT / "out"
        out.mkdir(exist_ok=True)
        (out / "bundle_audit.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    raise SystemExit(0 if report["valid"] else 1)


if __name__ == "__main__":
    main()
