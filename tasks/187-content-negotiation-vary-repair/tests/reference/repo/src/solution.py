def plan_content_negotiation_vary(requests, policy):
    if not isinstance(requests,list) or not isinstance(policy,dict): raise ValueError("requests and policy")
    def ranges(value,kind):
        result=[]
        for order,item in enumerate(value.split(',')):
            token,*params=[x.strip() for x in item.strip().split(';')]; q=1000
            for param in params:
                key,eq,val=param.partition('=')
                if key.lower()=='q' and eq:
                    try: q=int(float(val)*1000+0.5)
                    except ValueError: raise ValueError("q")
                    if not 0<=q<=1000: raise ValueError("q")
            specificity=0 if token=='*' or token=='*/*' else (1 if kind=='media' and token.endswith('/*') else len(token.split('-')) if kind=='language' else 2)
            result.append((token.lower(),q,specificity,-order))
        return result
    def media_match(token,value):
        return token=='*/*' or token==value or (token.endswith('/*') and value.startswith(token[:-1]))
    def lang_match(token,value): return token=='*' or value==token or value.startswith(token+'-')
    seen,decisions=set(),[]
    for req in requests:
        if not isinstance(req,dict) or not isinstance(req.get('id'),str) or not isinstance(req.get('accept','*/*'),str) or not isinstance(req.get('accept_language','*'),str) or not isinstance(req.get('variants'),list): raise ValueError("request")
        if req['id'] in seen: raise ValueError("duplicate id")
        seen.add(req['id']); mr=ranges(req.get('accept','*/*'),'media'); lr=ranges(req.get('accept_language','*'),'language'); ranked=[]; variant_ids=set()
        for var in req['variants']:
            if not isinstance(var,dict) or not isinstance(var.get('id'),str) or not isinstance(var.get('media_type'),str) or not isinstance(var.get('language'),str) or not isinstance(var.get('size'),int) or var['size']<0 or var['id'] in variant_ids: raise ValueError("variant")
            variant_ids.add(var['id'])
            mm=[x for x in mr if media_match(x[0],var['media_type'].lower())]; lm=[x for x in lr if lang_match(x[0],var['language'].lower())]
            if not mm or not lm: continue
            bestm=max(mm,key=lambda x:(x[2],x[3])); bestl=max(lm,key=lambda x:(x[2],x[3]))
            if bestm[1]==0 or bestl[1]==0: continue
            ranked.append({'score':bestm[1]*bestl[1],'media_specificity':bestm[2],'language_specificity':bestl[2],'size':var['size'],'id':var['id']})
        ranked.sort(key=lambda x:(-x['score'],-x['media_specificity'],-x['language_specificity'],x['size'],x['id'])); selected=ranked[0]['id'] if ranked else None
        media_values={v['media_type'] for v in req['variants']}; lang_values={v['language'] for v in req['variants']}; vary=[]
        if len(media_values)>1: vary.append('Accept')
        if len(lang_values)>1: vary.append('Accept-Language')
        decisions.append({'id':req['id'],'status':'selected' if selected else 'not_acceptable','selected':selected,'vary':vary})
    decisions.sort(key=lambda x:x['id']); return {'decisions':decisions}
