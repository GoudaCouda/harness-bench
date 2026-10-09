# Recover an Interrupted Purchase-Card Month Close

The July 2026 purchase-card close stopped after preparing one transaction. Recover it locally without changing the issuer feed, the posted ERP ledger, approval evidence, or receipt artifacts. The batch contains a missing receipt, a suspected split-purchase pair, non-reimbursable sales tax, a refund that belongs to a prior period, and a transaction without acceptance.

Work only inside `$WORKSPACE`; no bank, ERP, procurement, cardholder, or payment service is reachable. Start with:

```bash
python3 pcardctl.py --help
python3 pcardctl.py inspect
```

Use `pcardctl.py query` to inspect issuer transactions, ERP postings, acceptance decisions, parsed receipt contents and hashes, the split graph, and the interrupted journal. Do not edit the controller or any evidence source.

Create `reconciliation_plan.json` with:

- `schema_version`: `1`
- `close_id` and `period` from the close context
- `source_checkpoint`: the controller-reported checkpoint over the immutable business sources
- `actions`: exactly one object per current-period issuer transaction; each object has `transaction_id`, a policy disposition, and a non-empty `evidence_refs` list
- `external_actions_executed`: `false`

Use only dispositions published in `pcard_policy.md`. Evidence references must be local locators such as `issuer.db#transactions/PC-201` or `receipts/PC-201.pdf#sha256=...`; do not cite generated outputs, hidden files, URLs, absolute paths, or parent paths.

Complete the executable workflow:

1. `python3 pcardctl.py preview reconciliation_plan.json`
2. `python3 pcardctl.py apply reconciliation_plan.json`
3. run the same `apply` again and confirm an idempotent replay
4. `python3 pcardctl.py verify`
5. write `close_handoff.md`
6. `python3 pcardctl.py stage reconciliation_plan.json`
7. `python3 pcardctl.py replay reconciliation_plan.json` and confirm no close state or staged receipt changes

Required final artifacts:

- modified `pcard_close_state.db`
- `reconciliation_plan.json`
- `pcard_verification.json`
- `pcard_stage_receipt.json`
- `close_handoff.md`

The handoff must explain every transaction, the receipt media/hash checks, the connected split-purchase graph, tax treatment, prior-month refund link, missing acceptance, interrupted journal recovery, source-bound replay behavior, verification, and that no external posting, payment, message, or approval occurred.

Do not create a replacement database, modify already-posted ERP rows, or forge controller receipts. Keep `issuer.db`, `erp.db`, `acceptance.db`, `close_context.json`, `pcard_policy.md`, `receipt_manifest.json`, everything under `receipts/`, `pcardctl.py`, and `SOURCE_HASHES.json` byte-for-byte unchanged.
