# Smart-meter correction recovery handoff

## Authority and interval resolution

The raw interval feed arrived out of order and retransmitted `EVT-DST-02`.
Event identity was deduplicated without treating local clock time as identity.
For `MTR-DST-17`, both 01:30 readings were retained: one carries UTC offset
-04:00 and the other -05:00, so they are distinct fall-back intervals. Their UTC
starts and the other actual intervals support 4.500 kWh import. `MTR-ROL-42`
crossed a 10000 register modulus from 9998 to 4; the authoritative consumption
is therefore 6.000 kWh, not a negative delta or 9994 kWh.

`MTR-SOL-09` was resolved from four actual bidirectional intervals. Import totals
7.500 kWh and export totals 3.000 kWh; export was not netted away before the
billing comparison. The primary batch for `MTR-FBK-88` is truncated and was
rejected. Its local fallback record was accepted only after both its canonical
payload checksum and the signature bound to `meter-batch-key-2026` verified,
yielding 12.400 kWh import and zero export.

## Hold and local recovery

`MTR-HLD-55` remains `hold_insufficient_evidence`: only one actual interval and
one estimated interval are present, below the required coverage. No estimated
quantity was promoted to an actual correction. The other four projections are
`correction_pending_review`; these are proposals for billing review, not issued
bills or balance postings.

The prior `MBR-INTERRUPTED-20261116` partial reversal was restored from its
before-image inside the same SQLite transaction that committed this recovery.
Verification confirmed exact bill projections, one revision advance, the
restored journal, one current journal row per meter, unchanged account/meter
identity, and every invoice still `estimated_unissued`. The recovery was staged
locally, and semantic replay was a database- and receipt-byte-stable no-op.

No bill or refund was issued, no payment was taken, no meter command was sent,
and no customer was contacted. The receipt is pending metering and billing
review only; it does not authorize any external action.
