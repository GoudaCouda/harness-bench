HEX=set("0123456789abcdef")
def _int(v):return isinstance(v,int) and not isinstance(v,bool)
def _path(v):return isinstance(v,str) and v.startswith("/") and v!="/" and not v.endswith("/") and "\\" not in v and all(x not in ("",".","..") for x in v.split("/")[1:])
def _sum(v):return isinstance(v,str) and len(v)==64 and all(x in HEX for x in v)
def _prefix(path,prefix):return path==prefix or path.startswith(prefix+"/")
def _validate(snapshots,destination,request):
 if not isinstance(snapshots,list) or not isinstance(destination,list):raise ValueError()
 by_id={}
 for snap in snapshots:
  if not isinstance(snap,dict) or set(snap)!={"snapshot_id","parent_id","complete","entries"} or not isinstance(snap["snapshot_id"],str) or not snap["snapshot_id"] or snap["snapshot_id"] in by_id or not (snap["parent_id"] is None or isinstance(snap["parent_id"],str) and snap["parent_id"]) or not isinstance(snap["complete"],bool) or not isinstance(snap["entries"],list):raise ValueError()
  paths=[]
  for row in snap["entries"]:
   if not isinstance(row,dict) or set(row)!={"path","operation","kind","checksum","size"} or not _path(row["path"]):raise ValueError()
   if row["operation"]=="delete":
    if row["kind"] is not None or row["checksum"] is not None or row["size"] is not None:raise ValueError()
   elif row["operation"]=="upsert":
    if row["kind"]=="directory":
     if row["checksum"] is not None or row["size"]!=0:raise ValueError()
    elif row["kind"] in ("file","symlink"):
     if not _sum(row["checksum"]) or not _int(row["size"]) or row["size"]<0:raise ValueError()
    else:raise ValueError()
   else:raise ValueError()
   paths.append(row["path"])
  if len(paths)!=len(set(paths)):raise ValueError()
  by_id[snap["snapshot_id"]]=snap
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
  if not isinstance(row,dict) or set(row)!={"path","kind","checksum"} or not _path(row["path"]) or row["path"] in target or row["kind"] not in ("file","directory") or row["kind"]=="file" and not _sum(row["checksum"]) or row["kind"]=="directory" and row["checksum"] is not None:raise ValueError()
  target[row["path"]]=row
 if not isinstance(request,dict) or set(request)!={"snapshot_id","target_root","include","exclude","overwrite","dry_run","delete_extraneous"} or not isinstance(request["snapshot_id"],str) or not request["snapshot_id"] or not _path(request["target_root"]) or request["overwrite"] not in ("never","if_changed") or request["dry_run"] is not True or request["delete_extraneous"] is not False:raise ValueError()
 for field in ("include","exclude"):
  if not isinstance(request[field],list) or any(not _path(x) for x in request[field]) or len(request[field])!=len(set(request[field])):raise ValueError()
 return by_id,target
def plan_restore(snapshots,destination,request):
 by_id,target=_validate(snapshots,destination,request);sid=request["snapshot_id"]
 def blocked(reason,chain):return {"plan":{"status":"blocked","reason":reason,"snapshot_id":sid,"chain":chain,"actions":[]},"summary":{"restore":0,"unchanged":0,"conflict":0,"selected":0,"dry_run":True}}
 if sid not in by_id:return blocked("unknown_snapshot",[])
 reverse=[];current=sid
 while True:
  snap=by_id[current];reverse.append(current)
  if snap["parent_id"] is None:break
  if snap["parent_id"] not in by_id:return blocked("missing_parent",list(reversed(reverse)))
  current=snap["parent_id"]
 chain=list(reversed(reverse))
 if any(not by_id[x]["complete"] for x in chain):return blocked("incomplete_chain",chain)
 state={}
 for name in chain:
  for row in by_id[name]["entries"]:
   if row["operation"]=="delete":
    for old in list(state):
     if _prefix(old,row["path"]):state.pop(old)
   else:state[row["path"]]={key:row[key] for key in ("path","kind","checksum","size")}
 actions=[]
 for path in sorted(state):
  row=state[path]
  if request["include"] and not any(_prefix(path,x) for x in request["include"]) or any(_prefix(path,x) for x in request["exclude"]):continue
  target_path=request["target_root"]+path;existing=target.get(target_path);action="restore";reason="missing"
  if row["kind"]=="symlink":action,reason="conflict","unsupported_type"
  elif existing is not None:
   if existing["kind"]!=row["kind"]:action,reason="conflict","type_collision"
   elif row["kind"]=="directory" or existing["checksum"]==row["checksum"]:action,reason="unchanged","already_matches"
   elif request["overwrite"]=="never":action,reason="conflict","overwrite_disabled"
   else:reason="content_changed"
  actions.append({"source_path":path,"target_path":target_path,"kind":row["kind"],"checksum":row["checksum"],"action":action,"reason":reason})
 counts={name:sum(1 for row in actions if row["action"]==name) for name in ("restore","unchanged","conflict")}
 return {"plan":{"status":"ready","reason":"ready","snapshot_id":sid,"chain":chain,"actions":actions},"summary":{"restore":counts["restore"],"unchanged":counts["unchanged"],"conflict":counts["conflict"],"selected":len(actions),"dry_run":True}}
