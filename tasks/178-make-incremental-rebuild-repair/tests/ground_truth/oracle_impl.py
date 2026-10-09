def plan_make_incremental_rebuild(nodes, policy):
    if not isinstance(nodes, list) or not isinstance(policy, dict) or not isinstance(policy.get('targets'), list): raise ValueError("nodes and policy")
    graph = {}
    for node in nodes:
        if not isinstance(node, dict) or not isinstance(node.get('id'), str) or not node['id'] or not isinstance(node.get('prereqs', []), list) or not isinstance(node.get('order_only', []), list) or not isinstance(node.get('phony', False), bool) or not isinstance(node.get('recipe', False), bool) or not (node.get('mtime') is None or isinstance(node.get('mtime'), int)): raise ValueError("node")
        dependencies=node.get('prereqs', [])+node.get('order_only', [])
        if any(not isinstance(dep,str) or not dep for dep in dependencies): raise ValueError("dependency")
        if node['id'] in graph: raise ValueError("duplicate target")
        graph[node['id']] = node
    requested = policy['targets']
    if any(not isinstance(x, str) for x in requested): raise ValueError("targets")
    missing, closure = set(), set()
    def collect(name):
        if name in closure: return
        if name not in graph: missing.add(name); return
        closure.add(name)
        for dep in graph[name].get('prereqs', []) + graph[name].get('order_only', []): collect(dep)
    for name in requested: collect(name)
    visiting, done, order, cycles = [], set(), [], []
    def visit(name):
        if name in visiting:
            cycles.append(visiting[visiting.index(name):] + [name]); return
        if name in done or name not in graph: return
        visiting.append(name)
        for dep in sorted(graph[name].get('prereqs', []) + graph[name].get('order_only', [])): visit(dep)
        visiting.pop(); done.add(name); order.append(name)
    for name in sorted(requested): visit(name)
    if cycles or missing: return {'order': [], 'rebuild': [], 'up_to_date': [], 'missing': sorted(missing), 'cycles': cycles}
    rebuilt, up = set(), []
    for name in order:
        node = graph[name]; normal = node.get('prereqs', [])
        needs = node.get('phony', False) or node.get('mtime') is None or any(dep in rebuilt for dep in normal) or any(graph[dep].get('mtime') is not None and node.get('mtime') is not None and graph[dep]['mtime'] > node['mtime'] for dep in normal)
        if needs and node.get('recipe', False): rebuilt.add(name)
        elif name in closure: up.append(name)
    return {'order': order, 'rebuild': [x for x in order if x in rebuilt], 'up_to_date': up, 'missing': [], 'cycles': []}
