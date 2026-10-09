import re

IDENT=re.compile(r"[a-z0-9][a-z0-9_-]*"); CHECKSUM=re.compile(r"[0-9a-f]{64}")

def _validate(value,ledger=False):
    required={"id","from_version","to_version","checksum"} if ledger else {"id","from_version","to_version","checksum","statements"}
    if not isinstance(value,dict) or set(value)!=required or not isinstance(value["id"],str) or not IDENT.fullmatch(value["id"]) or type(value["from_version"]) is not int or type(value["to_version"]) is not int or value["from_version"]<0 or value["to_version"]<=value["from_version"] or not isinstance(value["checksum"],str) or not CHECKSUM.fullmatch(value["checksum"]):raise ValueError("identity")
    if not ledger and (not isinstance(value["statements"],list) or not value["statements"]):raise ValueError("statements")
    if not ledger:
        for statement in value["statements"]:
            if not isinstance(statement,str) or not statement.strip() or statement.strip().casefold().split()[0] in ("begin","commit","rollback","savepoint","release"):raise ValueError("statement")

def _full(m):return ["begin_immediate"]+[f"statement:{i}" for i in range(len(m["statements"]))]+[f"ledger_insert:{m['id']}:{m['checksum']}",f"set_user_version:{m['to_version']}","commit"]

def plan_migration_recovery(migration,db_state,observation):
    _validate(migration)
    if not isinstance(db_state,dict) or set(db_state)!={"user_version","ledger"} or type(db_state["user_version"]) is not int or db_state["user_version"]<0 or not isinstance(db_state["ledger"],list):raise ValueError("state")
    records={}; highest=0
    for record in db_state["ledger"]:
        _validate(record,True)
        if record["id"] in records:raise ValueError("duplicate")
        records[record["id"]]=record; highest=max(highest,record["to_version"])
    if highest!=db_state["user_version"]:raise ValueError("divergence")
    phases=("clean","busy_begin","busy_statement","busy_commit","commit_unknown","interrupted")
    if not isinstance(observation,dict) or set(observation)!={"phase","transaction_active"} or type(observation["transaction_active"]) is not bool or observation["phase"] not in phases or observation["transaction_active"]!=(observation["phase"] in ("busy_statement","busy_commit")):raise ValueError("observation")
    verify={"migration_id":migration["id"],"checksum":migration["checksum"],"user_version":migration["to_version"]}; existing=records.get(migration["id"])
    if existing is not None:
        if existing!={name:migration[name] for name in ("id","from_version","to_version","checksum")} or db_state["user_version"]!=migration["to_version"]:raise ValueError("identity")
        return {"decision":"noop","retry_scope":"none","actions":[],"verification":verify}
    if db_state["user_version"]!=migration["from_version"]:raise ValueError("version")
    phase=observation["phase"]
    if phase=="clean":return {"decision":"apply","retry_scope":"none","actions":_full(migration),"verification":verify}
    if phase=="busy_begin":return {"decision":"retry","retry_scope":"whole_transaction","actions":["wait_backoff"]+_full(migration),"verification":verify}
    if phase=="busy_statement":return {"decision":"retry","retry_scope":"whole_transaction","actions":["rollback","wait_backoff"]+_full(migration),"verification":verify}
    if phase=="busy_commit":return {"decision":"retry_commit","retry_scope":"commit_only","actions":["wait_backoff","commit"],"verification":verify}
    if phase=="commit_unknown":return {"decision":"probe","retry_scope":"after_recheck","actions":["reopen","read_ledger_and_user_version"],"verification":verify}
    return {"decision":"retry","retry_scope":"whole_transaction","actions":["reopen","read_ledger_and_user_version"]+_full(migration),"verification":verify}
