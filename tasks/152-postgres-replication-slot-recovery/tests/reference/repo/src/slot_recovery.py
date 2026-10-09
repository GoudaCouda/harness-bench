def _exact(value, keys):return isinstance(value,dict) and set(value)==set(keys)
def _token(value):return isinstance(value,str) and bool(value) and value==value.lower() and value.isascii() and all(char.isalnum() or char in "-_" for char in value)
def _lsn(value):return isinstance(value,int) and not isinstance(value,bool) and value>=0

def plan_slot_recovery(slots,consumers,observations,policy):
    slot_keys=("slot_name","database","plugin","active","restart_lsn","confirmed_flush_lsn","wal_status","invalidation_reason","failover","synced")
    consumer_keys=("consumer_id","slot_name","database","plugin","last_applied_lsn","can_resnapshot","state")
    if not isinstance(slots,list) or not isinstance(consumers,list):raise ValueError("lists required")
    if not _exact(observations,("primary_wal_lsn","oldest_available_lsn","standby_synced_slots","maintenance_window")):raise ValueError("invalid observations")
    if not _exact(policy,("max_retained_bytes","require_synced_failover")):raise ValueError("invalid policy")
    primary=observations["primary_wal_lsn"]; oldest=observations["oldest_available_lsn"]; standby=observations["standby_synced_slots"]
    if not _lsn(primary) or not _lsn(oldest) or oldest>primary or not isinstance(standby,list) or standby!=sorted(standby) or len(set(standby))!=len(standby) or not all(_token(x) for x in standby) or not isinstance(observations["maintenance_window"],bool):raise ValueError("invalid observations")
    cap=policy["max_retained_bytes"]
    if not isinstance(cap,int) or isinstance(cap,bool) or cap<=0 or not isinstance(policy["require_synced_failover"],bool):raise ValueError("invalid policy")
    slot_map={}; slot_order=[]
    for slot in slots:
        if not _exact(slot,slot_keys) or not all(_token(slot[k]) for k in ("slot_name","database","plugin")):raise ValueError("invalid slot")
        if not isinstance(slot["active"],bool) or not isinstance(slot["failover"],bool) or not isinstance(slot["synced"],bool) or slot["synced"] and not slot["failover"]:raise ValueError("invalid slot flags")
        if not _lsn(slot["restart_lsn"]) or not _lsn(slot["confirmed_flush_lsn"]) or slot["confirmed_flush_lsn"]<slot["restart_lsn"] or slot["confirmed_flush_lsn"]>primary:raise ValueError("invalid slot lsn")
        if slot["wal_status"] not in ("reserved","extended","unreserved","lost") or slot["invalidation_reason"] not in (None,"wal_removed","rows_removed","wal_level","idle_timeout"):raise ValueError("invalid slot status")
        if (slot["wal_status"]=="lost") != (slot["invalidation_reason"] is not None):raise ValueError("inconsistent invalidation")
        name=slot["slot_name"]
        if name in slot_map:raise ValueError("duplicate slot")
        slot_map[name]=slot; slot_order.append(name)
    if slot_order!=sorted(slot_order) or any(name not in slot_map or not slot_map[name]["failover"] for name in standby):raise ValueError("invalid slot order or standby")
    consumer_map={}; consumer_order=[]
    for consumer in consumers:
        if not _exact(consumer,consumer_keys) or not all(_token(consumer[k]) for k in ("consumer_id","slot_name","database","plugin")) or not _lsn(consumer["last_applied_lsn"]):raise ValueError("invalid consumer")
        if not isinstance(consumer["can_resnapshot"],bool) or consumer["state"] not in ("running","stopped"):raise ValueError("invalid consumer state")
        if consumer["consumer_id"] in consumer_map or consumer["slot_name"] not in slot_map:raise ValueError("duplicate or orphan consumer")
        slot=slot_map[consumer["slot_name"]]
        if consumer["database"]!=slot["database"] or consumer["plugin"]!=slot["plugin"] or consumer["last_applied_lsn"]>slot["confirmed_flush_lsn"]:raise ValueError("consumer mismatch")
        if slot["active"] != (consumer["state"]=="running"):raise ValueError("activity mismatch")
        consumer_map[consumer["slot_name"]]=consumer; consumer_order.append(consumer["consumer_id"])
    if consumer_order!=sorted(consumer_order) or set(consumer_map)!=set(slot_map):raise ValueError("consumer topology incomplete")
    plans=[]; counts={"keep":0,"resume":0,"rebuild":0,"blocked":0}; total=0
    for name in sorted(slot_map):
        slot=slot_map[name]; consumer=consumer_map[name]; retained=primary-slot["restart_lsn"]
        if retained<0:raise ValueError("slot ahead of primary")
        total+=retained
        unavailable=slot["wal_status"]=="lost" or slot["restart_lsn"]<oldest
        needs=unavailable or retained>cap
        if not needs:
            action="keep" if consumer["state"]=="running" else "resume"; reason="healthy"; resume=consumer["last_applied_lsn"]; steps=[] if action=="keep" else ["start_consumer"]
        else:
            recovery_reason="wal_unavailable" if unavailable else "retention_exceeded"
            blocked=None
            if policy["require_synced_failover"] and not (slot["failover"] and slot["synced"] and name in standby):blocked="failover_not_ready"
            elif slot["active"]:blocked="slot_active"
            elif not observations["maintenance_window"]:blocked="maintenance_required"
            elif not consumer["can_resnapshot"]:blocked="resnapshot_unavailable"
            if blocked:
                action="blocked"; reason=blocked; resume=None; steps=[]
            else:
                action="rebuild"; reason=recovery_reason; resume=primary; steps=["stop_consumer","drop_slot","create_slot","resnapshot_consumer","start_consumer"]
        counts[action]+=1; plans.append({"slot_name":name,"action":action,"reason":reason,"retained_bytes":retained,"resume_lsn":resume,"steps":steps})
    return {"plans":plans,"summary":{"slot_count":len(slots),"retained_bytes_total":total,"keep":counts["keep"],"resume":counts["resume"],"rebuild":counts["rebuild"],"blocked":counts["blocked"]}}
