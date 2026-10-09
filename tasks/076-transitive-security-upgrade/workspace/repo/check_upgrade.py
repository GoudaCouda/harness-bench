#!/usr/bin/env python3
from __future__ import annotations

import itertools
import json
import sys
from pathlib import Path

NODE = 18


def version(value: str) -> tuple[int, ...]:
    return tuple(int(part) for part in str(value).split("."))


def satisfies(value: str, specification: str) -> bool:
    current = version(value)
    for clause in specification.split():
        if clause.startswith(">=") and current < version(clause[2:]):
            return False
        if clause.startswith("<") and current >= version(clause[1:]):
            return False
    return True


def closure(selected: dict[str, str], registry: dict[str, dict[str, dict]]) -> tuple[dict[str, str], list[str]]:
    resolved: dict[str, str] = {}
    problems: list[str] = []
    pending = list(selected.items())
    while pending:
        name, chosen = pending.pop()
        if name in resolved:
            if resolved[name] != chosen:
                problems.append(f"resolution collision for {name}: {resolved[name]} versus {chosen}")
            continue
        metadata = registry.get(name, {}).get(chosen)
        if not metadata:
            problems.append(f"registry has no {name}@{chosen}")
            continue
        resolved[name] = chosen
        pending.extend(metadata.get("dependencies", {}).items())
    return resolved, problems


def graph_problems(selected, registry, advisories, profiles):
    resolved, problems = closure(selected, registry)
    for name, chosen in resolved.items():
        metadata = registry.get(name, {}).get(chosen, {})
        if not metadata.get("node_min", 0) <= NODE < metadata.get("node_max_exclusive", 0):
            problems.append(f"{name}@{chosen} does not support Node {NODE}")
        for peer_name, requirement in metadata.get("peer", {}).items():
            peer_version = resolved.get(peer_name)
            if peer_version is None or not satisfies(peer_version, requirement):
                problems.append(f"{name}@{chosen} requires peer {peer_name} {requirement}")
    for name, expected in profiles.items():
        chosen = resolved.get(name)
        actual = registry.get(name, {}).get(chosen, {}).get("compat_profile")
        if actual != expected:
            problems.append(f"{name}@{chosen} has compatibility profile {actual}, expected {expected}")
    for advisory in advisories:
        chosen = resolved.get(advisory["package"])
        if chosen is None or version(chosen) < version(advisory["affected_below"]):
            problems.append(f"{advisory['id']} remains applicable through {advisory['package']}@{chosen}")
    return problems, resolved


def expected_lock_entry(name: str, chosen: str, metadata: dict) -> dict:
    result = {"version": chosen, "integrity": metadata["integrity"]}
    if metadata.get("dependencies"):
        result["dependencies"] = metadata["dependencies"]
    if metadata.get("peer"):
        result["peerDependencies"] = metadata["peer"]
    return result


def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit("usage: check_upgrade.py ROOT_PACKAGE_JSON LOCK_JSON")
    manifest_path, lock_path = map(Path, sys.argv[1:])
    repo = manifest_path.resolve().parent
    workspace = Path(__file__).resolve().parents[1]
    root_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    worker_manifest = json.loads((repo / "packages/worker/package.json").read_text(encoding="utf-8"))
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    registry_record = json.loads((workspace / "package_registry.json").read_text(encoding="utf-8"))
    registry = registry_record["packages"]
    advisories = json.loads((workspace / "advisory.json").read_text(encoding="utf-8"))["advisories"]
    profiles = json.loads((repo / "compat_fixtures.json").read_text(encoding="utf-8"))["required_profiles"]

    selected = {**root_manifest.get("dependencies", {}), **worker_manifest.get("dependencies", {})}
    expected_direct = set(registry_record["direct_packages"])
    problems: list[str] = []
    if set(selected) != expected_direct:
        problems.append(f"direct parent set must remain {sorted(expected_direct)}")
    graph_errors, resolved = graph_problems(selected, registry, advisories, profiles)
    problems.extend(graph_errors)

    candidates: list[dict[str, str]] = []
    choices = [registry[name].keys() for name in registry_record["direct_packages"]]
    for values in itertools.product(*choices):
        candidate = dict(zip(registry_record["direct_packages"], values))
        if not graph_problems(candidate, registry, advisories, profiles)[0]:
            candidates.append(candidate)
    baseline = registry_record["baseline"]

    def cost(candidate: dict[str, str]) -> tuple:
        changed = sum(candidate[name] != baseline[name] for name in baseline)
        distance = sum(sum(version(candidate[name])) - sum(version(baseline[name])) for name in baseline)
        return changed, distance, tuple(version(candidate[name]) for name in registry_record["direct_packages"])

    if candidates:
        minimum = min(candidates, key=cost)
        if selected != minimum:
            problems.append(f"selected graph is not the least-change supported remediation; derived candidate is {minimum}")

    packages = lock.get("packages", {})
    expected_root = {
        "name": root_manifest.get("name"), "version": root_manifest.get("version"),
        "workspaces": root_manifest.get("workspaces"), "dependencies": root_manifest.get("dependencies"),
        "devDependencies": root_manifest.get("devDependencies"), "engines": root_manifest.get("engines"),
    }
    expected_worker = {
        "name": worker_manifest.get("name"), "version": worker_manifest.get("version"),
        "dependencies": worker_manifest.get("dependencies"), "engines": worker_manifest.get("engines"),
    }
    if packages.get("") != expected_root:
        problems.append("root lock package disagrees with the root manifest")
    if packages.get("packages/worker") != expected_worker:
        problems.append("workspace lock package disagrees with packages/worker/package.json")
    for name, chosen in resolved.items():
        expected = expected_lock_entry(name, chosen, registry[name][chosen])
        if packages.get(f"node_modules/{name}") != expected:
            problems.append(f"lock metadata for {name}@{chosen} is incomplete or incoherent")

    dev_dependencies = root_manifest.get("devDependencies", {})
    dev_resolved, dev_errors = closure(dev_dependencies, registry)
    problems.extend(dev_errors)
    for name, chosen in dev_resolved.items():
        if packages.get(f"node_modules/{name}") != expected_lock_entry(name, chosen, registry[name][chosen]):
            problems.append(f"unrelated development lock entry {name}@{chosen} changed")
    if root_manifest.get("engines") != {"node": "18.x"} or worker_manifest.get("engines") != {"node": "18.x"}:
        problems.append("root and worker runtimes must remain Node 18.x")
    if lock.get("metadata") != {"generated_by": "npm@10.8.2", "registry_snapshot": "reg-2026-08-12"}:
        problems.append("repository lock metadata changed")
    allowed_lock_keys = {"", "packages/worker"} | {f"node_modules/{name}" for name in set(resolved) | set(dev_resolved)}
    extras = sorted(set(packages) - allowed_lock_keys)
    missing = sorted(allowed_lock_keys - set(packages))
    if extras or missing:
        problems.append(f"lock package set mismatch; unexpected={extras}, missing={missing}")

    result = {
        "status": "PASS" if not problems else "FAIL", "selected": selected,
        "resolved_package_count": len(resolved), "secure_candidate_count": len(candidates),
        "checks": ["six_advisories", "two_manifests", "recursive_lock", "node18", "peers", "profiles", "minimal_change", "unrelated_scope"],
        "problems": problems,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if not problems else 2


if __name__ == "__main__":
    raise SystemExit(main())
