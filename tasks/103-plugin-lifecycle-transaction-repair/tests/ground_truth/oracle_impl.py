import copy


def _integer(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _exact(value, keys):
    return isinstance(value, dict) and set(value) == set(keys)


def _string_list(value, unique=True):
    return isinstance(value, list) and all(isinstance(item, str) and item for item in value) and (not unique or len(value) == len(set(value)))


def _preflight(state, catalog, request, faults):
    if not isinstance(catalog, list): raise ValueError("catalog")
    plugins = {}
    hooks = set()
    for item in catalog:
        if not _exact(item, ("name","depends","hooks")) or not isinstance(item["name"],str) or not item["name"] or not _string_list(item["depends"]) or not _string_list(item["hooks"]): raise ValueError("plugin")
        if item["name"] in plugins or item["name"] in item["depends"] or hooks.intersection(item["hooks"]): raise ValueError("duplicate")
        plugins[item["name"]]=item; hooks.update(item["hooks"])
    if any(dep not in plugins for item in catalog for dep in item["depends"]): raise ValueError("dependency")
    visiting=set(); done=set()
    def visit(name):
        if name in visiting: raise ValueError("cycle")
        if name in done: return
        visiting.add(name)
        for dep in plugins[name]["depends"]: visit(dep)
        visiting.remove(name); done.add(name)
    for name in plugins: visit(name)
    if not _exact(state,("generation","active","registrations")) or not _integer(state["generation"]) or state["generation"] < 0 or not _string_list(state["active"]): raise ValueError("state")
    if any(name not in plugins for name in state["active"]) or not isinstance(state["registrations"],list): raise ValueError("active")
    active=set(state["active"])
    if any(dep not in active for name in active for dep in plugins[name]["depends"]): raise ValueError("active closure")
    for row in state["registrations"]:
        if not _exact(row,("plugin","hook")) or not isinstance(row["plugin"],str) or not row["plugin"] or not isinstance(row["hook"],str) or not row["hook"]: raise ValueError("registration")
    for value in (request,faults):
        if not _exact(value,("enable","disable")) and value is request: raise ValueError("request")
        if not _exact(value,("activate","deactivate")) and value is faults: raise ValueError("faults")
    if not _string_list(request["enable"]) or not _string_list(request["disable"]) or not _string_list(faults["activate"]) or not _string_list(faults["deactivate"]): raise ValueError("lists")
    return plugins


def _topo(names, plugins):
    names=set(names); result=[]
    while names:
        ready=sorted(name for name in names if not (set(plugins[name]["depends"]) & names))
        if not ready: raise ValueError("cycle")
        for name in ready: result.append(name); names.remove(name)
    return result


def reconcile_plugins(state, catalog, request, faults):
    plugins=_preflight(state,catalog,request,faults)
    initial=copy.deepcopy(state); known=set(plugins)
    empty=lambda status,reason: {"state":copy.deepcopy(initial),"journal":{"status":status,"reason":reason,"activation_order":[],"deactivation_order":[],"failed_plugin":None,"rollback_order":[]}}
    if any(name not in known for name in request["enable"]+request["disable"]): return empty("rejected","unknown_plugin")
    if set(request["enable"]) & set(request["disable"]): return empty("rejected","request_conflict")
    enable=set()
    def add_dependencies(name):
        if name in enable: return
        for dep in plugins[name]["depends"]: add_dependencies(dep)
        enable.add(name)
    for name in request["enable"]: add_dependencies(name)
    active=set(state["active"]); disable=set(name for name in request["disable"] if name in active)
    changed=True
    while changed:
        changed=False
        for name in active-disable:
            if set(plugins[name]["depends"]) & disable:
                disable.add(name); changed=True
    if enable & disable: return empty("rejected","request_conflict")
    target=(active-disable)|enable
    activation=_topo(target-active,plugins)
    deactivation=list(reversed(_topo(disable,plugins)))
    successful=[]
    for name in deactivation:
        if name in faults["deactivate"]:
            return {"state":copy.deepcopy(initial),"journal":{"status":"rolled_back","reason":"deactivate_failed","activation_order":activation,"deactivation_order":deactivation,"failed_plugin":name,"rollback_order":list(reversed(successful))}}
        successful.append(name)
    for name in activation:
        if name in faults["activate"]:
            return {"state":copy.deepcopy(initial),"journal":{"status":"rolled_back","reason":"activate_failed","activation_order":activation,"deactivation_order":deactivation,"failed_plugin":name,"rollback_order":list(reversed(successful))}}
        successful.append(name)
    active_list=sorted(target)
    registrations=[{"plugin":name,"hook":hook} for name in active_list for hook in sorted(plugins[name]["hooks"])]
    changed_state=active_list != state["active"] or registrations != state["registrations"]
    result_state={"generation":state["generation"]+(1 if changed_state else 0),"active":active_list,"registrations":registrations}
    return {"state":result_state,"journal":{"status":"committed","reason":"ok" if changed_state else "no_change","activation_order":activation,"deactivation_order":deactivation,"failed_plugin":None,"rollback_order":[]}}
