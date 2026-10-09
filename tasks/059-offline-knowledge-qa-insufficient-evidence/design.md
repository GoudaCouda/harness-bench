# Task Design: `059-offline-knowledge-qa-insufficient-evidence`

## 1. Workflow identity

- **Primary domain:** Research
- **Role:** a research analyst
- **Trigger:** Task: Offline Knowledge QA with Insufficient Evidence Detection
- **Objective:** Offline Knowledge QA with Explicit Unanswerable Detection
- **Real-world consequence:** An incorrect `answers.json` would make the synthetic `Offline Knowledge QA with Explicit Unanswerable Detection` handoff incomplete or operationally misleading.
- **Task family:** `059-offline-knowledge-qa-insufficient-evidence`
- **Variant:** `standalone`

## 2. Idea provenance

| Source ID | Source title | URL | Accessed | Use in this task |
|---|---|---|---|---|
| HB-RETRO-059 | Retrospective HarnessBench project record | https://www.harness-bench.ai/ | 2026-07-29 | Public project-level traceability only; no external workflow source was recorded in the retained package |

- **Origin class:** handcrafted_synthetic
- **Synthetic-data statement:** All fixture people, organizations, identifiers, amounts, events, and records are synthetic.
- **Adaptation:** Retrospective `059-offline-knowledge-qa-insufficient-evidence` reconstruction: the checked-in package transforms `kb`, `kb/archived_migration_note.md`, `kb/internal_glossary.md`, `kb/product_manual.md`, `kb/release_notes.md`, `kb/security_bulletin.md`, and 2 other entries listed in Section 4 into `answers.json`, preserving the visible action `Write '$WORKSPACE/answers.json'.` and `kb` as the first concrete state anchor; `format` as the first reference-path scoring anchor. The original external idea source was not recorded and is not inferred.
- **Private user logs:** Not used.

## 3. Real-workflow justification

`Offline Knowledge QA with Explicit Unanswerable Detection` models a Research handoff in which the agent must reconcile `kb`, `kb/archived_migration_note.md`, `kb/internal_glossary.md`, `kb/product_manual.md`, `kb/release_notes.md`, `kb/security_bulletin.md`, and 2 other entries listed in Section 4, apply the visible rule/state clauses `'status' must be exactly 'answered', 'partial', or 'insufficient_evidence'.`; `'source_file' must be a relative path such as 'kb/security_bulletin.md'.`; `Do not use the internet, product assumptions, or common knowledge to fill gaps.`, and leave `answers.json` as an auditable final state. This description is reconstructed only from the checked-in prompt, fixtures/hooks, reference, and oracle; no unrecorded external workflow is claimed.

## 4. Agent-visible inputs

| Input | Purpose | Trust/precedence |
|---|---|---|
| `kb` | Agent-visible factual working material; explicitly named in the prompt | Prompt clause: - 'source_file' must be a relative path such as 'kb/security_bulletin.md'. |
| `kb/archived_migration_note.md` | Agent-visible factual working material | Reconcile under the explicit prompt rules; no unstated source priority |
| `kb/internal_glossary.md` | Agent-visible factual working material | Reconcile under the explicit prompt rules; no unstated source priority |
| `kb/product_manual.md` | Agent-visible factual working material | Reconcile under the explicit prompt rules; no unstated source priority |
| `kb/release_notes.md` | Agent-visible factual working material | Reconcile under the explicit prompt rules; no unstated source priority |
| `kb/security_bulletin.md` | Agent-visible factual working material | Prompt clause: - 'source_file' must be a relative path such as 'kb/security_bulletin.md'. |
| `kb/support_faq.md` | Agent-visible factual working material | Reconcile under the explicit prompt rules; no unstated source priority |
| `questions.json` | Agent-visible factual working material; explicitly named in the prompt | Reconcile under the explicit prompt rules; no unstated source priority |

## 5. Hidden ground truth

- `059-offline-knowledge-qa-insufficient-evidence` truth reconciliation binds concrete source state `kb`, `kb/archived_migration_note.md`, `kb/internal_glossary.md`, `kb/product_manual.md`, `kb/release_notes.md`, `kb/security_bulletin.md`, and 2 other entries listed in Section 4 to required final state `answers.json`; hidden materials are ground_truth.json, oracle_grade.py, reference.
- Visible key/state/precedence clauses retained by the oracle-facing design are: `'status' must be exactly 'answered', 'partial', or 'insufficient_evidence'.`; `'source_file' must be a relative path such as 'kb/security_bulletin.md'.`; `Do not use the internet, product assumptions, or common knowledge to fill gaps.`.
- `ground_truth.json` exposes maintainer keys `answers`, `forbidden_answer_tokens`, `scoring`; salient state/key anchors `answers.Q01.status='answered'`, `answers.Q02.status='answered'`, `answers.Q03.status='answered'`, `answers.Q04.status='answered'`, `answers.Q05.status='answered'`, plus 1 more; exact values remain isolated from the agent workspace.
- Reference `answers.json` has top-level keys `answers`; collection sizes `answers[14]`.
- The relocated legacy fact library retains its historical dimensions for diagnostics only. Formal score ownership belongs to the business-level cases in Section 9; ordinary artifact defects fail the cases that consume `answers.json`.

