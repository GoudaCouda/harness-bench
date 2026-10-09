TOKEN_CHARS="abcdefghijklmnopqrstuvwxyz0123456789-_.[]"
MISSING=()


def _fail():
    raise ValueError()


def _token(value):
    return isinstance(value,str) and bool(value) and value==value.lower() and value.isascii() and all(char in TOKEN_CHARS for char in value)


def _integer(value,minimum=0):
    return isinstance(value,int) and not isinstance(value,bool) and value>=minimum


def _scalar(value):
    return value is None or isinstance(value,(str,bool)) or _integer(value)


def _sorted_tokens(value):
    return isinstance(value,list) and value==sorted(set(value)) and all(_token(item) for item in value)


def _attributes(value):
    return isinstance(value,dict) and all(_token(key) and _scalar(child) for key,child in value.items())


def _topology(rows):
    dependencies={row["address"]:set(row["depends_on"]) for row in rows}; done=[]
    while len(done)<len(rows):
        ready=sorted(address for address,deps in dependencies.items() if address not in done and deps.issubset(set(done)))
        if not ready: _fail()
        done.extend(ready)
    return done


def _validate(resources,prior_state,observed,policy):
    if not isinstance(policy,dict) or set(policy)!={"allow_destroy","sensitive_keys"} or not isinstance(policy["allow_destroy"],bool) or not _sorted_tokens(policy["sensitive_keys"]): _fail()
    if not isinstance(resources,list) or not isinstance(prior_state,list) or not isinstance(observed,list): _fail()
    resource_keys={"address","depends_on","attributes","immutable","lifecycle"}; life_keys={"create_before_destroy","prevent_destroy","ignore_changes","replace_triggered_by","moved_from"}; desired={}
    for row in resources:
        if not isinstance(row,dict) or set(row)!=resource_keys or not _token(row["address"]) or row["address"] in desired or not _sorted_tokens(row["depends_on"]) or not _attributes(row["attributes"]) or not _sorted_tokens(row["immutable"]) or any(key not in row["attributes"] for key in row["immutable"]): _fail()
        life=row["lifecycle"]
        if not isinstance(life,dict) or set(life)!=life_keys or not isinstance(life["create_before_destroy"],bool) or not isinstance(life["prevent_destroy"],bool) or not _sorted_tokens(life["ignore_changes"]) or not _sorted_tokens(life["replace_triggered_by"]) or (life["moved_from"] is not None and not _token(life["moved_from"])): _fail()
        desired[row["address"]]=row
    for row in resources:
        if row["address"] in row["depends_on"] or any(dep not in desired for dep in row["depends_on"]) or row["address"] in row["lifecycle"]["replace_triggered_by"]: _fail()
    _topology(resources)
    state_keys={"address","generation","depends_on","attributes"}; prior={}
    for row in prior_state:
        if not isinstance(row,dict) or set(row)!=state_keys or not _token(row["address"]) or row["address"] in prior or not _integer(row["generation"],1) or not _sorted_tokens(row["depends_on"]) or not _attributes(row["attributes"]): _fail()
        prior[row["address"]]=row
    for row in prior_state:
        if row["address"] in row["depends_on"] or any(dep not in prior for dep in row["depends_on"]): _fail()
    _topology(prior_state)
    observation_keys={"address","exists","attributes","unknown"}; seen={}
    for row in observed:
        if not isinstance(row,dict) or set(row)!=observation_keys or row["address"] not in prior or row["address"] in seen or not isinstance(row["exists"],bool) or not _attributes(row["attributes"]) or not _sorted_tokens(row["unknown"]): _fail()
        if not row["exists"]:
            if row["attributes"] or row["unknown"]: _fail()
        elif set(row["attributes"]) & set(row["unknown"]) or set(row["attributes"]) | set(row["unknown"]) != set(prior[row["address"]]["attributes"]): _fail()
        seen[row["address"]]=row
    if set(seen)!=set(prior): _fail()
    moves={}; destinations=set(prior)
    for row in resources:
        old=row["lifecycle"]["moved_from"]
        if old is not None:
            if old not in prior or old in moves or row["address"] in destinations: _fail()
            moves[old]=row["address"]; destinations.add(row["address"])
    remapped=[]; remapped_seen=[]
    for row in prior_state:
        address=moves.get(row["address"],row["address"])
        remapped.append({"address":address,"generation":row["generation"],"depends_on":sorted(moves.get(dep,dep) for dep in row["depends_on"]), "attributes":dict(row["attributes"])})
        sight=seen[row["address"]]
        remapped_seen.append({"address":address,"exists":sight["exists"],"attributes":dict(sight["attributes"]), "unknown":list(sight["unknown"])})
    remapped_prior={row["address"]:row for row in remapped}; remapped_observed={row["address"]:row for row in remapped_seen}
    universe=set(desired)|set(remapped_prior)
    for row in resources:
        life=row["lifecycle"]; old=remapped_prior.get(row["address"]); keys=set(row["attributes"]) | (set(old["attributes"]) if old else set())
        if any(key not in keys for key in life["ignore_changes"]) or any(target not in universe for target in life["replace_triggered_by"]): _fail()
    return desired,remapped_prior,remapped_observed,moves,remapped


def _redact(values,unknown,sensitive):
    if values is None: return None
    result=dict(values)
    for key in unknown: result[key]="<unknown>"
    for key in sensitive:
        if key in result: result[key]="<sensitive>"
    return {key:result[key] for key in sorted(result)}


