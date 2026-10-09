# Clinical-trial results QC reconciliation handoff

The synthetic `NCT-SYN-21021` correction packet is staged only for responsible-party review. It was not submitted or posted, caused no registry or manuscript change, made no misconduct finding, and involved no external communication or external action.

## Authority and outcome history

The primary-completion date is 2025-06-30 and unblinding occurred 2025-07-10. `REG-V2`, posted 2025-05-15, is the last posted registry protocol version before primary completion. It identifies symptom-score change at Day 28 as primary and Day 56 as secondary. Signed pre-unblinding `SAP-V2` corroborates Day 28 as the primary modified-ITT analysis and says a reported Day-56 analysis is post hoc. `REG-V3` was posted 2025-08-20, after both cutoffs; it describes the current page but cannot retroactively establish Day 56 as pre-specified.

Accordingly, `OUT-28` is corrected from secondary to `primary_prespecified`, and `OUT-56` from primary to `additional_post_hoc`. This is a temporal classification based on the documents, not an inference about intent. The manuscript proof must replace “prespecified primary Day 56” with Day 28 primary and Day 56 post hoc before publication.

## Arm, population, and safety corrections

The stable mapping in `REG-V2`, `SAP-V2`, and `CSR-T14` is arm A = LX-21 and arm B = Placebo. The submitted labels were swapped while the numeric values followed the stable arm IDs. The corrected Day-28 results therefore remain -12.4 for LX-21/A and -5.1 for Placebo/B, each with 55 modified-ITT participants with observed Day-28 data. Day-56 remains -10.8 for LX-21/A with 52 and -4.8 for Placebo/B with 51, explicitly post hoc.

Participant flow is 120 randomized (60 per arm), 116 started treatment (58 per arm), and 112 completed Day 28 (56 per arm). Completion is not the primary analysis population: `CSR-14.2.1` supports 55 analyzed per arm, 110 total. Safety uses the treated population, 58 per arm, not randomized 60 per arm. Serious adverse-event participant counts remain 3 for LX-21/A and 1 for Placebo/B.

## Disclosure state and next steps

`SUB-QC-4` records results first submitted on 2026-08-10, with no results-first-posted date and state `under_qc_not_posted`. The results are not posted. The manuscript claim that results were posted on that date must say they were submitted and remain under QC; it must not imply public results disclosure is complete.

The seven-row discrepancy ledger covers both outcome classifications, the arm-map correction, Day-28 analysis denominator, safety denominator, and two manuscript statements. The source graph binds eight dated/typed authority nodes to immutable file hashes. The corrected payload, ledger, graph, input digests and staged state are bound into the controller receipt. Two replays completed; the second left state and receipt byte-stable with `replay_verified=true`.

The responsible party should verify the corrected payload against the source documents, respond to the pending QC comments, obtain manuscript-author confirmation, and only then use separately authorized registry and publication workflows. Until then, continue monitoring the QC cycle and public posted-date field. Nothing in this reconciliation establishes noncompliance or research misconduct, and this offline task grants no authority to submit, post, edit, notify, email, or otherwise communicate externally.
