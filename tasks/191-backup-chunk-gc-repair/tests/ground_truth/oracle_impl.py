def plan_backup_chunk_gc(nodes, policy):
    if not isinstance(nodes, list) or not isinstance(policy, dict) or not isinstance(policy.get('retain'), list): raise ValueError("nodes and policy")
    items = {}
    for node in nodes:
        if not isinstance(node, dict) or not isinstance(node.get('id'), str) or node.get('type') not in ('snapshot','chunk'): raise ValueError("node")
        if node['id'] in items: raise ValueError("duplicate id")
        if node['type'] == 'snapshot' and (not isinstance(node.get('chunks', []), list) or not (node.get('parent') is None or isinstance(node.get('parent'), str)) or node.get('state', 'complete') not in ('complete','partial','tombstoned') or not isinstance(node.get('hold', False), bool)): raise ValueError("snapshot")
        items[node['id']] = node
    snapshots = {k:v for k,v in items.items() if v['type']=='snapshot'}; chunks = {k for k,v in items.items() if v['type']=='chunk'}
    roots = set(policy['retain']) | {k for k,v in snapshots.items() if v.get('hold') or v.get('state') == 'partial'}
    if any(root not in snapshots for root in roots): raise ValueError("unknown retained snapshot")
    reachable_snapshots, reachable_chunks, missing, stack = set(), set(), set(), list(roots)
    while stack:
        sid = stack.pop()
        if sid in reachable_snapshots: continue
        reachable_snapshots.add(sid); snap = snapshots[sid]
        for chunk in snap.get('chunks', []):
            if chunk in chunks: reachable_chunks.add(chunk)
            else: missing.add(chunk)
        parent = snap.get('parent')
        if parent:
            if parent in snapshots: stack.append(parent)
            else: missing.add(parent)
    if missing: keep, delete = sorted(chunks), []
    else: keep, delete = sorted(reachable_chunks), sorted(chunks - reachable_chunks)
    return {'keep_chunks': keep, 'delete_chunks': delete, 'reachable_snapshots': sorted(reachable_snapshots), 'missing': sorted(missing), 'blocked': bool(missing)}
