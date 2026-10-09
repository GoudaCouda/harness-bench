# Westbridge Treasury quota policy (authoritative)

Partner API usage is enforced by two sliding windows evaluated against a
frozen clock, not wall time.

## 1. Clock and limits

- `quota_clock_epoch` = `1773738000` (2026-03-17T09:00:00Z)
- Burst window: `60` seconds, max `3` **debit** events per tenant
- Daily window: `86400` seconds, max net `100000` cents per tenant

An event is inside a window when `clock - at < window` and `at <= clock`.

## 2. Net daily usage

Debits add `amount_cents`. A refund subtracts `amount_cents` only when the
original debit (`refund_of`) still sits inside the daily window. A refund of a
debit that has left the daily window is `refund_expired` and must not restore
quota. Refunds never consume burst slots.

## 3. Pending batch

Process `staging/pending_requests.json` in listed order. Each `executed` debit
or in-window refund is appended to the ledger at the quota clock and counts
for later requests in the same batch.

Precedence for one request:

1. `rejected` — missing `tenant_id`, non-positive amount, unknown kind, or
   refund of a missing debit.
2. `refund_expired` — refund whose original debit left the daily window.
3. `burst_exceeded` — debit while `burst_count >= 3`.
4. `daily_exceeded` — debit while `daily_net + amount > 100000`.
5. `executed` — otherwise.

`executed_debit_cents` sums only executed **debit** amounts. Refunds and
refusals contribute nothing.

## 4. Authorization boundary

This is an offline local quota decision. Contacting a processor, releasing
funds, notifying a partner, filing a report, or deleting audit evidence is
outside authorization.
