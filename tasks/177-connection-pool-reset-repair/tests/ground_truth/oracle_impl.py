def plan_connection_pool_reset(requests, policy):
    if not isinstance(requests,list) or not isinstance(policy,dict) or not isinstance(policy.get('capacity'),int) or policy['capacity']<1 or not isinstance(policy.get('connections'),list): raise ValueError("requests and policy")
    conns={}
    for row in policy['connections']:
        if not isinstance(row,dict) or not isinstance(row.get('id'),str) or not row['id'] or not isinstance(row.get('generation'),int) or row['generation']<0 or row.get('state') not in ('idle','leased','quarantine','closed'): raise ValueError("connection")
        owner=row.get('owner'); leased=row['state']=='leased'
        if (leased and (not isinstance(owner,str) or not owner)) or (not leased and owner is not None): raise ValueError("connection owner")
        if row['id'] in conns: raise ValueError("duplicate connection")
        conns[row['id']]={'generation':row['generation'],'state':row['state'],'owner':row.get('owner')}
    seen,actions,queue=set(),[],[]; serial=0
    if sum(v['state']!='closed' for v in conns.values())>policy['capacity']:
        raise ValueError("capacity")
    for op in sorted(requests,key=lambda x:(x.get('at',-1),x.get('id','')) if isinstance(x,dict) else (-1,'')):
        if not isinstance(op,dict) or not isinstance(op.get('id'),str) or not op['id'] or not isinstance(op.get('at'),int) or op.get('kind') not in ('checkout','release','reset'): raise ValueError("operation")
        if op['id'] in seen: raise ValueError("duplicate operation")
        seen.add(op['id']); kind=op['kind']
        if kind=='release' and (not isinstance(op.get('client'),str) or not op['client'] or not isinstance(op.get('clean'),bool)): raise ValueError("release")
        if kind=='reset' and not isinstance(op.get('success'),bool): raise ValueError("reset")
        if kind!='checkout' and (not isinstance(op.get('connection'),str) or not op['connection']): raise ValueError("connection")
        if kind=='checkout':
            if not isinstance(op.get('client'),str) or not op['client']: raise ValueError("client")
            idle=sorted(cid for cid,v in conns.items() if v['state']=='idle')
            if idle:
                cid=idle[0]; conns[cid]['state']='leased'; conns[cid]['owner']=op['client']; action='leased'
            elif len([1 for v in conns.values() if v['state']!='closed'])<policy['capacity']:
                while True:
                    cid=f'new-{serial}'; serial+=1
                    if cid not in conns: break
                conns[cid]={'generation':0,'state':'leased','owner':op['client']}; action='created'
            else: cid=None; action='queued'; queue.append((op['at'],op['id'],op['client']))
            actions.append({'id':op['id'],'action':action,'connection':cid})
        else:
            cid=op.get('connection')
            if cid not in conns: raise ValueError("unknown connection")
            conn=conns[cid]
            if kind=='release':
                if conn['state']!='leased' or conn['owner']!=op.get('client'): action='ownership_block'
                elif op.get('clean') is True: conn['state']='idle'; conn['owner']=None; action='released'
                else: conn['state']='quarantine'; conn['owner']=None; action='quarantined'
            else:
                if conn['state']!='quarantine': action='reset_not_needed'
                elif op.get('success') is True: conn['generation']+=1; conn['state']='idle'; action='reset'
                else: conn['state']='closed'; action='closed'
            actions.append({'id':op['id'],'action':action,'connection':cid})
        while queue:
            idle=sorted(cid for cid,v in conns.items() if v['state']=='idle')
            if not idle: break
            _,qid,client=queue.pop(0); cid=idle[0]; conns[cid]['state']='leased'; conns[cid]['owner']=client
            actions.append({'id':qid+':dequeue','action':'leased_from_queue','connection':cid})
    final=[{'id':cid,**conns[cid]} for cid in sorted(conns)]; return {'actions':actions,'queue':[x[1] for x in queue],'connections':final}
