def _path(value):
    if not isinstance(value, str) or not value or value.startswith("/") or "\\" in value:
        return False
    parts = value.split("/")
    return all(part and part not in (".", "..") for part in parts)


def _digest(value):
    if not isinstance(value, str) or not value.startswith("sha256=") or len(value) == 7:
        return False
    return all(character.isalnum() or character in ("-", "_") for character in value[7:])


def _owners(value):
    return (isinstance(value, list) and value == sorted(value)
            and len(value) == len(set(value))
            and all(isinstance(owner, str) and owner for owner in value))


def _before(value):
    if value is None:
        return
    if not isinstance(value, dict) or set(value.keys()) != {"digest", "owners"}:
        raise ValueError("before schema")
    if not _digest(value["digest"]) or not _owners(value["owners"]):
        raise ValueError("before value")


def _same(current, before):
    if before is None:
        return current is None
    return (current is not None and current["digest"] == before["digest"]
            and current["owners"] == before["owners"])


def plan_recovery(site_state, journal, wheel_record):
    if not isinstance(site_state, dict) or set(site_state.keys()) != {"files"} or not isinstance(site_state["files"], list):
        raise ValueError("site schema")
    current = {}
    for item in site_state["files"]:
        if not isinstance(item, dict) or set(item.keys()) != {"path", "digest", "owners"}:
            raise ValueError("site file schema")
        if not _path(item["path"]) or not _digest(item["digest"]) or not _owners(item["owners"]) or item["path"] in current:
            raise ValueError("site file value")
        current[item["path"]] = item

    if not isinstance(wheel_record, list) or not wheel_record:
        raise ValueError("record schema")
    records = {}
    for item in wheel_record:
        if not isinstance(item, dict) or set(item.keys()) != {"path", "digest", "size"}:
            raise ValueError("record entry schema")
        size = item["size"]
        if (not _path(item["path"]) or not _digest(item["digest"])
                or not isinstance(size, int) or isinstance(size, bool) or size < 0
                or item["path"] in records):
            raise ValueError("record entry value")
        records[item["path"]] = item

    if not isinstance(journal, dict) or set(journal.keys()) != {"package", "phase", "entries"}:
        raise ValueError("journal schema")
    package = journal["package"]
    phase = journal["phase"]
    entries = journal["entries"]
    if (not isinstance(package, str) or not package or phase not in ("applying", "recovering", "committed")
            or not isinstance(entries, list) or not entries):
        raise ValueError("journal value")
    paths = set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry.keys()) != {"path", "before", "after_digest", "applied"}:
            raise ValueError("journal entry schema")
        path = entry["path"]
        _before(entry["before"])
        if (not _path(path) or path in paths or path not in records
                or entry["after_digest"] != records[path]["digest"]
                or not isinstance(entry["applied"], bool)):
            raise ValueError("journal entry value")
        paths.add(path)
    if paths != set(records.keys()):
        raise ValueError("journal record coverage")

    if phase == "committed":
        return {"decision": "committed", "actions": [], "conflicts": []}

    actions = []
    conflicts = []
    for index in range(len(entries) - 1, -1, -1):
        entry = entries[index]
        path = entry["path"]
        before = entry["before"]
        observed = current.get(path)
        if not entry["applied"]:
            if not _same(observed, before):
                conflicts.append({"path": path, "reason": "unexpected_unapplied_state"})
            continue
        if _same(observed, before):
            continue
        prior_owners = [] if before is None else before["owners"]
        expected_owners = sorted(set(prior_owners + [package]))
        if (observed is None or observed["digest"] != entry["after_digest"]
                or observed["owners"] != expected_owners):
            conflicts.append({"path": path, "reason": "post_write_drift"})
            continue
        if before is None:
            actions.append({"kind": "remove", "path": path})
        elif before["digest"] != entry["after_digest"]:
            actions.append({"kind": "restore", "path": path,
                            "digest": before["digest"], "owners": before["owners"]})
        elif package not in before["owners"]:
            actions.append({"kind": "detach_owner", "path": path, "owner": package})

    if conflicts:
        return {"decision": "manual_intervention", "actions": [], "conflicts": conflicts}
    decision = "rollback_required" if actions else "already_rolled_back"
    return {"decision": decision, "actions": actions, "conflicts": []}
