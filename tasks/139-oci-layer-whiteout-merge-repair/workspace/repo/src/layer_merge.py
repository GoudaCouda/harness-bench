def _parent(path):
    return path.rsplit("/", 1)[0] if "/" in path else ""


def _ancestors(path):
    parts = path.split("/")
    return ["/".join(parts[:index]) for index in range(1, len(parts))]


def merge_layers(layers, policy):
    """Overlay manifest entries in layer order without extracting an image.

    Opaque markers and file/directory replacement work for normal manifests.
    A known incident bug remains: an explicit directory whiteout removes only
    the directory entry, not its descendants. Hostile paths, marker encoding,
    and symlink traversal also still need fail-closed validation.
    """
    state = {}
    removed = set()
    whiteouts = opaque = implicit = 0
    for layer_index, layer in enumerate(layers):
        ordinary = []
        for entry in layer["entries"]:
            name = entry["path"].rsplit("/", 1)[-1]
            parent = _parent(entry["path"])
            if name == ".wh..wh..opq":
                whiteouts += 1
                opaque += 1
                prefix = parent + "/" if parent else ""
                victims = [path for path, row in state.items() if row["_layer"] < layer_index and path.startswith(prefix) and path != parent]
            elif name.startswith(".wh."):
                whiteouts += 1
                target = (parent + "/" if parent else "") + name[4:]
                victims = [path for path, row in state.items() if row["_layer"] < layer_index and path == target]
            else:
                ordinary.append(entry)
                continue
            for victim in victims:
                removed.add(victim)
                state.pop(victim)
        for entry in sorted(ordinary, key=lambda row: (row["path"].count("/"), row["path"])):
            path = entry["path"]
            for ancestor in _ancestors(path):
                if ancestor not in state:
                    state[ancestor] = {"path": ancestor, "kind": "dir", "digest": None, "target": None, "mode": policy["implicit_dir_mode"], "layer_digest": layer["digest"], "implicit": True, "_layer": layer_index}
                    implicit += 1
            if entry["kind"] != "dir":
                for victim in [candidate for candidate in state if candidate.startswith(path + "/")]:
                    removed.add(victim)
                    state.pop(victim)
            state[path] = {**entry, "layer_digest": layer["digest"], "implicit": False, "_layer": layer_index}
    rootfs = []
    for path in sorted(state):
        row = dict(state[path])
        row.pop("_layer")
        rootfs.append(row)
    return {"rootfs": rootfs, "audit": {"layer_count": len(layers), "entry_count": sum(len(layer["entries"]) for layer in layers), "removed_paths": sorted(removed), "whiteout_count": whiteouts, "opaque_whiteout_count": opaque, "implicit_directory_count": implicit}}
