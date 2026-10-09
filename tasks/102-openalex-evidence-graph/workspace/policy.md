Use canonical IDs only. Display names are never identity keys. Missing affiliation remains `unknown`, including when an author record contains a stale affiliation note.

Pagination rule: consume every available file declared in `pages_index.json`. If a declared page file is absent, do not invent records from it; report the missing page number in `pages_declared_not_found`. If `pages_index.json` declares `expected_rows`, compare it with the observed row count for every available page and report mismatches in `page_row_count_mismatches` as `page:<page>:expected:<n>:observed:<n>`.

DOI rule: normalize DOI values by trimming whitespace, removing `doi:`, `https://doi.org/`, `http://doi.org/`, `https://dx.doi.org/`, and `http://dx.doi.org/`, and case-folding the remaining DOI.

Duplicate rule: works with the same normalized DOI are duplicates unless a later rule creates a correction relationship. A DOI ending in `-v2` is a version alias of the same DOI without `-v2` only when normalized title, ordered author ids, and publication year also match. If any of those fields differ, keep the `-v2` DOI as its own canonical key and report that work id in `non_duplicate_version_aliases`. Keep one retained canonical work id and mark overlapping observed rows `duplicate`.

Missing DOI rule: if a work has no DOI but contains a local `suspected_doi` note, keep `canonical_key` empty and mark the row `quarantined_suspected_match`; do not promote the suspected DOI to a fact.

Correction rule: `correction_events.json` is authoritative only for the canonical keys and work ids it names. When a correction event names a `superseded_work_id`, `corrected_work_id`, and `authoritative_relation`, retain both observed rows, set both rows to the authoritative final `claim_relation`, mark the superseded row `superseded_by_correction`, mark the corrected row `canonical`, and report `superseded_work_id->corrected_work_id` in `resolved_correction_works`. This is a resolved correction, not a quarantine conflict.

Conflict rule: if the same canonical work appears with conflicting `claim_relation` values and no correction event or explicit rule resolves the conflict, mark all observed rows for that canonical work `quarantined_conflict` and set `claim_relation` to `conflict`.

Contagion rule: after duplicate, correction, suspected-DOI, and unresolved-conflict rules are applied, propagate dependency review through `referenced_work_ids`. If a retained canonical work references another observed work whose final status is `quarantined_suspected_match`, `quarantined_conflict`, or `review_required`, mark the referencing work `review_required` unless a correction event explicitly re-establishes the referenced work's authority. This propagation is transitive. Duplicate rows and `superseded_by_correction` rows are not propagation sources. Report direct propagation edges in `review_required_edges` as `source_work_id->referencing_work_id`.

Checkpoint rule: `prior_graph_state.json` is the previous accepted checkpoint after pages 1 and 2. Reconcile it with the current export; do not ignore it and do not copy it blindly. Report `prior_checkpoint_id`, `prior_processed_pages`, `new_pages_consumed`, and `state_changes` in `coverage.json`. `state_changes` must include these arrays: `released_from_review`, `added_review_required`, `newly_quarantined`, `unchanged_quarantined`, `new_duplicates`, `unchanged_duplicates`, and `changed_statuses`. Use `work_id:old_status->new_status` for `changed_statuses`.

Reference rule: preserve references to absent works. Do not delete dangling edges; report them in `dangling_references` as `source_work_id->missing_work_id`.

Relation count rule: `supporting_works` and `contradicting_works` count retained canonical work rows only. Exclude rows whose status is `duplicate`, `quarantined_suspected_match`, `quarantined_conflict`, `review_required`, or `superseded_by_correction`.

Evidence references must use local basenames plus existing record ids, such as `works_page1.json#W1`, `authors.json#A1`, `concepts.json#C1`, `correction_events.json#CE-1`, or `prior_graph_state.json#checkpoint-p2-102`. Extra local references are allowed only when directly relevant; invented record ids, external URLs, path-like references, or unverifiable notes are invalid.
