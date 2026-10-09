# Graph audit

Pagination coverage: the export declared pages 1, 2, 3, and 4 in `pages_index.json`. I consumed `works_page1.json`, `works_page2.json`, and `works_page4.json`, and recorded page 3 in `pages_declared_not_found` because `works_page3.json` is absent. I also checked declared row counts. Page 4 declared 7 rows but only 6 were observed, so `coverage.json` records `page:4:expected:7:observed:6`. No records were invented for the missing page or the row-count mismatch.

Duplicate resolution used DOI normalization and the explicit version-alias rule. `W1-DUP` resolves to retained canonical work `W1` through normalized DOI `10.oa/alpha`. `W4-ALIAS` resolves to retained canonical work `W4` because `10.oa/delta-v2` shares the normalized title, ordered author id `A6`, and publication year with `W4`. `W9` also has `10.oa/delta-v2`, but it is a non-duplicate version alias because the title and publication year differ from `W4`; it remains its own canonical work with key `10.oa/delta-v2`.

Same-name author separation used stable author ids only. `A1`, `A2`, and orphan author `A4` are all named Alex Kim, but only `A1` and `A2` appear in observed work rows and they remain separate. `A3`, `A4`, and `A9` have unknown current affiliations. The stale affiliation note on `A9` was not promoted into `institution_ids`.

The suspected DOI gap was quarantined. `W3` has no verified DOI and only a local note suggesting `10.oa/gamma`, so its `canonical_key` remains empty and its status is `quarantined_suspected_match`.

Correction-event handling was applied before generic conflict quarantine. `CE-1` in `correction_events.json` names `W8` as superseded and `W8-CORR` as corrected, with authoritative relation `contradicts`. Both observed rows are retained under canonical work `W8-CORR`; `W8` is marked `superseded_by_correction`, and `coverage.json` records `W8->W8-CORR`.

The unresolved relation conflict was quarantined. `W5` and `W5-CONFLICT` share canonical key `10.oa/epsilon` but disagree between `contradicts` and `supports`; no correction event names that pair, so both observed rows are retained under canonical work `W5` with `claim_relation` set to `conflict` and status `quarantined_conflict`.

Review-required propagation was then applied across graph references. `W7` references quarantined work `W5`, so `W7` is marked `review_required` even though its own row is otherwise well formed. `W10` references `W7`, so the review state propagates transitively and `W10` is also marked `review_required`. `coverage.json` records the direct propagation edges `W5->W7` and `W7->W10`.

Checkpoint reconciliation used `prior_graph_state.json#checkpoint-p2-102` as the accepted state after pages 1 and 2. The resume consumed new page 4 while preserving still-valid prior decisions. `W8` was released from the prior review hold because `CE-1` resolved it, so `state_changes.released_from_review` lists `W8` and `changed_statuses` records `W8:review_required->superseded_by_correction`. `W5` changed from prior `canonical` to `quarantined_conflict` after page 4 introduced `W5-CONFLICT`, so `changed_statuses` also records `W5:canonical->quarantined_conflict`. `state_changes.added_review_required` lists `W7` and `W10`; `W3` remains an unchanged quarantine, `W1-DUP` remains an unchanged duplicate, and `W4-ALIAS` is a new duplicate.

Dangling references were preserved. `W6` cites absent work `W-MISSING`, so the edge remains in `referenced_work_ids` and `coverage.json` reports `W6->W-MISSING`.

Verification: `evidence_graph.csv` contains exactly 14 observed work rows, coverage sets derive from the final ledger, relation counts exclude duplicate, quarantined, review_required, and superseded rows, and every evidence reference uses a local file and record id. This was an offline repair handoff only; no external OpenAlex API call, production write, deletion, publication, or account action was executed.
