import calendar
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo


def _local(value):
    if not isinstance(value,str) or len(value)!=16: raise ValueError()
    result=datetime.fromisoformat(value)
    if result.isoformat(timespec="minutes")!=value: raise ValueError()
    return result


def _day(value):
    if not isinstance(value,str) or len(value)!=10: raise ValueError()
    result=datetime.fromisoformat(value).date()
    if result.isoformat()!=value: raise ValueError()
    return result


def _utc(value):
    if not isinstance(value,str) or len(value)!=20: raise ValueError()
    result=datetime.fromisoformat(value[:-1]+"+00:00")
    if result.isoformat(timespec="seconds").replace("+00:00","Z")!=value: raise ValueError()
    return result


def _validate(schedules,window,overrides):
    keys={"schedule_id","start_local","frequency","interval","count","duration_minutes","timezone_history","gap_policy","fold_policy"}
    if not isinstance(schedules,list) or not isinstance(window,dict) or set(window)!={"start","end"}: raise ValueError()
    left,right=_utc(window["start"]),_utc(window["end"])
    if left>=right: raise ValueError()
    ids=[]; valid_ids=set(); prepared=[]
    for schedule in schedules:
        if not isinstance(schedule,dict) or set(schedule)!=keys or not isinstance(schedule["schedule_id"],str) or not schedule["schedule_id"]: raise ValueError()
        start=_local(schedule["start_local"])
        if schedule["frequency"] not in ("daily","weekly","monthly") or schedule["gap_policy"] not in ("shift_forward","skip") or schedule["fold_policy"] not in ("earlier","later"): raise ValueError()
        for name in ("interval","count","duration_minutes"):
            if not isinstance(schedule[name],int) or isinstance(schedule[name],bool) or schedule[name]<=0: raise ValueError()
        if schedule["count"]>1000 or not isinstance(schedule["timezone_history"],list) or not schedule["timezone_history"]: raise ValueError()
        history=[]; prior=None
        for row in schedule["timezone_history"]:
            if not isinstance(row,dict) or set(row)!={"effective_date","timezone"} or not isinstance(row["timezone"],str) or not row["timezone"]: raise ValueError()
            day=_day(row["effective_date"])
            if prior is not None and day<=prior: raise ValueError()
            try: ZoneInfo(row["timezone"])
            except Exception as exc: raise ValueError() from exc
            history.append((day,row["timezone"])); prior=day
        if history[0][0]>start.date(): raise ValueError()
        ids.append(schedule["schedule_id"]); prepared.append((schedule,start,history))
        for index in range(schedule["count"]): valid_ids.add(f'{schedule["schedule_id"]}#{index+1:04d}')
    if len(ids)!=len(set(ids)) or not isinstance(overrides,list): raise ValueError()
    override_map={}
    for row in overrides:
        if not isinstance(row,dict) or set(row)!={"occurrence_id","action","rescheduled_local"} or not isinstance(row["occurrence_id"],str) or not row["occurrence_id"] or row["occurrence_id"] in override_map: raise ValueError()
        if row["action"]=="skip":
            if row["rescheduled_local"] is not None: raise ValueError()
        elif row["action"]=="reschedule": _local(row["rescheduled_local"])
        else: raise ValueError()
        if row["occurrence_id"] not in valid_ids: raise ValueError()
        override_map[row["occurrence_id"]]=row
    return left,right,prepared,override_map


def _nominal(start,frequency,interval,index):
    if frequency=="daily": return start+timedelta(days=index*interval)
    if frequency=="weekly": return start+timedelta(days=index*interval*7)
    value=start.month-1+index*interval; year=start.year+value//12; month=value%12+1
    return start.replace(year=year,month=month,day=min(start.day,calendar.monthrange(year,month)[1]))


def _zone(local,history):
    result=None
    for day,name in history:
        if day<=local.date(): result=name
        else: break
    if result is None: raise ValueError()
    return result


def _candidates(local,name):
    result=[]; zone=ZoneInfo(name)
    for fold in (0,1):
        instant=local.replace(tzinfo=zone,fold=fold).astimezone(timezone.utc)
        if instant.astimezone(zone).replace(tzinfo=None)==local and instant not in result: result.append(instant)
    return sorted(result)


def _resolve(local,name,gap,fold):
    values=_candidates(local,name)
    if len(values)==1: return local,values[0],"normal"
    if len(values)==2: return local,(values[0] if fold=="earlier" else values[1]),"fold_"+fold
    if gap=="skip": return None,None,"dst_gap"
    for minute in range(1,181):
        shifted=local+timedelta(minutes=minute); values=_candidates(shifted,name)
        if values: return shifted,values[0],"gap_shift_forward"
    raise ValueError()


def expand_schedules(schedules,window,overrides):
    left,right,prepared,override_map=_validate(schedules,window,overrides); rows=[]; skipped=[]
    for schedule,start,history in prepared:
        for index in range(schedule["count"]):
            nominal=_nominal(start,schedule["frequency"],schedule["interval"],index); oid=f'{schedule["schedule_id"]}#{index+1:04d}'; override=override_map.get(oid)
            if override and override["action"]=="skip": skipped.append({"occurrence_id":oid,"nominal_local":nominal.isoformat(timespec="minutes"),"reason":"override_skip"}); continue
            scheduled=_local(override["rescheduled_local"]) if override else nominal; zone=_zone(scheduled,history)
            resolved,instant,resolution=_resolve(scheduled,zone,schedule["gap_policy"],schedule["fold_policy"])
            if instant is None: skipped.append({"occurrence_id":oid,"nominal_local":nominal.isoformat(timespec="minutes"),"reason":"dst_gap"}); continue
            if override and resolution=="normal": resolution="override"
            if left<=instant<right:
                rows.append({"occurrence_id":oid,"nominal_local":nominal.isoformat(timespec="minutes"),"scheduled_local":resolved.isoformat(timespec="minutes"),"timezone":zone,"utc_start":instant.isoformat(timespec="seconds").replace("+00:00","Z"),"utc_end":(instant+timedelta(minutes=schedule["duration_minutes"])).isoformat(timespec="seconds").replace("+00:00","Z"),"resolution":resolution,"override_applied":override is not None})
    rows.sort(key=lambda row:(row["utc_start"],row["occurrence_id"])); skipped.sort(key=lambda row:row["occurrence_id"])
    return {"occurrences":rows,"skipped":skipped}
