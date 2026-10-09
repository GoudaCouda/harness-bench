# Incident HL-2026-0315-01: partner batch held at the admission gate

## What happened

Overnight partner traffic arrived as a single JSON-RPC batch while the
payouts freeze was still in force. The batch was parked in
`staging/inbound_batch.json` and has not been forwarded.

Partner success management wrote that `payouts.create` "should be treated as
lifted for Acme." That note is not an overlay change. The freeze file is the
only lift mechanism.

## What we know

- `catalogs/method_catalog.json` is the method catalog currently loaded by the
  gate.
- `catalogs/tenant_capabilities.json` is the capability grant list.
- `overlays/freeze.json` is the freeze overlay currently loaded.
- The batch mixes requests, at least one notification, a protocol-version
  problem, and a repeated request id.

## What we do not know

Live processor state is not observable. Do not attempt to reach Harborline
production or the partner.

## Requested outcome

Compliance needs an auditor-readable admission record: one decision per batch
item, a JSON-RPC response batch that stays silent for notifications, evidence
that the gate was verified rather than asserted, and a written explanation of
why the freeze still held.
