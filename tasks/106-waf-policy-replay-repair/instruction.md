# Repair and stage an offline WAF policy through request replay

You are the application security engineer responsible for a local gateway WAF
policy. Revision 7 simultaneously blocks one verified vendor webhook, misses a
double-encoded download traversal, and permits a fourth login attempt inside an
approved rate window. Healthy SQL-injection and unrelated-route behavior must
remain unchanged.

Work only in `$WORKSPACE`. Read `incident.md` and `policy.md`, then inspect the
local evidence and replay interface:

1. Run `python3 wafctl.py --help`, `python3 wafctl.py status`, and
   `python3 wafctl.py replay`. The failing replay writes
   `replay_report.json`; use its request IDs with `python3 wafctl.py inspect
   --request-id ID` where useful.
2. Review `waf_policy_seed.json`, the mutable `waf_policy.json`,
   `traffic_corpus.json`, `trusted_signers.json`, and
   `baseline_snapshot.json`.
3. Repair `waf_policy.json` as data. Keep its exact top-level schema and all
   four rule IDs. Increment revision 7. Keep every baseline rule enabled.
4. Re-run the replay until all public cases pass. The hidden review also sends
   unseen requests, so do not special-case request IDs or weaken a rule
   globally.

## Required policy result

- Detect traversal under `/download/` after the policy-required bounded decode
  depth, without blocking safe nested download paths.
- Keep the upstream-style `RCE-932100` rule enabled. Add only a local exclusion
  scoped to the exact rule, `POST /hooks/vendor`, `body.message`, and a
  cryptographically verified active `vendor-prod` signer. Signature-shaped
  text, a retired key, a different route or method, and `body.command` do not
  qualify for that exclusion.
- Enforce the `/login` POST limit as three allowed requests per `client_ip` in
  a 60-second sliding window. The fourth and later requests in the window must
  return 429; another client has an independent window.
- Preserve SQL-injection blocking and the unrelated healthy behavior captured
  by the baseline snapshot. Do not add request-ID logic, a catch-all allow, or
  a global exclusion.

The public policy schema is intentionally compact. Each exclusion object has
exactly `rule_id`, `method`, `path`, `field`, and `verified_signer`. Rule object
keys already present in the seed are the supported keys; do not invent a new
engine schema.

## Handoff and closure

Keep the final controller-generated `replay_report.json`. Create
`change_record.md` that explains the incident evidence, root cause and narrow
repair for all three regressions, verified-signer boundary, unaffected SQL and
route regression evidence, remaining security-review gate, and the fact that
no deployment occurred.

Then run:

```text
python3 wafctl.py validate
python3 wafctl.py stage
python3 wafctl.py verify-stage
python3 wafctl.py verify-stage
```

Staging is local only. It creates `.waf_stage_state.json` and
`waf_stage_receipt.json`, both bound to the protected input bundle and exact
policy, replay report, and change-record bytes. The two verification runs must
pass without changing either file.

Keep `incident.md`, `policy.md`, `traffic_corpus.json`,
`trusted_signers.json`, `baseline_snapshot.json`, `waf_policy_seed.json`, and
`wafctl.py` unchanged. Do not use the network, modify a production WAF, send a
webhook, or claim deployment or security approval.
