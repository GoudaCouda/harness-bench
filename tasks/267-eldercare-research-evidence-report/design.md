# 267-eldercare-research-evidence-report

## 1. Workflow identity

请只使用 input/ 中固定的中英文资料，完成《岚州市养老服务供需与行动建议》，并保存为 output/养老行业研究报告.md。严格沿用模板六个章节；关键指标表必须给出 2025/2027 人口、复合增长率、三类规划服务量、三类供给缺口、简单回收期和三类缺口量级成本，说明计算口径并逐项引用。证据链必须区分事实、规划情景和限制；建议必须有证据、优先级和实施边界。S08 已废止，不得作为有效证据。不得把偏好调查写成精确需求，不得宣称试点证明因果、保证收益或预算已经获批，也不得建议投机性地产收购。禁止联网，只能修改指定输出文件。

## 2. Idea provenance

- **Adaptation:** NAMI Gold20 case_13 is adapted as 267-eldercare-research-evidence-report: retain original fixtures and business invariants, replace deployment-bound execution with portable Office/artifact tools and independent hidden grading.
- **Private user logs:** No raw private conversations, credentials or attachments are included.
- **Synthetic-data statement:** Business entities and records are the original frozen synthetic fixtures.
- Protocol provenance: the HarnessBench task packaging protocol, <https://arxiv.org/abs/2605.27922> (this is not a source for private business fixtures).
- Source alias: `NAMI-GOLD20-case_13`.

## 3. Real-workflow justification

267-eldercare-research-evidence-report: 需要跨八份中英文资料辨识有效版本，完成十三项数值计算、证据链、政策边界和无因果过度外推。
The workflow requires dependent evidence and a durable deliverable, specifically Business result；Evidence and cross-artifact consistency.

## 4. Agent-visible inputs

| Workspace path | Role |
|---|---|
| `input/corpus/S01_demographics_zh.md` | Protected task evidence or public contract |
| `input/corpus/S02_needs_survey_zh.md` | Protected task evidence or public contract |
| `input/corpus/S03_supply_registry_zh.csv` | Protected task evidence or public contract |
| `input/corpus/S04_policy_zh.md` | Protected task evidence or public contract |
| `input/corpus/S05_unit_costs_zh.md` | Protected task evidence or public contract |
| `input/corpus/S06_pilot_en.md` | Protected task evidence or public contract |
| `input/corpus/S07_audit_en.md` | Protected task evidence or public contract |
| `input/corpus/S08_superseded_memo_zh.md` | Protected task evidence or public contract |

Public helpers are initial workspace files. Hidden tests, reference material and private service state are never agent mounts.

## 5. Hidden ground truth

For 267-eldercare-research-evidence-report, the protected evidence `input/corpus/S01_demographics_zh.md`, `input/corpus/S02_needs_survey_zh.md`, `input/corpus/S03_supply_registry_zh.csv`, `input/corpus/S04_policy_zh.md`, `input/corpus/S05_unit_costs_zh.md`, `input/corpus/S06_pilot_en.md`, `input/corpus/S07_audit_en.md`, `input/corpus/S08_superseded_memo_zh.md` fixes the admissible state and record invariants. The independent evaluator checks `output/养老行业研究报告.md`; original verifier checks, fixture hashes and business-group mapping are frozen under tests/ground_truth; no candidate-authored claim replaces the hidden oracle.

## 6. Expected workflow

1. Inspect `input/corpus/S01_demographics_zh.md`, `input/corpus/S02_needs_survey_zh.md`, `input/corpus/S03_supply_registry_zh.csv`, `input/corpus/S04_policy_zh.md`, `input/corpus/S05_unit_costs_zh.md`, `input/corpus/S06_pilot_en.md`, `input/corpus/S07_audit_en.md`, `input/corpus/S08_superseded_memo_zh.md`, resolve the entities and rule precedence before changing state.
2. Perform Business result；Evidence and cross-artifact consistency using the public inputs and tools; inspect intermediate state and verify the cross-record invariant.
3. Deliver `output/养老行业研究报告.md`, verify the final state against the input contract, and remove temporary helpers from the delivery workspace.

## 7. Harness demands

multi_step_execution, evidence_grounding, output_contract, verification_behavior. No model-specific solution interface.

## 8. Stressors and difficulty

**Plausible failure mode:** 267-eldercare-research-evidence-report: an apparently valid artifact misses one coupled business condition in Business result；Evidence and cross-artifact consistency; a plan without durable state earns no execution credit.

**Difficulty rationale:** 需要跨八份中英文资料辨识有效版本，完成十三项数值计算、证据链、政策边界和无因果过度外推。

## 9. Oracle design

Pass threshold 0.8 with every core required. Core weights total 0.8, closure 0.2.

| Case | Weight | Core/gate | Meaning |
|---|---:|---|---|
| `business_result` | 0.4 | core | Original result checks: numeric_consistency evidence_chain summary_evidence |
| `evidence_consistency` | 0.4 | core | Original evidence checks: actionable_recommendations limitations_coverage bibliography_traceability unsupported_or_forbidden_claims |
| `complete_delivery` | 0.2 | closure | All applicable original checks pass, including format, required structure and final-state consistency. |
| `protected_workspace` | 0.0 | gate | Frozen inputs and tools are unchanged; no extra files, unsafe paths, symlinks or special nodes. |

Required final artifacts: `output/养老行业研究报告.md`. Every check is deterministic. Missing/ordinary malformed output fails its scored block. Actual input/state tampering, unsafe links and forged execution evidence are red lines.

## 10. Leakage, isolation, and safety review

The hidden original verifier reads only a bounded copied view; public inputs and helper identities are checked against frozen hashes. ZIP/XML payload safety is checked before parsing. Grading never changes the submission. Runtime dependencies and grader isolation are qualified separately.

## 11. Pilot plan

**Expected Gemma/OpenClaw failure modes:** For 267-eldercare-research-evidence-report, inspect failures in Business result；Evidence and cross-artifact consistency, incorrect tool paths, missing durable state and incomplete output checks; these are hypotheses rather than unrun model results.

Previous Sol/Flash/Opus × Goose/NanoBot experiments used earlier package/runtime identities. Their scores remain historical. Native-v2 acceptance records live in the suite validation reports; a fresh frozen model pilot must not be claimed from replayed outputs. Every terminal outcome remains in the denominator.

## 12. Human validation status

**Status:** `not_required`

Current project policy uses automated acceptance evidence. This package does not claim human approval. User-assigned final task numbers and explicit integration are still pending.
