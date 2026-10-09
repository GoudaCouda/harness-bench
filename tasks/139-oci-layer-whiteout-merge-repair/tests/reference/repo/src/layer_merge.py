def _fail():
    raise ValueError()


def _valid_path(path):
    if not isinstance(path, str) or not path or path.startswith("/") or path.endswith("/") or "\\" in path:
        _fail()
    parts = path.split("/")
    if any(part in ("", ".", "..") or any(ord(char) < 32 for char in part) for part in parts):
        _fail()
    return parts


def _ancestors(path):
    parts = path.split("/")
    return ["/".join(parts[:index]) for index in range(1, len(parts))]


def _parent(path):
    return path.rsplit("/", 1)[0] if "/" in path else ""


def _basename(path):
    return path.rsplit("/", 1)[-1]


def _marker(entry):
    name = _basename(entry["path"])
    if not name.startswith(".wh."):
        return None
    if entry["kind"] != "file" or entry["digest"] != "sha256:empty" or entry["target"] is not None or entry["mode"] != 0:
        _fail()
    if name == ".wh..wh..opq":
        return ("opaque", _parent(entry["path"]))
    target_name = name[4:]
    if not target_name or target_name.startswith(".wh."):
        _fail()
    parent = _parent(entry["path"])
    return ("explicit", parent + "/" + target_name if parent else target_name)


def _resolve_target(path, target):
    if not isinstance(target, str) or not target or target.startswith("/") or "\\" in target or any(ord(char) < 32 for char in target):
        _fail()
    stack = _parent(path).split("/") if _parent(path) else []
    for part in target.split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            if not stack:
                _fail()
            stack.pop()
        else:
            stack.append(part)
    return "/".join(stack)


def _validate(layers, policy):
    if not isinstance(policy, dict) or set(policy) != {"implicit_dir_mode"}:
        _fail()
    mode = policy["implicit_dir_mode"]
    if not isinstance(mode, int) or isinstance(mode, bool) or not 0 <= mode <= 511:
        _fail()
    if not isinstance(layers, list) or not layers:
        _fail()
    digests = set()
    entry_keys = {"path", "kind", "digest", "target", "mode"}
    prepared = []
    for layer in layers:
        if not isinstance(layer, dict) or set(layer) != {"digest", "entries"} or not isinstance(layer["digest"], str) or not layer["digest"] or layer["digest"] in digests or not isinstance(layer["entries"], list):
            _fail()
        digests.add(layer["digest"])
        paths = set()
        rows = []
        for raw in layer["entries"]:
            if not isinstance(raw, dict) or set(raw) != entry_keys:
                _fail()
            parts = _valid_path(raw["path"])
            if raw["path"] in paths:
                _fail()
            paths.add(raw["path"])
            if raw["kind"] not in ("file", "dir", "symlink") or not isinstance(raw["mode"], int) or isinstance(raw["mode"], bool) or not 0 <= raw["mode"] <= 511:
                _fail()
            if raw["kind"] == "file":
                if not isinstance(raw["digest"], str) or not raw["digest"] or raw["target"] is not None:
                    _fail()
            elif raw["kind"] == "dir":
                if raw["digest"] is not None or raw["target"] is not None:
                    _fail()
            else:
                if raw["digest"] is not None:
                    _fail()
                _resolve_target(raw["path"], raw["target"])
            rows.append(dict(raw))
        normal = {row["path"]: row for row in rows if _marker(row) is None}
        for path in normal:
            for ancestor in _ancestors(path):
                if ancestor in normal and normal[ancestor]["kind"] != "dir":
                    _fail()
        prepared.append({"digest": layer["digest"], "entries": rows})
    return prepared, mode


def merge_layers(layers, policy):
    layers, implicit_mode = _validate(layers, policy)
    state = {}
    removed = set()
    whiteouts = 0
    opaque = 0
    implicit_created = 0

    def remove_lower(target, layer_limit, children_only):
        prefix = target + "/" if target else ""
        victims = [path for path, row in state.items() if row["layer_index"] < layer_limit and ((children_only and path.startswith(prefix) and path != target) or (not children_only and (path == target or path.startswith(prefix))))]
        for path in victims:
            removed.add(path)
            state.pop(path)
        return victims

    def remove_descendants(target):
        prefix = target + "/"
        victims = [path for path in state if path.startswith(prefix)]
        for path in victims:
            removed.add(path)
            state.pop(path)

    for layer_index, layer in enumerate(layers):
        markers = []
        normal = []
        for row in layer["entries"]:
            parsed = _marker(row)
            if parsed is None:
                normal.append(row)
            else:
                markers.append(parsed)
        for kind, target in markers:
            whiteouts += 1
            if kind == "opaque":
                opaque += 1
                remove_lower(target, layer_index, True)
            else:
                remove_lower(target, layer_index, False)
        normal.sort(key=lambda row: (len(row["path"].split("/")), row["path"]))
        for row in normal:
            path = row["path"]
            for ancestor in _ancestors(path):
                existing = state.get(ancestor)
                if existing is not None and existing["kind"] != "dir":
                    _fail()
                if existing is None:
                    state[ancestor] = {"path": ancestor, "kind": "dir", "digest": None, "target": None, "mode": implicit_mode, "layer_digest": layer["digest"], "implicit": True, "layer_index": layer_index}
                    implicit_created += 1
            existing = state.get(path)
            if row["kind"] != "dir":
                remove_descendants(path)
            elif existing is not None and existing["kind"] != "dir":
                state.pop(path)
                removed.add(path)
            state[path] = {"path": path, "kind": row["kind"], "digest": row["digest"], "target": row["target"], "mode": row["mode"], "layer_digest": layer["digest"], "implicit": False, "layer_index": layer_index}
        for path, row in state.items():
            if row["kind"] != "symlink":
                continue
            resolved = _resolve_target(path, row["target"])
            for ancestor in _ancestors(resolved):
                target_row = state.get(ancestor)
                if target_row is not None and target_row["kind"] == "symlink":
                    _fail()

    rootfs = []
    for path in sorted(state):
        row = dict(state[path])
        row.pop("layer_index")
        rootfs.append(row)
    return {"rootfs": rootfs, "audit": {"layer_count": len(layers), "entry_count": sum(len(layer["entries"]) for layer in layers), "removed_paths": sorted(removed), "whiteout_count": whiteouts, "opaque_whiteout_count": opaque, "implicit_directory_count": implicit_created}}
