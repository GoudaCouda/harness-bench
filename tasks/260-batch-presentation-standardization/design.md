# 260-batch-presentation-standardization

## 1. Workflow identity

将输入目录中的三份演示稿按统一模板批量规范为 16:9：统一 Noto Sans SC 字体、字号、颜色、页脚、背景和四类对象的位置与尺寸。输出到 outputs/standardized 下的同名文件；不得覆盖输入，不得丢页、增页或修改标题与正文文案，也不得创建额外文件。页脚属于格式元数据，按样式表替换。

## 2. Idea provenance

- **Adaptation:** NAMI Gold20 case_06 is adapted as 260-batch-presentation-standardization: retain original fixtures and business invariants, replace deployment-bound execution with portable Office/artifact tools and independent hidden grading.
- **Private user logs:** No raw private conversations, credentials or attachments are included.
- **Synthetic-data statement:** Business entities and records are the original frozen synthetic fixtures.
- Protocol provenance: the HarnessBench task packaging protocol, <https://arxiv.org/abs/2605.27922> (this is not a source for private business fixtures).
- Source alias: `NAMI-GOLD20-case_06`.

## 3. Real-workflow justification

260-batch-presentation-standardization: 需要理解批量映射、检查三份异构比例演示稿、逐份调用工具，并同时满足内容保持、格式统一和副作用约束。
The workflow requires dependent evidence and a durable deliverable, specifically Business result；Evidence and cross-artifact consistency.

## 4. Agent-visible inputs

| Workspace path | Role |
|---|---|
| `inputs/brand_template.pptx` | Protected task evidence or public contract |
| `inputs/decks/market_brief.pptx` | Protected task evidence or public contract |
| `inputs/decks/project_update.pptx` | Protected task evidence or public contract |
| `inputs/decks/service_review.pptx` | Protected task evidence or public contract |
| `inputs/style_map.json` | Protected task evidence or public contract |
| `task.md` | Protected task evidence or public contract |

Public helpers are initial workspace files. Hidden tests, reference material and private service state are never agent mounts.

## 5. Hidden ground truth

For 260-batch-presentation-standardization, the protected evidence `inputs/brand_template.pptx`, `inputs/decks/market_brief.pptx`, `inputs/decks/project_update.pptx`, `inputs/decks/service_review.pptx`, `inputs/style_map.json`, `task.md` fixes the admissible state and record invariants. The independent evaluator checks `outputs/standardized/market_brief.pptx`, `outputs/standardized/project_update.pptx`, `outputs/standardized/service_review.pptx`; original verifier checks, fixture hashes and business-group mapping are frozen under tests/ground_truth; no candidate-authored claim replaces the hidden oracle.

## 6. Expected workflow

1. Inspect `inputs/brand_template.pptx`, `inputs/decks/market_brief.pptx`, `inputs/decks/project_update.pptx`, `inputs/decks/service_review.pptx`, `inputs/style_map.json`, `task.md`, resolve the entities and rule precedence before changing state.
2. Perform Business result；Evidence and cross-artifact consistency using the public inputs and tools; inspect intermediate state and verify the cross-record invariant.
3. Deliver `outputs/standardized/market_brief.pptx`, `outputs/standardized/project_update.pptx`, `outputs/standardized/service_review.pptx`, verify the final state against the input contract, and remove temporary helpers from the delivery workspace.

## 7. Harness demands

multi_step_execution, evidence_grounding, output_contract, verification_behavior. No model-specific solution interface.

## 8. Stressors and difficulty

**Plausible failure mode:** 260-batch-presentation-standardization: an apparently valid artifact misses one coupled business condition in Business result；Evidence and cross-artifact consistency; a plan without durable state earns no execution credit.

**Difficulty rationale:** 需要理解批量映射、检查三份异构比例演示稿、逐份调用工具，并同时满足内容保持、格式统一和副作用约束。

## 9. Oracle design

Pass threshold 0.8 with every core required. Core weights total 0.8, closure 0.2.

| Case | Weight | Core/gate | Meaning |
|---|---:|---|---|
| `business_result` | 0.4 | core | Original result checks: slide_and_content_preservation |
| `evidence_consistency` | 0.4 | core | Original evidence checks: uniform_typography_and_color uniform_footer canvas_alignment_and_geometry |
| `complete_delivery` | 0.2 | closure | All applicable original checks pass, including format, required structure and final-state consistency. |
| `protected_workspace` | 0.0 | gate | Frozen inputs and tools are unchanged; no extra files, unsafe paths, symlinks or special nodes. |

Required final artifacts: `outputs/standardized/market_brief.pptx`, `outputs/standardized/project_update.pptx`, `outputs/standardized/service_review.pptx`. Every check is deterministic. Missing/ordinary malformed output fails its scored block. Actual input/state tampering, unsafe links and forged execution evidence are red lines.

## 10. Leakage, isolation, and safety review

The hidden original verifier reads only a bounded copied view; public inputs and helper identities are checked against frozen hashes. ZIP/XML payload safety is checked before parsing. Grading never changes the submission. Runtime dependencies and grader isolation are qualified separately.

## 11. Pilot plan

**Expected Gemma/OpenClaw failure modes:** For 260-batch-presentation-standardization, inspect failures in Business result；Evidence and cross-artifact consistency, incorrect tool paths, missing durable state and incomplete output checks; these are hypotheses rather than unrun model results.

Previous Sol/Flash/Opus × Goose/NanoBot experiments used earlier package/runtime identities. Their scores remain historical. Native-v2 acceptance records live in the suite validation reports; a fresh frozen model pilot must not be claimed from replayed outputs. Every terminal outcome remains in the denominator.

## 12. Human validation status

**Status:** `not_required`

Current project policy uses automated acceptance evidence. This package does not claim human approval. User-assigned final task numbers and explicit integration are still pending.
