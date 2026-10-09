# Settlement ledger recovery handoff — incident NC-2026-0314-02

## What was broken

`settle-worker-7` died mid-batch and left the settlement idempotency ledger
holding three different kinds of record at once: work it had finished, a lease
it had claimed but never completed, and a record that had already left the
retention window before the batch began. The replay queue was never
acknowledged, so all eight requests still needed a decision.

Everything below is evaluated against the frozen recovery clock
`1773478800` and the published retention window of `86400` seconds.

## Ledger recovery

- `pay-1002` held a dead lease (`lease_expires_at` `1773478680`, already behind
  the recovery clock). The worker holding it is gone, so the lease was released.
- `pay-1004` was past retention (`created_at` `1773388800`, an age of `90000`
  seconds). It was dropped as unusable evidence rather than trusted.
- `pay-1003` holds a live lease (`lease_expires_at` `1773479400`) belonging to
  `settle-worker-4`. It was preserved untouched and was not settled here.
- `pay-1001` and `pay-1005` were inside retention and were left byte-for-byte
  as they were.

## Per-request decisions

| Request | Key | Decision | Why |
|---|---|---|---|
| `req-01` | `pay-1001` | `replayed` | Same fingerprint as the stored completed record, so the stored response was returned and nothing was settled again. |
| `req-02` | `pay-1005` | `conflict` | The key was already settled for `31000`, but this request asks for `31500`. Refused; the existing record was not overwritten. |
| `req-03` | `pay-1002` | `executed` | Its dead lease was released, so no usable record remained and the settlement ran once. |
| `req-04` | `pay-1004` | `executed` | The prior record was past retention, so this is a fresh settlement and its record starts a new retention window at the recovery clock. |
| `req-05` | `pay-1006` | `executed` | No prior record under this key. |
| `req-06` | `pay-1007` | `executed` | The raw key `  pay-1007\t` is usable after trimming spaces and tabs, and its canonical form had no prior record. |
| `req-07` | `pay 1008!` | `rejected` | The key still contains a space and an exclamation mark after trimming, so it fails the key rule and was never looked up. |
| `req-08` | `pay-1003` | `deferred` | A live lease is held by another worker; taking the work would risk a double settlement. |

## Settlement integrity

Four requests settled: `48000 + 22000 + 9900 + 15600`, so
`settled_total_cents` is `95500`. The replayed, conflicting, deferred, and
rejected requests contributed nothing. No invoice settled twice: the one
same-fingerprint retry replayed its stored response, and the one reused key with
a changed amount was refused rather than settled a second time.

## Verification

`python3 ledgerctl.py validate` was run twice against the final state. Both
attempts reported `pass` with no failed checks, which is the evidence that the
recovery is idempotent rather than merely asserted: re-running it does not
change the ledger, the decisions, or the totals. The result of both runs is
recorded in `state/verification.json`.

## Boundary

This was an offline local reconciliation. The payment processor was not
contacted, no funds were released, no customer was notified, no report was
filed, and no audit evidence was deleted. The suspected upstream
duplicate-submission bug behind `req-02` is reported here for the auditor and is
not fixed by this recovery.
