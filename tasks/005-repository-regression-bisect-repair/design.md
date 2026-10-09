# Task Design: `005-repository-regression-bisect-repair`

## 1. Workflow identity

- **Domain:** Software Engineering
- **Role:** on-call engineer maintaining an invoice-routing service
- **Trigger:** a dry-run incident contains one false-positive and one
  false-negative eligibility decision after several commits
- **Objective:** locate the first bad commit, repair the current branch
  minimally, and leave an evidence-bound offline verification report
- **Irreversible boundary:** no deployment, collection action, package install,
  history rewrite, or customer contact is authorized

## 2. Idea provenance

| Source ID | Source | URL | Accessed | Adaptation |
|---|---|---|---|---|
| GIT-BISECT-01 | Git `bisect` documentation | https://git-scm.com/docs/git-bisect/2.50.0.html | 2026-08-17 | Uses the official good/bad commit search and test-command exit behavior in a synthetic local incident repository |
| GIT-DIFF-01 | Git `diff` documentation | https://git-scm.com/docs/git-diff | 2026-08-17 | Uses working-tree versus `HEAD` comparison to enforce a minimal uncommitted repair |

All organizations, invoices, commits, dates, and policy facts are synthetic.
The repository is prepared locally with fixed commit identities and timestamps;
the task does not use a private log or live service.

- **Private user logs:** Not used.
- **Adaptation:** The Git bisect workflow becomes a fixed-history
  invoice-routing incident that requires causal localization, a current-branch
  repair, and a repository-evidence-bound handoff.

## 3. Real-workflow justification

The agent receives a current checkout, incident evidence, executable replay,
tests, and Git history. The newest commit is deliberately not the regression,
so a superficial “inspect HEAD” repair is insufficient. A successful path has
to separate incident reproduction, causal history, current-branch repair, and
post-repair verification. The output remains a reviewer-ready working tree,
which is a normal pre-commit on-call handoff.

## 4. Agent-visible inputs

| Evidence | Purpose | Precedence |
|---|---|---|
| `repo/docs/incident.md` | business rules, known-good subject, boundaries | authoritative policy |
| Git commits and diffs | chronological cause evidence | authoritative for first-bad identity |
| `repo/fixtures/incident_replay.json` | two observed mismatches | authoritative incident sample |
| `repo/tools/replay_incident.py` | executable incident feedback | authoritative for the two incident cases |
| `repo/tests/test_public_policy.py` | baseline regression feedback | public subset; not exhaustive |
| `repo/src/ledger_router/eligibility.py` | repair target | writable only at the declared path |

## 5. Hidden ground truth

- The fixed history makes `refactor account status eligibility` the first bad
  commit and binds it to one deterministic 40-character hash.
- Nine behavior cohorts cover supported regions, the two eligible statuses,
  three excluded statuses/conditions, trial precedence, and balance boundaries.
- The private evaluator reads candidate source as an audited AST subset before
  evaluating it; no candidate-selected tests or self-authored result claims are
  accepted as behavioral evidence.
- The reference patch and report are grader-only and are never copied into the
  agent workspace.
- The final state is a repaired `repo/src/ledger_router/eligibility.py` on the
  latest branch state and a `repo/regression_report.json` whose commit key and
  verification records bind to that state.

## 6. Expected workflow

1. Inspect `repo/docs/incident.md`, Git status/log, and current source state.
2. Reproduce both signals with `repo/tools/replay_incident.py` and
   `repo/tests/test_public_policy.py`.
3. Mark the current checkout bad and `enable GB collection routing` good, then
   use commit-by-commit tests or `git bisect run` to identify the status refactor.
4. Reset the bisect so `main` again points at the latest audit-reason commit.
5. Change only `repo/src/ledger_router/eligibility.py`, retaining regions, guard ordering,
   signature, and the later audit reason.
6. Run both declared commands and reconcile `repo/regression_report.json` with
   the actual Git state and first-bad commit key.

### Novelty review

Nearest existing tasks were compared across domain, role, trigger, tool chain,
state transition, final artifact, and failure mode.

| Nearest task | Similarity | Substantive differences |
|---|---|---|
| `025-dependency-upgrade-compat` | code patch plus tests | 005 diagnoses a historical behavioral regression rather than changing a dependency; it requires Git causality, bisect reset, incident replay, and commit-bound evidence |
| `070-ci-attempt-diagnosis` | failure diagnosis | 005 mutates source and validates business behavior; 070 classifies CI attempts and does not identify a first-bad commit or preserve later code |
| `076-transitive-security-upgrade` | minimal repository repair | 005 has coupled policy false positive/negative cases, fixed Git history, causal bisection, and a working-tree handoff rather than dependency graph remediation |

The task differs from every nearest neighbor on at least trigger, tool chain,
state transition, and final artifact, including more than two of tool/state/final
state. It is therefore not a renamed template variant.

