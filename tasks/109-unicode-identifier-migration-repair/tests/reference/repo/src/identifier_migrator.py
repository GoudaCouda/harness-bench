import unicodedata


def _canonical(value):return unicodedata.normalize("NFKC",unicodedata.normalize("NFKC",value).casefold())


def migrate_identifiers(records,reserved,policy):
    if not isinstance(policy,dict) or set(policy)!={"normalization","case_insensitive","max_codepoints"} or policy["normalization"]!="NFKC" or policy["case_insensitive"] is not True or not isinstance(policy["max_codepoints"],int) or isinstance(policy["max_codepoints"],bool) or not 0<policy["max_codepoints"]<=128:raise ValueError()
    if not isinstance(reserved,list) or any(not isinstance(x,str) or not x for x in reserved) or len(reserved)!=len(set(reserved)) or not isinstance(records,list):raise ValueError()
    ids=[]
    for record in records:
        if not isinstance(record,dict) or set(record)!={"record_id","identifier","references"} or not isinstance(record["record_id"],str) or not record["record_id"] or not isinstance(record["identifier"],str) or not isinstance(record["references"],list) or any(not isinstance(x,str) or not x for x in record["references"]) or len(record["references"])!=len(set(record["references"])):raise ValueError()
        ids.append(record["record_id"])
    if len(ids)!=len(set(ids)) or any(ref not in set(ids) for record in records for ref in record["references"]):raise ValueError()
    limit=policy["max_codepoints"]; reserved_keys=[]
    for item in reserved:
        value=_canonical(item)
        if not value or len(value)>limit or not value.isidentifier():raise ValueError()
        reserved_keys.append(value)
    if len(reserved_keys)!=len(set(reserved_keys)):raise ValueError()
    canonical={r["record_id"]:_canonical(r["identifier"]) for r in records}; groups={}
    for record in records:
        value=canonical[record["record_id"]]
        if value and len(value)<=limit and value.isidentifier():groups.setdefault(value,[]).append(record["record_id"])
    status={}
    for record in records:
        rid=record["record_id"]; value=canonical[rid]
        status[rid]="invalid" if not value or len(value)>limit or not value.isidentifier() else "reserved" if value in reserved_keys else "collision" if len(groups[value])>1 else "accepted"
    output=[]
    for record in records:
        rid=record["record_id"]
        output.append({"record_id":rid,"display_identifier":record["identifier"],"canonical_identifier":canonical[rid] if status[rid]=="accepted" else None,"status":status[rid],"canonical_references":sorted({canonical[x] for x in record["references"] if status[x]=="accepted"}),"unresolved_reference_ids":sorted(x for x in record["references"] if status[x]!="accepted")})
    conflicts=[]
    for value,members in groups.items():
        for reason in ("collision","reserved"):
            selected=sorted(rid for rid in members if status[rid]==reason)
            if selected:conflicts.append({"reason":reason,"canonical_identifier":value,"record_ids":selected})
    for record in records:
        if status[record["record_id"]]=="invalid":conflicts.append({"reason":"invalid","canonical_identifier":None,"record_ids":[record["record_id"]]})
    conflicts.sort(key=lambda row:(row["reason"],row["canonical_identifier"] or "",tuple(row["record_ids"])))
    return {"records":output,"conflicts":conflicts}
