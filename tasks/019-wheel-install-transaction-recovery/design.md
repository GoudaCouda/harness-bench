# Task Design: `019-wheel-install-transaction-recovery`

## 1. Workflow identity

- **Domain:** Software Engineering
- **Role:** packaging-platform engineer repairing an offline recovery planner
- **Trigger:** a wheel installation crashed after a subset of writes, while a
  concurrent process may have changed one affected path
- **Objective:** produce a safe, deterministic rollback plan and reviewable
  report without mutating site-packages
- **Irreversible boundary:** no package install/uninstall or environment change
  is authorized

## 2. Idea provenance

| Source ID | Source | URL | Accessed | Adaptation |
|---|---|---|---|---|
| PYPA-WHEEL-SPEC | PyPA binary distribution format | https://packaging.python.org/en/latest/specifications/binary-distribution-format/ | 2026-08-26 | Grounds wheel file manifests and installation layout |
| PYPA-INSTALLED-PROJECTS | PyPA recording installed projects | https://packaging.python.org/en/latest/specifications/recording-installed-packages/ | 2026-08-26 | Grounds RECORD path, digest, and ownership evidence used for safe recovery |

All package names, paths, hashes, journals, and site states are synthetic.

- **Private user logs:** None were used.
- **Adaptation:** The public metadata semantics are combined with a synthetic
  write-ahead journal. The benchmark asks for planning only, not a real install.

## 3. Real-workflow justification

Package managers must distinguish their own half-applied writes from files that
changed later. Recovery also needs reverse ordering, shared-path ownership, and
safe retries after a second crash. A plausible but unsafe implementation can
pass a simple create/delete example while destroying another package's file or
rolling back newer work.

## 4. Agent-visible inputs

`repo/docs/recovery_contract.md` is authoritative. Synthetic transactions are
in `repo/recovery_cases.json`; code and tests are
`repo/src/install_recovery.py` and `repo/tests/test_public.py`.

## 5. Hidden ground truth

All schemas, RECORD entries, digests, owners, paths, and journal relationships
are validated. A committed transaction is never rolled back. For an interrupted
transaction, applied entries are examined in reverse order. Already-restored
entries produce no duplicate action; an untouched unapplied entry is safe; an
exact post-write state yields remove, restore, or detach-owner as appropriate.
Any unexplained state suppresses the entire action list and requires manual
intervention. Required final workspace state is the repaired pure planner at
`repo/src/install_recovery.py`, the exact visible-case plan array at
`repo/recovery_report.json`, and a truthful verification handoff at
`repo/RECOVERY_NOTES.md`. All supplied inputs remain unchanged.

## 6. Expected workflow

1. Read `repo/docs/recovery_contract.md` and map each journal entry in
   `repo/recovery_cases.json` to its wheel RECORD evidence.
2. Run `repo/tests/test_public.py` and inspect create, shared-path, and drift
   state transitions.
3. Repair `repo/src/install_recovery.py` with strict validation and atomic
   conflict handling.
4. Generate `repo/recovery_report.json` by invoking the submitted planner in
   visible case order.
5. Rerun the unittest command and record evidence and risk in
   `repo/RECOVERY_NOTES.md`.

### Novelty review

| Nearest task | Similarity | Substantive differences |
|---|---|---|
| `076-transitive-security-upgrade` | package changes | 019 repairs a crashed local file transaction; 076 plans dependency upgrades |
| `119-schema-migration-backfill-repair` | recovery and idempotence | 019 reasons over RECORD ownership and file digests rather than database rows |
| `166-backup-restore-drill-recovery` | rollback workflow | 019 is a pure per-file package transaction planner with shared owners and drift |

## 7. Harness demands

The task requires multi-file grounding, executable repository repair, exact
structured output, state-transition reasoning, verification, and restraint at
the mutation boundary.

## 8. Stressors and difficulty

- **Stressors:** strict path/digest schemas, reverse journal order, same-content
  shared files, already-restored entries, unapplied writes, atomic conflict
  suppression, committed journals, and input immutability.
- **Plausible failure mode:** delete every applied path, trust only the journal,
  emit actions in write order, restore despite drift, or repeat completed work.
- **Difficulty:** hard.
- **Difficulty rationale:** independent safe-recovery invariants interact, and
  several locally reasonable shortcuts are destructive in hidden cohorts.

## 9. Oracle design

`transaction_rollback_behavior` (0.45 core) checks reverse rollback and RECORD
mapping. `shared_drift_and_retry_edges` (0.25 core) checks ownership, drift,
atomicity, and idempotence. `visible_recovery_report` (0.10 core) recomputes the
visible plans. `verification_handoff` (0.20 optional) checks truthful notes.
`source_and_workspace_boundary` is a zero-weight integrity gate limited to
protected-input and workspace redlines. Source defects and unsupported install
claims lose their ordinary scored cases. Core weight is 0.80.
Together these cases directly evaluate the implementation artifact
`repo/src/install_recovery.py`, exact generated artifact
`repo/recovery_report.json`, and handoff artifact `repo/RECOVERY_NOTES.md`.

### Adjacent examples

- **Nearest valid:** a transaction-created file still exactly matches its
  journaled digest and sole owner, so the plan removes it.
- **Nearest wrong 1:** a shared same-content file is deleted instead of only
  detaching the interrupted package's ownership.
- **Nearest wrong 2:** one safe restore is emitted even though another path has
  post-write drift; recovery must suppress all actions pending review.

## 10. Leakage, isolation, and safety review

Hidden cases, references, and design are excluded from the agent. Candidate
source is AST-audited and executed with only a static `re` import and without I/O, filesystem, or network.
Protected fixtures are integrity-checked and identifiers are synthetic.

## 11. Pilot plan

Require reference `1.0` and empty/untouched/malformed `0.0`. Mutate rollback
order, shared-file handling, drift atomicity, idempotence, committed handling,
RECORD validation, report order, and input mutation independently. Pilot Gemma
+ OpenClaw on a qualified worker and target a first-pass score around 0.30–0.70.

- **Expected Gemma/OpenClaw failure modes:** delete shared paths, overlook
  journal/RECORD mismatch, emit forward-order actions, recover through drift,
  or treat an already-restored entry as a conflict.

## 12. Human validation status

- **Status:** `not_required`; deterministic gates and model pilot are required.
- **Current evidence level:** official-source design and executable Oracle.
- **Model outcomes used for membership:** false.
- **Canonical registry:** `docs/task_reviews/review_registry.csv`.

## Scoring-group revision (Standard200)

Fine-grained diagnostics remain visible, but dependent core outcomes are scored as two natural all-or-nothing business blocks:

- `decision_and_state`: `transaction_rollback_behavior`.
- `validation_and_replay`: `shared_drift_and_retry_edges`, `visible_recovery_report`.

Each effective core block weighs at least 0.20; the 0.20 closure/handoff block remains independent.
