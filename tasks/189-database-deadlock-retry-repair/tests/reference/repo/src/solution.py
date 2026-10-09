def plan_database_deadlock_retry(requests, policy):
    if not isinstance(requests,list) or not isinstance(policy,dict) or not isinstance(policy.get('max_attempts'),int) or policy['max_attempts']<1 or not isinstance(policy.get('retryable'),list) or not isinstance(policy.get('backoff_ms'),list): raise ValueError("requests and policy")
    retryable=set(policy['retryable']); seen=set(); decisions=[]
    for req in requests:
        if not isinstance(req,dict) or not isinstance(req.get('id'),str) or not isinstance(req.get('attempts'),list) or not isinstance(req.get('replayable'),bool): raise ValueError("request")
        if req['id'] in seen: raise ValueError("duplicate id")
        seen.add(req['id']); action='blocked'; reason='no_attempt'; used=0; backoff=None
        for index,attempt in enumerate(req['attempts'][:policy['max_attempts']]):
            if not isinstance(attempt,dict) or not isinstance(attempt.get('outcome'),str) or attempt.get('phase') not in ('before_commit','commit','after_commit'): raise ValueError("attempt")
            used=index+1; outcome=attempt['outcome']
            if outcome=='success': action,reason='complete','committed'; break
            if attempt['phase']=='commit' and outcome in ('connection_lost','timeout'):
                probe=attempt.get('commit_probe')
                if probe=='committed': action,reason='complete','probe_committed'
                elif probe=='absent' and req['replayable'] and used<policy['max_attempts']: action,reason='retry','probe_absent'
                else: action,reason='probe_or_block','ambiguous_commit'
                break
            if attempt['phase']=='before_commit' and outcome in retryable and req['replayable'] and used<policy['max_attempts']:
                action,reason='retry','retryable_abort'; backoff=policy['backoff_ms'][min(index,len(policy['backoff_ms'])-1)] if policy['backoff_ms'] else 0
                continue
            action,reason=('exhausted','attempt_budget') if attempt['phase']=='before_commit' and outcome in retryable else ('blocked','non_retryable'); break
        decisions.append({'id':req['id'],'action':action,'reason':reason,'attempts_used':used,'next_backoff_ms':backoff if action=='retry' else None})
    decisions.sort(key=lambda x:x['id']); return {'decisions':decisions,'complete':sum(x['action']=='complete' for x in decisions)}
