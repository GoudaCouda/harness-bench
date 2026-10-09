def plan_mime_multipart_decoding(requests, policy):
    if not isinstance(requests,list) or not isinstance(policy,dict) or not isinstance(policy.get('max_parts'),int) or policy['max_parts']<1: raise ValueError("requests and policy")
    alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
    def b64(text):
        clean=''.join(text.split()); pad=len(clean)-len(clean.rstrip('=')); core=clean[:-pad] if pad else clean
        if len(clean)%4 or pad>2 or '=' in core or any(ch not in alphabet+'=' for ch in clean): raise ValueError("base64")
        out=[]
        for i in range(0,len(clean),4):
            block=clean[i:i+4]; value=0; pad=block.count('=')
            for ch in block: value=(value<<6)|(0 if ch=='=' else alphabet.index(ch))
            out.extend([(value>>16)&255,(value>>8)&255,value&255][:(3-pad)])
        return bytes(out).decode('utf-8')
    def qp(text):
        out=[]; i=0
        while i<len(text):
            if text[i]=='=' and i+2<len(text) and all(ch in '0123456789abcdefABCDEF' for ch in text[i+1:i+3]): out.append(int(text[i+1:i+3],16)); i+=3
            elif text[i:i+2]=='=\n': i+=2
            elif text[i:i+3]=='=\r\n': i+=3
            elif text[i]=='=': raise ValueError("quoted-printable")
            else: out.extend(text[i].encode()); i+=1
        return bytes(out).decode('utf-8')
    def boundary_of(content_type):
        for part in content_type.split(';')[1:]:
            key,sep,value=part.strip().partition('=')
            if sep and key.lower()=='boundary': return value.strip().strip('"')
        return None
    def parse(raw,boundary,path,parts):
        marker='--'+boundary; chunks=raw.split(marker)
        if len(chunks)<3 or not chunks[-1].lstrip().startswith('--'): raise ValueError("multipart boundary")
        for index,chunk in enumerate(chunks[1:-1]):
            chunk=chunk.lstrip('\r\n'); head,sep,body=chunk.partition('\r\n\r\n')
            if not sep: head,sep,body=chunk.partition('\n\n')
            if not sep: raise ValueError("part headers")
            headers={}
            for line in head.replace('\r\n','\n').split('\n'):
                name,colon,value=line.partition(':')
                if not colon: raise ValueError("header")
                headers[name.strip().lower()]=value.strip()
            body=body.rstrip('\r\n'); ctype=headers.get('content-type','text/plain'); nested=boundary_of(ctype)
            if ctype.lower().startswith('multipart/'):
                if not nested: raise ValueError("nested boundary")
                parse(body,nested,path+[index],parts); continue
            enc=headers.get('content-transfer-encoding','7bit').lower()
            if enc=='base64': decoded=b64(body)
            elif enc=='quoted-printable': decoded=qp(body)
            elif enc in ('7bit','8bit'): decoded=body
            else: raise ValueError("transfer encoding")
            disposition=headers.get('content-disposition',''); filename=None
            for item in disposition.split(';')[1:]:
                key,eq,value=item.strip().partition('=')
                if eq and key.lower()=='filename': filename=value.strip().strip('"')
            parts.append({'path':path+[index],'content_type':ctype.split(';')[0].lower(),'content_id':headers.get('content-id','').strip('<>') or None,'filename':filename,'body':decoded})
            if len(parts)>policy['max_parts']: raise ValueError("part limit")
    seen, results=set(),[]
    for req in requests:
        if not isinstance(req,dict) or not isinstance(req.get('id'),str) or not isinstance(req.get('raw'),str) or not isinstance(req.get('boundary'),str): raise ValueError("message")
        if req['id'] in seen: raise ValueError("duplicate id")
        seen.add(req['id']); parts=[]; parse(req['raw'],req['boundary'],[],parts); ids=[p['content_id'] for p in parts if p['content_id']]
        if len(ids)!=len(set(ids)): raise ValueError("duplicate content id")
        attachments=[p for p in parts if p['filename'] is not None]
        results.append({'id':req['id'],'parts':parts,'attachments':attachments})
    results.sort(key=lambda x:x['id']); return {'messages':results,'attachment_count':sum(len(x['attachments']) for x in results)}
