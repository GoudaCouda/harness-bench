#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from risklib import load, purl_parts, release_id


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect the exact release SBOM")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("inventory")
    component = sub.add_parser("component")
    component.add_argument("--purl", required=True)
    depends = sub.add_parser("depends")
    depends.add_argument("--purl", required=True)
    args = parser.parse_args()
    sbom = load("evidence/release.cdx.json")
    components = {str(row["purl"]): row for row in sbom.get("components", [])}
    if args.command == "inventory":
        result = {
            "release_id": release_id(sbom),
            "application": sbom["metadata"]["component"],
            "component_count": len(components),
            "components": [
                {"purl": purl, "name": row["name"], "version": row["version"], "scope": row.get("scope")}
                for purl, row in sorted(components.items())
            ],
        }
    elif args.command == "component":
        exact = components.get(args.purl)
        same_base = []
        try:
            requested_base, _ = purl_parts(args.purl)
        except ValueError:
            requested_base = args.purl
        for purl in components:
            if purl_parts(purl)[0] == requested_base:
                same_base.append(purl)
        result = {"requested": args.purl, "exact_match": exact, "same_package_in_release": sorted(same_base)}
    else:
        edges = {str(row["ref"]): list(row.get("dependsOn", [])) for row in sbom.get("dependencies", [])}
        parents = sorted(ref for ref, children in edges.items() if args.purl in children)
        result = {
            "purl": args.purl,
            "present": args.purl in components,
            "direct_dependencies": sorted(edges.get(args.purl, [])),
            "direct_dependents": parents,
        }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
