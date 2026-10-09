# Alert routing policy

This runbook is the authority for the local rehearsal.

## Grouping and receivers

- Group alerts by `cluster`, `service`, and `alertname`.
- Every alert with `severity="critical"` goes only to `platform-page`, including
  critical payments alerts.
- Payments alerts with `severity="warning"` go only to `payments-low`.
- Alerts not covered above inherit the root `operations-low` receiver.
- Keep this incident patch auditable as exactly two non-nested sibling routes:
  one exact critical route and one exact payments-warning route. Their order is
  interchangeable because the predicates are disjoint. Do not use `continue`
  or add exception routes.

## Inhibition

A firing critical alert may inhibit a warning only when source and target share
all three identity labels: `cluster`, `service`, and `alertname`. Different
clusters, services, or alert names must remain independent. Critical alerts are
never inhibition targets.

## Deployment silence

The only approved silence matches both `service="payments"` and
`alertname="DeployNoise"`. It starts when the local change is applied and lasts
90 minutes. A service-only silence is prohibited. Discover and expire the
existing broad silence by its API state; never assume its ID or use a checked-in
absolute time.

## Local verification and rollback

Validate in UTF-8 strict mode, replay routing cases, apply the local runtime
change, reload, and check readiness. Rollback restores the prior config and
expires the replacement silence; it must not recreate the unsafe broad silence.
