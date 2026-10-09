# 261-sales-analysis-formula-workbook

## 1. Workflow identity

根据固定销售明细和口径说明，交付一个可继续编辑的销售分析工作簿；完成明细清洗、逐行净销售额公式、区域与品类公式汇总、异常清单、关键指标和引用汇总数据的原生柱形图，同时保持输入不变且不留下额外产物。

## 2. Idea provenance

- **Adaptation:** NAMI Gold20 case_07 is adapted as 261-sales-analysis-formula-workbook: retain original fixtures and business invariants, replace deployment-bound execution with portable Office/artifact tools and independent hidden grading.
- **Private user logs:** No raw private conversations, credentials or attachments are included.
- **Synthetic-data statement:** Business entities and records are the original frozen synthetic fixtures.
- Protocol provenance: the HarnessBench task packaging protocol, <https://arxiv.org/abs/2605.27922> (this is not a source for private business fixtures).
- Source alias: `NAMI-GOLD20-case_07`.

## 3. Real-workflow justification

261-sales-analysis-formula-workbook: 需要从 20 条混合质量 CSV 中按优先级清洗，构造 50 个可编辑公式、两个汇总、异常清单和跨表原生图表，并在结束前清理中间文件。
The workflow requires dependent evidence and a durable deliverable, specifically Business result；Evidence and cross-artifact consistency.

## 4. Agent-visible inputs

| Workspace path | Role |
|---|---|
| `input/metric_rules.md` | Protected task evidence or public contract |
| `input/sales_records.csv` | Protected task evidence or public contract |
| `task.md` | Protected task evidence or public contract |

Public helpers are initial workspace files. Hidden tests, reference material and private service state are never agent mounts.

## 5. Hidden ground truth

For 261-sales-analysis-formula-workbook, the protected evidence `input/metric_rules.md`, `input/sales_records.csv`, `task.md` fixes the admissible state and record invariants. The independent evaluator checks `output/sales_analysis.xlsx`; original verifier checks, fixture hashes and business-group mapping are frozen under tests/ground_truth; no candidate-authored claim replaces the hidden oracle.

## 6. Expected workflow

1. Inspect `input/metric_rules.md`, `input/sales_records.csv`, `task.md`, resolve the entities and rule precedence before changing state.
2. Perform Business result；Evidence and cross-artifact consistency using the public inputs and tools; inspect intermediate state and verify the cross-record invariant.
3. Deliver `output/sales_analysis.xlsx`, verify the final state against the input contract, and remove temporary helpers from the delivery workspace.

## 7. Harness demands

multi_step_execution, evidence_grounding, output_contract, verification_behavior. No model-specific solution interface.

## 8. Stressors and difficulty

**Plausible failure mode:** 261-sales-analysis-formula-workbook: an apparently valid artifact misses one coupled business condition in Business result；Evidence and cross-artifact consistency; a plan without durable state earns no execution credit.

**Difficulty rationale:** 需要从 20 条混合质量 CSV 中按优先级清洗，构造 50 个可编辑公式、两个汇总、异常清单和跨表原生图表，并在结束前清理中间文件。

## 9. Oracle design

Pass threshold 0.8 with every core required. Core weights total 0.8, closure 0.2.

| Case | Weight | Core/gate | Meaning |
|---|---:|---|---|
| `business_result` | 0.4 | core | Original result checks: detail_cleaning detail_formulas region_summary category_summary |
| `evidence_consistency` | 0.4 | core | Original evidence checks: anomaly_list dashboard_kpis chart_binding |
| `complete_delivery` | 0.2 | closure | All applicable original checks pass, including format, required structure and final-state consistency. |
| `protected_workspace` | 0.0 | gate | Frozen inputs and tools are unchanged; no extra files, unsafe paths, symlinks or special nodes. |

Required final artifacts: `output/sales_analysis.xlsx`. Every check is deterministic. Missing/ordinary malformed output fails its scored block. Actual input/state tampering, unsafe links and forged execution evidence are red lines.

## 10. Leakage, isolation, and safety review

The hidden original verifier reads only a bounded copied view; public inputs and helper identities are checked against frozen hashes. ZIP/XML payload safety is checked before parsing. Grading never changes the submission. Runtime dependencies and grader isolation are qualified separately.

## 11. Pilot plan

**Expected Gemma/OpenClaw failure modes:** For 261-sales-analysis-formula-workbook, inspect failures in Business result；Evidence and cross-artifact consistency, incorrect tool paths, missing durable state and incomplete output checks; these are hypotheses rather than unrun model results.

Previous Sol/Flash/Opus × Goose/NanoBot experiments used earlier package/runtime identities. Their scores remain historical. Native-v2 acceptance records live in the suite validation reports; a fresh frozen model pilot must not be claimed from replayed outputs. Every terminal outcome remains in the denominator.

## 12. Human validation status

**Status:** `not_required`

Current project policy uses automated acceptance evidence. This package does not claim human approval. User-assigned final task numbers and explicit integration are still pending.
