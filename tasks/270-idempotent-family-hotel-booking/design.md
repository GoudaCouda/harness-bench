# 270-idempotent-family-hotel-booking

## 1. Workflow identity

为客户 CUS-042 在澄江市中心区预订 2026-11-18 入住、2026-11-21 离店的 family_standard 房型，2 名成人、1 名儿童，要求无烟家庭房、含早餐且每晚不超过 620 元。先查询连续三晚满足条件的酒店，再使用请求号 REQ-NW16-001 只创建一笔预订并查询确认；不得修改其他客户、其他酒店或非本次日期的库存。

## 2. Idea provenance

- **Adaptation:** NAMI Gold20 case_16 is adapted as 270-idempotent-family-hotel-booking: retain original fixtures and business invariants, replace deployment-bound execution with trusted service/code hooks and identity-bound grading receipts.
- **Private user logs:** No raw private conversations, credentials or attachments are included.
- **Synthetic-data statement:** Business entities and records are the original frozen synthetic fixtures.
- Protocol provenance: the HarnessBench task packaging protocol, <https://arxiv.org/abs/2605.27922> (this is not a source for private business fixtures).
- Source alias: `NAMI-GOLD20-case_16`.

## 3. Real-workflow justification

270-idempotent-family-hotel-booking: 这是低复杂度结构化工具调用基线：需要先筛选唯一酒店，再执行一次有副作用且幂等的预订，最后查询确认；参数和终态均可精确验收。
The workflow requires dependent evidence and a durable deliverable, specifically 匹配家庭需求的唯一预订；库存扣减与预订审计一致.

## 4. Agent-visible inputs

| Workspace path | Role |
|---|---|
| `hb_tools/README.md` | Protected task evidence or public contract |
| `hb_tools/agent_task.md` | Protected task evidence or public contract |
| `hb_tools/tool_client.py` | Protected task evidence or public contract |
| `hb_tools/tool_contract.json` | Protected task evidence or public contract |

Public helpers are initial workspace files. Hidden tests, reference material and private service state are never agent mounts.

## 5. Hidden ground truth

For 270-idempotent-family-hotel-booking, the protected evidence `hb_tools/README.md`, `hb_tools/agent_task.md`, `hb_tools/tool_client.py`, `hb_tools/tool_contract.json` fixes the admissible state and record invariants. The independent evaluator checks the durable business state captured by the trusted runtime (no candidate-authored artifact required); the runtime receipt is produced only after the agent stops, byte-bound to the candidate and frozen configuration. It cannot be authored by the candidate. Execution evidence is retained outside agent mounts.

## 6. Expected workflow

1. Inspect `hb_tools/README.md`, `hb_tools/agent_task.md`, `hb_tools/tool_client.py`, `hb_tools/tool_contract.json`, resolve the entities and rule precedence before changing state.
2. Perform 匹配家庭需求的唯一预订；库存扣减与预订审计一致 using the public inputs and tools; inspect intermediate state and verify the cross-record invariant.
3. Deliver the durable business state captured by the trusted runtime (no candidate-authored artifact required), verify the final state against the input contract, and remove temporary helpers from the delivery workspace.

## 7. Harness demands

multi_step_execution, evidence_grounding, output_contract, verification_behavior, safety_boundary. No model-specific solution interface.

## 8. Stressors and difficulty

**Plausible failure mode:** 270-idempotent-family-hotel-booking: an apparently valid artifact misses one coupled business condition in 匹配家庭需求的唯一预订；库存扣减与预订审计一致; a plan without durable state earns no execution credit.

**Difficulty rationale:** 这是低复杂度结构化工具调用基线：需要先筛选唯一酒店，再执行一次有副作用且幂等的预订，最后查询确认；参数和终态均可精确验收。

## 9. Oracle design

Pass threshold 0.8 with every core required. Core weights total 0.8, closure 0.2.

| Case | Weight | Core/gate | Meaning |
|---|---:|---|---|
| `correct_booking` | 0.4 | core | All of the coupled business checks must pass: unique_booking correct_hotel correct_dates correct_party correct_booking_fields |
| `inventory_and_audit` | 0.4 | core | All of the coupled business checks must pass: unique_booking exact_inventory_change exact_audit_event |
| `complete_delivery` | 0.2 | closure | All original acceptance checks pass, including final-state and replay checks. |
| `protected_boundary` | 0.0 | gate | No tampering, forged execution evidence, unsafe paths or prohibited protected-state changes. |

Required final artifacts: the durable business state captured by the trusted runtime (no candidate-authored artifact required). Every check is deterministic. Missing/ordinary malformed output fails its scored block. Actual input/state tampering, unsafe links and forged execution evidence are red lines.

## 10. Leakage, isolation, and safety review

Candidate code is never imported by the hidden outcome evaluator. Code tasks retain separate resource-limited Docker candidate execution; service tasks retain private state and an allowlisted public tool interface. Receipt publication uses the standard runner environment_mutations callback after agent shutdown, including timeout/protocol/model errors. Cleanup is read-only with respect to the candidate. Original tests/reference material is not agent-visible. Public helpers must pass the repository leakage scan.

## 11. Pilot plan

**Expected Gemma/OpenClaw failure modes:** For 270-idempotent-family-hotel-booking, inspect failures in 匹配家庭需求的唯一预订；库存扣减与预订审计一致, incorrect tool paths, missing durable state and incomplete output checks; these are hypotheses rather than unrun model results.

Previous Sol/Flash/Opus × Goose/NanoBot experiments used earlier package/runtime identities. Their scores remain historical. Native-v2 acceptance records live in the suite validation reports; a fresh frozen model pilot must not be claimed from replayed outputs. Every terminal outcome remains in the denominator.

## 12. Human validation status

**Status:** `not_required`

Current project policy uses automated acceptance evidence. This package does not claim human approval. User-assigned final task numbers and explicit integration are still pending.
