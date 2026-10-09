def canonical_archive_manifest(entries, source_date_epoch, build_root):
    if type(source_date_epoch) is not int or not 0 <= source_date_epoch <= 4354819198 or not isinstance(build_root, str): raise ValueError("invalid build state")
    root_parts = build_root.split("/")
    if not build_root or build_root.startswith("/") or "\\" in build_root or any(p in ("", ".", "..") for p in root_parts): raise ValueError("unsafe root")
    if not isinstance(entries, list): raise ValueError("invalid entries")
    stamp = max(source_date_epoch, 315532800); stamp -= stamp % 2
    prefix, seen, output = build_root + "/", set(), []
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"path", "kind", "sha256", "executable", "mtime"}: raise ValueError("invalid shape")
        path, kind = entry["path"], entry["kind"]
        if not isinstance(path, str) or not path.startswith(prefix) or "\\" in path: raise ValueError("outside root")
        relative = path[len(prefix):]
        if not relative or any(p in ("", ".", "..") for p in relative.split("/")): raise ValueError("unsafe member")
        if kind not in ("file", "dir") or type(entry["executable"]) is not bool or type(entry["mtime"]) is not int: raise ValueError("invalid values")
        canonical = relative + ("/" if kind == "dir" else "")
        if canonical in seen or relative in seen or relative + "/" in seen: raise ValueError("duplicate")
        seen.add(canonical); digest = entry["sha256"]
        if kind == "dir":
            if digest is not None or entry["executable"]: raise ValueError("bad dir")
            mode = 493
        else:
            if not isinstance(digest, str) or len(digest) != 64 or digest != digest.casefold() or any(c not in "0123456789abcdef" for c in digest): raise ValueError("bad digest")
            mode = 493 if entry["executable"] else 420
        output.append({"path": canonical, "kind": kind, "sha256": digest, "mode": mode, "timestamp": stamp})
    return sorted(output, key=lambda row: row["path"])