def build_lifecycle_plan(resources,prior_state,observed,policy):
    desired,prior,sights,moves,remapped=_validate(resources,prior_state,observed,policy); sensitive=set(policy["sensitive_keys"]); entries={}
    for row in resources:
        address=row["address"]; life=row["lifecycle"]; old=prior.get(address); reasons=[]
        if old is None:
            action="create"; before=None; effective=dict(row["attributes"]); reasons.append("missing_state")
        else:
            sight=sights[address]
            if not sight["exists"]:
                action="create"; before=None; effective=dict(row["attributes"]); reasons.append("missing_remote")
            else:
                before=_redact(sight["attributes"],sight["unknown"],sensitive); effective={}; changed=set(); immutable_unknown=False
                keys=set(row["attributes"])|set(old["attributes"])
                for key in keys:
                    if key in life["ignore_changes"]:
                        if key in sight["attributes"]: effective[key]=sight["attributes"][key]
                        elif key in old["attributes"]: effective[key]=old["attributes"][key]
                        continue
                    if key in row["attributes"]: effective[key]=row["attributes"][key]
                    if key in sight["unknown"]:
                        changed.add(key); reasons.append("unknown_observed:"+key)
                        if key in row["immutable"]: immutable_unknown=True
                        continue
                    desired_value=row["attributes"].get(key,MISSING); prior_value=old["attributes"].get(key,MISSING); observed_value=sight["attributes"].get(key,MISSING)
                    if desired_value!=prior_value:
                        changed.add(key); reasons.append("configuration:"+key)
                    if observed_value!=prior_value:
                        changed.add(key); reasons.append("drift:"+key)
                if immutable_unknown:
                    action="blocked"; reasons.append("unknown_immutable")
                elif changed & set(row["immutable"]): action="replace"
                elif changed: action="update"
                else: action="no-op"
        if life["moved_from"] is not None: reasons.append("moved_from:"+life["moved_from"])
        entries[address]={"address":address,"action":action,"reasons":reasons,"before":before,"after":_redact(effective,[],sensitive),"create_before_destroy":bool(action=="replace" and life["create_before_destroy"])}
    for address,row in prior.items():
        if address in desired: continue
        sight=sights[address]; before=_redact(sight["attributes"],sight["unknown"],sensitive) if sight["exists"] else None
        if not sight["exists"]: action="no-op"; reasons=["already_absent"]
        elif policy["allow_destroy"]: action="delete"; reasons=["removed_configuration"]
        else: action="blocked"; reasons=["destroy_not_allowed"]
        entries[address]={"address":address,"action":action,"reasons":reasons,"before":before,"after":None,"create_before_destroy":False}
    for row in resources:
        entry=entries[row["address"]]
        if entry["action"]=="replace" and row["lifecycle"]["prevent_destroy"]:
            entry["action"]="blocked"; entry["create_before_destroy"]=False; entry["reasons"].append("prevent_destroy")
    changed=True
    while changed:
        changed=False
        for row in resources:
            entry=entries[row["address"]]
            if entry["action"] in ("create","replace","blocked"): continue
            active=sorted(target for target in row["lifecycle"]["replace_triggered_by"] if entries[target]["action"] in ("create","update","replace","delete"))
            if active:
                entry["action"]="replace"; entry["reasons"].extend("replace_triggered_by:"+target for target in active); entry["create_before_destroy"]=row["lifecycle"]["create_before_destroy"]; changed=True
            if entry["action"]=="replace" and row["lifecycle"]["prevent_destroy"]:
                entry["action"]="blocked"; entry["create_before_destroy"]=False; entry["reasons"].append("prevent_destroy"); changed=True
    changed=True
    while changed:
        changed=False
        for row in resources:
            if entries[row["address"]]["action"]=="replace" and entries[row["address"]]["create_before_destroy"]:
                for dep in row["depends_on"]:
                    if entries[dep]["action"]=="replace" and not entries[dep]["create_before_destroy"]:
                        entries[dep]["create_before_destroy"]=True; entries[dep]["reasons"].append("create_before_destroy_propagated"); changed=True
    for entry in entries.values(): entry["reasons"]=sorted(set(entry["reasons"]))
    desired_order=_topology(resources); prior_order=_topology(remapped); steps=[]
    for address in reversed(desired_order):
        if entries[address]["action"]=="replace" and not entries[address]["create_before_destroy"]: steps.append({"address":address,"operation":"destroy_replacement"})
    for address in desired_order:
        action=entries[address]["action"]
        if action=="create": steps.append({"address":address,"operation":"create"})
        elif action=="update": steps.append({"address":address,"operation":"update"})
        elif action=="replace": steps.append({"address":address,"operation":"create_replacement"})
    for address in reversed(desired_order):
        if entries[address]["action"]=="replace" and entries[address]["create_before_destroy"]: steps.append({"address":address,"operation":"destroy_deposed"})
    for address in reversed(prior_order):
        if entries[address]["action"]=="delete": steps.append({"address":address,"operation":"delete"})
    plan_resources=[entries[address] for address in sorted(entries)]; summary={name:sum(entry["action"]==name for entry in plan_resources) for name in ("create","update","replace","delete","no-op","blocked")}; summary["step_count"]=len(steps); summary["moved_count"]=len(moves)
    return {"plan":{"resources":plan_resources,"steps":steps},"summary":summary}
