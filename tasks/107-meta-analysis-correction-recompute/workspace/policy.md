# Quantitative synthesis correction policy

`protocol.json` controls population, outcome, timepoint, effect measure, model,
and claim thresholds. Accepted corrections supersede only the extraction named
by their scope; an unrelated correction does not authorize changing another
outcome. Retain the stale analysis as provenance and never count a superseded,
duplicate, wrong-timepoint, wrong-outcome, or wrong-population record as an
independent study.

Create `analysis_manifest.json` with `analysis_id`, `protocol_version`,
`included_records`, `excluded_records`, and `correction_chain`. Each included
row has `study_id`, `record_id`, and a non-empty `evidence` array. Each excluded
row has `record_id`, `reason`, and `evidence`. The correction chain has
`correction_id`, `superseded_record_id`, `replacement_record_id`, and
`evidence`. Evidence values use `basename#identifier`; generated outputs,
absolute paths, parent paths, URLs, and hidden files are invalid evidence.

`analysisctl.py build --manifest analysis_manifest.json` computes the protocol
model, a leave-one-out sensitivity analysis, and a forest plot from the selected
protected rows. It writes `meta_analysis.json`, `sensitivity.csv`,
`forest_plot.svg`, and replaces the interrupted `.analysis_build_state.json`.
Do not hand-edit generated artifacts.

Create `claim_updates.json` with one keyed row per claim. Each row has
`claim_id`, `prior_status`, `new_status`, `action`, and `evidence`. Use
`revise` only when the recomputed statistic changes the claim; preserve an
out-of-scope claim as `unchanged` without inventing an analysis. Derive the
status labels from the generated fields rather than paraphrasing them:

- `CLAIM-PRIMARY.new_status` equals
  `meta_analysis.json#pooled_random_effects.conclusion` and its evidence must
  include both `publication_claims.json#CLAIM-PRIMARY` and
  `meta_analysis.json#pooled_random_effects`.
- `CLAIM-HETEROGENEITY.new_status` equals
  `meta_analysis.json#heterogeneity.band` and its evidence must include both
  `publication_claims.json#CLAIM-HETEROGENEITY` and
  `meta_analysis.json#heterogeneity`.
- `CLAIM-SAFETY` keeps its published `prior_status`, uses `unchanged`, and cites
  `publication_claims.json#CLAIM-SAFETY` because no safety outcome was analyzed.

For each row, `action` is `revise` exactly when `new_status` differs from
`prior_status`. Generated analysis references are valid here even though they
are not valid as protected-source evidence in `analysis_manifest.json`.

`update_handoff.md` must explain the authority chain, selected/excluded record
families, old-versus-new pooled result and heterogeneity, correction-specific
sensitivity, all claim actions, forest-plot regeneration, byte-bound local
stage, and the offline/no-publication boundary. Local staging is review
evidence, not external publication or approval.
