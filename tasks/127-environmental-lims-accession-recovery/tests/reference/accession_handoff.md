# Environmental LIMS accession recovery handoff

## Evidence authority and identity

The protected COC-BATCH-20260819-AM stream was processed offline. Every unique event signature validated against the supplied trust material. File order was not treated as chronology, and the second byte-identical EVT-RECV-042 occurrence was collapsed without hiding a conflict. Field labels were joined to protected sample IDs, then the highest continuous authorized alias version controlled. In particular SMP-26-043 moved from the erroneous version-1 `LIMS-S-20260819-034` alias to version 2 `LIMS-S-20260819-043`.

EVT-COC-043 was recorded with a pending field signature. EVT-LATE-SIG-043 arrived 1 hour 15 minutes later, its target checksum binds the signed custody event, and it is inside the two-hour policy grace period. The resulting custody status is `late_signature_valid`, not an inferred or waived signature.

## Sample dispositions

- SMP-26-041 / RIV-A-0819 is `accepted_pending_analysis`: 4.4 C is within the 2–6 C range, nitric-acid preservation and the intact HDPE bottle comply, custody is complete, and the metals holding time is open.
- SMP-26-042 / RIV-B-0819 is `quarantine_temperature_excursion`: the sterile container, no-preservative rule, custody, and six-hour holding time comply, but 8.1 C exceeds the 2–6 C receipt range. It remains in controlled storage for QA review.
- SMP-26-043 / SOIL-C-0819 is `accepted_pending_analysis`: 5.1 C, methanol preservation, intact glass vial, 48-hour holding time, corrected alias, and the later checksum-bound custody signature comply.
- SMP-26-044 / RIV-D-0819 is `rejected_container_integrity`: temperature, sulfuric-acid preservation, custody, and holding time comply, but the amber-glass container was observed cracked. It is isolated only for QA disposition; it was not disposed.

## Recovery and closeout

The interrupted LIMS-ACC-INTERRUPTED-20260818 journal entry was restored before the four decisions were committed atomically under stable recovery ID LIMS-ACC-20260819-07 and its protected source checkpoint. Verification closed exact sample rows, protected project/client identity, journal restoration, a single current transaction, and local-only safety flags. The local receipt was staged pending accession QA review. Semantic replay with the same plan was database- and receipt-byte-stable.

No environmental analysis was started, no result was released, no sample was disposed, and no client notification or other external action occurred. `accepted_pending_analysis` is a local queue state only and does not authorize testing.
