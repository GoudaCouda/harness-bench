# Repair checkout authentication after an issuer migration

You are taking over a production checkout incident after an issuer migration.
The checkout path is still rejecting partner sessions. Diagnose the causal
service, make the smallest safe repair in the isolated service repository, and
leave an operator-ready handoff.

Use these offline inputs:

- `$WORKSPACE/topology.json`
- `$WORKSPACE/metrics/service_metrics.csv`
- `$WORKSPACE/logs/checkout-web.log`
- `$WORKSPACE/logs/payment-api.log`
- `$WORKSPACE/logs/auth-gateway.log`
- `$WORKSPACE/logs/orders-db.log`
- `$WORKSPACE/service_repo/change_record.md`
- `$WORKSPACE/service_repo/auth_gateway_config.json`
- `$WORKSPACE/service_repo/fixtures/token_cases.json`
- `$WORKSPACE/service_repo/verify_checkout.py`

Run the repository verifier before and after your repair:

```bash
python3 $WORKSPACE/service_repo/verify_checkout.py \
  --config $WORKSPACE/service_repo/auth_gateway_config.json
```

Repair `$WORKSPACE/service_repo/auth_gateway_config.json` in place. Preserve
unaffected employee authentication, accepted audiences, signing-key checks,
cache behavior, and fail-closed validation. Do not broaden trust with wildcards
or keep a retired issuer solely to make an old token pass. The final verifier
run must pass all positive and negative cases.

Also create exactly these output files:

- `$WORKSPACE/root_cause.json`
- `$WORKSPACE/triage_notes.md`

## `root_cause.json`

- Use a top-level object with `incident_id`, `root_cause_service`,
  `root_cause_change_id`, `confidence`, `affected_services`, `evidence`,
  `excluded_red_herrings`, and `recommended_next_steps`.
- The inputs do not provide a canonical incident ID. Use any concise non-empty
  local audit label, or `UNKNOWN`, without presenting it as an extracted fact.
- `affected_services` must cover the customer-impacting `checkout-web` and
  `payment-api` boundary. You may also include the diagnosed root service if
  your incident convention treats the failing origin as affected; do not add
  unrelated services.
- `evidence` must contain objects with `source_file` and `observation`. Bind at
  least three distinct declared input paths to concrete service, change, error,
  dependency, or metric observations. A joined path string does not count as
  multiple sources.
- `excluded_red_herrings` must identify misleading signals and explain why each
  is not the primary cause.

## `triage_notes.md`

- Separate directly observed facts from inference.
- Explain the ordered dependency path and the issuer/JWKS change that caused
  the incident, citing at least three concrete input paths.
- Record the exact verifier command and its final pass count.
- Explain why the config change is minimal, what remains valid, and how to
  restore the original issuer allowlist if post-change monitoring regresses.

Do not modify logs, metrics, topology, the verifier, fixtures, or change record.
Do not use live services or external APIs. Only the auth-gateway config and the
two declared handoff files may differ when you finish.
