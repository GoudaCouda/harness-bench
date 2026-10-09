def plan_systemd_restart_budget(events, policy):
    if not isinstance(events,list) or not isinstance(policy,dict) or not all(isinstance(policy.get(k),int) for k in ('now','interval','burst','restart_sec','success_reset_sec')) or policy['interval']<=0 or policy['burst']<1 or policy['restart_sec']<0 or policy['success_reset_sec']<0: raise ValueError("events and policy")
    seen, grouped=set(),{}
    for row in events:
        if not isinstance(row,dict) or not isinstance(row.get('id'),str) or not isinstance(row.get('unit'),str) or not isinstance(row.get('at'),int) or row.get('event') not in ('start','exit','reset') or not isinstance(row.get('generation'),int): raise ValueError("event")
        if row['id'] in seen: raise ValueError("duplicate id")
        if row['event']=='exit' and row.get('result') not in ('success','manual_stop','failure','watchdog'):
            raise ValueError("exit result")
        seen.add(row['id']); grouped.setdefault(row['unit'],[]).append(row)
    decisions=[]
    for unit,rows in grouped.items():
        generation=max(x['generation'] for x in rows); rows=sorted((x for x in rows if x['generation']==generation and x['at']<=policy['now']),key=lambda x:(x['at'],x['id']))
        starts=[]; last_start=None; running=False; last_exit=None
        for row in rows:
            if row['event']=='reset': starts=[]
            elif row['event']=='start': starts=[t for t in starts if row['at']-policy['interval']<t]; starts.append(row['at']); last_start=row['at']; running=True
            else:
                running=False; last_exit=row
                if last_start is not None and row['at']-last_start>=policy['success_reset_sec']: starts=[]
        starts=[t for t in starts if policy['now']-policy['interval']<t]
        if running: action, next_at, reason='none',None,'running'
        elif last_exit is None or last_exit.get('result') in ('success','manual_stop'): action,next_at,reason='none',None,'not_restartable'
        elif len(starts)>=policy['burst']: action,next_at,reason='suppressed',(min(starts)+policy['interval']),'start_limit'
        else: action,next_at,reason='restart',(last_exit['at']+policy['restart_sec']),'failure_restart'
        decisions.append({'unit':unit,'generation':generation,'action':action,'next_at':next_at,'reason':reason,'starts_in_window':len(starts)})
    decisions.sort(key=lambda x:x['unit']); return {'decisions':decisions,'suppressed':sum(x['action']=='suppressed' for x in decisions)}
