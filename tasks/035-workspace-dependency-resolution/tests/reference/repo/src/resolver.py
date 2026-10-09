def resolve_workspace(manifest, registry, current_lock, target):
    def parse(value):
        if type(value) is not str: raise ValueError("bad version")
        text = value[1:] if value.startswith("^") else value; parts = text.split(".")
        if len(parts) != 3 or any(not part.isdigit() for part in parts): raise ValueError("bad version")
        return tuple(int(part) for part in parts)
    def matches(version, requirement):
        actual, base = parse(version), parse(requirement)
        return actual == base if not requirement.startswith("^") else actual[0] == base[0] and actual >= base
    def allowed(release):
        for field in ("os","cpu"):
            rules = release.get(field)
            if rules is None: continue
            if type(rules) is not list or any(type(x) is not str or not x for x in rules): raise ValueError("bad marker")
            value = target[field]
            if "!"+value in rules or (any(not x.startswith("!") for x in rules) and value not in rules): return False
        return True
    if type(manifest) is not dict or set(manifest) != {"dependencies","optionalDependencies"} or type(registry) is not dict or type(current_lock) is not dict or type(target) is not dict or set(target) != {"os","cpu"} or any(type(target[x]) is not str or not target[x] for x in target): raise ValueError("bad root")
    required, optional = manifest["dependencies"], manifest["optionalDependencies"]
    if type(required) is not dict or type(optional) is not dict or set(required)&set(optional): raise ValueError("bad manifest")
    for mapping in (required,optional,current_lock):
        if any(type(k) is not str or not k or type(v) is not str for k,v in mapping.items()): raise ValueError("bad mapping")
    for value in list(required.values())+list(optional.values()): parse(value)
    names, options = sorted(registry), {}
    for name in names:
        releases = registry[name]
        if type(name) is not str or not name or type(releases) is not list: raise ValueError("bad registry")
        clean, versions = [], set()
        for raw in releases:
            if type(raw) is not dict or "version" not in raw: raise ValueError("bad release")
            release=dict(raw); parse(release["version"])
            if release["version"] in versions: raise ValueError("duplicate")
            versions.add(release["version"])
            for field in ("dependencies","peerDependencies","peerDependenciesMeta"):
                if field in release and type(release[field]) is not dict: raise ValueError("bad metadata")
            for field in ("dependencies","peerDependencies"):
                for dep,constraint in release.get(field,{}).items():
                    if type(dep) is not str or not dep: raise ValueError("bad dependency")
                    parse(constraint)
            clean.append(release)
        options[name]=sorted(clean,key=lambda x:parse(x["version"]),reverse=True)
    assignments, solutions = {}, []
    def validate():
        for name,constraint in required.items():
            if assignments.get(name) is None or not matches(assignments[name]["version"],constraint): return
        for name,constraint in optional.items():
            if assignments.get(name) is not None and not matches(assignments[name]["version"],constraint): return
        selected={name:rel for name,rel in assignments.items() if rel is not None}
        reachable=set(name for name in required if name in selected)|set(name for name in optional if name in selected); changed=True
        while changed:
            changed=False
            for name in list(reachable):
                rel=selected[name]
                for dep in rel.get("dependencies",{}):
                    if dep in selected and dep not in reachable: reachable.add(dep); changed=True
                for dep in rel.get("peerDependencies",{}):
                    meta=rel.get("peerDependenciesMeta",{}).get(dep,{})
                    if not (type(meta) is dict and meta.get("optional") is True) and dep in selected and dep not in reachable: reachable.add(dep); changed=True
        if set(selected)!=reachable: return
        graph={name:[] for name in selected}
        for name,rel in selected.items():
            if not allowed(rel): return
            for dep,constraint in rel.get("dependencies",{}).items():
                if dep not in selected or not matches(selected[dep]["version"],constraint): return
                graph[name].append(dep)
            for dep,constraint in rel.get("peerDependencies",{}).items():
                meta=rel.get("peerDependenciesMeta",{}).get(dep,{}); opt=type(meta) is dict and meta.get("optional") is True
                if dep not in selected:
                    if not opt: return
                elif not matches(selected[dep]["version"],constraint): return
        visiting,visited=set(),set()
        def visit(name):
            if name in visiting: raise ValueError("cycle")
            if name in visited: return
            visiting.add(name)
            for dep in graph[name]: visit(dep)
            visiting.remove(name); visited.add(name)
        try:
            for name in sorted(graph): visit(name)
        except ValueError: return
        key=(sum(1 for name in optional if name in selected),sum(1 for name,rel in selected.items() if current_lock.get(name)==rel["version"]),tuple(parse(selected[name]["version"]) if name in selected else (-1,-1,-1) for name in names))
        solutions.append((key,selected))
    def search(index):
        if index==len(names): validate(); return
        name=names[index]
        for release in options[name]+[None]: assignments[name]=release; search(index+1)
        assignments.pop(name,None)
    search(0)
    if not solutions: raise ValueError("unresolvable")
    selected=max(solutions,key=lambda item:item[0])[1]
    return {"packages":[{"name":name,"version":selected[name]["version"],"source":"preserved" if current_lock.get(name)==selected[name]["version"] else "selected"} for name in sorted(selected)],"skipped_optional":sorted(name for name in optional if name not in selected)}
