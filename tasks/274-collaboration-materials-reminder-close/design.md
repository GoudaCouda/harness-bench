# 274-collaboration-materials-reminder-close

## 1. Workflow identity

请按输入目录中的材料收集规则，检查本地 project-materials 协作消息及附件：为名单内每位人员判断两类必交材料是否在统计截止时间前提交；同类材料有修订时只采用最新版本。通过本地协作工具下载应采纳附件并保持原字节，按规定路径归档；生成固定列、固定人员顺序的 outputs/material_register.csv；只向缺件人员各发送一次严格套用模板的提醒。不要处理截止时间后的附件、示例附件或非名单对象，不要提醒已交齐人员，不要覆盖附件、修改输入、访问真实平台或留下额外文件。

## 2. Idea provenance

- **Adaptation:** NAMI Gold20 case_20 is adapted as 274-collaboration-materials-reminder-close: retain original fixtures and business invariants, replace deployment-bound execution with trusted service/code hooks and identity-bound grading receipts.
- **Private user logs:** No raw private conversations, credentials or attachments are included.
- **Synthetic-data statement:** Business entities and records are the original frozen synthetic fixtures.
- Protocol provenance: the HarnessBench task packaging protocol, <https://arxiv.org/abs/2605.27922> (this is not a source for private business fixtures).
- Source alias: `NAMI-GOLD20-case_20`.

## 3. Real-workflow justification

274-collaboration-materials-reminder-close: 任务跨消息检索、时间截断、附件版本选择、原字节归档、六行登记表和条件提醒，且一次误发、旧版采纳或额外副作用都会失败。
The workflow requires dependent evidence and a durable deliverable, specifically 材料归档保真且登记表一致；对正确对象发送对应提醒.

## 4. Agent-visible inputs

| Workspace path | Role |
|---|---|
| `inputs/material_requirements.md` | Protected task evidence or public contract |
| `inputs/person_roster.csv` | Protected task evidence or public contract |

Public helpers are initial workspace files. Hidden tests, reference material and private service state are never agent mounts.

## 5. Hidden ground truth

For 274-collaboration-materials-reminder-close, the protected evidence `inputs/material_requirements.md`, `inputs/person_roster.csv` fixes the admissible state and record invariants. The independent evaluator checks `outputs/material_register.csv`; the runtime receipt is produced only after the agent stops, byte-bound to the candidate and frozen configuration. It cannot be authored by the candidate. Execution evidence is retained outside agent mounts.

## 6. Expected workflow

1. Inspect `inputs/material_requirements.md`, `inputs/person_roster.csv`, resolve the entities and rule precedence before changing state.
2. Perform 材料归档保真且登记表一致；对正确对象发送对应提醒 using the public inputs and tools; inspect intermediate state and verify the cross-record invariant.
3. Deliver `outputs/material_register.csv`, verify the final state against the input contract, and remove temporary helpers from the delivery workspace.

## 7. Harness demands

multi_step_execution, evidence_grounding, output_contract, verification_behavior, safety_boundary. No model-specific solution interface.

## 8. Stressors and difficulty

**Plausible failure mode:** 274-collaboration-materials-reminder-close: an apparently valid artifact misses one coupled business condition in 材料归档保真且登记表一致；对正确对象发送对应提醒; a plan without durable state earns no execution credit.

**Difficulty rationale:** 任务跨消息检索、时间截断、附件版本选择、原字节归档、六行登记表和条件提醒，且一次误发、旧版采纳或额外副作用都会失败。

## 9. Oracle design

Pass threshold 0.8 with every core required. Core weights total 0.8, closure 0.2.

| Case | Weight | Core/gate | Meaning |
|---|---:|---|---|
| `materials_archive` | 0.4 | core | All of the coupled business checks must pass: archive_exact_set archive_byte_fidelity archive_pdf_structure register_schema register_exact_rows download_audit_exact |
| `recipient_reminders` | 0.4 | core | All of the coupled business checks must pass: reminder_recipients_exact reminder_content_exact |
| `complete_delivery` | 0.2 | closure | All original acceptance checks pass, including final-state and replay checks. |
| `protected_boundary` | 0.0 | gate | No tampering, forged execution evidence, unsafe paths or prohibited protected-state changes. |

Required final artifacts: `outputs/material_register.csv`. Every check is deterministic. Missing/ordinary malformed output fails its scored block. Actual input/state tampering, unsafe links and forged execution evidence are red lines.

## 10. Leakage, isolation, and safety review

Candidate code is never imported by the hidden outcome evaluator. Code tasks retain separate resource-limited Docker candidate execution; service tasks retain private state and an allowlisted public tool interface. Receipt publication uses the standard runner environment_mutations callback after agent shutdown, including timeout/protocol/model errors. Cleanup is read-only with respect to the candidate. Original tests/reference material is not agent-visible. Public helpers must pass the repository leakage scan.

## 11. Pilot plan

**Expected Gemma/OpenClaw failure modes:** For 274-collaboration-materials-reminder-close, inspect failures in 材料归档保真且登记表一致；对正确对象发送对应提醒, incorrect tool paths, missing durable state and incomplete output checks; these are hypotheses rather than unrun model results.

Previous Sol/Flash/Opus × Goose/NanoBot experiments used earlier package/runtime identities. Their scores remain historical. Native-v2 acceptance records live in the suite validation reports; a fresh frozen model pilot must not be claimed from replayed outputs. Every terminal outcome remains in the denominator.

## 12. Human validation status

**Status:** `not_required`

Current project policy uses automated acceptance evidence. This package does not claim human approval. User-assigned final task numbers and explicit integration are still pending.
