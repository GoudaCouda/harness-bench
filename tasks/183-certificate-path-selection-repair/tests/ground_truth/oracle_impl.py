def plan_certificate_path_selection(nodes, policy):
    if not isinstance(nodes, list) or not isinstance(policy, dict) or not isinstance(policy.get('leaf'), str) or not isinstance(policy.get('anchors'), list) or not isinstance(policy.get('now'), int) or not isinstance(policy.get('dns_name'), str): raise ValueError("nodes and policy")
    certs = {}
    for node in nodes:
        required = ('id','subject','issuer','not_before','not_after','is_ca')
        if not isinstance(node, dict) or not all(k in node for k in required) or not all(isinstance(node[k], str) for k in ('id','subject','issuer')) or not isinstance(node['not_before'], int) or not isinstance(node['not_after'], int) or not isinstance(node['is_ca'], bool) or node['not_before'] >= node['not_after']: raise ValueError("certificate")
        if node['id'] in certs: raise ValueError("duplicate certificate")
        certs[node['id']] = node
    if policy['leaf'] not in certs or any(a not in certs for a in policy['anchors']): raise ValueError("leaf or anchor")
    leaf = certs[policy['leaf']]
    paths, rejected = [], []
    def walk(cid, path):
        cert = certs[cid]
        if cid in policy['anchors']:
            paths.append(path); return
        parents = sorted(x['id'] for x in certs.values() if x['subject'] == cert['issuer'] and x['id'] not in path)
        if not parents: rejected.append({'path': path, 'reason': 'issuer_missing'}); return
        for parent in parents: walk(parent, path + [parent])
    walk(policy['leaf'], [policy['leaf']])
    valid = []
    for path in paths:
        reason = None
        for index, cid in enumerate(path):
            cert = certs[cid]
            if not cert['not_before'] <= policy['now'] < cert['not_after']: reason = 'time_invalid'; break
            if index > 0 and not cert['is_ca']: reason = 'issuer_not_ca'; break
            if index > 0 and cert.get('path_len') is not None and index - 1 > cert['path_len']: reason = 'path_length'; break
        if reason is None and policy['dns_name'] not in leaf.get('dns_names', []): reason = 'name_mismatch'
        if reason: rejected.append({'path': path, 'reason': reason})
        else: valid.append(path)
    valid.sort(key=lambda p: (len(p), p)); rejected.sort(key=lambda r: (r['path'], r['reason']))
    return {'status': 'selected' if valid else 'no_valid_path', 'selected_path': valid[0] if valid else None, 'valid_paths': valid, 'rejected': rejected}
