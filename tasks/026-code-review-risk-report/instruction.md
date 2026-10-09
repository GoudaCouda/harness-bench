Review the proposed bulk-export change using `$WORKSPACE/review/diff.patch`.
Reconcile it with `$WORKSPACE/review/export_contract.md` and
`$WORKSPACE/review/schema.sql`; findings that ignore those contracts are not
actionable.

Create `$WORKSPACE/review_findings.json` with this shape:

{
  "findings": [
    {
      "id": "short-stable-id",
      "severity": "critical|high|medium|low",
      "file": "relative/path",
      "line_hint": "string or number",
      "risk": "what can go wrong",
      "recommendation": "what should change",
      "test": "specific regression or security test to add",
      "evidence": "quote or concise reference"
    }
  ],
  "summary": "brief review summary"
}

Do not modify fixture files. Focus on merge-blocking correctness, security,
concurrency, and state-transition risks rather than style comments. Report only
evidence-supported regressions introduced by the diff; do not flag the added
`requested_by` audit field, parameterized SQL, or ordinary metadata as risks.
Use the severity policy in `export_contract.md`. Each proposed test must name a
trigger and an observable safe outcome, not merely say "add a test".
