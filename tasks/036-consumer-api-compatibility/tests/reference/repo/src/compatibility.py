def assess_compatibility(baseline, candidate, consumers):
    def check_document(document):
        if type(document) is not dict: raise ValueError("document")
        for operation_id, operation in document.items():
            if type(operation_id) is not str or not operation_id or type(operation) is not dict or set(operation) != {"request","response"}: raise ValueError("operation")
            for direction in ("request","response"):
                schema=operation[direction]
                if type(schema) is not dict or set(schema)!={"properties","required"} or type(schema["properties"]) is not dict or type(schema["required"]) is not list or len(schema["required"])!=len(set(schema["required"])): raise ValueError("schema")
                if any(x not in schema["properties"] for x in schema["required"]): raise ValueError("required")
                for field, prop in schema["properties"].items():
                    if type(field) is not str or not field or type(prop) is not dict or not set(prop).issubset({"type","enum"}) or "type" not in prop or type(prop["type"]) is not list or not prop["type"] or len(prop["type"])!=len(set(prop["type"])) or any(x not in ("string","number","integer","boolean","object","array","null") for x in prop["type"]): raise ValueError("property")
                    if "enum" in prop and (type(prop["enum"]) is not list or not prop["enum"]): raise ValueError("enum")
    def json_type(value):
        if value is None: return "null"
        if type(value) is bool: return "boolean"
        if type(value) is int: return "integer"
        if type(value) is float: return "number"
        if type(value) is str: return "string"
        if type(value) is list: return "array"
        if type(value) is dict: return "object"
        raise ValueError("value")
    check_document(baseline); check_document(candidate)
    if type(consumers) is not list: raise ValueError("consumers")
    issues=[]; consumer_ids=set()
    for consumer in consumers:
        fields={"consumer_id","operations","always_sends","request_values","response_fields","accepts_null","exhaustive_enums","reject_unknown_response"}
        if type(consumer) is not dict or set(consumer)!=fields or type(consumer["consumer_id"]) is not str or not consumer["consumer_id"] or consumer["consumer_id"] in consumer_ids or type(consumer["operations"]) is not list or len(consumer["operations"])!=len(set(consumer["operations"])): raise ValueError("consumer")
        consumer_ids.add(consumer["consumer_id"])
        for key in fields-{"consumer_id","operations"}:
            if type(consumer[key]) is not dict: raise ValueError("consumer map")
        for operation_id in consumer["operations"]:
            if operation_id not in baseline: raise ValueError("unknown subscription")
            for key in ("always_sends","request_values","response_fields","accepts_null","exhaustive_enums","reject_unknown_response"):
                if operation_id not in consumer[key]: raise ValueError("missing consumer scope")
            def add(direction, field, code): issues.append({"consumer_id":consumer["consumer_id"],"operation_id":operation_id,"direction":direction,"field":field,"code":code})
            if operation_id not in candidate:
                add("operation","*","operation_removed"); continue
            old=baseline[operation_id]; new=candidate[operation_id]
            sent=consumer["always_sends"][operation_id]; values=consumer["request_values"][operation_id]
            consumed=consumer["response_fields"][operation_id]; nulls=consumer["accepts_null"][operation_id]; exhaustive=consumer["exhaustive_enums"][operation_id]; strict=consumer["reject_unknown_response"][operation_id]
            if any(type(x) is not str for x in sent+consumed+nulls+exhaustive) or type(values) is not dict or type(strict) is not bool: raise ValueError("consumer values")
            old_req,new_req=old["request"],new["request"]
            for field in sorted(set(new_req["required"])-set(old_req["required"])):
                if field not in sent: add("request",field,"request_required_added")
            for field in sorted(set(old_req["properties"])&set(new_req["properties"])):
                before,after=old_req["properties"][field],new_req["properties"][field]
                removed_types=set(before["type"])-set(after["type"])
                if any(json_type(value) in removed_types or (json_type(value)=="integer" and "number" in removed_types) for value in values.get(field,[])): add("request",field,"request_type_narrowed")
                if "enum" in before and "enum" in after and any(value in set(before["enum"])-set(after["enum"]) for value in values.get(field,[])): add("request",field,"request_enum_narrowed")
            old_res,new_res=old["response"],new["response"]
            for field in sorted(set(consumed)-set(new_res["properties"])):
                if field in old_res["properties"]: add("response",field,"response_field_removed")
            for field in sorted(set(consumed)&set(old_res["properties"])&set(new_res["properties"])):
                before,after=old_res["properties"][field],new_res["properties"][field]
                if "null" not in before["type"] and "null" in after["type"] and field not in nulls: add("response",field,"response_nullable_added")
                if field in exhaustive and "enum" in before and "enum" in after and set(after["enum"])-set(before["enum"]): add("response",field,"response_enum_widened")
            if strict:
                for field in sorted(set(new_res["properties"])-set(old_res["properties"])): add("response",field,"response_property_added")
    issues=sorted(issues,key=lambda x:(x["consumer_id"],x["operation_id"],x["direction"],x["field"],x["code"]))
    return {"compatible":not issues,"issues":issues}
