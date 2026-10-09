# Task Design: `051-smallfile-batch-reject-ledger`

## 1. Workflow identity

- **Primary domain:** Data Analytics
- **Role:** data intake pipeline operator
- **Trigger:** A mixed-format dropbox batch must be normalized after a prior implementation produced noisy and non-idempotent rejects.
- **Objective:** Normalize accepted customer, order, and case records; classify each meaningful reject once; prove replay stability.
- **Real-world consequence:** Duplicate identities, silent data loss, or non-idempotent replays corrupt the downstream catalog and make the intake audit unusable.
- **Task family:** `051-smallfile-batch-reject-ledger`
- **Variant:** `standalone`

## 2. Idea provenance

| Source ID | Source title | URL | Accessed | Use in this task |
|---|---|---|---|---|
| HB-RETRO-051 | HarnessBench retained-workflow retrospective | https://www.harness-bench.ai/ | 2026-08-09 | Retained mixed-file intake idea; current records, rejection causes, and replay rules were reconstructed. |

- **Origin class:** handcrafted_synthetic
- **Synthetic-data statement:** All records and identifiers are synthetic.
- **Adaptation:** The old package repeated one unsupported-extension branch 30 times. The current task keeps nine accepted records and nine semantically different rejects, adds error precedence, and makes idempotent replay part of the operational handoff.
- **Private user logs:** Not used.

## 3. Real-workflow justification

File-drop integrations routinely receive CSV, JSON, text, malformed content, unsupported media, duplicate IDs, and partially valid multi-row files. An operator must conserve every input outcome, emit canonical records, and ensure a replay neither creates duplicate output nor changes the ledger. The task measures that batch state transition rather than raw parsing volume.

## 4. Agent-visible inputs

| Input | Purpose | Trust/precedence |
|---|---|---|
| `dropbox/customers/customers_01.csv` | Batch evidence or the normative normalization rule. | Apply `normalization_rules.yaml`; validate a row before duplicate-ID reservation. |
| `dropbox/customers/customers_bad.csv` | Batch evidence or the normative normalization rule. | Apply `normalization_rules.yaml`; validate a row before duplicate-ID reservation. |
| `dropbox/customers/customers_extra.csv` | Batch evidence or the normative normalization rule. | Apply `normalization_rules.yaml`; validate a row before duplicate-ID reservation. |
| `dropbox/misc/empty.md` | Batch evidence or the normative normalization rule. | Apply `normalization_rules.yaml`; validate a row before duplicate-ID reservation. |
| `dropbox/misc/image.png` | Batch evidence or the normative normalization rule. | Apply `normalization_rules.yaml`; validate a row before duplicate-ID reservation. |
| `dropbox/notes/case_500.txt` | Batch evidence or the normative normalization rule. | Apply `normalization_rules.yaml`; validate a row before duplicate-ID reservation. |
| `dropbox/notes/case_501.txt` | Batch evidence or the normative normalization rule. | Apply `normalization_rules.yaml`; validate a row before duplicate-ID reservation. |
| `dropbox/notes/case_502.txt` | Batch evidence or the normative normalization rule. | Apply `normalization_rules.yaml`; validate a row before duplicate-ID reservation. |
| `dropbox/notes/case_bad.txt` | Batch evidence or the normative normalization rule. | Apply `normalization_rules.yaml`; validate a row before duplicate-ID reservation. |
| `dropbox/orders/2026/order_100.json` | Batch evidence or the normative normalization rule. | Apply `normalization_rules.yaml`; validate a row before duplicate-ID reservation. |
| `dropbox/orders/2026/order_101.JSON` | Batch evidence or the normative normalization rule. | Apply `normalization_rules.yaml`; validate a row before duplicate-ID reservation. |
| `dropbox/orders/2026/order_102.json` | Batch evidence or the normative normalization rule. | Apply `normalization_rules.yaml`; validate a row before duplicate-ID reservation. |
| `dropbox/orders/2026/order_bad.json` | Batch evidence or the normative normalization rule. | Apply `normalization_rules.yaml`; validate a row before duplicate-ID reservation. |
| `dropbox/orders/2026/order_dup.json` | Batch evidence or the normative normalization rule. | Apply `normalization_rules.yaml`; validate a row before duplicate-ID reservation. |
| `dropbox/orders/2026/order_missing_currency.json` | Batch evidence or the normative normalization rule. | Apply `normalization_rules.yaml`; validate a row before duplicate-ID reservation. |
| `normalization_rules.yaml` | Batch evidence or the normative normalization rule. | Apply `normalization_rules.yaml`; validate a row before duplicate-ID reservation. |

