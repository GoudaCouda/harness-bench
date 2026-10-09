import ipaddress


def plan_proxy_no_proxy_matching(records, policy):
    if not isinstance(records,list) or not isinstance(policy,dict) or not ('no_proxy' in policy) or not (policy['no_proxy'] is None or isinstance(policy['no_proxy'],str)):
        raise ValueError("records and policy")
    raw_entries=[] if policy['no_proxy'] in (None,'') else [x.strip() for x in policy['no_proxy'].split(',') if x.strip()]
    entries=[]
    for original in raw_entries:
        if original == '*':
            entries.append((original,'wildcard',None,None)); continue
        token=original; required_port=None
        if token.startswith('['):
            end=token.find(']')
            if end<0: raise ValueError("ipv6 entry")
            try: value=ipaddress.IPv6Address(token[1:end])
            except ipaddress.AddressValueError as exc: raise ValueError("ipv6 entry") from exc
            rest=token[end+1:]
            if rest:
                if not rest.startswith(':') or not rest[1:].isdigit(): raise ValueError("port")
                required_port=int(rest[1:])
            kind,target='ipv6',value
        else:
            if token.count(':')>1: raise ValueError("IPv6 entries must be bracketed")
            if ':' in token:
                token,port=token.rsplit(':',1)
                if not token or not port.isdigit(): raise ValueError("port")
                required_port=int(port)
            if '/' in token:
                try: target=ipaddress.IPv4Network(token,strict=False)
                except (ipaddress.AddressValueError,ipaddress.NetmaskValueError) as exc: raise ValueError("cidr") from exc
                kind='cidr'
            else:
                target=token.lower().lstrip('.').rstrip('.')
                if not target or any(not label or len(label)>63 for label in target.split('.')): raise ValueError("domain")
                kind='domain'
        if required_port is not None and not 1<=required_port<=65535: raise ValueError("port")
        entries.append((original,kind,target,required_port))
    seen,decisions=set(),[]
    for row in records:
        if not isinstance(row,dict) or not isinstance(row.get('id'),str) or not isinstance(row.get('host'),str) or not isinstance(row.get('port'),int) or not 1<=row['port']<=65535:
            raise ValueError("request")
        if row['id'] in seen: raise ValueError("duplicate id")
        seen.add(row['id']); host=row['host'].lower().rstrip('.'); matched=None; reason='no_match'
        for original,kind,target,required_port in entries:
            if kind=='wildcard': ok=True; reason_for_match='wildcard'
            elif kind=='ipv6':
                try: ok=ipaddress.IPv6Address(host.strip('[]'))==target
                except ipaddress.AddressValueError: ok=False
                reason_for_match='entry_match'
            elif kind=='cidr':
                try: value=ipaddress.IPv4Address(host)
                except ipaddress.AddressValueError: ok=False
                else: ok=value in target
                reason_for_match='entry_match'
            else:
                ok=host==target or host.endswith('.'+target); reason_for_match='entry_match'
            if ok and (required_port is None or required_port==row['port']):
                matched=original; reason=reason_for_match; break
        decisions.append({'id':row['id'],'action':'bypass' if matched else 'proxy','matched':matched,'reason':reason})
    decisions.sort(key=lambda x:x['id'])
    return {'decisions':decisions,'source':'explicit_empty' if policy['no_proxy']=='' else 'unset' if policy['no_proxy'] is None else 'configured'}
