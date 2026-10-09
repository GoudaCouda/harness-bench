# July purchase-card close recovery handoff

The local close `PCLOSE-2026-07-CARDOPS` is committed and staged pending ERP posting approval. No external posting, payment, cardholder message, procurement approval, or notification occurred.

## Evidence and adjudication

PC-201 clears because its PDF receipt was parsed, its manifest SHA-256 matched, and ACC-8201 accepted the charge. PC-202 remains a full missing-receipt hold because no receipt artifact exists. PC-203 and PC-204 each have valid HTML/JSON receipt evidence and acceptance, but their same-cardholder, same-merchant, same-day connected component totals 520.00 USD while each charge is below the 500.00 threshold; both remain separately held for suspected split-purchase review. They were not collapsed into one ledger row.

PC-205 has a valid HTML receipt and acceptance for its 100.00 USD subtotal. Its 10.00 USD sales tax is separately retained as non-reimbursable, so only the subtotal clears. PC-206 is a -50.00 USD refund linked to immutable prior-month ERP posting PC-099; it is not netted against PC-202 or the split exceptions. PC-207 has a parsed, hash-matched PDF receipt but no acceptance row, so the entire charge remains held for department acceptance.

## Recovery and verification

The interrupted journal had only prepared PC-205; it did not prove an ERP posting. Recovery consumed that prepared action and committed one seven-action local close transaction. The issuer, ERP, acceptance, policy, manifest, and PDF/HTML/JSON receipts stayed immutable. Controller verification reconciled every disposition, cleared and exception cents, the split edge, refund link, journal, and source checkpoint.

Re-running apply with the same business close identity and semantically equivalent source-bound plan returned an idempotent replay. The staged receipt is digest-bound to the logical close, plan, verification, and source checkpoint; replay left the SQLite close state and staged receipt byte-for-byte unchanged. External ERP posting still requires independent approval.
