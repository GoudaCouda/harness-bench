# INC-2471: collection routing eligibility regression

The nightly dry-run on 2026-07-05 produced two policy mismatches. `INV-401`
belongs to a suspended account and must not enter the collection queue.
`INV-402` belongs to a delinquent account with a positive balance and must be
eligible. No live collection action was run.

Policy invariants:

- only `active` and `delinquent` account states can be eligible;
- trial accounts, non-positive balances, unsupported regions, `suspended`, and
  `closed` accounts are never eligible;
- US, CA, and GB are supported regions;
- eligible results must retain the current `eligible_balance` audit reason;
- `collection_decision(invoice)` and its `(boolean, reason)` return contract are
  public API.

The incident began after the known-good commit whose subject is
`enable GB collection routing`. Find the first bad descendant from repository
evidence. Repair and verify the offline checkout only.
