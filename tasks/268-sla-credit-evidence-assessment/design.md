# 268-sla-credit-evidence-assessment

## 1. Workflow identity

仅使用已验证、目标区域内的 2025-Q3 非计划中断记录，按合成云服务合同逐事件扣除宽限后核算服务信用金，应用重复故障倍率，并按 P1 事件数和合格总分钟判定整改级别。精确排除计划维护、未验证记录和非目标区域记录，不使用非约束性销售预测。将结果写入 outputs/sla_credit_assessment.json，不修改初始资产或创建额外路径。

## 2. Idea provenance

- **Adaptation:** NAMI Gold20 case_14 is adapted as 268-sla-credit-evidence-assessment: retain original fixtures and business invariants, replace deployment-bound execution with portable Office/artifact tools and independent hidden grading.
- **Private user logs:** No raw private conversations, credentials or attachments are included.
- **Synthetic-data statement:** Business entities and records are the original frozen synthetic fixtures.
- Protocol provenance: the HarnessBench task packaging protocol, <https://arxiv.org/abs/2605.27922> (this is not a source for private business fixtures).
- Source alias: `NAMI-GOLD20-case_14`.

## 3. Real-workflow justification

268-sla-credit-evidence-assessment: 任务需在六条多类型事件中精确筛选三条合格记录，逐条扣除宽限，完成整数金额与有理数倍率计算，并同时判定整改规则、证据集和精确排除集。
The workflow requires dependent evidence and a durable deliverable, specifically Business result；Evidence and cross-artifact consistency.

## 4. Agent-visible inputs

| Workspace path | Role |
|---|---|
| `TASK.md` | Protected task evidence or public contract |
| `inputs/nonbinding_sales_projection.json` | Protected task evidence or public contract |
| `inputs/output_contract.json` | Protected task evidence or public contract |
| `inputs/region_registry.csv` | Protected task evidence or public contract |
| `inputs/sla_rules.json` | Protected task evidence or public contract |

Public helpers are initial workspace files. Hidden tests, reference material and private service state are never agent mounts.

## 5. Hidden ground truth

For 268-sla-credit-evidence-assessment, the protected evidence `TASK.md`, `inputs/nonbinding_sales_projection.json`, `inputs/output_contract.json`, `inputs/region_registry.csv`, `inputs/sla_rules.json` fixes the admissible state and record invariants. The independent evaluator checks `outputs/sla_credit_assessment.json`; original verifier checks, fixture hashes and business-group mapping are frozen under tests/ground_truth; no candidate-authored claim replaces the hidden oracle.

## 6. Expected workflow

1. Inspect `TASK.md`, `inputs/nonbinding_sales_projection.json`, `inputs/output_contract.json`, `inputs/region_registry.csv`, `inputs/sla_rules.json`, resolve the entities and rule precedence before changing state.
2. Perform Business result；Evidence and cross-artifact consistency using the public inputs and tools; inspect intermediate state and verify the cross-record invariant.
3. Deliver `outputs/sla_credit_assessment.json`, verify the final state against the input contract, and remove temporary helpers from the delivery workspace.

## 7. Harness demands

multi_step_execution, evidence_grounding, output_contract, verification_behavior. No model-specific solution interface.

## 8. Stressors and difficulty

**Plausible failure mode:** 268-sla-credit-evidence-assessment: an apparently valid artifact misses one coupled business condition in Business result；Evidence and cross-artifact consistency; a plan without durable state earns no execution credit.

**Difficulty rationale:** 任务需在六条多类型事件中精确筛选三条合格记录，逐条扣除宽限，完成整数金额与有理数倍率计算，并同时判定整改规则、证据集和精确排除集。

## 9. Oracle design

Pass threshold 0.8 with every core required. Core weights total 0.8, closure 0.2.

| Case | Weight | Core/gate | Meaning |
|---|---:|---|---|
| `business_result` | 0.4 | core | Original result checks: eligible_event_set eligible_minutes_by_event eligible_aggregate credit_calculation |
| `evidence_consistency` | 0.4 | core | Original evidence checks: credit_rule_evidence remediation_rule excluded_records_exact ignored_sources_exact |
| `complete_delivery` | 0.2 | closure | All applicable original checks pass, including format, required structure and final-state consistency. |
| `protected_workspace` | 0.0 | gate | Frozen inputs and tools are unchanged; no extra files, unsafe paths, symlinks or special nodes. |

Required final artifacts: `outputs/sla_credit_assessment.json`. Every check is deterministic. Missing/ordinary malformed output fails its scored block. Actual input/state tampering, unsafe links and forged execution evidence are red lines.

## 10. Leakage, isolation, and safety review

The hidden original verifier reads only a bounded copied view; public inputs and helper identities are checked against frozen hashes. ZIP/XML payload safety is checked before parsing. Grading never changes the submission. Runtime dependencies and grader isolation are qualified separately.

## 11. Pilot plan

**Expected Gemma/OpenClaw failure modes:** For 268-sla-credit-evidence-assessment, inspect failures in Business result；Evidence and cross-artifact consistency, incorrect tool paths, missing durable state and incomplete output checks; these are hypotheses rather than unrun model results.

Previous Sol/Flash/Opus × Goose/NanoBot experiments used earlier package/runtime identities. Their scores remain historical. Native-v2 acceptance records live in the suite validation reports; a fresh frozen model pilot must not be claimed from replayed outputs. Every terminal outcome remains in the denominator.

## 12. Human validation status

**Status:** `not_required`

Current project policy uses automated acceptance evidence. This package does not claim human approval. User-assigned final task numbers and explicit integration are still pending.
