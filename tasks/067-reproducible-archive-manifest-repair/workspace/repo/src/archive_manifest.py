def canonical_archive_manifest(entries, source_date_epoch, build_root):
    """Broken planner: leaks build paths, mtimes, modes, and input order."""
    result = []
    for entry in entries:
        result.append({
            "path": entry["path"],
            "kind": entry["kind"],
            "sha256": entry.get("sha256"),
            "mode": 493 if entry.get("executable") else 420,
            "timestamp": entry.get("mtime", source_date_epoch),
        })
    return result
