# CODEOWNER review handoff

The last matching ownership rule wins. That makes the generated client a
platform path, the payment runbook a payments-docs path, the secret config a
security path, and the workflow a CI path; the remaining paths resolve to the
owners recorded in the ledger.

Platform reviewer platb approved only the generated path at old SHA `old100`,
so that path still lacks a current approval even though platd's current scoped
approval satisfies `src/shared/logging.py`. The release review from rela was
dismissed, leaving the release script missing approval. SRE reviewer srec has
current-SHA changes requested on the infrastructure path, which blocks the PR.
Payments, payments-docs, security, platform-shared, and CI coverage is current.

The next handoff needs a current platform approval for the generated client, a
fresh release approval, and resolution plus re-review of the SRE block.
Verification reconciled eight changed paths to five satisfied, two missing,
and one blocked row. No review request, merge, or external action was executed.
