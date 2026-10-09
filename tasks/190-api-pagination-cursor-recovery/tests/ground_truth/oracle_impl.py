def plan_api_pagination_cursor(requests, policy):
    if not isinstance(requests,list) or not isinstance(policy,dict): raise ValueError("requests and policy")
    seen_req, decisions=set(),[]
    for req in requests:
        if not isinstance(req,dict) or not isinstance(req.get('id'),str) or not isinstance(req.get('pages'),list) or not isinstance(req.get('checkpoint_key'),int): raise ValueError("request")
        if req['id'] in seen_req: raise ValueError("duplicate id")
        seen_req.add(req['id']); snapshot=None; cursors=set(); item_ids=set(); items=[]; mode='cursor'; status='complete'; last_key=req['checkpoint_key']
        for page in req['pages']:
            if not isinstance(page,dict) or page.get('status') not in ('ok','invalid_cursor') or not isinstance(page.get('cursor'),str) or not isinstance(page.get('items'),list) or not isinstance(page.get('snapshot'),str): raise ValueError("page")
            if snapshot is None: snapshot=page['snapshot']
            elif page['snapshot']!=snapshot: status='blocked'; break
            if page['cursor'] in cursors: status='blocked'; break
            cursors.add(page['cursor'])
            if page['status']=='invalid_cursor': mode='stable_key_fallback'
            for item in page['items']:
                if not isinstance(item,dict) or not isinstance(item.get('id'),str) or not isinstance(item.get('sort_key'),int): raise ValueError("item")
                if mode=='stable_key_fallback' and item['sort_key']<=req['checkpoint_key']: continue
                if item['id'] in item_ids: continue
                if item['sort_key']<last_key: status='blocked'; break
                item_ids.add(item['id']); items.append({'id':item['id'],'sort_key':item['sort_key']}); last_key=max(last_key,item['sort_key'])
            if status=='blocked': break
        decisions.append({'id':req['id'],'status':status,'mode':mode,'items':items if status=='complete' else [],'checkpoint_key':last_key if status=='complete' else req['checkpoint_key'],'snapshot':snapshot})
    decisions.sort(key=lambda x:x['id']); return {'decisions':decisions}
