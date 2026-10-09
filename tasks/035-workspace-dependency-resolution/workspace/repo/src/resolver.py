def resolve_workspace(manifest, registry, current_lock, target):
    """Broken greedy resolver; repair from docs/resolution_contract.md."""
    packages = []
    skipped = []
    wanted = dict(manifest.get("dependencies", {}))
    wanted.update(manifest.get("optionalDependencies", {}))
    for name in sorted(wanted):
        releases = registry.get(name, [])
        if not releases:
            if name in manifest.get("optionalDependencies", {}):
                skipped.append(name)
                continue
            raise ValueError("missing")
        release = sorted(releases, key=lambda item: item["version"])[-1]
        packages.append({"name": name, "version": release["version"], "source": "selected"})
    return {"packages": packages, "skipped_optional": skipped}
