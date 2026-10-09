# ECN-442 configuration-recovery handoff

The approved ECN-442 replaces CONN-CU-4P with CONN-NI-4P at quantity two in
ACTUATOR-MODULE C→D. The released where-used traversal propagated that child
revision through PUMP-100 12→13 and SKID-900 5→6, and independently through
FIELD-KIT 2→3. All four new baselines remain pending configuration review; no
engineering release was executed. CONN-NI-4P-A is the only approved substitute
carried onto revision D. The obsolete copper substitute was not copied.

Serial effectivity begins at SN-0500. WO-900 / SN-0498 is already assembled and
remains the immutable as-built revision 5. WO-901 / SN-0501 had the old connector
issued, so it is held for controlled re-kit on baseline 6 without pretending the
physical kit was returned. WO-902 / SN-0502 had no material issued and adopts
baseline 6. Lot effectivity begins at LOT-2026-09: WO-903 remains on the
pre-effectivity revision 2, WO-904 may keep issued CONN-NI-4P-A because it is an
approved new-part substitute while adopting revision 3, and unissued WO-905 also
adopts revision 3.

The controller restored both effects of the interrupted
ECNREC-20260818-442-PARTIAL run: its wrong
WO-901 planning mutation and its lone ACTUATOR-MODULE D baseline insert. It then
committed one source-checkpoint-bound SQLite recovery, verified the exact BOM,
work-order and journal state, and staged only an internal
pending_configuration_review receipt. Semantic replay treated reordered sets and
records as the same plan and was database-byte-stable and receipt-byte-stable.

No shop-floor instruction or physical re-kit occurred. No release, no supplier
order, no inventory issue or return, and no other external action occurred.
Production and configuration
control must review the staged effectivity decisions before any execution.
