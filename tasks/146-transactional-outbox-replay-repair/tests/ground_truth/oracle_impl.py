TOKEN_CHARS="abcdefghijklmnopqrstuvwxyz0123456789-_."


def _fail():
    raise ValueError()


def _token(value):
    return isinstance(value,str) and bool(value) and value==value.lower() and value.isascii() and all(char in TOKEN_CHARS for char in value)


def _integer(value,minimum=0,maximum=None):
    return isinstance(value,int) and not isinstance(value,bool) and value>=minimum and (maximum is None or value<=maximum)


def _hash(value):
    return isinstance(value,str) and len(value)==64 and all(char in "0123456789abcdef" for char in value)


def _validate(events,receipts,policy):
    if not isinstance(policy,dict) or set(policy)!={"now","worker","lease_seconds","max_attempts"}:
        _fail()
    if not _integer(policy["now"]) or not _token(policy["worker"]) or not _integer(policy["lease_seconds"],1,86400) or not _integer(policy["max_attempts"],1,20):
        _fail()
    if not isinstance(events,list) or not isinstance(receipts,list):
        _fail()
    event_keys={"event_id","aggregate_id","sequence","payload_hash","status","attempts","lease_owner","lease_until","last_error"}
    ids=set(); positions=set(); by_id={}
    for row in events:
        if not isinstance(row,dict) or set(row)!=event_keys or not _token(row["event_id"]) or row["event_id"] in ids or not _token(row["aggregate_id"]) or not _integer(row["sequence"],1) or (row["aggregate_id"],row["sequence"]) in positions or not _hash(row["payload_hash"]):
            _fail()
        ids.add(row["event_id"]); positions.add((row["aggregate_id"],row["sequence"])); by_id[row["event_id"]]=row
        if row["status"] not in ("pending","leased","sent","dead") or not _integer(row["attempts"],0,policy["max_attempts"]):
            _fail()
        if row["last_error"] is not None and (not isinstance(row["last_error"],str) or not row["last_error"] or len(row["last_error"])>200):
            _fail()
        if row["status"]=="pending":
            valid=row["attempts"]<policy["max_attempts"] and row["lease_owner"] is None and row["lease_until"] is None
        elif row["status"]=="leased":
            valid=_integer(row["attempts"],1,policy["max_attempts"]) and _token(row["lease_owner"]) and _integer(row["lease_until"])
        elif row["status"]=="sent":
            valid=_integer(row["attempts"],1,policy["max_attempts"]) and row["lease_owner"] is None and row["lease_until"] is None
        else:
            valid=row["attempts"]==policy["max_attempts"] and row["lease_owner"] is None and row["lease_until"] is None
        if not valid:
            _fail()
    receipt_keys={"event_id","attempt","outcome","payload_hash","observed_at"}
    seen={}
    for row in receipts:
        if not isinstance(row,dict) or set(row)!=receipt_keys or row["event_id"] not in by_id or not _integer(row["attempt"],1) or row["attempt"]>by_id[row["event_id"]]["attempts"] or row["outcome"] not in ("acked","rejected","unknown") or row["payload_hash"]!=by_id[row["event_id"]]["payload_hash"] or not _integer(row["observed_at"],0,policy["now"]):
            _fail()
        key=(row["event_id"],row["attempt"])
        frozen=(row["event_id"],row["attempt"],row["outcome"],row["payload_hash"],row["observed_at"])
        if key in seen and seen[key]!=frozen:
            _fail()
        seen[key]=frozen
    return seen


def recover_outbox(events,receipts,policy):
    receipt_rows=_validate(events,receipts,policy)
    state=[dict(row) for row in events]
    by_id={row["event_id"]:row for row in state}
    acknowledged={event_id for (event_id,_),row in receipt_rows.items() if row[2]=="acked"}
    reserved={}
    for row in state:
        event_id=row["event_id"]
        if row["status"] in ("sent","dead"):
            continue
        if event_id in acknowledged:
            row["status"]="sent"; row["lease_owner"]=None; row["lease_until"]=None; row["last_error"]=None
            continue
        current=receipt_rows.get((event_id,row["attempts"]))
        outcome=current[2] if current else None
        if outcome=="unknown":
            continue
        active=row["status"]=="leased" and row["lease_until"]>policy["now"]
        if active and outcome!="rejected":
            continue
        if row["status"]=="leased" or outcome=="rejected":
            row["lease_owner"]=None; row["lease_until"]=None
            if outcome=="rejected":
                row["last_error"]="rejected"
            if row["attempts"]>=policy["max_attempts"]:
                row["status"]="dead"
                reserved[row["aggregate_id"]]={"type":"dead_letter","event_id":event_id,"attempt":row["attempts"],"idempotency_key":event_id,"payload_hash":row["payload_hash"]}
            else:
                row["status"]="pending"
    aggregates={}
    for row in state:
        aggregates.setdefault(row["aggregate_id"],[]).append(row)
    actions=list(reserved.values())
    for aggregate_id in sorted(aggregates):
        if aggregate_id in reserved:
            continue
        rows=sorted(aggregates[aggregate_id],key=lambda item:item["sequence"])
        head=next((row for row in rows if row["status"] not in ("sent","dead")),None)
        if head is None:
            continue
        current=receipt_rows.get((head["event_id"],head["attempts"]))
        if current and current[2]=="unknown":
            actions.append({"type":"probe","event_id":head["event_id"],"attempt":head["attempts"],"idempotency_key":head["event_id"],"payload_hash":head["payload_hash"]})
        elif head["status"]=="pending":
            head["attempts"]+=1; head["status"]="leased"; head["lease_owner"]=policy["worker"]; head["lease_until"]=policy["now"]+policy["lease_seconds"]; head["last_error"]=None
            actions.append({"type":"publish","event_id":head["event_id"],"attempt":head["attempts"],"idempotency_key":head["event_id"],"payload_hash":head["payload_hash"]})
    position={row["event_id"]:(row["aggregate_id"],row["sequence"]) for row in state}
    actions.sort(key=lambda action:(position[action["event_id"]][0],position[action["event_id"]][1],action["type"]))
    return {"state":state,"actions":actions}
