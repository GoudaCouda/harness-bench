def plan_csv_dialect_encoding_intake(records, policy):
    if not isinstance(records, list) or not isinstance(policy, dict):
        raise ValueError("records and policy")
    allowed_encodings = policy.get("allowed_encodings")
    allowed_delimiters = policy.get("allowed_delimiters")
    default_encoding = policy.get("default_encoding")
    if not isinstance(allowed_encodings, list) or not allowed_encodings or not isinstance(allowed_delimiters, list) or not allowed_delimiters or default_encoding not in allowed_encodings:
        raise ValueError("policy")

    def parse_rows(text, delimiter):
        rows, row, field, quoted, i = [], [], "", False, 0
        while i < len(text):
            ch = text[i]
            if ch == '"':
                if quoted and i + 1 < len(text) and text[i + 1] == '"':
                    field += '"'; i += 2; continue
                quoted = not quoted; i += 1; continue
            if not quoted and ch == delimiter:
                row.append(field); field = ""; i += 1; continue
            if not quoted and ch in "\r\n":
                row.append(field); rows.append(row); row, field = [], ""
                if ch == "\r" and i + 1 < len(text) and text[i + 1] == "\n": i += 1
                i += 1; continue
            field += ch; i += 1
        if quoted:
            return None
        if field or row:
            row.append(field); rows.append(row)
        return rows

    seen, decisions = set(), []
    for record in records:
        if not isinstance(record, dict) or not isinstance(record.get("id"), str) or not isinstance(record.get("payload_hex"), str):
            raise ValueError("record")
        if record["id"] in seen: raise ValueError("duplicate id")
        seen.add(record["id"])
        try: raw = bytes.fromhex(record["payload_hex"])
        except ValueError: raise ValueError("payload hex")
        declared = record.get("declared_encoding", "__MISSING__")
        bom = None
        if raw.startswith(b"\xef\xbb\xbf"): bom = "utf-8-sig"
        elif raw.startswith(b"\xff\xfe"): bom = "utf-16-le"
        elif raw.startswith(b"\xfe\xff"): bom = "utf-16-be"
        if declared not in ("__MISSING__", None) and declared not in allowed_encodings: raise ValueError("declared encoding")
        if bom and declared not in ("__MISSING__", None, bom):
            decisions.append({"id": record["id"], "status": "reject", "encoding": None, "delimiter": None, "columns": None, "reason": "encoding_conflict"}); continue
        encoding = bom or (default_encoding if declared == "__MISSING__" else declared)
        if encoding is None:
            decisions.append({"id": record["id"], "status": "review", "encoding": None, "delimiter": None, "columns": None, "reason": "encoding_unknown"}); continue
        try: text = raw.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            decisions.append({"id": record["id"], "status": "reject", "encoding": encoding, "delimiter": None, "columns": None, "reason": "decode_error"}); continue
        hint = record.get("delimiter")
        if hint is not None and hint not in allowed_delimiters: raise ValueError("delimiter")
        candidates = [hint] if hint is not None else list(allowed_delimiters)
        valid = []
        for delimiter in candidates:
            rows = parse_rows(text, delimiter)
            if rows and len(rows) >= 2 and len({len(row) for row in rows}) == 1 and len(rows[0]) > 1:
                valid.append((delimiter, len(rows[0])))
        if not valid:
            status, delimiter, columns, reason = "reject", None, None, "malformed_or_inconsistent_rows"
        elif len(valid) > 1:
            status, delimiter, columns, reason = "review", None, None, "ambiguous_delimiter"
        else:
            status, (delimiter, columns), reason = "accept", valid[0], "validated"
        decisions.append({"id": record["id"], "status": status, "encoding": encoding, "delimiter": delimiter, "columns": columns, "reason": reason})
    decisions.sort(key=lambda row: row["id"])
    return {"decisions": decisions, "summary": {key: sum(row["status"] == key for row in decisions) for key in ("accept", "review", "reject")}}
