# Version decision

The 2026 change `CH-2026-04` is a major new cohort update, so the provider's attempted reuse of `10.data/cohort.v3` cannot stand. The final public new version is `10.data/cohort.v4`. The older findable versions `v1`, `v2`, and `v3` are retained, while draft record `10.data/cohort.v3-draft` is excluded from the public graph.

Relation direction repairs used `relations.json` and the prior checkpoint. `R3` was a wrong-direction concept/version relation, so the final ledger contains `10.data/cohort HasVersion 10.data/cohort.v2` and `10.data/cohort.v2 IsVersionOf 10.data/cohort`. Duplicate concept edge `R5` was deduplicated. Invalid `R9` was a self-edge and `R10` was a draft public edge; both were removed. The final version chain is v1 to v2 to v3 to v4 with reciprocal previous-version edges.

Citation policy was applied without migrating every citation to the latest version. Duplicate rows `C1` and `C1-DUP` collapse to one citation from `10.paper/alpha` to `10.data/cohort.v2`. `C2` is dated after the 2026 update and explicitly describes the new cohort, so it is retargeted from reused `10.data/cohort.v3` to `10.data/cohort.v4`. `C3` cites the concept landing page and remains a concept citation.

Checkpoint reconciliation used `prior_graph_state.json#datacite-v3-checkpoint`. The state_changes record added the v4 concept, version, and chain edges; corrected `R3`; removed `R9` and `R10`; retained the valid prior edges; retargeted `C2`; and left `C1` and `C3` as unchanged citation decisions.

Verification: SQLite `repository.db` passes integrity checking and contains exactly 17 canonical final edges plus seven stable `change_log` entries. `graph_validation.json` reports zero cycles and zero self_edges, old versions are retained, the draft DOI is excluded, and duplicate citations removed equals one. The controller's hash-bound local stage and replay both passed. This was an offline local repair only; no external DataCite API call, production write, DOI registration, deletion, or account action was executed.
