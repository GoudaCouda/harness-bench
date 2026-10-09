# Reconcile a clinical-trial results QC correction packet

You are a research-compliance analyst reviewing an offline synthetic registry correction case. The record includes posted protocol versions, a pre-unblinding SAP, a results submission still under QC, CSR source tables, QC comments, and a manuscript proof. Determine what was pre-specified at primary completion, correct results and population data, and stage a responsible-party review packet. Do not submit, post, contact anyone, or allege misconduct.

Work only in `$WORKSPACE`; do not use the network. Treat `evidence/`, `policy/`, `trial_lib.py`, and `trialctl.py` as immutable. Modify `state/correction_case.json` only through the controller.

Start with `python3 trialctl.py --help`, then use `status`, `versions`, `submission`, and targeted `source --id <source-id>` inspection. Respect posted version history and dates: a later current record cannot silently redefine what was pre-specified before primary completion. Keep submitted-under-QC distinct from publicly posted.

Create the following controller-schema documents. Arrays described as keyed
must contain unique IDs; their order is irrelevant.

- `work/source_graph.json` has `trial_id`, `primary_completion_date`,
  `unblinding_date`, and a `nodes` array. Each node has `source_id`, `kind`,
  `source_date`, `authority`, `relationship`, and the SHA-256 of its containing
  evidence file. Use `null` for `source_date` when the visible source has no
  date. The controlled `kind` values are `registry_protocol_version`,
  `statistical_analysis_plan`, `results_submission`,
  `clinical_study_report_tables`, `registry_qc_comments`, and
  `manuscript_proof`. Use the controlled authority vocabulary
  `superseded_historical`, `controlling_prespecification`,
  `current_but_not_prespecification`, `pre_unblinding_corroboration`,
  `candidate_under_qc`, `result_and_population_source`, `correction_trigger`,
  and `downstream_candidate`. Relationship values are concise snake-case
  statements of the dated role; they must distinguish submitted from posted.
- `work/discrepancy_ledger.json` has `trial_id` and a `findings` array with
  exactly one row for each of these seven correction targets:
  `OUT-28.classification`, `OUT-56.classification`, `arm_labels`,
  `OUT-28.analysis_denominator`, `serious_adverse_events.denominator`,
  `prespecified_primary_claim`, and `registry_posting_claim`. Each row has a
  unique `finding_id`, plus `artifact`, `field`, `observed`, `corrected`,
  `authority_ids`, `classification`, and a meaningful `action`. Use
  `results_submission` or `manuscript_proof` for `artifact`, and use
  `registry_correction` or `manuscript_correction` for `classification`.
  Preserve the source value's native JSON shape in `observed` and `corrected`:
  arm labels and per-arm denominators are objects keyed by arm ID, while result
  classifications use the controlled result values below. The two manuscript
  claim rows may use concise evidence-grounded prose rather than a fixed
  sentence.
- `work/corrected_results.json` has `trial_id`; a `registry_status` object with
  `results_first_submitted_date`, `results_first_posted_date`, and `state`; an
  `arms` array keyed by `arm_id`; `participant_flow` preserving the CSR's
  `randomized`, `started`, and `completed_day28` keys; and an `outcomes` array
  keyed by `outcome_id`. Each outcome includes `classification`, `measure`,
  `time_frame`, `population`, and `groups` keyed by `arm_id`, with label, `n`,
  and value. Use `primary_prespecified` and `additional_post_hoc` as the two
  result-classification values. `serious_adverse_events` contains `population`,
  `denominator`, and `participants_with_event`.

Run `validate`, then `stage`, then `replay` twice with all three files. The controller creates the receipt. Finish `work/compliance_handoff.md` with the authority cutoff, all corrections, submitted-versus-posted state, QC next steps, replay evidence, and cautious interpretation. State that the synthetic packet is staged only for responsible-party review, was not submitted or posted, caused no registry/manuscript change, made no misconduct finding, and involved no external communication.