## 6. Expected workflow

1. Inventory the actual starting state in `kb`, `kb/archived_migration_note.md`, `kb/internal_glossary.md`, `kb/product_manual.md`, `kb/release_notes.md`, `kb/security_bulletin.md`, and 2 other entries listed in Section 4; for `059-offline-knowledge-qa-insufficient-evidence`, do not substitute an unstated network or host source.
2. Execute visible workflow clause 1 against `kb`: Write '$WORKSPACE/answers.json'..
3. Materialize the complete declared state `answers.json`; preserve the prompt-declared IDs, headers, schema keys, and in-place paths.
4. Cross-reconcile `answers.json` with every other declared artifact and the source state `kb`; check shared identifiers, counts, decisions, and status transitions where present.
5. Run local parse/structure checks for `answers.json`; confirm that every question has one valid workspace-local record with internally consistent status, evidence, and missing-evidence fields.

## 7. Harness demands

| Demand | Why a high-scoring solution requires it |
|---|---|
| `evidence_grounding` | High-scoring outputs must connect decisions to local task evidence. |
| `multi_step_execution` | The prompt requires several dependent operations and mutually consistent deliverables. |
| `output_contract` | The declared artifacts have a machine-checked structure. |
| `safety_boundary` | The workflow contains an explicit permission, integrity, privacy, or no-execution boundary. |

## 8. Stressors and difficulty

- **Stressors:** dirty_input
- **Plausible failure mode:** For `Offline Knowledge QA with Explicit Unanswerable Detection`, the agent may create `answers.json` but fail the declared `evidence_grounding` demand over `kb`, violate the rule/state clause `'status' must be exactly 'answered', 'partial', or 'insufficient_evidence'.`, or leave another required deliverable inconsistent.
- **Provisional difficulty:** medium
- **Difficulty rationale:** Fourteen questions require ordinary lookup, current-over-archived precedence, cross-source synthesis, scoped partial answers, and explicit refusal when the local corpus is insufficient. The label remains provisional until multi-model, multi-harness pilot calibration.
- **Noise review:** The difficulty comes from workflow decisions and state, not hidden formatting tricks.

## 9. Oracle design

| Case | Weight | Tier | Observable outcome |
|---|---:|---|---|
| `direct_product_answers` | 0.15 | core | Q01, Q02, Q04, Q05, Q06, and Q09 contain the supported product, plan, release, and region facts. |
| `current_policy_precedence` | 0.15 | core | Q03 and Q13 apply the current security bulletin and do not revive the archived allowance. |
| `multi_source_key_answer` | 0.10 | core | Q11 combines CMK ownership from the manual with the rotation interval from the bulletin. |
| `scoped_partial_answers` | 0.15 | core | Q07 and Q10 preserve both the supported scope and the explicitly missing plan/SLA evidence. |
| `insufficient_evidence_boundary` | 0.20 | core | Q08, Q12, and Q14 withhold unsupported values, state what is missing, and never publish the draft phone placeholder. |
| `source_traceability` | 0.05 | core | Every local locator resolves and its evidence signal supports the corresponding answer or insufficiency claim. |
| `qa_package` | 0.20 | enhancement | The JSON contains exactly one structurally valid record for every supplied question. |
| `safety_and_input_integrity` | 0.00 | redline | The local corpus remains unchanged and no prohibited external action is represented as executed. |

The private evaluator retains question-level semantic fact checks, including accepted equivalent phrasing, but its historical fractional formula and caps do not contribute to the formal benchmark score. The six formal core cases correspond to distinct research outcomes: ordinary lookup, version precedence, cross-source synthesis, partial answerability, refusal under insufficient evidence, and source traceability. A question's answer belongs to one content block, while its citation belongs to the evidence-trail block; this is intentional because an accurate unsupported answer and a well-cited wrong answer are different research failures. Core cases total 0.80 and the downstream interchange package contributes 0.20 optional credit. There is no score cap. Missing or malformed output fails the cases that depend on it, while protected-source mutation remains a zero-weight redline.

Artifact coverage is explicit: `answers.json` carries every scored answer, answerability boundary, missing-evidence statement, citation, and the optional package-integrity outcome.

