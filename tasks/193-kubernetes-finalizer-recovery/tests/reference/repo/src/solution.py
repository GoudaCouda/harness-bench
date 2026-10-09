def plan_kubernetes_finalizer(nodes, policy):
    if not isinstance(nodes, list) or not isinstance(policy, dict) or not isinstance(policy.get('managed_finalizers'), list) or policy.get('propagation') not in ('foreground','orphan'): raise ValueError("nodes and policy")
    if not all(isinstance(value, str) and value for value in policy['managed_finalizers']) or not isinstance(policy.get('protected', []), list) or not all(isinstance(value, str) and value for value in policy.get('protected', [])):
        raise ValueError("policy lists")
    managed, protected = set(policy['managed_finalizers']), set(policy.get('protected', [])); resources = {}
    for node in nodes:
        if not isinstance(node, dict) or not isinstance(node.get('id'), str) or not isinstance(node.get('finalizers', []), list) or not (node.get('owner') is None or isinstance(node.get('owner'), str)) or not isinstance(node.get('dependents_gone', False), bool) or not all(isinstance(value, str) and value for value in node.get('finalizers', [])) or not (node.get('deletion_timestamp') is None or isinstance(node.get('deletion_timestamp'), int)): raise ValueError("resource")
        if node['id'] in resources: raise ValueError("duplicate resource")
        resources[node['id']] = node
    if any(row.get('owner') is not None and row['owner'] not in resources for row in resources.values()): raise ValueError("unknown owner")
    candidates, blocked, untouched = set(), [], []
    for rid, row in resources.items():
        if row.get('deletion_timestamp') is None: untouched.append(rid); continue
        if not row.get('finalizers'):
            continue
        unknown = sorted(set(row['finalizers']) - managed)
        if rid in protected: blocked.append({'id': rid, 'reason': 'protected'}); continue
        if unknown: blocked.append({'id': rid, 'reason': 'unknown_finalizer'}); continue
        if policy['propagation'] == 'foreground' and not row.get('dependents_gone'): blocked.append({'id': rid, 'reason': 'dependents_remaining'}); continue
        candidates.add(rid)
    # Owners may only finalize after candidate children.
    graph = {rid: set() for rid in candidates}
    for rid in candidates:
        owner = resources[rid].get('owner')
        if owner in candidates: graph[owner].add(rid)
    order = []
    while graph:
        ready = sorted(rid for rid,deps in graph.items() if not deps)
        if not ready:
            for rid in sorted(graph): blocked.append({'id': rid, 'reason': 'owner_cycle'})
            break
        order.extend(ready)
        for rid in ready: graph.pop(rid)
        for deps in graph.values(): deps.difference_update(ready)
    blocked.sort(key=lambda x: x['id']); untouched.sort()
    return {'remove_finalizers': order, 'blocked': blocked, 'untouched': untouched}
