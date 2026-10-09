# 258-policy-document-contradiction-review

## 1. Workflow identity

审阅工作区 input/ 中的五份制度文件，找出有直接原文证据的事实矛盾、版本不一致和引用错误，形成 output/review_report.json。每项必须给出文件、章节、逐字引文、严重性判断和可直接采用的修订文本；仅措辞不同但事实一致的要求不得误报。不得修改输入或创建其他文件。

## 2. Idea provenance

- **Adaptation:** NAMI Gold20 case_04 is adapted as 258-policy-document-contradiction-review: retain original fixtures and business invariants, replace deployment-bound execution with portable Office/artifact tools and independent hidden grading.
- **Private user logs:** No raw private conversations, credentials or attachments are included.
- **Synthetic-data statement:** Business entities and records are the original frozen synthetic fixtures.
- Protocol provenance: the HarnessBench task packaging protocol, <https://arxiv.org/abs/2605.27922> (this is not a source for private business fixtures).
- Source alias: `NAMI-GOLD20-case_04`.

## 3. Real-workflow justification

258-policy-document-contradiction-review: 需要跨五份文档区分五个确定性问题与三组同义干扰，逐项定位证据并给出可执行修订，同时严格保护输入。
The workflow requires dependent evidence and a durable deliverable, specifically Business result；Evidence and cross-artifact consistency.

## 4. Agent-visible inputs

| Workspace path | Role |
|---|---|
| `TASK.md` | Protected task evidence or public contract |
| `input/A01_采购管理办法_v3.2.md` | Protected task evidence or public contract |
| `input/A02_费用报销细则_v2.0.md` | Protected task evidence or public contract |
| `input/A03_信息安全控制标准_v4.0.md` | Protected task evidence or public contract |
| `input/A04_远程办公实施细则_v1.3.md` | Protected task evidence or public contract |
| `input/A05_制度版本与引用目录_2026Q2.md` | Protected task evidence or public contract |

Public helpers are initial workspace files. Hidden tests, reference material and private service state are never agent mounts.

## 5. Hidden ground truth

For 258-policy-document-contradiction-review, the protected evidence `TASK.md`, `input/A01_采购管理办法_v3.2.md`, `input/A02_费用报销细则_v2.0.md`, `input/A03_信息安全控制标准_v4.0.md`, `input/A04_远程办公实施细则_v1.3.md`, `input/A05_制度版本与引用目录_2026Q2.md` fixes the admissible state and record invariants. The independent evaluator checks `output/review_report.json`; original verifier checks, fixture hashes and business-group mapping are frozen under tests/ground_truth; no candidate-authored claim replaces the hidden oracle.

## 6. Expected workflow

1. Inspect `TASK.md`, `input/A01_采购管理办法_v3.2.md`, `input/A02_费用报销细则_v2.0.md`, `input/A03_信息安全控制标准_v4.0.md`, `input/A04_远程办公实施细则_v1.3.md`, `input/A05_制度版本与引用目录_2026Q2.md`, resolve the entities and rule precedence before changing state.
2. Perform Business result；Evidence and cross-artifact consistency using the public inputs and tools; inspect intermediate state and verify the cross-record invariant.
3. Deliver `output/review_report.json`, verify the final state against the input contract, and remove temporary helpers from the delivery workspace.

## 7. Harness demands

multi_step_execution, evidence_grounding, output_contract, verification_behavior. No model-specific solution interface.

## 8. Stressors and difficulty

**Plausible failure mode:** 258-policy-document-contradiction-review: an apparently valid artifact misses one coupled business condition in Business result；Evidence and cross-artifact consistency; a plan without durable state earns no execution credit.

**Difficulty rationale:** 需要跨五份文档区分五个确定性问题与三组同义干扰，逐项定位证据并给出可执行修订，同时严格保护输入。

## 9. Oracle design

Pass threshold 0.8 with every core required. Core weights total 0.8, closure 0.2.

| Case | Weight | Core/gate | Meaning |
|---|---:|---|---|
| `business_result` | 0.4 | core | Original result checks: contradiction_recall false_positive_control |
| `evidence_consistency` | 0.4 | core | Original evidence checks: evidence_localization severity_accuracy actionable_recommendations summary_consistency |
| `complete_delivery` | 0.2 | closure | All applicable original checks pass, including format, required structure and final-state consistency. |
| `protected_workspace` | 0.0 | gate | Frozen inputs and tools are unchanged; no extra files, unsafe paths, symlinks or special nodes. |

Required final artifacts: `output/review_report.json`. Every check is deterministic. Missing/ordinary malformed output fails its scored block. Actual input/state tampering, unsafe links and forged execution evidence are red lines.

## 10. Leakage, isolation, and safety review

The hidden original verifier reads only a bounded copied view; public inputs and helper identities are checked against frozen hashes. ZIP/XML payload safety is checked before parsing. Grading never changes the submission. Runtime dependencies and grader isolation are qualified separately.

## 11. Pilot plan

**Expected Gemma/OpenClaw failure modes:** For 258-policy-document-contradiction-review, inspect failures in Business result；Evidence and cross-artifact consistency, incorrect tool paths, missing durable state and incomplete output checks; these are hypotheses rather than unrun model results.

Previous Sol/Flash/Opus × Goose/NanoBot experiments used earlier package/runtime identities. Their scores remain historical. Native-v2 acceptance records live in the suite validation reports; a fresh frozen model pilot must not be claimed from replayed outputs. Every terminal outcome remains in the denominator.

## 12. Human validation status

**Status:** `not_required`

Current project policy uses automated acceptance evidence. This package does not claim human approval. User-assigned final task numbers and explicit integration are still pending.
