HEX = set("0123456789abcdef")


def _safe(path):
    return isinstance(path, str) and path and "\\" not in path and "\0" not in path and not path.startswith("/") and not (len(path) > 1 and path[1] == ":") and all(part not in ("", ".", "..") for part in path.split("/"))


def _names(values, nonempty=True):
    if not isinstance(values, list) or (nonempty and not values) or any(not isinstance(value, str) or not value for value in values) or len(set(values)) != len(values):
        raise ValueError("invalid policy list")
    return values


def _policy(policy):
    if not isinstance(policy, dict) or set(policy) != {"roots", "extensions", "temporary_prefixes", "temporary_suffixes"}:
        raise ValueError("invalid policy")
    roots = _names(policy["roots"])
    extensions = _names(policy["extensions"])
    prefixes = _names(policy["temporary_prefixes"], False)
    suffixes = _names(policy["temporary_suffixes"], False)
    if any(not _safe(root) for root in roots) or any(not ext.startswith(".") or "/" in ext or "\\" in ext for ext in extensions):
        raise ValueError("invalid path policy")
    return roots, extensions, prefixes, suffixes


def _managed(path, rules):
    roots, extensions, prefixes, suffixes = rules
    if not _safe(path) or not any(path.startswith(root + "/") for root in roots):
        return False
    base = path.split("/")[-1]
    return any(base.endswith(ext) for ext in extensions) and not any(base.startswith(prefix) for prefix in prefixes) and not any(base.endswith(suffix) for suffix in suffixes)


def _entry(entry, snapshot=False):
    expected = {"type", "inode", "digest"} if snapshot else {"inode", "digest"}
    if not isinstance(entry, dict) or set(entry) != expected:
        raise ValueError("invalid entry shape")
    if snapshot and entry["type"] not in ("file", "symlink", "directory"):
        raise ValueError("invalid node type")
    if snapshot and entry["type"] != "file":
        if entry["inode"] is not None or entry["digest"] is not None:
            raise ValueError("unsafe node identity")
        return
    inode, digest = entry["inode"], entry["digest"]
    if type(inode) is not int or inode <= 0 or not isinstance(digest, str) or len(digest) != 64 or any(char not in HEX for char in digest):
        raise ValueError("invalid file identity")


def reconcile_batch(checkpoint, batch, policy):
    rules = _policy(policy)
    if not isinstance(checkpoint, dict) or set(checkpoint) != {"seq", "watched"} or type(checkpoint["seq"]) is not int or checkpoint["seq"] < 0 or not isinstance(checkpoint["watched"], dict):
        raise ValueError("invalid checkpoint")
    watched = {}
    for path, entry in checkpoint["watched"].items():
        if not _managed(path, rules):
            raise ValueError("unmanaged checkpoint path")
        _entry(entry)
        watched[path] = dict(entry)
    if not isinstance(batch, dict) or set(batch) != {"seq", "events", "snapshot"} or type(batch["seq"]) is not int or batch["seq"] <= checkpoint["seq"] or not isinstance(batch["events"], list) or not isinstance(batch["snapshot"], dict):
        raise ValueError("invalid batch")
    full_scan, hinted = False, set()
    for event in batch["events"]:
        if not isinstance(event, dict) or set(event) != {"kind", "path"} or event["kind"] not in ("change", "rename"):
            raise ValueError("invalid event")
        path = event["path"]
        if path is None:
            full_scan = True
        elif not _safe(path):
            raise ValueError("unsafe event path")
        elif _managed(path, rules):
            hinted.add(path)
    snapshot = {}
    for path, entry in batch["snapshot"].items():
        if not _safe(path):
            raise ValueError("unsafe snapshot path")
        _entry(entry, True)
        snapshot[path] = entry
    candidates = set(watched) | {path for path in snapshot if _managed(path, rules)} if full_scan else hinted
    actions = []
    for path in sorted(candidates):
        previous, current = watched.get(path), snapshot.get(path)
        if current is None:
            if previous is not None:
                actions.append({"path": path, "action": "delete", "reason": "removed"})
                watched.pop(path)
        elif current["type"] != "file":
            actions.append({"path": path, "action": "block", "reason": "unsafe_node"})
        elif previous is None:
            actions.append({"path": path, "action": "reload", "reason": "created"})
            watched[path] = {"inode": current["inode"], "digest": current["digest"]}
        elif previous["digest"] != current["digest"]:
            actions.append({"path": path, "action": "reload", "reason": "content_changed"})
            watched[path] = {"inode": current["inode"], "digest": current["digest"]}
        elif previous["inode"] != current["inode"]:
            actions.append({"path": path, "action": "rebind", "reason": "inode_replaced"})
            watched[path] = {"inode": current["inode"], "digest": current["digest"]}
    return {"actions": actions, "checkpoint": {"seq": batch["seq"], "watched": {path: watched[path] for path in sorted(watched)}}}
