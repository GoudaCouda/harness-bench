# General task suite

The benchmark contains 274 general tasks in `tasks/` and 26 multimodal tasks in `multimodal-tasks/`, 300 in total. All use the current taxonomy described in [the task taxonomy](TASK_TAXONOMY_V3.md). `standard274` is the runner manifest identifier for the general subset.

## Scoring policy

Tasks use domain-specific structured cases rather than one fixed weight template.
High-value business decisions and durable state carry most of the score; closure
and handoff cannot rescue an incorrect core. Zero-weight gates are limited to
genuine red lines such as protected-source tampering, unsafe filesystem state,
secret disclosure, or a claimed or executed irreversible external action.

A 7200-second deadline is a measurement budget, not a success waiver. Timeout
and every other model or protocol terminal outcome remain in the denominator.
Bounded semantic judging is permitted only where the task explicitly declares
it, and must not override deterministic evidence.

## Acceptance

Before release, run task layout and design validation, Oracle four-state quality,
discrimination, public leakage, deadline, generated catalog, content lock,
isolation, unit test, lint, and production Docker-reference checks. Then run a
fresh temperature-1 model/harness evaluation for all 274 tasks and audit complete
trajectories, token accounting, and score attribution.

## Task identifiers

Task IDs are stable identifiers, not descriptions. Results, the content lock,
source aliases, and regression tests all key on them, so a package keeps its ID
when its content is redesigned. Use `title` in `catalog/task_catalog.csv` or
`task.yaml` to describe a task. The IDs below no longer describe their tasks:

| Task ID | Current task |
|---|---|
| `001-meeting-summary` | Recover a crashed DNSSEC rollover staging run |
| `004-office-docs` | Prepare a quarter-close regional sales memo and reconciled upload |
| `008-db-doc-consistency` | Repair a production runbook before an on-call handoff |
| `032-anomalous-transaction-detect` | Recover an interrupted supplier-bank release gate |
| `040-service-dependency-triage` | Repair checkout authentication after an issuer migration |
| `052-local-html-dom-form-extract` | Place a safe passport-renewal appointment hold |
