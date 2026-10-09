import copy


def _strings(value):
    return isinstance(value,list) and all(isinstance(x,str) and x for x in value) and len(value)==len(set(value))


def _preflight(state,catalog,request,faults):
    if not isinstance(catalog,list): raise ValueError()
    plugins={}; hooks=set()
    for item in catalog:
        if not isinstance(item,dict) or set(item)!={"name","depends","hooks"} or not isinstance(item["name"],str) or not item["name"] or not _strings(item["depends"]) or not _strings(item["hooks"]): raise ValueError()
        if item["name"] in plugins or item["name"] in item["depends"] or hooks.intersection(item["hooks"]): raise ValueError()
        plugins[item["name"]]=item; hooks.update(item["hooks"])
    if any(dep not in plugins for item in catalog for dep in item["depends"]): raise ValueError()
    visiting=set(); done=set()
    def visit(name):
        if name in visiting: raise ValueError()
        if name in done: return
        visiting.add(name)
        for dep in plugins[name]["depends"]: visit(dep)
        visiting.remove(name); done.add(name)
    for name in plugins: visit(name)
    if not isinstance(state,dict) or set(state)!={"generation","active","registrations"} or not isinstance(state["generation"],int) or isinstance(state["generation"],bool) or state["generation"]<0 or not _strings(state["active"]) or not isinstance(state["registrations"],list): raise ValueError()
    active=set(state["active"])
    if any(name not in plugins for name in active) or any(dep not in active for name in active for dep in plugins[name]["depends"]): raise ValueError()
    if any(not isinstance(row,dict) or set(row)!={"plugin","hook"} or not isinstance(row["plugin"],str) or not row["plugin"] or not isinstance(row["hook"],str) or not row["hook"] for row in state["registrations"]): raise ValueError()
    if not isinstance(request,dict) or set(request)!={"enable","disable"} or not _strings(request["enable"]) or not _strings(request["disable"]): raise ValueError()
    if not isinstance(faults,dict) or set(faults)!={"activate","deactivate"} or not _strings(faults["activate"]) or not _strings(faults["deactivate"]): raise ValueError()
    return plugins


def _topo(names,plugins):
    names=set(names); result=[]
    while names:
        ready=sorted(name for name in names if not (set(plugins[name]["depends"]) & names))
        if not ready: raise ValueError()
        for name in ready: result.append(name); names.remove(name)
    return result


def reconcile_plugins(state,catalog,request,faults):
    plugins=_preflight(state,catalog,request,faults); initial=copy.deepcopy(state); known=set(plugins)
    def reject(reason):
        return {"state":copy.deepcopy(initial),"journal":{"status":"rejected","reason":reason,"activation_order":[],"deactivation_order":[],"failed_plugin":None,"rollback_order":[]}}
    if any(name not in known for name in request["enable"]+request["disable"]): return reject("unknown_plugin")
    if set(request["enable"]) & set(request["disable"]): return reject("request_conflict")
    enable=set()
    def add(name):
        if name in enable: return
        for dep in plugins[name]["depends"]: add(dep)
        enable.add(name)
    for name in request["enable"]: add(name)
    active=set(state["active"]); disable={name for name in request["disable"] if name in active}
    changed=True
    while changed:
        changed=False
        for name in active-disable:
            if set(plugins[name]["depends"]) & disable: disable.add(name); changed=True
    if enable & disable: return reject("request_conflict")
    target=(active-disable)|enable; activation=_topo(target-active,plugins); deactivation=list(reversed(_topo(disable,plugins))); successful=[]
    for name in deactivation:
        if name in faults["deactivate"]:
            return {"state":copy.deepcopy(initial),"journal":{"status":"rolled_back","reason":"deactivate_failed","activation_order":activation,"deactivation_order":deactivation,"failed_plugin":name,"rollback_order":list(reversed(successful))}}
        successful.append(name)
    for name in activation:
        if name in faults["activate"]:
            return {"state":copy.deepcopy(initial),"journal":{"status":"rolled_back","reason":"activate_failed","activation_order":activation,"deactivation_order":deactivation,"failed_plugin":name,"rollback_order":list(reversed(successful))}}
        successful.append(name)
    active_list=sorted(target); registrations=[{"plugin":name,"hook":hook} for name in active_list for hook in sorted(plugins[name]["hooks"])]
    changed_state=active_list!=state["active"] or registrations!=state["registrations"]
    return {"state":{"generation":state["generation"]+(1 if changed_state else 0),"active":active_list,"registrations":registrations},"journal":{"status":"committed","reason":"ok" if changed_state else "no_change","activation_order":activation,"deactivation_order":deactivation,"failed_plugin":None,"rollback_order":[]}}
