def plan_dmarc_alignment(records, policy):
    if not isinstance(records, list) or not isinstance(policy, dict): raise ValueError("records and policy")
    if policy.get("adkim") not in ('r', 's') or policy.get("aspf") not in ('r', 's') or policy.get("p") not in ('none', 'quarantine', 'reject') or policy.get("sp", policy.get("p")) not in ('none', 'quarantine', 'reject') or not isinstance(policy.get("pct"), int) or not 0 <= policy["pct"] <= 100 or not isinstance(policy.get("organizational_domains"), dict): raise ValueError("policy")
    orgs = policy["organizational_domains"]
    def aligned(auth_domain, from_domain, mode):
        if not isinstance(auth_domain, str): return False
        a, f = auth_domain.lower().rstrip('.'), from_domain.lower().rstrip('.')
        if mode == 's': return a == f
        return orgs.get(a) is not None and orgs.get(a) == orgs.get(f)
    seen, decisions = set(), []
    for row in records:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str) or not isinstance(row.get("from_domain"), str) or not isinstance(row.get("spf"), dict) or not isinstance(row.get("dkim"), list) or not isinstance(row.get("sample_bucket"), int) or not 0 <= row["sample_bucket"] <= 99: raise ValueError("record")
        if row["id"] in seen: raise ValueError("duplicate id")
        seen.add(row["id"]); from_domain = row["from_domain"].lower().rstrip('.')
        if from_domain not in orgs: raise ValueError("unknown organizational domain")
        spf = row["spf"]
        if not isinstance(spf.get("domain"), str) or not isinstance(spf.get("result"), str):
            raise ValueError("spf result")
        spf_aligned = spf["result"] == 'pass' and aligned(spf["domain"], from_domain, policy["aspf"])
        dkim_aligned = False
        for sig in row["dkim"]:
            if not isinstance(sig, dict) or not isinstance(sig.get("domain"), str) or not isinstance(sig.get("result"), str):
                raise ValueError("dkim signature")
            if sig["result"] == 'pass' and aligned(sig["domain"], from_domain, policy["adkim"]): dkim_aligned = True
        passed = spf_aligned or dkim_aligned
        is_subdomain = orgs[from_domain] != from_domain
        requested = policy.get("sp", policy["p"]) if is_subdomain else policy["p"]
        if passed: disposition, reason = "none", "dmarc_pass"
        elif row["sample_bucket"] >= policy["pct"]: disposition, reason = "none", "outside_sample"
        else: disposition, reason = requested, "policy_applied"
        decisions.append({"id": row["id"], "pass": passed, "spf_aligned": spf_aligned, "dkim_aligned": dkim_aligned, "disposition": disposition, "reason": reason})
    decisions.sort(key=lambda row: row["id"])
    return {"decisions": decisions, "summary": {"pass": sum(r["pass"] for r in decisions), "quarantine": sum(r["disposition"] == 'quarantine' for r in decisions), "reject": sum(r["disposition"] == 'reject' for r in decisions)}}