## 5. Hidden ground truth

Concrete agent-visible inputs include `normalization_rules.yaml`, `dropbox/customers/customers_01.csv`, `dropbox/orders/2026/order_100.json`, `dropbox/notes/case_500.txt`, and the remaining paths in Section 4. Hidden truth contains the exact nine accepted canonical records and nine reject events keyed by source path and row where applicable.

- `accepted_records`: Every accepted small file is normalized to the correct canonical record. Every accepted small file is normalized to the correct canonical record; all related facts, relationships, and closed-set constraints must agree before this outcome earns credit.
- `canonical_index`: The index contains every accepted record exactly once. The index contains every accepted record exactly once; all related facts, relationships, and closed-set constraints must agree before this outcome earns credit.
- `reject_ledger`: All rejected files are classified exactly once in deterministic order. The reject ledger must be the exact closed rejection set, sorted by source path as required by the downstream batch interface.
- `batch_summary`: Success and rejection totals reconcile by type. Success and rejection totals reconcile by type; all related facts, relationships, and closed-set constraints must agree before this outcome earns credit.
- `ledger_integrity`: Index and reject ledgers use closed published schemas. Index and reject ledgers use closed published schemas; all related facts, relationships, and closed-set constraints must agree before this outcome earns credit.

The conservation invariant is nine accepted plus nine rejected outcomes. A malformed or rejected row does not reserve its proposed record ID; a later valid record may therefore be accepted. Re-running against the same seed must leave the same closed file set, index, reject ledger, and totals.

The required final workspace state is `normalized`, `index.csv`,
`reject_ledger.csv`, and `batch_summary.json`; the hidden evaluator derives
cross-artifact counts from those candidate outputs rather than trusting a
self-reported total.

## 6. Expected workflow

1. Read `normalization_rules.yaml` and inventory every file beneath `dropbox/`.
2. Parse supported formats row by row, validate required values before duplicate detection, and preserve source-path evidence.
3. Write one canonical JSON per accepted record under `normalized/`; write every accepted record exactly once to `index.csv`.
4. Write every meaningful rejection exactly once to `reject_ledger.csv` and derive `batch_summary.json` from the two ledgers.
5. Replay the transformation from the same seed and verify the file set, ordering, IDs, and conservation totals are unchanged.

## 7. Harness demands

| Demand | Why a high-scoring solution requires it |
|---|---|
| `error_recovery` | Malformed and partially valid inputs must be isolated without losing valid records. |
| `evidence_grounding` | Every accepted or rejected outcome must retain a source-path relationship. |
| `multi_step_execution` | Parsing, canonicalization, ledger construction, rollup, and replay verification depend on one another. |
| `safety_boundary` | Source evidence must remain unchanged and rejected data must not enter canonical output. |

## 8. Stressors and difficulty

- **Stressors:** dirty_input, partial_failure, duplicate_identity, idempotent_replay.
- **Plausible failure mode:** A rejected row reserves an ID and incorrectly blocks a later valid record, or a replay appends duplicate ledger rows.
- **Provisional difficulty:** hard.
- **Difficulty rationale:** Sixteen visible files contain multi-row CSV, case-insensitive extensions, malformed payloads, duplicate identities, and mixed valid/invalid outcomes; the four outputs must form one conserved and replay-stable batch state.
- **Why the difficulty is workflow-derived rather than noise:** Thirty identical `.bak` files were removed; every retained failure mode changes a distinct business decision.

