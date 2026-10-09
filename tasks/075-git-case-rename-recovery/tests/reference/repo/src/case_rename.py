import re

OID = re.compile(r"[0-9a-f]{40}")

def _safe(path): return isinstance(path,str) and path and not path.startswith("/") and "\\" not in path and all(part not in ("",".","..") for part in path.split("/"))

def _key(value, ignore_case): return value.casefold() if ignore_case else value

def plan_case_renames(entries, requests, ignore_case):
    if type(ignore_case) is not bool or not isinstance(entries,list) or not entries or not isinstance(requests,list) or not requests: raise ValueError("batch")
    current={}; occupied=set()
    for entry in entries:
        if not isinstance(entry,dict) or set(entry)!={"path","oid","stage"} or not _safe(entry.get("path")) or not isinstance(entry.get("oid"),str) or not OID.fullmatch(entry["oid"]) or type(entry.get("stage")) is not int or entry["stage"] != 0: raise ValueError("entry")
        if entry["path"] in current or _key(entry["path"],ignore_case) in occupied: raise ValueError("duplicate")
        current[entry["path"]]=dict(entry); occupied.add(_key(entry["path"],ignore_case))
    pending={}; sources=set(); destinations=set()
    for request in requests:
        if not isinstance(request,dict) or set(request)!={"from","to"} or not _safe(request.get("from")) or not _safe(request.get("to")) or request["from"] == request["to"] or request["from"] not in current: raise ValueError("request")
        if _key(request["from"],ignore_case) in sources or _key(request["to"],ignore_case) in destinations: raise ValueError("duplicate request")
        sources.add(_key(request["from"],ignore_case)); destinations.add(_key(request["to"],ignore_case)); pending[request["from"]]=request["to"]
    if any(value in occupied and value not in sources for value in destinations): raise ValueError("occupied")
    operations=[]
    while pending:
        occupied_now={_key(path,ignore_case) for path in current}; movable=[source for source,destination in pending.items() if _key(destination,ignore_case) not in occupied_now]
        if movable: source=sorted(movable)[0]; destination=pending.pop(source)
        else:
            source=sorted(pending)[0]; destination=pending.pop(source); parent,basename=source.rsplit("/",1) if "/" in source else ("",source); counter=1
            while True:
                leaf=f".{basename}.hb-rename-tmp-{counter}"; temporary=f"{parent}/{leaf}" if parent else leaf; reserved={_key(path,ignore_case) for path in current}|{_key(value,ignore_case) for value in pending.values()}|{_key(destination,ignore_case)}
                if _key(temporary,ignore_case) not in reserved: break
                counter += 1
            pending[temporary]=destination; destination=temporary
        entry=current.pop(source); operations.append({"op":"git_mv","from":source,"to":destination}); entry["path"]=destination; current[destination]=entry
    return {"operations":operations,"final_entries":sorted(current.values(),key=lambda entry:entry["path"])}
