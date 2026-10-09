# 257-equipment-inspection-word-form

## 1. Workflow identity

根据完全合成的医院抬头、四台监控系统设备台账和巡检规范，生成一个可编辑、可打印、可填写的 Word 巡检记录表。每台设备独占一页，准确映射设备字段和巡检项目，并保留状态、问题处理、签字及日期填写位。只交付指定 DOCX，不得修改输入或加入真实敏感信息。

## 2. Idea provenance

- **Adaptation:** NAMI Gold20 case_03 is adapted as 257-equipment-inspection-word-form: retain original fixtures and business invariants, replace deployment-bound execution with portable Office/artifact tools and independent hidden grading.
- **Private user logs:** No raw private conversations, credentials or attachments are included.
- **Synthetic-data statement:** Business entities and records are the original frozen synthetic fixtures.
- Protocol provenance: the HarnessBench task packaging protocol, <https://arxiv.org/abs/2605.27922> (this is not a source for private business fixtures).
- Source alias: `NAMI-GOLD20-case_03`.

## 3. Real-workflow justification

257-equipment-inspection-word-form: 需要联合读取三类输入、准确映射四台异构设备、形成二十条巡检项并生成四页可编辑表单；字段串行和副作用均可被确定性识别。
The workflow requires dependent evidence and a durable deliverable, specifically Business result；Evidence and cross-artifact consistency.

## 4. Agent-visible inputs

| Workspace path | Role |
|---|---|
| `input/equipment_registry.json` | Protected task evidence or public contract |
| `input/hospital_header.json` | Protected task evidence or public contract |
| `input/inspection_standard.json` | Protected task evidence or public contract |
| `task/instruction.md` | Protected task evidence or public contract |
| `tools/tool_contract.json` | Protected task evidence or public contract |

Public helpers are initial workspace files. Hidden tests, reference material and private service state are never agent mounts.

## 5. Hidden ground truth

For 257-equipment-inspection-word-form, the protected evidence `input/equipment_registry.json`, `input/hospital_header.json`, `input/inspection_standard.json`, `task/instruction.md`, `tools/tool_contract.json` fixes the admissible state and record invariants. The independent evaluator checks `output/monitoring_equipment_inspection_form.docx`; original verifier checks, fixture hashes and business-group mapping are frozen under tests/ground_truth; no candidate-authored claim replaces the hidden oracle.

## 6. Expected workflow

1. Inspect `input/equipment_registry.json`, `input/hospital_header.json`, `input/inspection_standard.json`, `task/instruction.md`, `tools/tool_contract.json`, resolve the entities and rule precedence before changing state.
2. Perform Business result；Evidence and cross-artifact consistency using the public inputs and tools; inspect intermediate state and verify the cross-record invariant.
3. Deliver `output/monitoring_equipment_inspection_form.docx`, verify the final state against the input contract, and remove temporary helpers from the delivery workspace.

## 7. Harness demands

multi_step_execution, evidence_grounding, output_contract, verification_behavior. No model-specific solution interface.

## 8. Stressors and difficulty

**Plausible failure mode:** 257-equipment-inspection-word-form: an apparently valid artifact misses one coupled business condition in Business result；Evidence and cross-artifact consistency; a plan without durable state earns no execution credit.

**Difficulty rationale:** 需要联合读取三类输入、准确映射四台异构设备、形成二十条巡检项并生成四页可编辑表单；字段串行和副作用均可被确定性识别。

## 9. Oracle design

Pass threshold 0.8 with every core required. Core weights total 0.8, closure 0.2.

| Case | Weight | Core/gate | Meaning |
|---|---:|---|---|
| `business_result` | 0.4 | core | Original result checks: device_mapping inspection_rows |
| `evidence_consistency` | 0.4 | core | Original evidence checks: fillable_areas page_layout privacy_boundary |
| `complete_delivery` | 0.2 | closure | All applicable original checks pass, including format, required structure and final-state consistency. |
| `protected_workspace` | 0.0 | gate | Frozen inputs and tools are unchanged; no extra files, unsafe paths, symlinks or special nodes. |

Required final artifacts: `output/monitoring_equipment_inspection_form.docx`. Every check is deterministic. Missing/ordinary malformed output fails its scored block. Actual input/state tampering, unsafe links and forged execution evidence are red lines.

## 10. Leakage, isolation, and safety review

The hidden original verifier reads only a bounded copied view; public inputs and helper identities are checked against frozen hashes. ZIP/XML payload safety is checked before parsing. Grading never changes the submission. Runtime dependencies and grader isolation are qualified separately.

## 11. Pilot plan

**Expected Gemma/OpenClaw failure modes:** For 257-equipment-inspection-word-form, inspect failures in Business result；Evidence and cross-artifact consistency, incorrect tool paths, missing durable state and incomplete output checks; these are hypotheses rather than unrun model results.

Previous Sol/Flash/Opus × Goose/NanoBot experiments used earlier package/runtime identities. Their scores remain historical. Native-v2 acceptance records live in the suite validation reports; a fresh frozen model pilot must not be claimed from replayed outputs. Every terminal outcome remains in the denominator.

## 12. Human validation status

**Status:** `not_required`

Current project policy uses automated acceptance evidence. This package does not claim human approval. User-assigned final task numbers and explicit integration are still pending.