## 9. Oracle design

| Dimension | Weight | Observable evidence |
|---|---:|---|
| `accepted_records` — Every accepted small file is normalized to the correct canonical record | 0.34 | Every accepted small file is normalized to the correct canonical record; all related facts, relationships, and closed-set constraints must agree before this outcome earns credit. |
| `canonical_index` — The index contains every accepted record exactly once | 0.25 | The index contains every accepted record exactly once; all related facts, relationships, and closed-set constraints must agree before this outcome earns credit. |
| `reject_ledger` — All rejected files are classified exactly once in deterministic order | 0.21 | The reject ledger must be the exact closed rejection set, sorted by source path as required by the downstream batch interface. |
| `batch_summary` — Success and rejection totals reconcile by type | 0.10 | Success and rejection totals reconcile by type; all related facts, relationships, and closed-set constraints must agree before this outcome earns credit. |
| `ledger_integrity` — Index and reject ledgers use closed published schemas | 0.10 | Index and reject ledgers use closed published schemas; all related facts, relationships, and closed-set constraints must agree before this outcome earns credit. |
| `safety_and_input_integrity` — Source evidence and execution boundaries are preserved | gate | Protected inputs and true redline boundaries remain intact; ordinary business mistakes lose their own cases instead of triggering this gate. |

The oracle explicitly covers required artifacts `normalized`, `index.csv`, `reject_ledger.csv`, and `batch_summary.json`; no required deliverable is credited only by generic file existence.
- **Critical gates:** source/input integrity and the shared required-artifact contract.
- **Partial-credit rationale:** Accepted canonical records, canonical index, and reject ledger are three whole core outcomes totaling 0.80; reconciled totals and ledger integrity are independent 0.10 outcomes.
- **Order/format tolerance:** Ledger ordering follows the visible deterministic source-path rule; JSON key order and prose wording are not scored.
- **Empty workspace:** must score `0.0`.
- **Untouched workspace seed:** must score `0.0`.
- **Malformed artifacts:** must score `0.0`.
- **Reference workspace:** must score `1.0`.

## 10. Leakage, isolation, and safety review

- **Hidden files excluded from agent workspace:** `tests/`, `design.md`, and reference/ground-truth materials.
- **Network:** disabled.
- **Workspace mutation contract:** only `normalized/`, `index.csv`, `reject_ledger.csv`, and `batch_summary.json` may be created; the seed is immutable.
- **Trusted between-round mutations:** none.
- **Potential destructive action and guard:** The task never authorizes source deletion; source mutation is a zero-credit gate.
- **Sensitive-data review:** all records are synthetic.
- **Host-path or author-environment dependency:** none.

## 11. Pilot plan

- **Expected Gemma/OpenClaw failure modes:** skips partially valid CSV rows; reserves an ID before validation; normalizes malformed content; omits unsupported media; or appends on replay.
- **Expected strong-harness success band:** To be calibrated from fresh hash-bound pilots; no target score is used to tune the task.
- **Signals that indicate task ambiguity:** competent agents disagree about error precedence despite reading `normalization_rules.yaml`.
- **Signals that indicate environment/oracle failure:** reference nondeterminism, a changed result on identical replay, or a correct keyed ledger rejected only for serialization.
- **Revision rule after pilot:** repair task-wide ambiguity or verifier defects; do not add repeated junk files or relax business invariants to tune a model score.

## 12. Human validation status

- **Status:** `not_required` under the deterministic benchmark-acceptance policy.
- **Automated evidence:** package, scoring, oracle-quality, discrimination, leakage,
  task-set identity, and Docker-reference checks own admission.
- **Model calibration:** a fresh model/harness pilot remains useful difficulty
  evidence, but is not an acceptance prerequisite.
- **Approval claim:** this status does not claim human approval; human approval
  is not part of benchmark admission.
