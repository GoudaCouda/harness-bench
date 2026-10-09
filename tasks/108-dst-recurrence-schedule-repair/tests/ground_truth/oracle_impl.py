import calendar
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo


SCHEDULE_KEYS={"schedule_id","start_local","frequency","interval","count","duration_minutes","timezone_history","gap_policy","fold_policy"}


def _integer(value): return isinstance(value,int) and not isinstance(value,bool)


def _local(value):
    if not isinstance(value,str) or len(value)!=16: raise ValueError("local")
    parsed=datetime.strptime(value,"%Y-%m-%dT%H:%M")
    if parsed.strftime("%Y-%m-%dT%H:%M")!=value: raise ValueError("local")
    return parsed


def _day(value):
    if not isinstance(value,str) or len(value)!=10: raise ValueError("date")
    parsed=datetime.strptime(value,"%Y-%m-%d").date()
    if parsed.isoformat()!=value: raise ValueError("date")
    return parsed


def _utc(value):
    if not isinstance(value,str) or len(value)!=20: raise ValueError("utc")
    parsed=datetime.strptime(value,"%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    if parsed.strftime("%Y-%m-%dT%H:%M:%SZ")!=value: raise ValueError("utc")
    return parsed


def _preflight(schedules,window,overrides):
    if not isinstance(schedules,list) or not isinstance(window,dict) or set(window)!={"start","end"}: raise ValueError("batch")
    start_utc,end_utc=_utc(window["start"]),_utc(window["end"])
    if start_utc>=end_utc: raise ValueError("window")
    ids=[]; generated=set(); prepared=[]
    for schedule in schedules:
        if not isinstance(schedule,dict) or set(schedule)!=SCHEDULE_KEYS or not isinstance(schedule["schedule_id"],str) or not schedule["schedule_id"]: raise ValueError("schedule")
        start=_local(schedule["start_local"])
        if schedule["frequency"] not in ("daily","weekly","monthly") or schedule["gap_policy"] not in ("shift_forward","skip") or schedule["fold_policy"] not in ("earlier","later"): raise ValueError("policy")
        if any(not _integer(schedule[name]) or schedule[name]<=0 for name in ("interval","count","duration_minutes")) or schedule["count"]>1000: raise ValueError("number")
        history=schedule["timezone_history"]
        if not isinstance(history,list) or not history: raise ValueError("history")
        prior=None; parsed_history=[]
        for row in history:
            if not isinstance(row,dict) or set(row)!={"effective_date","timezone"} or not isinstance(row["timezone"],str) or not row["timezone"]: raise ValueError("history row")
            day=_day(row["effective_date"])
            if prior is not None and day<=prior: raise ValueError("history order")
            try: ZoneInfo(row["timezone"])
            except Exception as exc: raise ValueError("zone") from exc
            parsed_history.append((day,row["timezone"])); prior=day
        if parsed_history[0][0]>start.date(): raise ValueError("history start")
        ids.append(schedule["schedule_id"])
        for index in range(schedule["count"]): generated.add(f'{schedule["schedule_id"]}#{index+1:04d}')
        prepared.append((schedule,start,parsed_history))
    if len(ids)!=len(set(ids)) or not isinstance(overrides,list): raise ValueError("ids")
    override_ids=[]; override_map={}
    for row in overrides:
        if not isinstance(row,dict) or set(row)!={"occurrence_id","action","rescheduled_local"} or not isinstance(row["occurrence_id"],str) or not row["occurrence_id"]: raise ValueError("override")
        if row["action"]=="skip":
            if row["rescheduled_local"] is not None: raise ValueError("skip")
        elif row["action"]=="reschedule": _local(row["rescheduled_local"])
        else: raise ValueError("action")
        override_ids.append(row["occurrence_id"]); override_map[row["occurrence_id"]]=row
    if len(override_ids)!=len(set(override_ids)) or any(item not in generated for item in override_ids): raise ValueError("override id")
    return start_utc,end_utc,prepared,override_map


def _nominal(start,frequency,interval,index):
    if frequency=="daily": return start+timedelta(days=index*interval)
    if frequency=="weekly": return start+timedelta(days=index*interval*7)
    months=(start.month-1)+index*interval
    year=start.year+months//12; month=months%12+1
    day=min(start.day,calendar.monthrange(year,month)[1])
    return start.replace(year=year,month=month,day=day)


def _zone_for(local,history):
    selected=None
    for effective,zone in history:
        if effective<=local.date(): selected=zone
        else: break
    if selected is None: raise ValueError("zone history")
    return selected


def _candidates(local,zone):
    result=[]; tz=ZoneInfo(zone)
    for fold in (0,1):
        aware=local.replace(tzinfo=tz,fold=fold)
        instant=aware.astimezone(timezone.utc)
        if instant.astimezone(tz).replace(tzinfo=None)==local and instant not in result: result.append(instant)
    return sorted(result)


def _resolve(local,zone,gap_policy,fold_policy):
    candidates=_candidates(local,zone)
    if len(candidates)==1: return local,candidates[0],"normal"
    if len(candidates)==2:
        return local,(candidates[0] if fold_policy=="earlier" else candidates[1]),f"fold_{fold_policy}"
    if gap_policy=="skip": return None,None,"dst_gap"
    for minute in range(1,181):
        shifted=local+timedelta(minutes=minute); candidates=_candidates(shifted,zone)
        if candidates: return shifted,candidates[0],"gap_shift_forward"
    raise ValueError("gap")


def expand_schedules(schedules,window,overrides):
    start_utc,end_utc,prepared,override_map=_preflight(schedules,window,overrides)
    occurrences=[]; skipped=[]
    for schedule,start,history in prepared:
        for index in range(schedule["count"]):
            nominal=_nominal(start,schedule["frequency"],schedule["interval"],index)
            occurrence_id=f'{schedule["schedule_id"]}#{index+1:04d}'
            override=override_map.get(occurrence_id)
            if override and override["action"]=="skip":
                skipped.append({"occurrence_id":occurrence_id,"nominal_local":nominal.strftime("%Y-%m-%dT%H:%M"),"reason":"override_skip"}); continue
            scheduled=_local(override["rescheduled_local"]) if override else nominal
            zone=_zone_for(scheduled,history)
            resolved,instant,resolution=_resolve(scheduled,zone,schedule["gap_policy"],schedule["fold_policy"])
            if instant is None:
                skipped.append({"occurrence_id":occurrence_id,"nominal_local":nominal.strftime("%Y-%m-%dT%H:%M"),"reason":"dst_gap"}); continue
            if override and resolution=="normal": resolution="override"
            if start_utc<=instant<end_utc:
                occurrences.append({"occurrence_id":occurrence_id,"nominal_local":nominal.strftime("%Y-%m-%dT%H:%M"),"scheduled_local":resolved.strftime("%Y-%m-%dT%H:%M"),"timezone":zone,"utc_start":instant.strftime("%Y-%m-%dT%H:%M:%SZ"),"utc_end":(instant+timedelta(minutes=schedule["duration_minutes"])).strftime("%Y-%m-%dT%H:%M:%SZ"),"resolution":resolution,"override_applied":override is not None})
    occurrences.sort(key=lambda row:(row["utc_start"],row["occurrence_id"])); skipped.sort(key=lambda row:row["occurrence_id"])
    return {"occurrences":occurrences,"skipped":skipped}
