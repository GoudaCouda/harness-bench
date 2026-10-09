# Task Design: `026-code-review-risk-report`

## 1. Workflow identity

- **Domain:** Software Engineering
- **Role:** senior engineer reviewing a bulk customer-export pull request
- **Trigger:** a refactor changes API authorization, job claiming, upload state,
  pagination, retention, and download logging in one release candidate
- **Objective:** deliver an evidence-grounded, machine-readable merge review
- **Irreversible boundary:** review only; no source mutation, deployment, or network use

## 2. Idea provenance

| Source ID | Source | URL | Accessed | Adaptation |
|---|---|---|---|---|
| HB-RETRO-026 | Retained HarnessBench code-review workflow | https://www.harness-bench.ai/ | 2026-08-26 | Keeps the useful code-review handoff while rebuilding obvious disconnected vulnerabilities into one export state machine |

All services, schemas, tenants, IDs, and code are synthetic. No private review
or user logs were used. The package is a ground-up reconstruction rather than a
restoration of the archived answer-shaped vulnerability list.

- **Private user logs:** not used.

- **Adaptation:** the retained code-review workflow is transformed into a
  cross-file bulk-export state-machine review whose contract, schema, patch,
  structured handoff, and deterministic business cohorts are all task-specific.

## 3. Real-workflow justification

Large pull requests routinely span authorization, persistence, workers, data
pagination, configuration, and observability. A reviewer must reconcile the
diff with explicit service contracts and schema constraints: reading each hunk
in isolation misses tenant-key, lease, completion, tuple-cursor, falsy-value,
and bearer-secret failures. The final JSON models a review-bot or release-gate
handoff rather than an essay.

## 4. Agent-visible inputs

- `review/diff.patch`: the proposed multi-file change.
- `review/export_contract.md`: authoritative security, state, pagination,
  retention, and severity rules.
- `review/schema.sql`: authoritative tenant/idempotency key and job state shape.

The contract and schema take precedence over assumptions inferred from names.

## 5. Hidden ground truth

Seven regressions are grounded in changed lines and visible contracts: removed
PII scope authorization, global request-token lookup, non-atomic worker claim,
completion after failed upload, non-lexicographic cursor filtering, loss of
explicit zero TTL, and signed bearer URL logging. Added requester audit metadata
and parameterized queries are intentional non-findings.

The required final workspace state is a valid `review_findings.json` record;
its findings set must preserve each defect's file binding, severity, invariant,
remediation, evidence, and concrete test while fixture checksums remain intact.

## 6. Expected workflow

1. Read `review/export_contract.md` and `review/schema.sql` before judging the patch.
2. Trace tenant and authorization state from `app/export_api.py` to `app/export_repo.py`.
3. Trace queued job state through `app/export_worker.py`: claim, upload failure, retry, and completion.
4. Check cursor keys, explicit-zero configuration state, and log sensitivity in the named diff files.
5. Produce `review_findings.json` with grounded remedies and executable trigger/outcome tests.

### Novelty review

| Nearest task | Similarity | Substantive differences |
|---|---|---|
| `003-git-pr-merge` | pull-request workflow | 026 grades technical cross-file review, not merge mechanics |
| `044-legal-compliance-review` | evidence review | 026 requires executable code/state reasoning and concurrency analysis |
| `177-structured-log-redaction-repair` (planned) | secret logging | logging is one coupled edge here, not the task's primary workflow |

## 7. Harness demands

The task requires cross-file evidence grounding, multi-step state tracing,
structured artifact creation, correct prioritization, and restraint from editing
the reviewed fixtures.

## 8. Stressors and difficulty

- **Stressors:** tenant-scoped idempotency, conditional authorization, split
  compare-and-set, false terminal state, tuple pagination, absent-versus-zero
  configuration, and bearer-secret observability.
- **Plausible failure mode:** identify obvious authorization/logging defects but
  miss concurrency, cursor, or explicit-zero behavior; or report harmless audit
  metadata as a blocker.
- **Difficulty:** hard.
- **Difficulty rationale:** no single file states both the implementation and
  invariant, and full credit requires seven distinct trigger/outcome tests.

## 9. Oracle design

`authorization_and_tenant_review` (0.30 core) requires both PII authorization and
tenant-scoped idempotency. `worker_state_review` (0.25 core) requires atomic
claim and truthful upload completion. `data_lifecycle_review` (0.20 core)
requires cursor, zero-TTL, and signed-URL handling. `actionable_handoff` (0.05
core), `prioritization_and_verification` (0.10 optional), and `report_integrity`
(0.10 optional) grade usable review quality. Fixture/workspace safety is a
zero-weight hard gate.

`review_findings.json` is the sole required artifact. It must be non-empty,
valid JSON, workspace-local, and contain a summary plus complete finding records;
missing, malformed, linked, or undeclared output fails the artifact gate.

Matching is unordered and accepts alternate prose when file binding, risk
terms, remedy, severity, and concrete trigger/outcome test agree. A missed
finding loses its business cohort once rather than receiving repeated field
penalties.

### Adjacent examples

- **Nearest valid:** two tenants reuse one token and receive independent jobs.
- **Nearest wrong 1:** the review calls the token lookup idempotent without
  noticing that `tenant_id` disappeared.
- **Nearest wrong 2:** the review mentions upload retry but misses the following
  unconditional `mark_complete` transition.

## 10. Leakage, isolation, and safety review

Reference findings, ground truth, tests, and design are hidden from the agent.
Only synthetic code and policy are mounted. The workspace contract permits
creation of `review_findings.json` and rejects edits to review evidence,
symlinks, special files, and undeclared output.

## 11. Pilot plan

Require reference 1.0 and empty, untouched, malformed, and fixture-mutated
states at 0.0. Mutation tests remove findings, change severity, truncate output,
and alter evidence. Target Gemma/OpenClaw first-pass score is 0.30–0.70; a score
above 0.80 triggers another realism/difficulty review.

- **Expected Gemma/OpenClaw failure modes:** global idempotency accepted as safe,
  split claim race missed, upload failure still marked complete, tuple cursor
  treated as ordinary SQL, or explicit zero collapsed into default.

## 12. Human validation status

- **Status:** `not_required`; deterministic gates and model pilot are required.
- **Model outcomes used for membership:** diagnostic difficulty calibration only;
  deterministic task and Oracle evidence control membership.
- **Canonical registry:** `docs/task_reviews/review_registry.csv`.

## Scoring-group revision (Standard200)

Fine-grained diagnostics remain visible, but dependent core outcomes are scored as two natural all-or-nothing business blocks:

- `decision_and_state`: `authorization_and_tenant_review`.
- `validation_and_replay`: `worker_state_review`, `data_lifecycle_review`, `actionable_handoff`.

Each effective core block weighs at least 0.20; the 0.20 closure/handoff block remains independent.
