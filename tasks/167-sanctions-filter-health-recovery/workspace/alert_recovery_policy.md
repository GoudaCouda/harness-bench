# Synthetic alert policy SAN-CTRL-9

The healthy configuration is `config_version=FILTER-8` and `list_version=LIST-2026-07-15`.

Apply rules in order:

1. Missing post-repair result, stale list version, stale config version, or failed health probe: decision=`pending_rescreen`, reason_code=`CONTROL_NOT_VERIFIED`, owner=`sanctions_operations`, next_action=`resume_post_repair_screening`.
2. Exact post-repair match: decision=`blocked`, reason_code=`EXACT_ALERT_MATCH`, owner=`sanctions_compliance`, next_action=`open_alert_investigation`.
3. Possible post-repair match: decision=`review`, reason_code=`POSSIBLE_ALERT_MATCH`, owner=`sanctions_compliance`, next_action=`perform_alert_review`.
4. No-match may be clear only when `disposition_role=compliance_officer`: decision=`clear`, reason_code=`AUTHORIZED_NO_MATCH`, owner=`sanctions_compliance`, next_action=`record_authorized_clearance`.
5. An attempted clearance by any other role is decision=`review`, reason_code=`UNAUTHORIZED_DISPOSITION`, owner=`sanctions_compliance`, next_action=`route_to_authorized_reviewer`.

Do not run screening or clear production alerts; classify the recovery evidence only.

Output evidence rule: for every ledger row, set evidence_refs to `post_repair_alerts.csv#<item_id>;alert_recovery_policy.md;context.md` in any order. Here `<item_id>` is a substitution marker: use the row's literal item ID after `#` and do not emit angle or square brackets.
