# Settlement idempotency policy (authoritative)

Northgate Clearing runs invoice settlements behind an idempotency ledger so a
retried request can never settle the same invoice twice. This document is the
authoritative rule set for recovery. Where the ledger contents and this policy
disagree, this policy wins.

## 1. Recovery clock

Recovery is evaluated against a single frozen clock, not wall time:

- `recovery_clock_epoch` = `1773478800` (2026-03-14T09:00:00Z)

Every retention and lease comparison below uses that value. `ledgerctl.py clock`
prints it.

## 2. Idempotency keys

A key is usable only when, after stripping leading and trailing spaces (`0x20`)
and tabs (`0x09`), it matches `^[A-Za-z0-9._:-]{1,64}$`. Keys are
case-sensitive; no other normalization is applied. `  pay-42\t` and `pay-42`
are the same key. A key that is unusable after trimming is never looked up in
the ledger.

## 3. Request fingerprint

A request fingerprint is the lowercase hex SHA-256 of

```
method + "\n" + path + "\n" + canonical_body
```

where `canonical_body` is the request body serialized as JSON with sorted keys
and no whitespace between tokens. `ledgerctl.py fingerprint <request-id>`
computes this for any queued request.

## 4. Record retention

A ledger record is retained for `record_ttl_seconds` = `86400` seconds measured
from its own `created_at`. When
`recovery_clock_epoch - created_at >= 86400`, the record has left the retention
window: it is no longer usable evidence and must not remain in the recovered
ledger. A later request under that key is treated as if no record existed.

## 5. Leases

An `in_flight` record carries `lease_expires_at`.

- When `recovery_clock_epoch >= lease_expires_at`, the lease is dead. The worker
  that held it is gone, so the record is released and must not remain in the
  recovered ledger.
- When `recovery_clock_epoch < lease_expires_at`, the lease is live. Another
  worker may still be settling it. The record is preserved byte-for-byte and its
  key must not be settled by this recovery.

## 6. Decision precedence

Recover the ledger first, then evaluate each queued request against the
recovered ledger in exactly this order. The first matching rule wins.

1. `rejected` — the key is unusable under section 2.
2. `replayed` — a `completed` record exists for the key and its `fingerprint`
   equals the request fingerprint. Return the record's stored `response`
   unchanged. Do not settle again.
3. `conflict` — a `completed` record exists for the key and its `fingerprint`
   differs. Refuse the request. Do not settle, and do not overwrite the record.
4. `deferred` — an `in_flight` record with a live lease exists for the key.
5. `executed` — otherwise. Settle the request and write a `completed` record.

## 7. Settlement response and record shape

An executed settlement produces exactly

```json
{
  "invoice": "<body.invoice>",
  "status": "settled",
  "amount_cents": <body.amount_cents>,
  "receipt_id": "RCP-<canonical key>"
}
```

and stores the record

```json
{
  "status": "completed",
  "fingerprint": "<request fingerprint>",
  "created_at": <recovery_clock_epoch>,
  "response": { ... as above ... }
}
```

A record that is re-settled after leaving the retention window starts a fresh
retention window, so its `created_at` becomes the recovery clock.

## 8. Money boundary

`settled_total_cents` counts only amounts actually settled by this recovery,
that is, only `executed` decisions. Replayed, conflicting, deferred, and
rejected requests contribute nothing. Double-counting a previously settled
invoice is a settlement integrity failure, not a rounding difference.

## 9. Authorization boundary

This recovery is an offline local reconciliation. Contacting the payment
processor, releasing funds, notifying a customer, filing a report, or deleting
audit evidence is outside the authorization of this task.
