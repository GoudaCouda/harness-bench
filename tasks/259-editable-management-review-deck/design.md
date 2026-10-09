# 259-editable-management-review-deck

## 1. Workflow identity

阅读工作区中的合成经营报告、指标表和品牌约束，制作一份 6 页、16:9、数据可追溯且所有文字与图形均可编辑的中文管理汇报演示稿；不得修改输入、补造预测、堆砌全文或以整页图片冒充可编辑页面。

## 2. Idea provenance

- **Adaptation:** NAMI Gold20 case_05 is adapted as 259-editable-management-review-deck: retain original fixtures and business invariants, replace deployment-bound execution with portable Office/artifact tools and independent hidden grading.
- **Private user logs:** No raw private conversations, credentials or attachments are included.
- **Synthetic-data statement:** Business entities and records are the original frozen synthetic fixtures.
- Protocol provenance: the HarnessBench task packaging protocol, <https://arxiv.org/abs/2605.27922> (this is not a source for private business fixtures).
- Source alias: `NAMI-GOLD20-case_05`.

## 3. Real-workflow justification

259-editable-management-review-deck: 需要跨 Markdown、CSV 和 JSON 提炼事实，复算指标，组织六页管理叙事，并生成几何与数据均可机器检查的原生 OOXML 对象。
The workflow requires dependent evidence and a durable deliverable, specifically Business result；Evidence and cross-artifact consistency.

## 4. Agent-visible inputs

| Workspace path | Role |
|---|---|
| `TASK.md` | Protected task evidence or public contract |
| `input/brand.json` | Protected task evidence or public contract |
| `input/metrics.csv` | Protected task evidence or public contract |
| `input/report.md` | Protected task evidence or public contract |

Public helpers are initial workspace files. Hidden tests, reference material and private service state are never agent mounts.

## 5. Hidden ground truth

For 259-editable-management-review-deck, the protected evidence `TASK.md`, `input/brand.json`, `input/metrics.csv`, `input/report.md` fixes the admissible state and record invariants. The independent evaluator checks `output/management_review.pptx`; original verifier checks, fixture hashes and business-group mapping are frozen under tests/ground_truth; no candidate-authored claim replaces the hidden oracle.

## 6. Expected workflow

1. Inspect `TASK.md`, `input/brand.json`, `input/metrics.csv`, `input/report.md`, resolve the entities and rule precedence before changing state.
2. Perform Business result；Evidence and cross-artifact consistency using the public inputs and tools; inspect intermediate state and verify the cross-record invariant.
3. Deliver `output/management_review.pptx`, verify the final state against the input contract, and remove temporary helpers from the delivery workspace.

## 7. Harness demands

multi_step_execution, evidence_grounding, output_contract, verification_behavior. No model-specific solution interface.

## 8. Stressors and difficulty

**Plausible failure mode:** 259-editable-management-review-deck: an apparently valid artifact misses one coupled business condition in Business result；Evidence and cross-artifact consistency; a plan without durable state earns no execution credit.

**Difficulty rationale:** 需要跨 Markdown、CSV 和 JSON 提炼事实，复算指标，组织六页管理叙事，并生成几何与数据均可机器检查的原生 OOXML 对象。

## 9. Oracle design

Pass threshold 0.8 with every core required. Core weights total 0.8, closure 0.2.

| Case | Weight | Core/gate | Meaning |
|---|---:|---|---|
| `business_result` | 0.4 | core | Original result checks: numeric_grounding chart_data_binding |
| `evidence_consistency` | 0.4 | core | Original evidence checks: slide_1_evidence slide_2_evidence slide_3_evidence slide_4_evidence slide_5_evidence slide_6_evidence |
| `complete_delivery` | 0.2 | closure | All applicable original checks pass, including format, required structure and final-state consistency. |
| `protected_workspace` | 0.0 | gate | Frozen inputs and tools are unchanged; no extra files, unsafe paths, symlinks or special nodes. |

Required final artifacts: `output/management_review.pptx`. Every check is deterministic. Missing/ordinary malformed output fails its scored block. Actual input/state tampering, unsafe links and forged execution evidence are red lines.

## 10. Leakage, isolation, and safety review

The hidden original verifier reads only a bounded copied view; public inputs and helper identities are checked against frozen hashes. ZIP/XML payload safety is checked before parsing. Grading never changes the submission. Runtime dependencies and grader isolation are qualified separately.

## 11. Pilot plan

**Expected Gemma/OpenClaw failure modes:** For 259-editable-management-review-deck, inspect failures in Business result；Evidence and cross-artifact consistency, incorrect tool paths, missing durable state and incomplete output checks; these are hypotheses rather than unrun model results.

Previous Sol/Flash/Opus × Goose/NanoBot experiments used earlier package/runtime identities. Their scores remain historical. Native-v2 acceptance records live in the suite validation reports; a fresh frozen model pilot must not be claimed from replayed outputs. Every terminal outcome remains in the denominator.

## 12. Human validation status

**Status:** `not_required`

Current project policy uses automated acceptance evidence. This package does not claim human approval. User-assigned final task numbers and explicit integration are still pending.
