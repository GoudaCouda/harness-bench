import re

TAG = re.compile(r"v?(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-(alpha|beta|rc)\.(0|[1-9][0-9]*))?")
CURRENT = {"python": re.compile(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:(a|b|rc)(0|[1-9][0-9]*))?"), "npm": re.compile(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-(alpha|beta|rc)\.(0|[1-9][0-9]*))?"), "cargo": re.compile(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-(alpha|beta|rc)\.(0|[1-9][0-9]*))?")}
BASE = {"python": "pyproject.toml", "npm": "package.json", "cargo": "Cargo.toml"}

def _tag(value):
    if not isinstance(value, str): raise ValueError("invalid tag")
    match = TAG.fullmatch(value)
    if not match: raise ValueError("invalid tag")
    major, minor, patch = (int(match.group(i)) for i in (1, 2, 3)); label, number = match.group(4), match.group(5)
    canonical = f"{major}.{minor}.{patch}" + (f"-{label}.{int(number)}" if label else "")
    return canonical, (major, minor, patch, 3 if label is None else {"alpha":0,"beta":1,"rc":2}[label], -1 if number is None else int(number)), label, number

def plan_version_sync(release_tag, previous_tag, manifests):
    release, key, label, number = _tag(release_tag); previous, old_key, _, _ = _tag(previous_tag)
    if key <= old_key or not isinstance(manifests, list) or not manifests: raise ValueError("invalid release")
    rows=[]; seen=set()
    for item in manifests:
        if not isinstance(item, dict) or set(item) != {"path","ecosystem","current","publish"}: raise ValueError("shape")
        path, ecosystem, current = item["path"], item["ecosystem"], item["current"]
        safe = isinstance(path,str) and path and not path.startswith("/") and "\\" not in path and all(p not in ("",".","..") for p in path.split("/"))
        if ecosystem not in BASE or not safe or path.split("/")[-1] != BASE[ecosystem] or path in seen or type(item["publish"]) is not bool or not isinstance(current,str) or not CURRENT[ecosystem].fullmatch(current): raise ValueError("manifest")
        seen.add(path); target = release.split("-")[0] + {"alpha":"a","beta":"b","rc":"rc"}[label] + str(int(number)) if label and ecosystem == "python" else release
        rows.append({"path":path,"ecosystem":ecosystem,"from":current,"to":target,"action":"noop" if current == target else "update","publish":item["publish"]})
    rows.sort(key=lambda row: row["path"])
    return {"release":release,"previous":previous,"prerelease":label is not None,"changes":rows}
