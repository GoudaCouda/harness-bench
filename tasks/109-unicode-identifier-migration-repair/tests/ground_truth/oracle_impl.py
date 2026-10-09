import unicodedata


def _canonical(value): return unicodedata.normalize("NFKC",unicodedata.normalize("NFKC",value).casefold())


def _integer(value): return isinstance(value,int) and not isinstance(value,bool)


def migrate_identifiers(records,reserved,policy):
    if not isinstance(policy,dict) or set(policy)!={"normalization","case_insensitive","max_codepoints"} or policy["normalization"]!="NFKC" or policy["case_insensitive"] is not True or not _integer(policy["max_codepoints"]) or not 0<policy["max_codepoints"]<=128: raise ValueError("policy")
    if not isinstance(reserved,list) or any(not isinstance(item,str) or not item for item in reserved) or len(reserved)!=len(set(reserved)) or not isinstance(records,list): raise ValueError("reserved")
    ids=[]
    for record in records:
        if not isinstance(record,dict) or set(record)!={"record_id","identifier","references"} or not isinstance(record["record_id"],str) or not record["record_id"] or not isinstance(record["identifier"],str) or not isinstance(record["references"],list) or any(not isinstance(item,str) or not item for item in record["references"]) or len(record["references"])!=len(set(record["references"])): raise ValueError("record")
        ids.append(record["record_id"])
    if len(ids)!=len(set(ids)) or any(ref not in set(ids) for record in records for ref in record["references"]): raise ValueError("references")
    limit=policy["max_codepoints"]
    reserved_keys=[]
    for item in reserved:
        value=_canonical(item)
        if not value or len(value)>limit or not value.isidentifier(): raise ValueError("reserved profile")
        reserved_keys.append(value)
    if len(reserved_keys)!=len(set(reserved_keys)): raise ValueError("reserved collision")
    canonical={record["record_id"]:_canonical(record["identifier"]) for record in records}
    groups={}
    for record in records:
        value=canonical[record["record_id"]]
        if value and len(value)<=limit and value.isidentifier(): groups.setdefault(value,[]).append(record["record_id"])
    status={}
    for record in records:
        rid=record["record_id"]; value=canonical[rid]
        if not value or len(value)>limit or not value.isidentifier(): status[rid]="invalid"
        elif value in reserved_keys: status[rid]="reserved"
        elif len(groups[value])>1: status[rid]="collision"
        else: status[rid]="accepted"
    output=[]
    for record in records:
        rid=record["record_id"]
        accepted_refs=sorted({canonical[ref] for ref in record["references"] if status[ref]=="accepted"})
        unresolved=sorted(ref for ref in record["references"] if status[ref]!="accepted")
        output.append({"record_id":rid,"display_identifier":record["identifier"],"canonical_identifier":canonical[rid] if status[rid]=="accepted" else None,"status":status[rid],"canonical_references":accepted_refs,"unresolved_reference_ids":unresolved})
    conflicts=[]
    for value,record_ids in groups.items():
        colliding=[rid for rid in record_ids if status[rid]=="collision"]
        reserved_group=[rid for rid in record_ids if status[rid]=="reserved"]
        if colliding: conflicts.append({"reason":"collision","canonical_identifier":value,"record_ids":sorted(colliding)})
        if reserved_group: conflicts.append({"reason":"reserved","canonical_identifier":value,"record_ids":sorted(reserved_group)})
    for record in records:
        if status[record["record_id"]]=="invalid": conflicts.append({"reason":"invalid","canonical_identifier":None,"record_ids":[record["record_id"]]})
    conflicts.sort(key=lambda row:(row["reason"],row["canonical_identifier"] or "",tuple(row["record_ids"])))
    return {"records":output,"conflicts":conflicts}
