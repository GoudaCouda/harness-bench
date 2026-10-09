# 262-user-service-registration-repair

## 1. Workflow identity

请在给定的小型 Python 账号服务仓库中实现用户注册功能。遵循 TASK.md 的输入校验、大小写不敏感唯一性、密码哈希、同事务审计和返回字段要求；保持已有认证功能正常，只修改 POLICY.md 允许的源码文件，并运行公开测试自检。

## 2. Idea provenance

- **Adaptation:** NAMI Gold20 case_08 is adapted as 262-user-service-registration-repair: retain original fixtures and business invariants, replace deployment-bound execution with trusted service/code hooks and identity-bound grading receipts.
- **Private user logs:** No raw private conversations, credentials or attachments are included.
- **Synthetic-data statement:** Business entities and records are the original frozen synthetic fixtures.
- Protocol provenance: the HarnessBench task packaging protocol, <https://arxiv.org/abs/2605.27922> (this is not a source for private business fixtures).
- Source alias: `NAMI-GOLD20-case_08`.

## 3. Real-workflow justification

262-user-service-registration-repair: 需要理解现有三模块架构，并同时满足输入校验、加密存储、大小写唯一性、事务原子性、回归和文件边界；公开测试仅覆盖基础合同。
The workflow requires dependent evidence and a durable deliverable, specifically 注册事务与安全密码存储；兼容现有认证并拒绝冲突与非法请求.

## 4. Agent-visible inputs

| Workspace path | Role |
|---|---|
| `POLICY.md` | Protected task evidence or public contract |
| `README.md` | Protected task evidence or public contract |
| `TASK.md` | Protected task evidence or public contract |

Public helpers are initial workspace files. Hidden tests, reference material and private service state are never agent mounts.

## 5. Hidden ground truth

For 262-user-service-registration-repair, the protected evidence `POLICY.md`, `README.md`, `TASK.md` fixes the admissible state and record invariants. The independent evaluator checks `nami_service/users.py`; the runtime receipt is produced only after the agent stops, byte-bound to the candidate and frozen configuration. It cannot be authored by the candidate. Execution evidence is retained outside agent mounts.

## 6. Expected workflow

1. Inspect `POLICY.md`, `README.md`, `TASK.md`, resolve the entities and rule precedence before changing state.
2. Perform 注册事务与安全密码存储；兼容现有认证并拒绝冲突与非法请求 using the public inputs and tools; inspect intermediate state and verify the cross-record invariant.
3. Deliver `nami_service/users.py`, verify the final state against the input contract, and remove temporary helpers from the delivery workspace.

## 7. Harness demands

multi_step_execution, evidence_grounding, output_contract, verification_behavior, safety_boundary. No model-specific solution interface.

## 8. Stressors and difficulty

**Plausible failure mode:** 262-user-service-registration-repair: an apparently valid artifact misses one coupled business condition in 注册事务与安全密码存储；兼容现有认证并拒绝冲突与非法请求; a plan without durable state earns no execution credit.

**Difficulty rationale:** 需要理解现有三模块架构，并同时满足输入校验、加密存储、大小写唯一性、事务原子性、回归和文件边界；公开测试仅覆盖基础合同。

## 9. Oracle design

Pass threshold 0.8 with every core required. Core weights total 0.8, closure 0.2.

| Case | Weight | Core/gate | Meaning |
|---|---:|---|---|
| `registration_transaction` | 0.4 | core | All of the coupled business checks must pass: valid_registration password_storage audit_event |
| `compatibility_and_rejection` | 0.4 | core | All of the coupled business checks must pass: existing_authentication database_unique_constraints case_insensitive_conflicts invalid_input_rejection transaction_rollback |
| `complete_delivery` | 0.2 | closure | All original acceptance checks pass, including final-state and replay checks. |
| `protected_boundary` | 0.0 | gate | No tampering, forged execution evidence, unsafe paths or prohibited protected-state changes. |

Required final artifacts: `nami_service/users.py`. Every check is deterministic. Missing/ordinary malformed output fails its scored block. Actual input/state tampering, unsafe links and forged execution evidence are red lines.

## 10. Leakage, isolation, and safety review

Candidate code is never imported by the hidden outcome evaluator. Code tasks retain separate resource-limited Docker candidate execution; service tasks retain private state and an allowlisted public tool interface. Receipt publication uses the standard runner environment_mutations callback after agent shutdown, including timeout/protocol/model errors. Cleanup is read-only with respect to the candidate. Original tests/reference material is not agent-visible. Public helpers must pass the repository leakage scan.

## 11. Pilot plan

**Expected Gemma/OpenClaw failure modes:** For 262-user-service-registration-repair, inspect failures in 注册事务与安全密码存储；兼容现有认证并拒绝冲突与非法请求, incorrect tool paths, missing durable state and incomplete output checks; these are hypotheses rather than unrun model results.

Previous Sol/Flash/Opus × Goose/NanoBot experiments used earlier package/runtime identities. Their scores remain historical. Native-v2 acceptance records live in the suite validation reports; a fresh frozen model pilot must not be claimed from replayed outputs. Every terminal outcome remains in the denominator.

## 12. Human validation status

**Status:** `not_required`

Current project policy uses automated acceptance evidence. This package does not claim human approval. User-assigned final task numbers and explicit integration are still pending.
