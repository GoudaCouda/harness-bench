def plan_case_renames(entries, requests, ignore_case):
    """Broken implementation: emits direct moves and drops index identity."""
    operations = [{"op": "git_mv", "from": item["from"], "to": item["to"]} for item in requests]
    paths = {entry["path"] for entry in entries}
    for item in requests:
        paths.discard(item["from"])
        paths.add(item["to"])
    return {"operations": operations, "final_entries": [{"path": path, "oid": "", "stage": 0} for path in sorted(paths)]}
