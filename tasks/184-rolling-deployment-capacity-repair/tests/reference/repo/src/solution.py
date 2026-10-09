def plan_rolling_deployment_capacity(requests, policy):
    if not isinstance(requests,list) or not isinstance(policy,dict): raise ValueError("requests and policy")
    seen,decisions=set(),[]
    for row in requests:
        ints=('desired','old_total','old_ready','new_total','new_ready','terminating','max_surge','max_unavailable')
        if not isinstance(row,dict) or not isinstance(row.get('id'),str) or not all(isinstance(row.get(k),int) and row[k]>=0 for k in ints): raise ValueError("deployment")
        if row['id'] in seen: raise ValueError("duplicate id")
        seen.add(row['id'])
        if row['old_ready']>row['old_total'] or row['new_ready']>row['new_total']: raise ValueError("counts")
        total=row['old_total']+row['new_total']; available=row['old_ready']+row['new_ready']; max_total=row['desired']+row['max_surge']; min_available=max(0,row['desired']-row['max_unavailable'])
        create=max(0,min(row['desired']-row['new_total'],max_total-total-row['terminating']))
        projected_available=available
        deletable=max(0,projected_available-min_available); delete=min(row['old_ready'],deletable)
        if create>0: reason='surge_create'
        elif delete>0: reason='safe_old_delete'
        elif row['new_ready']<row['desired']: reason='wait_readiness_or_capacity'
        else: reason='complete'
        decisions.append({'id':row['id'],'create_new':create,'delete_old':delete,'reason':reason,'max_total':max_total,'min_available':min_available})
    decisions.sort(key=lambda x:x['id']); return {'decisions':decisions}
