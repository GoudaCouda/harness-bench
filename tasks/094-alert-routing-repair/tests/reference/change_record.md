# INC-482 local rehearsal handoff

## Root cause and repair

The service-only payments child route stopped traversal before the critical
route, while an active `service=payments` silence also covered the root-cause
page. The empty inhibition equality set could suppress unrelated warnings. I
put the global critical matcher first so every critical alert goes only to
`platform-page`, limited the payments-low route to warnings, grouped on
`cluster`, `service`, and `alertname`, and made the inhibition rule compare the
same three identity labels.

The isolated control-plane emulator is not an Alertmanager daemon. The local
apply command discovered and expired the active broad silence in its API state,
then created the exact `service=payments` plus `alertname=DeployNoise`
replacement with a runtime 90-minute lifetime. It requested reload and checked
readiness after both runtime mutations. The first reload returned the injected
transient HTTP 503; bounded retry recovered without repeating the completed
silence delete or creation. A second run was idempotent: it reused the active
replacement and produced no duplicate silence, then reloaded and checked ready.

## Observed local checks

I loaded `$ALERTMANAGER_ENV` and ran `$ALERTMANAGER_VALIDATOR check-config
repo/alertmanager.yml --utf8-strict`; the pinned `hb-amconfig` 0.32.1-profile
validator reported a valid configuration. `python repo/tools/check_public_routes.py
repo/alertmanager.yml` passed all four public route cases. Finally, the
temporary `/runtime` repair helper completed against `$ALERTMANAGER_URL`
twice against the stateful control-plane rehearsal, including transient recovery, reload, and
readiness.

## Rollback and scope

Rollback restores the previous configuration, requests another local reload,
and expires the narrow replacement silence. It must not recreate the unsafe
service-wide silence. No production endpoint was contacted and no production
action was performed.
