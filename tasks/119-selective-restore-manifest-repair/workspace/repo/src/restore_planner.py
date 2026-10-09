def plan_restore(snapshots, destination, request):
    """Broken: restores every file from the lexically newest snapshot."""
    snapshot=sorted(snapshots,key=lambda item:item["snapshot_id"])[-1]
    actions=[]
    for entry in snapshot["entries"]:
        if entry["operation"]=="upsert": actions.append({"source_path":entry["path"],"target_path":request["target_root"]+entry["path"],"kind":entry["kind"],"checksum":entry["checksum"],"action":"restore","reason":"missing"})
    return {"plan":{"status":"ready","reason":"ready","snapshot_id":snapshot["snapshot_id"],"chain":[snapshot["snapshot_id"]],"actions":actions},"summary":{"restore":len(actions),"unchanged":0,"conflict":0,"selected":len(actions),"dry_run":True}}
