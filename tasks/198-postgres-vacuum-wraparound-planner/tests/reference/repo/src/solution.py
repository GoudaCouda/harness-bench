def plan_postgres_vacuum_wraparound(requests, policy):
    if not isinstance(requests,list) or not isinstance(policy,dict) or not all(isinstance(policy.get(k),int) for k in ('warn_age','emergency_age','worker_slots','io_budget_mb')) or not 0<policy['warn_age']<policy['emergency_age'] or policy['worker_slots']<0 or policy['io_budget_mb']<0: raise ValueError("requests and policy")
    seen,ranked,decisions=set(),[],[]
    for row in requests:
        if not isinstance(row,dict) or not isinstance(row.get('id'),str) or not isinstance(row.get('database'),str) or not isinstance(row.get('age'),int) or row['age']<0 or not isinstance(row.get('size_mb'),int) or row['size_mb']<0 or not isinstance(row.get('locked'),bool): raise ValueError("table")
        if row['id'] in seen: raise ValueError("duplicate id")
        seen.add(row['id'])
        if row['locked']: decisions.append({'id':row['id'],'action':'blocked_lock','priority':'emergency' if row['age']>=policy['emergency_age'] else 'warning' if row['age']>=policy['warn_age'] else 'normal'})
        elif row['age']<policy['warn_age']: decisions.append({'id':row['id'],'action':'monitor','priority':'normal'})
        else: ranked.append(row)
    ranked.sort(key=lambda x:(x['age']<policy['emergency_age'],-x['age'],x['size_mb'],x['database'],x['id']))
    slots,budget=policy['worker_slots'],policy['io_budget_mb']
    for row in ranked:
        priority='emergency' if row['age']>=policy['emergency_age'] else 'warning'
        if slots<=0: action='defer_workers'
        elif row['size_mb']>budget: action='defer_io'
        else: action='vacuum'; slots-=1; budget-=row['size_mb']
        decisions.append({'id':row['id'],'action':action,'priority':priority})
    decisions.sort(key=lambda x:x['id']); return {'decisions':decisions,'workers_remaining':slots,'io_remaining_mb':budget,'emergency_blocked':sum(x['priority']=='emergency' and x['action']!='vacuum' for x in decisions)}
