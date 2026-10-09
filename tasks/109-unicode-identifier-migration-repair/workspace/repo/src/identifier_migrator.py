def migrate_identifiers(records, reserved, policy):
    """Broken: ASCII lowercase overwrites collisions and drops blocked refs."""
    output=[]
    for record in records:
        canonical=record["identifier"].lower()
        output.append({"record_id":record["record_id"],"display_identifier":canonical,"canonical_identifier":canonical,"status":"accepted","canonical_references":[],"unresolved_reference_ids":[]})
    return {"records":output,"conflicts":[]}