## 7. Harness demands

| Demand | Why it is necessary |
|---|---|
| `multi_step_execution` | reproduction, history search, reset, repair, two validations, and report depend on one another |
| `evidence_grounding` | incident policy and actual commit history jointly determine the answer |
| `error_recovery` | the task starts with failing replay cases and a bisect can leave the checkout detached unless reset |
| `verification_behavior` | both business replay and repository tests must close after repair |
| `safety_boundary` | history, evidence, live collections, deployment, and customer contact are explicitly out of scope |

## 8. Stressors and difficulty

- **Stressors:** misleading newest commit; simultaneous false inclusion and
  false exclusion; preservation of a later behavior; immutable evidence;
  minimal diff; bisect state cleanup.
- **Difficulty:** hard. The difficulty comes from causal localization and state
  restoration rather than hidden formatting. The task has a short repository,
  but a solver that skips Git evidence can make a correct patch while failing
  the causal handoff, and a solver that repairs the bisected checkout can lose
  later behavior.
- **Plausible failure mode:** repair the detached bisect checkout or identify
  the latest commit as causal, leaving the final branch state or report wrong.
- **Difficulty rationale:** causal localization, branch restoration, minimal
  mutation, and two verification signals must close as one workflow.

## 9. Oracle design

| Case | Weight | Deterministic evidence |
|---|---:|---|
| `eligibility_behavior` | 0.35 core | audited, side-effect-free AST subset evaluated against nine policy cohorts |
| `minimal_current_branch_repair` | 0.25 core | only the source file differs from latest `main`, with a one-line replacement and later behavior retained |
| `bisect_evidence` | 0.20 core | report hash and subject resolve to the actual fixed-history status-refactor commit |
| `verification_handoff` | 0.20 optional | closed-set incident IDs, commands, results, changed file, cause concepts, and offline scope |
| `safety_and_input_integrity` | gate | immutable seed files, no forbidden external-action claim, and no filesystem redline; ordinary extra workspace files remain diagnostic |

The three core cases total 0.80. The optional handoff creates a natural
`0.80 -> 1.00` ladder. Empty, untouched, malformed, wrong-commit, detached
bisect, broad-rewrite, and unsafe-claim outcomes are independently
adversarially testable. Equivalent Python syntax is accepted inside the small
auditable language when the behavior and Git diff constraints hold; reference
wording is not scored.

The oracle explicitly covers `repo/src/ledger_router/eligibility.py` and
`repo/regression_report.json` as business-level results rather than awarding
credit for isolated fields.

### Adjacent examples

- **Nearest valid:** restore `{"active", "delinquent"}`, reset to `main`, preserve
  `eligible_balance`, report the status-refactor hash, and record both commands.
- **Nearest wrong 1:** fix behavior at the bisected detached commit. Tests pass,
  but later GB/audit behavior and the current-branch state are not preserved.
- **Nearest wrong 2:** fix current behavior but report the latest audit-reason
  commit as first bad. The repair cases pass; causal evidence does not.

## 10. Leakage, isolation, and safety review

- Git history is created by the trusted runtime hook; hook source, ground truth,
  references, tests, and this design are not copied into the agent workspace.
- The task is offline and contains no credential, personal data, live endpoint,
  or external messaging mechanism.
- Only one source file may be modified and one JSON report is required. Input
  digests, Git branch/HEAD state, and unsafe external-action claims are checked;
  ordinary extra workspace files are reported diagnostically rather than treated
  as a zero-score safety violation.
- The evaluator refuses symlinked, oversized, malformed, or side-effectful
  candidate source before behavior evaluation.

## 11. Pilot plan

- Static gate: reference `1.0`, empty/untouched `0.0`, core-only `0.8`, each
  adjacent negative loses only its corresponding case, repeated scoring stable.
- Real pilot: Gemma 4 31B through OpenClaw on a fresh task/controller/service
  identity after any instruction, fixture, hook, or evaluator change.
- Review: inspect whether the model uses history and resets bisect; a high score
  without meaningful Git/tool interaction is a realism defect even if the
  deterministic oracle is correct.
- Status: silver, pending adversarial suite and fresh real pilot.
- **Expected Gemma/OpenClaw failure modes:** stopping at a passing patch without
  resetting bisect, losing later behavior, choosing the wrong causal commit, or
  writing report claims that do not match repository state.

## 12. Human validation status

- **Status:** `not_required` under the deterministic benchmark-acceptance policy.
- **Automated evidence:** package, scoring, oracle-quality, discrimination, leakage,
  task-set identity, and Docker-reference checks own admission.
- **Model calibration:** a fresh model/harness pilot remains useful difficulty
  evidence, but is not an acceptance prerequisite.
- **Approval claim:** this status does not claim human approval; human approval
  is not part of benchmark admission.
