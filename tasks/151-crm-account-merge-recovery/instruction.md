# Recover the Northwind CRM account merge

A synthetic CRM merge crashed after duplicate detection but before dependent
records moved. Work only in `$WORKSPACE` and do not contact customers.

1. Read `merge_policy.md`; run `python3 crmctl.py candidates` and use the
   read-only `query` command to inspect accounts, contacts, opportunities,
   activities, consent, and the merge log.
2. Create `merge_plan.json` with `primary_account`, `duplicate_account`,
   `preserve_accounts`, field decisions, consent resolution, and dependent
   record classes to move.
3. Run `python3 crmctl.py preview merge_plan.json`; repair any identity,
   near-match, consent, or completeness failure.
4. Run `python3 crmctl.py merge merge_plan.json`, then `python3 crmctl.py verify`.
   The verifier writes `merge_receipt.json`.
5. Merge the identical plan again to prove a single idempotent transaction.
6. Write `crm_handoff.md` covering survivor choice, moved records, opt-out
   precedence, the preserved near-match, verification, and offline scope.

Do not directly update SQLite, edit the schema/controller, delete history, or
claim any live CRM change, email, or sales action.
