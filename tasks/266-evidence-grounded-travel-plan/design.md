# 266-evidence-grounded-travel-plan

## 1. Workflow identity

请仅依据工作区 input 目录中的固定旅行快照、用户偏好和引用索引，为两位旅客比较澄江市往返海岚市的交通、住宿与活动组合。严格满足预算、日期、时间、评分、距离、早餐、退订和行李约束，按照偏好文件中的确定性规则选出唯一推荐。请在 output 目录交付 recommendation.json、comparison.csv 和中文 report.md；费用必须逐项可复算，推荐方案及关键结论必须引用能够精确回连的引用编号。不得访问实时网站、修改输入或写入额外文件。

## 2. Idea provenance

- **Adaptation:** NAMI Gold20 case_12 is adapted as 266-evidence-grounded-travel-plan: retain original fixtures and business invariants, replace deployment-bound execution with portable Office/artifact tools and independent hidden grading.
- **Private user logs:** No raw private conversations, credentials or attachments are included.
- **Synthetic-data statement:** Business entities and records are the original frozen synthetic fixtures.
- Protocol provenance: the HarnessBench task packaging protocol, <https://arxiv.org/abs/2605.27922> (this is not a source for private business fixtures).
- Source alias: `NAMI-GOLD20-case_12`.

## 3. Real-workflow justification

266-evidence-grounded-travel-plan: 需要跨四类候选应用多项硬约束，复算不同计价字段，比较多个可行组合，并保持机器可验的引用闭环。
The workflow requires dependent evidence and a durable deliverable, specifically Business result；Evidence and cross-artifact consistency.

## 4. Agent-visible inputs

| Workspace path | Role |
|---|---|
| `input/citation_index.json` | Protected task evidence or public contract |
| `input/preferences.json` | Protected task evidence or public contract |
| `input/travel_snapshot.json` | Protected task evidence or public contract |

Public helpers are initial workspace files. Hidden tests, reference material and private service state are never agent mounts.

## 5. Hidden ground truth

For 266-evidence-grounded-travel-plan, the protected evidence `input/citation_index.json`, `input/preferences.json`, `input/travel_snapshot.json` fixes the admissible state and record invariants. The independent evaluator checks `output/recommendation.json`, `output/comparison.csv`, `output/report.md`; original verifier checks, fixture hashes and business-group mapping are frozen under tests/ground_truth; no candidate-authored claim replaces the hidden oracle.

## 6. Expected workflow

1. Inspect `input/citation_index.json`, `input/preferences.json`, `input/travel_snapshot.json`, resolve the entities and rule precedence before changing state.
2. Perform Business result；Evidence and cross-artifact consistency using the public inputs and tools; inspect intermediate state and verify the cross-record invariant.
3. Deliver `output/recommendation.json`, `output/comparison.csv`, `output/report.md`, verify the final state against the input contract, and remove temporary helpers from the delivery workspace.

## 7. Harness demands

multi_step_execution, evidence_grounding, output_contract, verification_behavior. No model-specific solution interface.

## 8. Stressors and difficulty

**Plausible failure mode:** 266-evidence-grounded-travel-plan: an apparently valid artifact misses one coupled business condition in Business result；Evidence and cross-artifact consistency; a plan without durable state earns no execution credit.

**Difficulty rationale:** 需要跨四类候选应用多项硬约束，复算不同计价字段，比较多个可行组合，并保持机器可验的引用闭环。

## 9. Oracle design

Pass threshold 0.8 with every core required. Core weights total 0.8, closure 0.2.

| Case | Weight | Core/gate | Meaning |
|---|---:|---|---|
| `business_result` | 0.4 | core | Original result checks: optimal_selection cost_recalculation feasible_comparison |
| `evidence_consistency` | 0.4 | core | Original evidence checks: recommendation_citations comparison_consistency report_evidence_alignment |
| `complete_delivery` | 0.2 | closure | All applicable original checks pass, including format, required structure and final-state consistency. |
| `protected_workspace` | 0.0 | gate | Frozen inputs and tools are unchanged; no extra files, unsafe paths, symlinks or special nodes. |

Required final artifacts: `output/recommendation.json`, `output/comparison.csv`, `output/report.md`. Every check is deterministic. Missing/ordinary malformed output fails its scored block. Actual input/state tampering, unsafe links and forged execution evidence are red lines.

## 10. Leakage, isolation, and safety review

The hidden original verifier reads only a bounded copied view; public inputs and helper identities are checked against frozen hashes. ZIP/XML payload safety is checked before parsing. Grading never changes the submission. Runtime dependencies and grader isolation are qualified separately.

## 11. Pilot plan

**Expected Gemma/OpenClaw failure modes:** For 266-evidence-grounded-travel-plan, inspect failures in Business result；Evidence and cross-artifact consistency, incorrect tool paths, missing durable state and incomplete output checks; these are hypotheses rather than unrun model results.

Previous Sol/Flash/Opus × Goose/NanoBot experiments used earlier package/runtime identities. Their scores remain historical. Native-v2 acceptance records live in the suite validation reports; a fresh frozen model pilot must not be claimed from replayed outputs. Every terminal outcome remains in the denominator.

## 12. Human validation status

**Status:** `not_required`

Current project policy uses automated acceptance evidence. This package does not claim human approval. User-assigned final task numbers and explicit integration are still pending.
