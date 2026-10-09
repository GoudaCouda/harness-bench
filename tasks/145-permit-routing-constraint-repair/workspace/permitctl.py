#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def load(name: str) -> dict:
    return json.loads((ROOT / name).read_text())


def write(name: str, value: object) -> None:
    (ROOT / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def digest(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def expected_config() -> dict:
    layers = load("map_layers.json")
    constraints = sorted(
        layers.get("review_constraints", []),
        key=lambda row: (
            int(row.get("precedence", 999)),
            str(row.get("attribute", "")),
        ),
    )
    return {
        "map_version": layers.get("version"),
        "base_revision": layers.get("config_base_revision"),
        "precedence": [row.get("attribute") for row in constraints],
        "routes": {
            str(row.get("attribute")): str(row.get("route")) for row in constraints
        },
    }


def core(config: dict) -> dict:
    return {key: config.get(key) for key in ("map_version", "precedence", "routes")}


def checks(config: dict) -> dict[str, bool]:
    expected = expected_config()
    return {
        "current_map_version": config.get("map_version") == expected["map_version"],
        "constraint_precedence": config.get("precedence") == expected["precedence"],
        "reviewer_routes": config.get("routes") == expected["routes"],
    }


def staging_checks(config: dict) -> dict[str, bool]:
    result = checks(config)
    result["base_revision"] = (
        config.get("revision") == expected_config()["base_revision"]
        and config.get("commits") == []
    )
    return result


def route(attributes: dict, config: dict) -> list[str]:
    routes: list[str] = []
    catalog = {
        row["attribute"]: row
        for row in load("map_layers.json").get("review_constraints", [])
    }
    for constraint in config["precedence"]:
        rule = catalog.get(constraint, {})
        value = attributes.get(rule.get("source_attribute", constraint))
        if (rule.get("match") == "true" and value is True) or (
            rule.get("match") == "present" and bool(value)
        ):
            routes.append(config["routes"][constraint])
    return sorted(set(routes))


def status() -> int:
    print(json.dumps(load("routing_config.json"), indent=2))
    return 0


def validate(name: str) -> int:
    result = staging_checks(load(name))
    print(
        json.dumps(
            {"status": "pass" if all(result.values()) else "fail", "checks": result},
            indent=2,
        )
    )
    return 0 if all(result.values()) else 2


def replay(name: str) -> int:
    config = load(name)
    result = staging_checks(config)
    maps = load("map_layers.json")["parcels"]
    applications = load("applications.json")
    actual = (
        {
            row["id"]: route(maps[row["parcel"]], config)
            for row in applications["applications"]
        }
        if all(result.values())
        else {}
    )
    controls = (
        {
            row["id"]: route(row["parcel_attributes"], config)
            for row in applications["historical_controls"]
        }
        if all(result.values())
        else {}
    )
    expected = {
        row["id"]: route(maps[row["parcel"]], expected_config())
        for row in applications["applications"]
    }
    result["current_applications"] = actual == expected
    result["historical_controls"] = all(
        controls.get(row["id"]) == sorted(set(row.get("expected", [])))
        for row in applications["historical_controls"]
    )
    report = {
        "status": "pass" if all(result.values()) else "fail",
        "checks": result,
        "application_routes": actual,
        "historical_routes": controls,
        "config_core_sha256": digest(core(config)),
    }
    write("replay_report.json", report)
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "pass" else 2


def commit(name: str) -> int:
    config = load(name)
    result = checks(config)
    if not all(result.values()):
        print(json.dumps({"status": "rejected", "checks": result}, indent=2))
        return 2
    expected = expected_config()
    base_revision = expected["base_revision"]
    target_revision = base_revision + 1
    commits = config.get("commits", [])
    if len(commits) == 1:
        commit_row = commits[0]
        if (
            config.get("revision") == target_revision
            and commit_row.get("from_revision") == base_revision
            and commit_row.get("to_revision") == target_revision
            and commit_row.get("config_sha256") == digest(core(config))
        ):
            print(
                json.dumps(
                    {"status": "idempotent", "revision": config.get("revision")},
                    indent=2,
                )
            )
            return 0
    if config.get("revision") != base_revision or commits != []:
        print(
            json.dumps(
                {
                    "status": "rejected",
                    "reason": "revision history",
                    "expected_base_revision": base_revision,
                },
                indent=2,
            )
        )
        return 2
    config["revision"] = target_revision
    config["commits"] = [
        {
            "from_revision": base_revision,
            "to_revision": target_revision,
            "config_sha256": digest(core(config)),
        }
    ]
    write(name, config)
    print(json.dumps({"status": "committed", "revision": target_revision}, indent=2))
    return 0


def verify() -> int:
    config = load("routing_config.json")
    base_revision = expected_config()["base_revision"]
    report = (
        load("replay_report.json") if (ROOT / "replay_report.json").is_file() else {}
    )
    commits = config.get("commits", [])
    transition_ok = (
        len(commits) == 1
        and commits[0].get("from_revision") == base_revision
        and commits[0].get("to_revision") == base_revision + 1
        and config.get("revision") == base_revision + 1
    )
    values = {
        "configuration": all(checks(config).values()),
        "single_revision": transition_ok,
        "commit_digest": commits[0].get("config_sha256") == digest(core(config))
        if commits
        else False,
        "replay": report.get("status") == "pass"
        and report.get("config_core_sha256") == digest(core(config)),
    }
    receipt = {
        "tool": "permitctl/1",
        "status": "pass" if all(values.values()) else "fail",
        "checks": values,
        "config_sha256": digest(config),
        "replay_sha256": digest(report),
    }
    write("routing_receipt.json", receipt)
    print(json.dumps(receipt, indent=2))
    return 0 if receipt["status"] == "pass" else 2


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    for command in ("validate", "replay", "commit"):
        child = sub.add_parser(command)
        child.add_argument("config")
    sub.add_parser("verify")
    args = parser.parse_args()
    commands = {
        "status": status,
        "validate": lambda: validate(args.config),
        "replay": lambda: replay(args.config),
        "commit": lambda: commit(args.config),
        "verify": verify,
    }
    return commands[args.command]()


if __name__ == "__main__":
    raise SystemExit(main())
