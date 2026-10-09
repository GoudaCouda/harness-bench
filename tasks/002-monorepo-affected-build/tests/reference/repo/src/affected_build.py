"""Affected-package planning for the Acorn monorepo."""


def plan_affected(changed_paths, graph):
    """Return buildable packages affected by the supplied repository paths."""

    if not isinstance(changed_paths, list) or not isinstance(graph, dict):
        raise ValueError("invalid planner input")
    packages = graph.get("packages")
    global_inputs = graph.get("global_inputs")
    if not isinstance(packages, dict) or not isinstance(global_inputs, dict):
        raise ValueError("invalid build graph")

    names = sorted(packages.keys())
    buildable = set()
    dependants = {}
    indegree = {}
    for name in names:
        record = packages.get(name)
        if not isinstance(name, str) or not isinstance(record, dict):
            raise ValueError("invalid package")
        dependencies = record.get("dependencies")
        roots = record.get("source_roots")
        generated = record.get("generated_inputs")
        if not isinstance(dependencies, list):
            raise ValueError("invalid dependencies")
        if not isinstance(roots, list) or not isinstance(generated, list):
            raise ValueError("invalid package paths")
        if record.get("buildable") is True:
            buildable.add(name)
        dependants[name] = []
        indegree[name] = len(dependencies)

    for name in names:
        for dependency in packages[name]["dependencies"]:
            if dependency not in packages:
                raise ValueError("missing dependency")
            dependants[dependency].append(name)

    ready = []
    for name in names:
        if indegree[name] == 0:
            ready.append(name)
    ready = sorted(ready)
    ordered = []
    while ready:
        name = ready[0]
        ready.remove(name)
        ordered.append(name)
        for dependant in sorted(dependants[name]):
            indegree[dependant] = indegree[dependant] - 1
            if indegree[dependant] == 0:
                ready.append(dependant)
                ready = sorted(ready)
    if len(ordered) != len(names):
        raise ValueError("dependency cycle")

    depth = {}
    for name in ordered:
        value = 0
        for dependency in packages[name]["dependencies"]:
            if dependency in buildable and depth[dependency] + 1 > value:
                value = depth[dependency] + 1
        depth[name] = value

    direct = set()
    unique_paths = set()
    for path in changed_paths:
        if not isinstance(path, str):
            raise ValueError("invalid changed path")
        unique_paths.add(path)
    for path in unique_paths:
        if path in global_inputs:
            targets = global_inputs[path]
            if not isinstance(targets, list):
                raise ValueError("invalid global input")
            for target in targets:
                if target not in packages:
                    raise ValueError("invalid global target")
                if target in buildable:
                    direct.add(target)
            continue

        generated_owner = None
        for name in names:
            if path in packages[name]["generated_inputs"] and name in buildable:
                generated_owner = name
                break
        if generated_owner is not None:
            direct.add(generated_owner)
            continue
        if path.lower().endswith(".md"):
            continue

        owner = None
        owner_length = -1
        for name in names:
            if name not in buildable:
                continue
            for root in packages[name]["source_roots"]:
                if path.startswith(root):
                    if len(root) > owner_length:
                        owner = name
                        owner_length = len(root)
        if owner is not None:
            direct.add(owner)

    affected = set(direct)
    changed = True
    while changed:
        changed = False
        for name in names:
            if name not in buildable or name in affected:
                continue
            for dependency in packages[name]["dependencies"]:
                if dependency in affected:
                    affected.add(name)
                    changed = True
                    break

    result = []
    maximum_depth = 0
    if depth:
        maximum_depth = max(depth.values())
    for level in range(maximum_depth + 1):
        for name in sorted(affected):
            if depth[name] == level:
                result.append(name)
    return result