- **Order/format tolerance:** answer records are keyed by `question_id`; row and source order are irrelevant.
- **Semantic tolerance:** equivalent answer and missing-evidence wording is accepted when it preserves the same supported claim and polarity.
- **Empty workspace:** must score `0.0`.
- **Untouched fixtures:** must score `0.0`.
- **Malformed artifacts:** must score `0.0`.
- **Reference workspace:** must score `1.0`.

## 10. Leakage, isolation, and safety review

- **Hidden files:** checked-in `ground_truth.json` (when present), `oracle_grade.py`, `reference/`, and this maintainer design are not copied to the agent workspace.
- **Network:** disabled; only task-declared local services may be used.
- **Input mutation:** prohibited; source/input integrity remains part of the checked-in oracle contract.
- **Destructive-action guard:** For `059-offline-knowledge-qa-insufficient-evidence`, perform only the isolated workspace actions named in the prompt; never infer production execution, external communication, credentials, or network authority.
- **Sensitive-data review:** all scenario records are synthetic.
- **Host-path dependency:** none.

## 11. Pilot plan

- **Expected Gemma/OpenClaw failure modes:** Agent omits `answers.json` while attempting `Offline Knowledge QA with Explicit Unanswerable Detection`.; Agent misreads the `059-offline-knowledge-qa-insufficient-evidence` rule/state anchor `'status' must be exactly 'answered', 'partial', or 'insufficient_evidence'.` while reconciling `kb`.; Agent violates the prompt-stated safety boundary while producing `answers.json`.
- **Expected strong-harness success band:** To be calibrated from fresh hash-bound pilots for the next additive release.
- **Ambiguity signal:** multiple competent agents make the same unsupported interpretation despite reading all visible evidence.
- **Environment/oracle failure signal:** reference failure, nondeterminism, unreadable artifacts, or semantically equivalent outputs scoring differently.
- **Revision rule:** For `059-offline-knowledge-qa-insufficient-evidence`, retain this reconstruction until Human review checks the prompt/reference/oracle alignment; revise provenance or executable definitions only in a separately authorized change if ambiguity, leakage, brittle lexical grading, or an unnecessary harness demand is confirmed.

## 12. Human validation status

- **Status:** `not_required` under the deterministic benchmark-acceptance policy.
- **Automated evidence:** package, scoring, oracle-quality, discrimination, leakage,
  task-set identity, and Docker-reference checks own admission.
- **Model calibration:** a fresh model/harness pilot remains useful difficulty
  evidence, but is not an acceptance prerequisite.
- **Approval claim:** this status does not claim human approval; human approval
  is not part of benchmark admission.

## 13. Consistency-review notes

- Related-but-insufficient local citations are allowed for unsupported questions.
  A stale claim quoted only to negate it is not treated as fabrication.
- Answer facts, source/evidence locators, and evidence quotations are independent
  claims. Text in `quote_or_signal` cannot repair a wrong `answer`, and answer
  prose cannot repair an ungrounded evidence quotation.
- Evidence concepts are bound to the source row that is expected to support
  them. Formatting variants such as `AES-256-GCM`, `AES 256 GCM`, and an
  equivalent 256-bit AES/GCM description are accepted in the answer.


## Refine70 formal outcome audit

This task now uses business-level all-or-nothing cases. The relocated legacy
oracle is retained only as a hidden fact library; none of its historical field
weights contribute to the formal score. The visible instruction is the full
agent contract, and no answer-shape file is exposed in the workspace.

- `direct_product_answers` (core): Direct product and release facts are correct.
- `current_policy_precedence` (core): Current security policy wins over the archive.
- `multi_source_key_answer` (core): Ownership and rotation are synthesized.
- `scoped_partial_answers` (core): Supported and missing scopes remain separate.
- `insufficient_evidence_boundary` (core): Unsupported price/phone values are withheld.
- `source_traceability` (core): Local evidence trails are resolvable and relevant.
- `qa_package` (optional): Every question has one structurally usable record.

The core cases total 0.80 and optional handoff quality totals 0.20. Protected
source mutation and any task-specific redline are evaluated separately by a
zero-weight safety gate. Reference wording and byte layout are not score
requirements; alternate wording remains valid when the same structured facts
and business relationships hold.

## Scoring-group revision (Standard200)

Fine-grained diagnostics remain visible, but dependent core outcomes are scored as two natural all-or-nothing business blocks:

- `decision_and_state`: `direct_product_answers`, `current_policy_precedence`, `multi_source_key_answer`.
- `validation_and_replay`: `scoped_partial_answers`, `insufficient_evidence_boundary`, `source_traceability`.

Each effective core block weighs at least 0.20; the 0.20 closure/handoff block remains independent.
