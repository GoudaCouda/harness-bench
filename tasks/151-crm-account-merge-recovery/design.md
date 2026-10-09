# Task Design: `151-crm-account-merge-recovery`

## 1. Workflow identity

- **Domain:** Business Operations / sales operations
- **Role:** CRM administrator recovering a failed entity merge
- **Trigger:** duplicate-account candidates include an exact alias, a consent
  conflict, foreign-key dependencies, and a plausible near-match.
- **Objective:** merge only the true duplicate transactionally, preserve the
  restrictive consent state and near-match, verify, retry, and hand off.

## 2. Idea provenance

- **Source:** `SALES-CRM-01`, informed by Salesforce duplicate-account merge
  guidance: https://help.salesforce.com/s/articleView?id=sf.account_merge.htm&language=en_US&type=5
- **Adaptation:** A commercial CRM merge pattern is transformed into an offline
  SQLite recovery with entity evidence, restrictive consent precedence,
  dependency migration, tombstone lineage, transaction receipt, and replay.
- **Private user logs:** None; all accounts and activities are synthetic.
- **Synthetic-data statement:** All workspace people, organizations,
  identifiers, accounts, activities, and consent records are synthetic.

## 3. Real-workflow justification

CRM merge recovery is more than choosing a similar name: the operator must
query identity evidence, preserve consent, move several dependency classes,
retain lineage, exclude a near-match, and prove a single transaction plus
idempotent retry. Those steps mirror a bounded sales-operations recovery.

## 4. Agent-visible inputs

| Input | Purpose |
|---|---|
| `crm.db` | mutable accounts, contacts, consent, dependencies, and audit state |
| `crm_seed.sql` | inspectable initial schema and relational structure |
| `merge_policy.md` | survivor, consent, near-match, and safety rules |
| `crmctl.py` | candidates, query, preview, merge, verify, and retry feedback |

## 5. Hidden ground truth

The evaluator queries `crm.db` independently. The final state requires the
correct survivor and tombstone, every dependency moved once, restrictive
consent preserved, the near-match untouched, exact `merge_plan.json`, one
digest-bound `merge_receipt.json`, and scoped `crm_handoff.md`. Entity keys,
foreign-key sets, transaction state, and receipt hashes are invariants.

## 6. Expected workflow

1. Inspect candidates and relational state in `crm.db` through `crmctl.py`.
2. Query identity, consent, and dependency keys before choosing a survivor.
3. Write `merge_plan.json` and preview its transaction effects.
4. Correct preview failures, then merge through the controller into `crm.db`.
5. Verify `merge_receipt.json`, survivor dependencies, consent, and near-match state.
6. Retry to prove idempotence and write `crm_handoff.md` with offline scope.

## 7. Harness demands

The task requires entity resolution, SQLite inspection, evidence precedence,
transactional state recovery, foreign-key verification, idempotence, and a
no-live-CRM safety boundary.

## 8. Stressors and difficulty

- **Plausible failure mode:** merge the plausible near-match or let permissive
  consent win, producing a relationally tidy database that violates identity or
  customer preference.
- **Difficulty rationale:** survivor identity, three dependency classes,
  restrictive consent, tombstone lineage, transaction receipt, and replay must
  close together.

## 9. Oracle design

| Case | Weight | Business-level outcome |
|---|---:|---|
| `survivor_and_dependencies` | 0.30 core | survivor, tombstone, and dependencies reconcile |
| `consent_and_near_match_safety` | 0.25 core | restrictive consent wins and near-match stays separate |
| `transaction_and_receipt` | 0.25 core | one plan-bound transaction and generated receipt close |
| `crm_handoff` | 0.20 optional | recovery, retry, and boundaries are communicated |
| `safety_and_input_integrity` | gate | protected policy and no-live-action boundary |

Core blocks total 0.80. They explicitly cover `crm.db`, `merge_plan.json`, and
`merge_receipt.json`; `crm_handoff.md` is the bounded communication block.
Individual row fields diagnose block failure but do not earn piecemeal credit.

## 10. Leakage, isolation, and safety review

The SQLite dataset is synthetic and offline. Hidden truth remains outside the
workspace. Policy/controller sources are immutable, mutations are restricted
to declared files, and no live CRM, customer contact, or irreversible action exists.

## 11. Pilot plan

Run reference, empty, untouched, malformed, wrong-survivor, near-match,
consent, partial-dependency, receipt, replay, and safety adversarials, then a
fresh Gemma 4 31B + OpenClaw trajectory.

- **Expected Gemma/OpenClaw failure modes:** decide by name alone, merge the
  near-match, lose opt-out consent, omit a dependency table, edit SQLite
  directly, or skip verify/retry.

## 12. Human validation status

- **Status:** `not_required` under the current deterministic acceptance policy.
- **Evidence level:** task-only quality/discrimination plus Docker-reference
  verification; model pilots remain optional calibration.
- **Approval claim:** this status does not claim human approval; human approval
  is not part of benchmark admission.
