def plan_message_inbox_dedup(events, policy):
    if not isinstance(events,list) or not isinstance(policy,dict): raise ValueError("events and policy")
    seen_event, identities, producers, process, conflicts = set(), {}, {}, [], []
    ordered=sorted(events,key=lambda x:(x.get('at',-1),x.get('id','')) if isinstance(x,dict) else (-1,''))
    for row in ordered:
        if not isinstance(row,dict) or not all(isinstance(row.get(k),t) for k,t in (('id',str),('producer',str),('epoch',int),('seq',int),('payload_hash',str),('at',int))) or row.get('kind') not in ('receive','tombstone'): raise ValueError("event")
        fingerprint=(row['id'],row['producer'],row['epoch'],row['seq'],row['payload_hash'],row['kind'],row['at'])
        if not row['id'] or not row['producer'] or not row['payload_hash'] or row['epoch']<0 or row['seq']<0:
            raise ValueError("event identity")
        if fingerprint in seen_event: continue
        if row['id'] in seen_event: raise ValueError("event id conflict")
        seen_event.add(fingerprint); seen_event.add(row['id'])
        key=(row['producer'],row['epoch'],row['seq']); existing=identities.get(key)
        if existing is not None and existing!=row['payload_hash']:
            conflicts.append({'producer':row['producer'],'epoch':row['epoch'],'seq':row['seq']}); continue
        identities[key]=row['payload_hash']; current=producers.get(row['producer'],{'epoch':-1,'seq':-1,'tombstone':-1})
        if row['epoch']<current['epoch'] or (row['epoch']==current['epoch'] and row['seq']<=current['tombstone']): continue
        if row['epoch']>current['epoch']: current={'epoch':row['epoch'],'seq':-1,'tombstone':-1}
        if row['kind']=='tombstone': current['tombstone']=max(current['tombstone'],row['seq']); current['seq']=max(current['seq'],row['seq'])
        elif row['seq']>current['seq']: process.append({'producer':row['producer'],'epoch':row['epoch'],'seq':row['seq'],'payload_hash':row['payload_hash']}); current['seq']=row['seq']
        producers[row['producer']]=current
    process.sort(key=lambda x:(x['producer'],x['epoch'],x['seq'])); conflicts.sort(key=lambda x:(x['producer'],x['epoch'],x['seq']))
    return {'process':process,'conflicts':conflicts,'ledger':{k:producers[k] for k in sorted(producers)}}
