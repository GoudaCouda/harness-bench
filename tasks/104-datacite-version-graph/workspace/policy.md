# Repository versioning policy

Concept DOI: `10.data/cohort`.

Public versions are findable version records only. Draft records are excluded from the public relation graph and must be reported in `excluded_records`.

Major update rule: adding a new cohort is a major version. If a provider attempts to reuse an existing findable version DOI for a major update, assign the next version-specific DOI instead. For this graph, the next public version after `10.data/cohort.v3` is `10.data/cohort.v4`.

Relation topology rule: the concept points `HasVersion` to every public version, and every public version points `IsVersionOf` to the concept. Adjacent public versions use `IsNewVersionOf` from newer to older and `IsPreviousVersionOf` from older to newer. No self-edge, cycle, draft public edge, or relation to a non-public draft DOI may remain in the final ledger.

Dirty relation rule: wrong-direction concept/version edges must be corrected rather than preserved as alternate facts. Exact duplicate canonical edges are represented once. Invalid self-edges, cycles, and draft public edges are removed from the final ledger and reported in validation.

Citation policy: exact duplicate citation rows collapse to one final `Cites` edge. A citation dated before the 2026 major update remains on the DOI it cited. A citation to the reused candidate DOI after the 2026 major update is retargeted to the new version only when its local citation note explicitly describes the 2026 new cohort. A citation to the concept DOI remains a concept citation and must not be migrated to the latest version.

Checkpoint rule: `prior_graph_state.json` is the accepted state before the 2026 update. Reconcile it with the final graph; do not ignore it and do not copy it blindly. Report `prior_checkpoint_id` and `state_changes` in `graph_validation.json`. Use `from_doi|relation|to_doi` for edge identifiers in state-change arrays.

Evidence references must use local basenames plus existing record ids, such as `records.json#10.data/cohort.v3`, `change.json#CH-2026-04`, `relations.json#R4`, `citations.json#C2`, or `prior_graph_state.json#datacite-v3-checkpoint`. External URLs, host paths, invented record ids, and unverifiable notes are invalid.
