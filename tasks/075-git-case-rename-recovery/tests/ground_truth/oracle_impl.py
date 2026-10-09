import re

OID = re.compile(r"[0-9a-f]{40}")


def _safe(path):
    return (
        isinstance(path, str)
        and path
        and not path.startswith("/")
        and "\\" not in path
        and all(part not in ("", ".", "..") for part in path.split("/"))
    )


def _key(value, ignore_case):
    return value.casefold() if ignore_case else value


def plan_case_renames(entries, requests, ignore_case):
    if (
        type(ignore_case) is not bool
        or not isinstance(entries, list)
        or not entries
        or not isinstance(requests, list)
        or not requests
    ):
        raise ValueError("invalid batch")
    current = {}
    occupied = set()
    for entry in entries:
        if (
            not isinstance(entry, dict)
            or set(entry) != {"path", "oid", "stage"}
            or not _safe(entry.get("path"))
            or not isinstance(entry.get("oid"), str)
            or not OID.fullmatch(entry["oid"])
            or type(entry.get("stage")) is not int
            or entry["stage"] != 0
        ):
            raise ValueError("invalid entry")
        path_key = _key(entry["path"], ignore_case)
        if entry["path"] in current or path_key in occupied:
            raise ValueError("duplicate entry")
        current[entry["path"]] = dict(entry)
        occupied.add(path_key)
    mapping = {}
    sources = set()
    destinations = set()
    for request in requests:
        if (
            not isinstance(request, dict)
            or set(request) != {"from", "to"}
            or not _safe(request.get("from"))
            or not _safe(request.get("to"))
            or request["from"] == request["to"]
            or request["from"] not in current
        ):
            raise ValueError("invalid request")
        source_key = _key(request["from"], ignore_case)
        destination_key = _key(request["to"], ignore_case)
        if source_key in sources or destination_key in destinations:
            raise ValueError("duplicate request")
        sources.add(source_key)
        destinations.add(destination_key)
        mapping[request["from"]] = request["to"]
    for destination_key in destinations:
        if destination_key in occupied and destination_key not in sources:
            raise ValueError("occupied destination")
    operations = []
    pending = dict(mapping)
    while pending:
        movable = []
        occupied_now = {_key(path, ignore_case) for path in current}
        for source, destination in pending.items():
            if _key(destination, ignore_case) not in occupied_now:
                movable.append(source)
        if movable:
            source = sorted(movable)[0]
            destination = pending.pop(source)
        else:
            source = sorted(pending)[0]
            destination = pending.pop(source)
            parent, basename = source.rsplit("/", 1) if "/" in source else ("", source)
            counter = 1
            while True:
                leaf = f".{basename}.hb-rename-tmp-{counter}"
                temporary = f"{parent}/{leaf}" if parent else leaf
                reserved = (
                    {_key(path, ignore_case) for path in current}
                    | {_key(value, ignore_case) for value in pending.values()}
                    | {_key(destination, ignore_case)}
                )
                if _key(temporary, ignore_case) not in reserved:
                    break
                counter += 1
            pending[temporary] = destination
            destination = temporary
        entry = current.pop(source)
        operations.append({"op": "git_mv", "from": source, "to": destination})
        entry["path"] = destination
        current[destination] = entry
    final_entries = sorted(current.values(), key=lambda entry: entry["path"])
    return {"operations": operations, "final_entries": final_entries}
