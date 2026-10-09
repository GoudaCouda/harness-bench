# 265-weekly-operations-brief-generator

## 1. Workflow identity

请编写一个可重复运行的 Python 脚本，读取 input/weekly_operations.csv、input/metric_definitions.json 和 input/brief_template.md，生成 output/summary.json 与 output/weekly_brief.md。指标、环比、风险和行动项必须遵循给定口径；脚本必须能处理同格式的其他周期和渠道，两次运行产物字节完全一致。CSV 异常时必须在执行时限内主动非零退出：若 output/ 原本为空，不得留下任何文件；若其中已有一组完整正确产物，两份旧产物都必须逐字节保持不变。除两份输出外，不得修改输入、新建持久化缓存或向 workspace 外写入持久化文件；容器提供的 4096 字节 /dev/shm 仅允许 Python 运行时临时使用，其中内容不得成为交付依赖并随容器销毁。

## 2. Idea provenance

- **Adaptation:** NAMI Gold20 case_11 is adapted as 265-weekly-operations-brief-generator: retain original fixtures and business invariants, replace deployment-bound execution with trusted service/code hooks and identity-bound grading receipts.
- **Private user logs:** No raw private conversations, credentials or attachments are included.
- **Synthetic-data statement:** Business entities and records are the original frozen synthetic fixtures.
- Protocol provenance: the HarnessBench task packaging protocol, <https://arxiv.org/abs/2605.27922> (this is not a source for private business fixtures).
- Source alias: `NAMI-GOLD20-case_11`.

## 3. Real-workflow justification

265-weekly-operations-brief-generator: 需要校验异构 CSV、独立实现精确 Decimal 口径、分组与环比、规则触发、模板渲染、原子写入和异常恢复，并必须在隐藏数据上复用。
The workflow requires dependent evidence and a durable deliverable, specifically 主数据简报交付与可重复执行；新数据泛化与非法输入原子拒绝.

## 4. Agent-visible inputs

| Workspace path | Role |
|---|---|
| `input/brief_template.md` | Protected task evidence or public contract |
| `input/metric_definitions.json` | Protected task evidence or public contract |
| `input/weekly_operations.csv` | Protected task evidence or public contract |

Public helpers are initial workspace files. Hidden tests, reference material and private service state are never agent mounts.

## 5. Hidden ground truth

For 265-weekly-operations-brief-generator, the protected evidence `input/brief_template.md`, `input/metric_definitions.json`, `input/weekly_operations.csv` fixes the admissible state and record invariants. The independent evaluator checks `submission/generate_brief.py`, `output/summary.json`, `output/weekly_brief.md`; the runtime receipt is produced only after the agent stops, byte-bound to the candidate and frozen configuration. It cannot be authored by the candidate. Execution evidence is retained outside agent mounts.

## 6. Expected workflow

1. Inspect `input/brief_template.md`, `input/metric_definitions.json`, `input/weekly_operations.csv`, resolve the entities and rule precedence before changing state.
2. Perform 主数据简报交付与可重复执行；新数据泛化与非法输入原子拒绝 using the public inputs and tools; inspect intermediate state and verify the cross-record invariant.
3. Deliver `submission/generate_brief.py`, `output/summary.json`, `output/weekly_brief.md`, verify the final state against the input contract, and remove temporary helpers from the delivery workspace.

## 7. Harness demands

multi_step_execution, evidence_grounding, output_contract, verification_behavior, safety_boundary. No model-specific solution interface.

## 8. Stressors and difficulty

**Plausible failure mode:** 265-weekly-operations-brief-generator: an apparently valid artifact misses one coupled business condition in 主数据简报交付与可重复执行；新数据泛化与非法输入原子拒绝; a plan without durable state earns no execution credit.

**Difficulty rationale:** 需要校验异构 CSV、独立实现精确 Decimal 口径、分组与环比、规则触发、模板渲染、原子写入和异常恢复，并必须在隐藏数据上复用。

## 9. Oracle design

Pass threshold 0.8 with every core required. Core weights total 0.8, closure 0.2.

| Case | Weight | Core/gate | Meaning |
|---|---:|---|---|
| `primary_delivery` | 0.4 | core | All of the coupled business checks must pass: submission_terminal_state fresh_primary_run_1 fresh_primary_run_2 byte_idempotency |
| `generalization_and_atomicity` | 0.4 | core | All of the coupled business checks must pass: hidden_generalization minimal_valid_generalization invalid_missing_column invalid_extra_cell invalid_date invalid_numeric invalid_duplicate invalid_logic invalid_zero_denominator invalid_input_atomicity invalid_existing_output_atomicity |
| `complete_delivery` | 0.2 | closure | All original acceptance checks pass, including final-state and replay checks. |
| `protected_boundary` | 0.0 | gate | No tampering, forged execution evidence, unsafe paths or prohibited protected-state changes. |

Required final artifacts: `submission/generate_brief.py`, `output/summary.json`, `output/weekly_brief.md`. Every check is deterministic. Missing/ordinary malformed output fails its scored block. Actual input/state tampering, unsafe links and forged execution evidence are red lines.

## 10. Leakage, isolation, and safety review

Candidate code is never imported by the hidden outcome evaluator. Code tasks retain separate resource-limited Docker candidate execution; service tasks retain private state and an allowlisted public tool interface. Receipt publication uses the standard runner environment_mutations callback after agent shutdown, including timeout/protocol/model errors. Cleanup is read-only with respect to the candidate. Original tests/reference material is not agent-visible. Public helpers must pass the repository leakage scan.

## 11. Pilot plan

**Expected Gemma/OpenClaw failure modes:** For 265-weekly-operations-brief-generator, inspect failures in 主数据简报交付与可重复执行；新数据泛化与非法输入原子拒绝, incorrect tool paths, missing durable state and incomplete output checks; these are hypotheses rather than unrun model results.

Previous Sol/Flash/Opus × Goose/NanoBot experiments used earlier package/runtime identities. Their scores remain historical. Native-v2 acceptance records live in the suite validation reports; a fresh frozen model pilot must not be claimed from replayed outputs. Every terminal outcome remains in the denominator.

## 12. Human validation status

**Status:** `not_required`

Current project policy uses automated acceptance evidence. This package does not claim human approval. User-assigned final task numbers and explicit integration are still pending.
