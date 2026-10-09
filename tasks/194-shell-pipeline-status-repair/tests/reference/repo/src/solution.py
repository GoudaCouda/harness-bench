def plan_shell_pipeline_status(requests, policy):
    if not isinstance(requests,list) or not isinstance(policy,dict) or not isinstance(policy.get('retryable_statuses'),list): raise ValueError("requests and policy")
    retryable=set(policy['retryable_statuses']); seen=set(); decisions=[]
    for req in requests:
        if not isinstance(req,dict) or not isinstance(req.get('id'),str) or not isinstance(req.get('stages'),list) or not isinstance(req.get('pipefail'),bool) or not isinstance(req.get('replayable'),bool): raise ValueError("request")
        if req['id'] in seen: raise ValueError("duplicate id")
        seen.add(req['id']); codes=[]; side_effect=False
        raw_codes=[]
        for stage in req['stages']:
            if not isinstance(stage,dict) or not isinstance(stage.get('code'),int) or not 0<=stage['code']<=255: raise ValueError("stage")
            raw_codes.append(stage['code'])
        codes=list(raw_codes); downstream_success=True
        for index in range(len(req['stages'])-1,-1,-1):
            stage=req['stages'][index]; code=raw_codes[index]
            if code==141 and stage.get('expected_short_read') is True and downstream_success: code=0
            codes[index]=code; downstream_success=downstream_success and code==0
        side_effect=any(stage.get('side_effect') is True and codes[index]==0 for index,stage in enumerate(req['stages']))
        status=(next((code for code in reversed(codes) if code!=0),0) if req['pipefail'] else (codes[-1] if codes else 0))
        if status==0: action='complete'
        elif status in retryable and req['replayable'] and not side_effect: action='retry'
        elif status in retryable and side_effect: action='probe_or_block'
        else: action='fail'
        decisions.append({'id':req['id'],'status':status,'stage_statuses':codes,'action':action,'side_effect_committed':side_effect})
    decisions.sort(key=lambda x:x['id']); return {'decisions':decisions}
