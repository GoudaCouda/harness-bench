# 255-construction-implementation-plan

## 1. Workflow identity

请在离线工作区中阅读 inputs/ 下的合成招标要求、公司资质、评审标准、编制约束和 DOCX 模板，编制一份可编辑的施工实施方案。输出文件必须保存为 outputs/新桥市综合管廊监控升级项目_施工实施方案.docx。方案须准确覆盖项目事实、人员与合成资格信息、设备数量、六个里程碑、质量与安全目标、测试验收和质保安排；使用模板内的标题、一级标题、二级标题和表格样式，并用表格呈现关键信息。不得修改 inputs/，不得生成指定输出之外的文件，不得访问网络，也不得虚构材料未提供的品牌、奖项、业绩或证书。

## 2. Idea provenance

- **Adaptation:** NAMI Gold20 case_01 is adapted as 255-construction-implementation-plan: retain original fixtures and business invariants, replace deployment-bound execution with portable Office/artifact tools and independent hidden grading.
- **Private user logs:** No raw private conversations, credentials or attachments are included.
- **Synthetic-data statement:** Business entities and records are the original frozen synthetic fixtures.
- Protocol provenance: the HarnessBench task packaging protocol, <https://arxiv.org/abs/2605.27922> (this is not a source for private business fixtures).
- Source alias: `NAMI-GOLD20-case_01`.

## 3. Real-workflow justification

255-construction-implementation-plan: 需要综合五种输入、保持模板结构、准确引用多组事实和里程碑、生成可编辑 Office 成品，并同时满足输入不可改写与文件作用域约束。
The workflow requires dependent evidence and a durable deliverable, specifically Business result；Evidence and cross-artifact consistency.

## 4. Agent-visible inputs

| Workspace path | Role |
|---|---|
| `inputs/01_招标要求.md` | Protected task evidence or public contract |
| `inputs/02_公司资质.json` | Protected task evidence or public contract |
| `inputs/03_评审标准.csv` | Protected task evidence or public contract |
| `inputs/04_编制约束.md` | Protected task evidence or public contract |
| `inputs/05_实施方案模板.docx` | Protected task evidence or public contract |

Public helpers are initial workspace files. Hidden tests, reference material and private service state are never agent mounts.

## 5. Hidden ground truth

For 255-construction-implementation-plan, the protected evidence `inputs/01_招标要求.md`, `inputs/02_公司资质.json`, `inputs/03_评审标准.csv`, `inputs/04_编制约束.md`, `inputs/05_实施方案模板.docx` fixes the admissible state and record invariants. The independent evaluator checks `outputs/新桥市综合管廊监控升级项目_施工实施方案.docx`; original verifier checks, fixture hashes and business-group mapping are frozen under tests/ground_truth; no candidate-authored claim replaces the hidden oracle.

## 6. Expected workflow

1. Inspect `inputs/01_招标要求.md`, `inputs/02_公司资质.json`, `inputs/03_评审标准.csv`, `inputs/04_编制约束.md`, `inputs/05_实施方案模板.docx`, resolve the entities and rule precedence before changing state.
2. Perform Business result；Evidence and cross-artifact consistency using the public inputs and tools; inspect intermediate state and verify the cross-record invariant.
3. Deliver `outputs/新桥市综合管廊监控升级项目_施工实施方案.docx`, verify the final state against the input contract, and remove temporary helpers from the delivery workspace.

## 7. Harness demands

multi_step_execution, evidence_grounding, output_contract, verification_behavior. No model-specific solution interface.

## 8. Stressors and difficulty

**Plausible failure mode:** 255-construction-implementation-plan: an apparently valid artifact misses one coupled business condition in Business result；Evidence and cross-artifact consistency; a plan without durable state earns no execution credit.

**Difficulty rationale:** 需要综合五种输入、保持模板结构、准确引用多组事实和里程碑、生成可编辑 Office 成品，并同时满足输入不可改写与文件作用域约束。

## 9. Oracle design

Pass threshold 0.8 with every core required. Core weights total 0.8, closure 0.2.

| Case | Weight | Core/gate | Meaning |
|---|---:|---|---|
| `business_result` | 0.4 | core | Original result checks: check_fact_anchors check_no_fabrication |
| `evidence_consistency` | 0.4 | core | Original evidence checks: check_required_sections check_tables_and_styles |
| `complete_delivery` | 0.2 | closure | All applicable original checks pass, including format, required structure and final-state consistency. |
| `protected_workspace` | 0.0 | gate | Frozen inputs and tools are unchanged; no extra files, unsafe paths, symlinks or special nodes. |

Required final artifacts: `outputs/新桥市综合管廊监控升级项目_施工实施方案.docx`. Every check is deterministic. Missing/ordinary malformed output fails its scored block. Actual input/state tampering, unsafe links and forged execution evidence are red lines.

## 10. Leakage, isolation, and safety review

The hidden original verifier reads only a bounded copied view; public inputs and helper identities are checked against frozen hashes. ZIP/XML payload safety is checked before parsing. Grading never changes the submission. Runtime dependencies and grader isolation are qualified separately.

## 11. Pilot plan

**Expected Gemma/OpenClaw failure modes:** For 255-construction-implementation-plan, inspect failures in Business result；Evidence and cross-artifact consistency, incorrect tool paths, missing durable state and incomplete output checks; these are hypotheses rather than unrun model results.

Previous Sol/Flash/Opus × Goose/NanoBot experiments used earlier package/runtime identities. Their scores remain historical. Native-v2 acceptance records live in the suite validation reports; a fresh frozen model pilot must not be claimed from replayed outputs. Every terminal outcome remains in the denominator.

## 12. Human validation status

**Status:** `not_required`

Current project policy uses automated acceptance evidence. This package does not claim human approval. User-assigned final task numbers and explicit integration are still pending.
