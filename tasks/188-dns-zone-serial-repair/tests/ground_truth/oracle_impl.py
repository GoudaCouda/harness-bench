def plan_dns_zone_serial(events, policy):
    if not isinstance(events,list) or not isinstance(policy,dict) or not isinstance(policy.get('zones'),dict): raise ValueError("events and policy")
    modulus=2**32; half=2**31; state={}
    for zone,value in policy['zones'].items():
        if not isinstance(zone,str) or not isinstance(value,dict) or not isinstance(value.get('serial'),int) or not 0<=value['serial']<modulus or not isinstance(value.get('epoch'),int): raise ValueError("zone state")
        state[zone]={'serial':value['serial'],'epoch':value['epoch']}
    seen, decisions=set(),[]
    for row in sorted(events,key=lambda x:(x.get('observed_at',-1),x.get('id','')) if isinstance(x,dict) else (-1,'')):
        if not isinstance(row,dict) or not all(isinstance(row.get(k),t) for k,t in (('id',str),('zone',str),('serial',int),('epoch',int),('observed_at',int))) or not 0<=row['serial']<modulus or row['zone'] not in state: raise ValueError("event")
        if row['id'] in seen: raise ValueError("duplicate id")
        seen.add(row['id']); current=state[row['zone']]
        if row['epoch']<current['epoch']: action,reason='ignore','stale_epoch'
        elif row['epoch']>current['epoch']: action,reason='apply','new_primary_epoch'; state[row['zone']]={'serial':row['serial'],'epoch':row['epoch']}
        else:
            diff=(row['serial']-current['serial'])%modulus
            if diff==0: action,reason='ignore','equal_serial'
            elif diff==half: action,reason='block','ambiguous_half_range'
            elif diff<half: action,reason='apply','newer_serial'; current['serial']=row['serial']
            else: action,reason='ignore','older_serial'
        decisions.append({'id':row['id'],'zone':row['zone'],'action':action,'reason':reason,'serial':row['serial'],'epoch':row['epoch']})
    decisions.sort(key=lambda x:x['id']); return {'decisions':decisions,'zones':{k:state[k] for k in sorted(state)},'blocked':sum(x['action']=='block' for x in decisions)}
