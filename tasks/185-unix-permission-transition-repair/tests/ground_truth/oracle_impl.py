def plan_unix_permission_transition(records, policy):
    if not isinstance(records, list) or not isinstance(policy, dict) or not isinstance(policy.get("umask"), int) or not 0 <= policy["umask"] <= 0o777: raise ValueError("records and policy")
    preserve_special = policy.get("preserve_special", False)
    if not isinstance(preserve_special, bool): raise ValueError("policy")
    masks = {'u': 0o700, 'g': 0o070, 'o': 0o007}; bits = {'r': 4, 'w': 2, 'x': 1}
    def symbolic(mode, expression):
        if not isinstance(expression, str) or not expression: raise ValueError("symbolic mode")
        for clause in expression.split(','):
            pos = 0
            while pos < len(clause) and clause[pos] in 'ugo': pos += 1
            who = clause[:pos] or 'ugo'
            if pos >= len(clause) or clause[pos] not in '+-=': raise ValueError("symbolic clause")
            op, perms = clause[pos], clause[pos + 1:]
            if any(ch not in 'rwx' for ch in perms): raise ValueError("symbolic perms")
            target_mask, add = 0, 0
            for owner in who:
                target_mask |= masks[owner]
                shift = {'u': 6, 'g': 3, 'o': 0}[owner]
                for ch in perms: add |= bits[ch] << shift
            if op == '+': mode |= add
            elif op == '-': mode &= ~add
            else: mode = (mode & ~target_mask) | add
        return mode
    seen, decisions = set(), []
    for row in records:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str) or row.get("operation") not in ('create', 'chmod') or not isinstance(row.get("is_dir"), bool): raise ValueError("record")
        if row["id"] in seen: raise ValueError("duplicate id")
        seen.add(row["id"])
        if row["operation"] == 'create':
            requested = row.get("requested_mode", 0o777 if row["is_dir"] else 0o666)
            if not isinstance(requested, int) or requested < 0 or requested > 0o7777: raise ValueError("requested mode")
            result = requested & ~policy["umask"] & 0o777
        else:
            current = row.get("current_mode")
            if not isinstance(current, int) or current < 0 or current > 0o7777: raise ValueError("current mode")
            result = symbolic(current & 0o777, row.get("symbolic"))
            if preserve_special: result |= current & 0o7000
        decisions.append({"id": row["id"], "mode": format(result, '04o'), "changed": row.get("current_mode") != result if row["operation"] == 'chmod' else True, "operation": row["operation"]})
    decisions.sort(key=lambda row: row["id"])
    return {"decisions": decisions, "summary": {"created": sum(r["operation"] == 'create' for r in decisions), "chmod": sum(r["operation"] == 'chmod' for r in decisions)}}
