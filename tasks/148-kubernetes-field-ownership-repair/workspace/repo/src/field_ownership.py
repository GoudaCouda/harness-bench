def _owner_map(rows):
    return {row["path"]: list(row["managers"]) for row in rows}


def apply_intents(live, ownership, defaults, intents, policy):
    """Apply captured field-manager intents to a flat object snapshot.

    Ordinary conflict atomicity and shared ownership work.  The implementation
    still lacks strict request validation, protected-prefix semantics, default
    ownership transfer, and omission/pruning behavior.
    """
    current = dict(live)
    owners = _owner_map(ownership)
    decisions = []
    for intent in intents:
        conflicts = sorted(
            path for path, value in intent["fields"].items()
            if path in owners
            and any(manager != intent["manager"] for manager in owners[path])
            and current.get(path) != value
        )
        if conflicts and not intent["force"]:
            decisions.append({"request_id": intent["request_id"], "status": "conflict", "conflicts": conflicts, "changed": [], "removed": []})
            continue
        changed = []
        for path, value in intent["fields"].items():
            if current.get(path) != value:
                changed.append(path)
                current[path] = value
            if intent["force"] and path in conflicts:
                owners[path] = [intent["manager"]]
            else:
                owners.setdefault(path, [])
                if intent["manager"] not in owners[path]:
                    owners[path].append(intent["manager"])
                    owners[path].sort()
        decisions.append({"request_id": intent["request_id"], "status": "applied", "conflicts": [], "changed": sorted(changed), "removed": []})
    ownership_rows = [{"path": path, "managers": managers} for path, managers in sorted(owners.items())]
    return {"object": current, "ownership": ownership_rows, "decisions": decisions}
