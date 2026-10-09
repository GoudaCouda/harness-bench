def plan_retention_hold_compaction(requests, policy):
    if not isinstance(requests,list) or not isinstance(policy,dict) or not all(isinstance(policy.get(k),int) for k in ('watermark','data_ttl','tombstone_ttl','capacity_bytes')) or policy['data_ttl']<0 or policy['tombstone_ttl']<0 or policy['capacity_bytes']<0: raise ValueError("requests and policy")
    seen,eligible,decisions=set(),[],[]
    for row in requests:
        if not isinstance(row,dict) or not isinstance(row.get('id'),str) or not isinstance(row.get('tenant'),str) or not isinstance(row.get('event_time'),int) or not isinstance(row.get('bytes'),int) or row['bytes']<0 or row.get('kind') not in ('data','tombstone') or not isinstance(row.get('hold',False),bool): raise ValueError("record")
        if row['id'] in seen: raise ValueError("duplicate id")
        seen.add(row['id']); ttl=policy['tombstone_ttl'] if row['kind']=='tombstone' else policy['data_ttl']; expired=row['event_time']+ttl<=policy['watermark']
        if row['hold']: decisions.append({'id':row['id'],'action':'keep','reason':'legal_hold','bytes':row['bytes']})
        elif expired: eligible.append(row)
        else: decisions.append({'id':row['id'],'action':'keep','reason':'not_expired','bytes':row['bytes']})
    used=0
    for row in sorted(eligible,key=lambda x:(x['event_time'],x['tenant'],x['id'])):
        if used+row['bytes']<=policy['capacity_bytes']: action,reason='delete','expired'; used+=row['bytes']
        else: action,reason='defer','capacity'
        decisions.append({'id':row['id'],'action':action,'reason':reason,'bytes':row['bytes']})
    decisions.sort(key=lambda x:x['id']); return {'decisions':decisions,'planned_bytes':used,'remaining_capacity':policy['capacity_bytes']-used}
