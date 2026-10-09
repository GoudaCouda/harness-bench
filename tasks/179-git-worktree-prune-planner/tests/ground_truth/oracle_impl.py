def plan_git_worktree_prune(records, policy):
    if not isinstance(records,list) or not isinstance(policy,dict) or not isinstance(policy.get('now'),int) or not isinstance(policy.get('expire_after'),int) or policy['expire_after']<0 or not isinstance(policy.get('protected_branches'),list) or not isinstance(policy.get('main_path'),str): raise ValueError("records and policy")
    protected=set(policy['protected_branches']); seen=set(); decisions=[]
    for row in records:
        if not isinstance(row,dict) or not isinstance(row.get('id'),str) or not isinstance(row.get('path'),str) or not (row.get('branch') is None or isinstance(row.get('branch'),str)) or not isinstance(row.get('locked'),bool) or not isinstance(row.get('exists'),bool) or not isinstance(row.get('admin_exists'),bool) or not isinstance(row.get('dirty'),bool) or not isinstance(row.get('last_seen'),int): raise ValueError("worktree")
        if row['id'] in seen: raise ValueError("duplicate id")
        seen.add(row['id']); stale=policy['now']-row['last_seen']>=policy['expire_after']
        if row['path']==policy['main_path']: action,reason='keep','main_worktree'
        elif row['locked']: action,reason='keep','locked'
        elif row['branch'] in protected: action,reason='keep','protected_branch'
        elif row['exists'] and row['dirty']: action,reason='keep','dirty_existing_worktree'
        elif row['exists'] and not row['admin_exists']: action,reason='repair_registration','missing_admin_metadata'
        elif not row['exists'] and row['admin_exists'] and stale: action,reason='prune_admin','missing_and_expired'
        elif not row['exists'] and row['admin_exists']: action,reason='keep','missing_but_not_expired'
        elif not row['exists'] and not row['admin_exists']: action,reason='already_absent','no_metadata'
        else: action,reason='keep','healthy'
        decisions.append({'id':row['id'],'action':action,'reason':reason,'path':row['path']})
    decisions.sort(key=lambda x:x['id']); return {'decisions':decisions,'prune_paths':[x['path'] for x in decisions if x['action']=='prune_admin'],'repair_paths':[x['path'] for x in decisions if x['action']=='repair_registration']}
