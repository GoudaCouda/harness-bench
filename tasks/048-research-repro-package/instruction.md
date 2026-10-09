# Audit the deposited analysis package by actually exercising it

You are the reproducibility analyst for a manuscript release. The deposit in
the workspace contains the paper claims, README, analysis code, raw trial data,
shipped result table, deposit manifest, and an author execution log.

Inspect the package and run its documented commands locally. Use a temporary
output path so the deposited evidence remains unchanged. Check the script's
available flags rather than assuming every README command is implemented, and
reconcile observed rerun values with both the shipped table and the snapshot
provenance in the manifest/log.

Create:

- `reproducibility_report.md` with exactly one section headed
  `### Claim CLAIM-X` for each of CLAIM-1 through CLAIM-4. For each claim, state
  the claimed result, relevant artifacts, command or inspection performed,
  observed result, evidence disagreement, and support/reproducibility status.
  End with a package-level conclusion that separates “a command ran” from “the
  published result was reproduced.”
- `missing_steps.csv` with header `item,type,impact,recommended_fix`, one row per
  independently evidenced blocker or provenance disagreement. Use concrete
  paths/commands and actionable fixes; keep the ledger closed rather than
  listing symptoms twice.

Do not repair the deposit, overwrite `results.csv`, fabricate a run, assert
successful reproduction merely because a precomputed value exists, modify any
source file, or use the network.
