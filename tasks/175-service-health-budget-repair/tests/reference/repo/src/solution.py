def plan_service_health_budget(events, policy):
    if not isinstance(events,list) or not isinstance(policy,dict) or not all(isinstance(policy.get(k),int) for k in ('now','window','max_failures','recovery_successes')) or policy['window']<0 or policy['max_failures']<1 or policy['recovery_successes']<1: raise ValueError("events and policy")
    seen, grouped = set(), {}
    for row in events:
        if not isinstance(row,dict) or not isinstance(row.get('id'),str) or not isinstance(row.get('service'),str) or not isinstance(row.get('at'),int) or not isinstance(row.get('generation'),int) or row.get('status') not in ('success','failure','maintenance_start','maintenance_end'): raise ValueError("probe")
        if row['id'] in seen: raise ValueError("duplicate id")
        seen.add(row['id']); grouped.setdefault(row['service'],[]).append(row)
    states=[]
    for service,rows in grouped.items():
        generation=max(x['generation'] for x in rows); rows=sorted((x for x in rows if x['generation']==generation and policy['now']-policy['window'] < x['at'] <= policy['now']),key=lambda x:(x['at'],x['id']))
        maintenance=False; failures=0; consecutive_success=0; state='healthy'
        for row in rows:
            if row['status']=='maintenance_start': maintenance=True; failures=0; consecutive_success=0
            elif row['status']=='maintenance_end': maintenance=False; failures=0; consecutive_success=0
            elif maintenance: continue
            elif row['status']=='failure': failures+=1; consecutive_success=0
            else:
                consecutive_success+=1
                if state=='unhealthy' and consecutive_success>=policy['recovery_successes']: state='healthy'; failures=0
            if failures>=policy['max_failures']: state='unhealthy'
        states.append({'service':service,'generation':generation,'state':'maintenance' if maintenance else state,'failures':failures,'consecutive_success':consecutive_success})
    states.sort(key=lambda x:x['service'])
    return {'states':states,'summary':{'healthy':sum(x['state']=='healthy' for x in states),'unhealthy':sum(x['state']=='unhealthy' for x in states),'maintenance':sum(x['state']=='maintenance' for x in states)}}
