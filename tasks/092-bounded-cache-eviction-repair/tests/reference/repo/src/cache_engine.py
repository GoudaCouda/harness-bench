from copy import deepcopy
import math


def _integer(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _json(value, depth=0):
    if value is None or isinstance(value, (str, bool)) or _integer(value):
        return True
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, list):
        return depth < 8 and all(_json(item, depth + 1) for item in value)
    if isinstance(value, dict):
        return depth < 8 and all(isinstance(key, str) and _json(item, depth + 1) for key, item in value.items())
    return False


def _exact(value, keys):
    return isinstance(value, dict) and set(value) == set(keys)


def _preflight(state, operations, policy):
    if not _exact(policy, ("capacity", "max_entry_size")) or not _integer(policy["capacity"]) or not _integer(policy["max_entry_size"]) or not 0 < policy["max_entry_size"] <= policy["capacity"]:
        raise ValueError("invalid policy")
    if not _exact(state, ("clock", "next_access", "entries")) or not _integer(state["clock"]) or state["clock"] < 0 or not _integer(state["next_access"]) or state["next_access"] <= 0 or not isinstance(state["entries"], dict):
        raise ValueError("invalid state")
    total = 0
    for key, entry in state["entries"].items():
        if not isinstance(key, str) or not key or not _exact(entry, ("value", "size", "expires_at", "last_access", "pinned")):
            raise ValueError("invalid entry")
        if not _json(entry["value"]) or not _integer(entry["size"]) or entry["size"] <= 0 or not _integer(entry["expires_at"]) or entry["expires_at"] < 0 or not _integer(entry["last_access"]) or not 0 <= entry["last_access"] < state["next_access"] or not isinstance(entry["pinned"], bool):
            raise ValueError("invalid entry value")
        total += entry["size"]
    if total > policy["capacity"] or not isinstance(operations, list):
        raise ValueError("invalid capacity or operations")
    clock = state["clock"]
    for operation in operations:
        if not isinstance(operation, dict) or operation.get("op") not in ("advance", "get", "put", "unpin"):
            raise ValueError("invalid operation")
        kind = operation["op"]
        if kind == "advance":
            if not _exact(operation, ("op", "to")) or not _integer(operation["to"]) or operation["to"] < clock:
                raise ValueError("invalid advance")
            clock = operation["to"]
        elif kind in ("get", "unpin"):
            if not _exact(operation, ("op", "key")) or not isinstance(operation["key"], str) or not operation["key"]:
                raise ValueError("invalid key operation")
        else:
            if not _exact(operation, ("op", "key", "value", "size", "ttl", "pinned")) or not isinstance(operation["key"], str) or not operation["key"] or not _json(operation["value"]) or not _integer(operation["size"]) or operation["size"] <= 0 or not _integer(operation["ttl"]) or operation["ttl"] <= 0 or not isinstance(operation["pinned"], bool):
                raise ValueError("invalid put")


def replay_cache(state, operations, policy):
    _preflight(state, operations, policy)
    current = deepcopy(state)
    events = []

    def expire():
        expired = sorted(key for key, entry in current["entries"].items() if entry["expires_at"] <= current["clock"])
        for key in expired:
            current["entries"].pop(key)
        return expired

    for operation in operations:
        kind = operation["op"]
        if kind == "advance":
            initial = expire()
            current["clock"] = operation["to"]
            expired = sorted(set(initial) | set(expire()))
            events.append({"op": "advance", "to": operation["to"], "status": "ok", "expired": expired})
            continue
        expired = expire()
        key = operation["key"]
        if kind == "get":
            entry = current["entries"].get(key)
            if entry is None:
                events.append({"op": "get", "key": key, "status": "miss", "expired": expired})
            else:
                value = deepcopy(entry["value"])
                entry["last_access"] = current["next_access"]
                current["next_access"] += 1
                events.append({"op": "get", "key": key, "status": "hit", "value": value, "expired": expired})
        elif kind == "unpin":
            entry = current["entries"].get(key)
            status = "missing" if entry is None else "updated"
            if entry is not None:
                entry["pinned"] = False
            events.append({"op": "unpin", "key": key, "status": status, "expired": expired})
        else:
            if operation["size"] > policy["max_entry_size"] or operation["size"] > policy["capacity"]:
                events.append({"op": "put", "key": key, "status": "rejected_size", "expired": expired, "evicted": []})
                continue
            candidate = deepcopy(current["entries"])
            candidate.pop(key, None)
            total = sum(entry["size"] for entry in candidate.values())
            victims = sorted(((entry["last_access"], victim) for victim, entry in candidate.items() if not entry["pinned"]))
            evicted = []
            for _, victim in victims:
                if total + operation["size"] <= policy["capacity"]:
                    break
                total -= candidate[victim]["size"]
                candidate.pop(victim)
                evicted.append(victim)
            if total + operation["size"] > policy["capacity"]:
                events.append({"op": "put", "key": key, "status": "rejected_capacity", "expired": expired, "evicted": []})
                continue
            candidate[key] = {"value": deepcopy(operation["value"]), "size": operation["size"], "expires_at": current["clock"] + operation["ttl"], "last_access": current["next_access"], "pinned": operation["pinned"]}
            current["next_access"] += 1
            current["entries"] = candidate
            events.append({"op": "put", "key": key, "status": "stored", "expired": expired, "evicted": sorted(evicted)})
    current["entries"] = {key: current["entries"][key] for key in sorted(current["entries"])}
    return {"state": current, "events": events}

