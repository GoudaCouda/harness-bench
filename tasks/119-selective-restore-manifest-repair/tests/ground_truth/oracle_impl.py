HEX=set("0123456789abcdef")


def _integer(value):return isinstance(value,int) and not isinstance(value,bool)
def _path(value):
 return isinstance(value,str) and value.startswith("/") and value!="/" and not value.endswith("/") and "\\" not in value and all(part not in ("",".","..") for part in value.split("/")[1:])
def _checksum(value):return isinstance(value,str) and len(value)==64 and all(ch in HEX for ch in value)
def _prefix(path,prefix):return path==prefix or path.startswith(prefix+"/")


def _preflight(snapshots,destination,request):
 if not isinstance(snapshots,list) or not isinstance(destination,list):raise ValueError()
 by_id={}
 for snapshot in snapshots:
  if not isinstance(snapshot,dict) or set(snapshot)!={"snapshot_id","parent_id","complete","entries"} or not isinstance(snapshot["snapshot_id"],str) or not snapshot["snapshot_id"] or snapshot["snapshot_id"] in by_id or not (snapshot["parent_id"] is None or isinstance(snapshot["parent_id"],str) and snapshot["parent_id"]) or not isinstance(snapshot["complete"],bool) or not isinstance(snapshot["entries"],list):raise ValueError()
  paths=[]
  for row in snapshot["entries"]:
   if not isinstance(row,dict) or set(row)!={"path","operation","kind","checksum","size"} or not _path(row["path"]):raise ValueError()
   if row["operation"]=="delete":
    if any(row[name] is not None for name in ("kind","checksum","size")):raise ValueError()
   elif row["operation"]=="upsert":
    if row["kind"]=="directory":
     if row["checksum"] is not None or row["size"]!=0:raise ValueError()
    elif row["kind"] in ("file","symlink"):
     if not _checksum(row["checksum"]) or not _integer(row["size"]) or row["size"]<0:raise ValueError()
    else:raise ValueError()
   else:raise ValueError()
   paths.append(row["path"])
  if len(paths)!=len(set(paths)):raise ValueError()
  by_id[snapshot["snapshot_id"]]=snapshot
 visiting=set();done=set()
 def visit(name):
  if name in visiting:raise ValueError()
  if name in done:return
  visiting.add(name);parent=by_id[name]["parent_id"]
  if parent in by_id:visit(parent)
  visiting.remove(name);done.add(name)
 for name in by_id:visit(name)
 target={}
 for row in destination:
  if not isinstance(row,dict) or set(row)!={"path","kind","checksum"} or not _path(row["path"]) or row["path"] in target or row["kind"] not in ("file","directory") or (row["kind"]=="file" and not _checksum(row["checksum"])) or (row["kind"]=="directory" and row["checksum"] is not None):raise ValueError()
  target[row["path"]]=row
 if not isinstance(request,dict) or set(request)!={"snapshot_id","target_root","include","exclude","overwrite","dry_run","delete_extraneous"} or not isinstance(request["snapshot_id"],str) or not request["snapshot_id"] or not _path(request["target_root"]) or request["overwrite"] not in ("never","if_changed") or request["dry_run"] is not True or request["delete_extraneous"] is not False:raise ValueError()
 for name in ("include","exclude"):
  if not isinstance(request[name],list) or any(not _path(item) for item in request[name]) or len(request[name])!=len(set(request[name])):raise ValueError()
 return by_id,target


def plan_restore(snapshots,destination,request):
 by_id,target=_preflight(snapshots,destination,request);sid=request["snapshot_id"]
 def blocked(reason,chain):return {"plan":{"status":"blocked","reason":reason,"snapshot_id":sid,"chain":chain,"actions":[]},"summary":{"restore":0,"unchanged":0,"conflict":0,"selected":0,"dry_run":True}}
 if sid not in by_id:return blocked("unknown_snapshot",[])
 reverse=[];current=sid
 while True:
  snap=by_id[current];reverse.append(current)
  if snap["parent_id"] is None:break
  if snap["parent_id"] not in by_id:return blocked("missing_parent",list(reversed(reverse)))
  current=snap["parent_id"]
 chain=list(reversed(reverse))
 if any(not by_id[name]["complete"] for name in chain):return blocked("incomplete_chain",chain)
 state={}
 for name in chain:
  for row in by_id[name]["entries"]:
   path=row["path"]
   if row["operation"]=="delete":
    for old in list(state):
     if _prefix(old,path):state.pop(old)
   else:state[path]={key:row[key] for key in ("path","kind","checksum","size")}
 actions=[]
 for path in sorted(state):
  row=state[path]
  included=not request["include"] or any(_prefix(path,prefix) for prefix in request["include"])
  excluded=any(_prefix(path,prefix) for prefix in request["exclude"])
  if not included or excluded:continue
  target_path=request["target_root"]+path;existing=target.get(target_path);action="restore";reason="missing"
  if row["kind"]=="symlink":action,reason="conflict","unsupported_type"
  elif existing is not None:
   if existing["kind"]!=row["kind"]:action,reason="conflict","type_collision"
   elif row["kind"]=="directory" or existing["checksum"]==row["checksum"]:action,reason="unchanged","already_matches"
   elif request["overwrite"]=="never":action,reason="conflict","overwrite_disabled"
   else:action,reason="restore","content_changed"
  actions.append({"source_path":path,"target_path":target_path,"kind":row["kind"],"checksum":row["checksum"],"action":action,"reason":reason})
 counts={name:sum(1 for row in actions if row["action"]==name) for name in ("restore","unchanged","conflict")}
 return {"plan":{"status":"ready","reason":"ready","snapshot_id":sid,"chain":chain,"actions":actions},"summary":{"restore":counts["restore"],"unchanged":counts["unchanged"],"conflict":counts["conflict"],"selected":len(actions),"dry_run":True}}
