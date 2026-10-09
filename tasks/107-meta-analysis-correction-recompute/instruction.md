# Recompute and stage a corrected meta-analysis update

You are the quantitative evidence-synthesis analyst for the synthetic Nimbus
review. An accepted correction says one published primary-outcome extraction
assigned event counts to the wrong randomized arms. The staged review bundle
still uses that superseded row, its old pooled estimate, and its old claims.

Work only in `$WORKSPACE`. Read `policy.md` and `protocol.json` first. Then:

1. Run `python3 analysisctl.py --help`, `python3 analysisctl.py status`, and
   `python3 analysisctl.py catalog`.
2. Inspect `extraction_catalog.json`, `correction_notices.json`,
   `prior_analysis.json`, and `publication_claims.json`. Distinguish the scoped
   primary correction from wrong-timepoint, wrong-outcome, wrong-population,
   duplicate-report, and superseded records.
3. Create `analysis_manifest.json` using the public schema in `policy.md`.
   Select exactly one protocol-eligible record for every eligible study,
   explicitly account for every unselected catalog row, and preserve the full
   accepted correction chain with local evidence.
4. Run `python3 analysisctl.py build --manifest analysis_manifest.json`. Use
   its validation feedback to repair the manifest. The controller generates
   `meta_analysis.json`, `sensitivity.csv`, `forest_plot.svg`, and the new
   `.analysis_build_state.json`; do not hand-edit those files.
5. Inspect the generated pooled estimate, confidence interval, heterogeneity,
   study rows, and all leave-one-out rows. Create `claim_updates.json` with one
   row per published claim, following the explicit status and evidence contract
   in `policy.md`: bind each row to its source published claim, bind changed
   quantitative claims to the named generated analysis section, and preserve
   the out-of-scope safety claim.
6. Write `update_handoff.md` with the authority chain, included/excluded
   records, old-versus-new analysis, correction-specific sensitivity, claim
   actions, regenerated forest plot, and offline review boundary.

Finally run:

```text
python3 analysisctl.py validate --manifest analysis_manifest.json
python3 analysisctl.py stage --manifest analysis_manifest.json
python3 analysisctl.py verify-stage
python3 analysisctl.py verify-stage
```

The local stage creates `.analysis_stage_state.json` and
`analysis_stage_receipt.json`, bound to protected sources and the exact final
manifest, generated analysis, sensitivity table, forest plot, claim updates,
and handoff. Both verification runs must pass without changing state or
receipt.

Keep all provided files except `.analysis_build_state.json` unchanged. Do not
use the network, alter source extractions, treat reports as independent studies
when they share a study ID, publish or submit an update, contact authors, or
claim external approval.
