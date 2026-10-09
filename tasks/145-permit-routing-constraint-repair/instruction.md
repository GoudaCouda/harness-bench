# Repair permit routing after map revision Z-2026.3

You operate an offline municipal permit-routing simulator. The zoning layer was
updated, but the current routing configuration still uses Z-2026.2 and skips a
historic-overlay review for mixed-use parcels.

1. Read `routing_policy.md`, `map_layers.json`, `applications.json`, and inspect
   `routing_config.json` with `python3 permitctl.py status`.
2. Run `python3 permitctl.py replay routing_config.json` and inspect each
   misroute. Edit only `routing_config.json` to the correct map version,
   precedence, and reviewer routes.
3. Run `python3 permitctl.py validate routing_config.json`, then replay again.
   The replay writes `replay_report.json`.
4. Run `python3 permitctl.py commit routing_config.json` to record one local
   configuration revision, then `python3 permitctl.py verify` to create
   `routing_receipt.json`. Repeat commit to prove idempotency.
5. Write `permit_handoff.md` explaining every application route, constraint
   precedence, historical replay result, and that no permit was approved,
   denied, published, or sent to a live agency.

Do not modify source map, applications, policy, or the controller.
