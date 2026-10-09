# Adjudicate SBOM and VEX evidence for a release gate

You are the software-supply-chain analyst for the pending Meridian API release in this offline workspace. Security intake received an exact release SBOM, supplier VEX statements, a frozen vulnerability feed, a frozen KEV snapshot, a trust store, and the organization's release policy. Some supplier assertions are inapplicable or untrustworthy. Determine the effective risk for this exact release and apply the policy-controlled gate safely.

Work only inside `$WORKSPACE`. Do not use the network. Treat `evidence/`, `policy/`, and the three `*ctl.py` controllers as immutable. The only existing file you may modify is `state/release_gate.json`.

Use the local tools rather than guessing:

- `python3 sbomctl.py inventory`
- `python3 sbomctl.py component --purl <purl>`
- `python3 sbomctl.py depends --purl <purl>`
- `python3 vexctl.py verify`
- `python3 vexctl.py verify --statement <statement-id>`
- `python3 releasectl.py evaluate --ledger work/decision_ledger.json --rejections work/rejected_statements.json`
- `python3 releasectl.py apply --ledger work/decision_ledger.json --rejections work/rejected_statements.json`
- `python3 releasectl.py replay --ledger work/decision_ledger.json --rejections work/rejected_statements.json`

Create these deliverables:

- `work/decision_ledger.json`
- `work/rejected_statements.json`
- `work/evaluation_receipt.json` (created by `releasectl apply`, then closed by `releasectl replay`)
- the policy-correct final `state/release_gate.json`
- `work/handoff.md`

`decision_ledger.json` must contain `release_id`, `policy_version`, a keyed `decisions` row for every vulnerability that actually applies to a component in the release, and an `out_of_scope` row for every feed vulnerability whose component is absent. Each decision row must contain `component_purl`, `vulnerability_id`, `scope`, `vex_statement_id` (or `null`), `vex_accepted`, `rejection_reasons`, `effective_status`, `kev`, `priority`, and `disposition`.

`rejected_statements.json` must contain `release_id` and one row per rejected VEX statement with its complete set of rejection reasons. Preserve even plausible supplier assertions when they fail identity, integrity, or policy checks; do not rewrite source evidence to make them valid.

Apply these boundaries:

- Match exact component identity and installed version before consuming a VEX status.
- Verify signer, payload digest, freshness, and any status-specific requirements.
- A KEV entry raises priority only after the vulnerable component and version are established as present.
- `under_investigation` remains unresolved under this policy.
- Do not create an exception, edit the policy, clear the gate manually, deploy anything, or claim an external action occurred.
- Run `releasectl replay` after `apply`, then run it once more and verify that the receipt and gate bytes do not change.

In `work/handoff.md`, summarize the accepted and rejected supplier evidence, the true blocker(s), the absent-component KEV treatment, the final gate state, the replay result, and the next remediation or investigation actions. State explicitly that this was an offline gate adjudication and no deployment or external communication occurred.
