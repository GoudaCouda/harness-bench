# 264-node-record-processing-contract

## 1. Workflow identity

请修复工作区中完全合成的 Node.js 数据处理命令。只可修改 src/process.js；不得修改公开测试、package.json 或 package-lock.json，不得新增文件、网络依赖或后台进程。程序必须严格按 task.md 的固定 JSON 输入输出合同处理空输入、稳定排序、按类别汇总、重复编号、缺失字段、非法数值、错误 JSON 与错误 schema，并在固定大输入上同时满足正确结果和宽松资源上限。

## 2. Idea provenance

- **Adaptation:** NAMI Gold20 case_10 is adapted as 264-node-record-processing-contract: retain original fixtures and business invariants, replace deployment-bound execution with trusted service/code hooks and identity-bound grading receipts.
- **Private user logs:** No raw private conversations, credentials or attachments are included.
- **Synthetic-data statement:** Business entities and records are the original frozen synthetic fixtures.
- Protocol provenance: the HarnessBench task packaging protocol, <https://arxiv.org/abs/2605.27922> (this is not a source for private business fixtures).
- Source alias: `NAMI-GOLD20-case_10`.

## 3. Real-workflow justification

264-node-record-processing-contract: 任务同时要求严格 schema、确定性错误语义、稳定多键排序、整数金额汇总、线性聚合性能以及禁止仓库和运行时副作用；公开测试只覆盖少量行为。
The workflow requires dependent evidence and a durable deliverable, specifically 有效记录的稳定处理与聚合；无效输入的完整拒绝合同.

## 4. Agent-visible inputs

| Workspace path | Role |
|---|---|
| `package-lock.json` | Protected task evidence or public contract |
| `package.json` | Protected task evidence or public contract |
| `task.md` | Protected task evidence or public contract |

Public helpers are initial workspace files. Hidden tests, reference material and private service state are never agent mounts.

## 5. Hidden ground truth

For 264-node-record-processing-contract, the protected evidence `package-lock.json`, `package.json`, `task.md` fixes the admissible state and record invariants. The independent evaluator checks `src/process.js`; the runtime receipt is produced only after the agent stops, byte-bound to the candidate and frozen configuration. It cannot be authored by the candidate. Execution evidence is retained outside agent mounts.

## 6. Expected workflow

1. Inspect `package-lock.json`, `package.json`, `task.md`, resolve the entities and rule precedence before changing state.
2. Perform 有效记录的稳定处理与聚合；无效输入的完整拒绝合同 using the public inputs and tools; inspect intermediate state and verify the cross-record invariant.
3. Deliver `src/process.js`, verify the final state against the input contract, and remove temporary helpers from the delivery workspace.

## 7. Harness demands

multi_step_execution, evidence_grounding, output_contract, verification_behavior, safety_boundary. No model-specific solution interface.

## 8. Stressors and difficulty

**Plausible failure mode:** 264-node-record-processing-contract: an apparently valid artifact misses one coupled business condition in 有效记录的稳定处理与聚合；无效输入的完整拒绝合同; a plan without durable state earns no execution credit.

**Difficulty rationale:** 任务同时要求严格 schema、确定性错误语义、稳定多键排序、整数金额汇总、线性聚合性能以及禁止仓库和运行时副作用；公开测试只覆盖少量行为。

## 9. Oracle design

Pass threshold 0.8 with every core required. Core weights total 0.8, closure 0.2.

| Case | Weight | Core/gate | Meaning |
|---|---:|---|---|
| `valid_processing` | 0.4 | core | All of the coupled business checks must pass: functional_success_empty functional_success_stable_and_aggregate functional_success_unicode_codepoint_sort functional_success_inclusive_schema_boundaries |
| `invalid_processing` | 0.4 | core | All of the coupled business checks must pass: functional_error_malformed_json functional_error_wrong_top_schema functional_error_missing_records functional_error_top_level_array functional_error_records_not_array functional_error_record_not_object functional_error_missing_field functional_error_duplicate_trimmed_id functional_error_invalid_negative_amount functional_error_invalid_fractional_cents functional_error_unexpected_record_field functional_error_blank_trimmed_id functional_error_blank_trimmed_category functional_error_amount_above_maximum functional_error_priority_out_of_range functional_error_priority_not_integer functional_error_active_not_boolean functional_error_amount_not_number functional_error_record_count_above_maximum functional_error_input_above_two_mib |
| `complete_delivery` | 0.2 | closure | All original acceptance checks pass, including final-state and replay checks. |
| `protected_boundary` | 0.0 | gate | No tampering, forged execution evidence, unsafe paths or prohibited protected-state changes. |

Required final artifacts: `src/process.js`. Every check is deterministic. Missing/ordinary malformed output fails its scored block. Actual input/state tampering, unsafe links and forged execution evidence are red lines.

## 10. Leakage, isolation, and safety review

Candidate code is never imported by the hidden outcome evaluator. Code tasks retain separate resource-limited Docker candidate execution; service tasks retain private state and an allowlisted public tool interface. Receipt publication uses the standard runner environment_mutations callback after agent shutdown, including timeout/protocol/model errors. Cleanup is read-only with respect to the candidate. Original tests/reference material is not agent-visible. Public helpers must pass the repository leakage scan.

## 11. Pilot plan

**Expected Gemma/OpenClaw failure modes:** For 264-node-record-processing-contract, inspect failures in 有效记录的稳定处理与聚合；无效输入的完整拒绝合同, incorrect tool paths, missing durable state and incomplete output checks; these are hypotheses rather than unrun model results.

Previous Sol/Flash/Opus × Goose/NanoBot experiments used earlier package/runtime identities. Their scores remain historical. Native-v2 acceptance records live in the suite validation reports; a fresh frozen model pilot must not be claimed from replayed outputs. Every terminal outcome remains in the denominator.

## 12. Human validation status

**Status:** `not_required`

Current project policy uses automated acceptance evidence. This package does not claim human approval. User-assigned final task numbers and explicit integration are still pending.
