def canonical_archive_manifest(entries, source_date_epoch, build_root):
    if type(source_date_epoch) is not int or source_date_epoch < 0 or source_date_epoch > 4354819198:
        raise ValueError("invalid SOURCE_DATE_EPOCH")
    if not isinstance(build_root, str):
        raise ValueError("invalid build root")
    root_parts = build_root.split("/")
    if not build_root or build_root.startswith("/") or "\\" in build_root or any(part in ("", ".", "..") for part in root_parts):
        raise ValueError("unsafe build root")
    if not isinstance(entries, list):
        raise ValueError("invalid entries")
    timestamp = max(source_date_epoch, 315532800)
    timestamp -= timestamp % 2
    output = []
    seen = set()
    prefix = build_root + "/"
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"path", "kind", "sha256", "executable", "mtime"}:
            raise ValueError("invalid entry shape")
        path = entry["path"]
        kind = entry["kind"]
        if not isinstance(path, str) or not path.startswith(prefix) or "\\" in path:
            raise ValueError("path outside build root")
        relative = path[len(prefix):]
        parts = relative.split("/")
        if not relative or any(part in ("", ".", "..") for part in parts):
            raise ValueError("unsafe member")
        if kind not in ("file", "dir") or type(entry["executable"]) is not bool or type(entry["mtime"]) is not int:
            raise ValueError("invalid entry values")
        canonical = relative + ("/" if kind == "dir" else "")
        if canonical in seen or relative in seen or relative + "/" in seen:
            raise ValueError("duplicate member")
        seen.add(canonical)
        digest = entry["sha256"]
        if kind == "dir":
            if digest is not None or entry["executable"]:
                raise ValueError("invalid directory metadata")
            mode = 493
        else:
            if not isinstance(digest, str) or len(digest) != 64 or digest != digest.casefold() or any(ch not in "0123456789abcdef" for ch in digest):
                raise ValueError("invalid sha256")
            mode = 493 if entry["executable"] else 420
        output.append({"path": canonical, "kind": kind, "sha256": digest, "mode": mode, "timestamp": timestamp})
    return sorted(output, key=lambda row: row["path"])
