# 269-constrained-shopping-cart-update

## 1. Workflow identity

请在晨星生活馆的本地商品目录中，为 user_alpha 找到同时满足以下条件的商品：尺码 M、颜色海蓝、评分不低于 4.6、价格不超过 300 元且有库存。若有多个合格商品，只把其中价格最低且最低价唯一的商品以数量 1 加入购物车。完成后核对购物车。不得添加其他商品，不得修改商品价格或库存，不得改动其他用户购物车，也不得进入结算或创建订单。

## 2. Idea provenance

- **Adaptation:** NAMI Gold20 case_15 is adapted as 269-constrained-shopping-cart-update: retain original fixtures and business invariants, replace deployment-bound execution with trusted service/code hooks and identity-bound grading receipts.
- **Private user logs:** No raw private conversations, credentials or attachments are included.
- **Synthetic-data statement:** Business entities and records are the original frozen synthetic fixtures.
- Protocol provenance: the HarnessBench task packaging protocol, <https://arxiv.org/abs/2605.27922> (this is not a source for private business fixtures).
- Source alias: `NAMI-GOLD20-case_15`.

## 3. Real-workflow justification

269-constrained-shopping-cart-update: 需要读取固定网页状态、组合五项筛选条件、比较多个合格商品并执行一次受限写操作，同时避免多商品、其他用户和结算副作用。
The workflow requires dependent evidence and a durable deliverable, specifically 满足约束的目标购物车更新；精确审计记录对应本次购物车变更.

## 4. Agent-visible inputs

| Workspace path | Role |
|---|---|
| `hb_tools/README.md` | Protected task evidence or public contract |
| `hb_tools/browser_snapshot.py` | Protected task evidence or public contract |
| `hb_tools/cart_tool.py` | Protected task evidence or public contract |
| `hb_tools/tool_contracts.json` | Protected task evidence or public contract |

Public helpers are initial workspace files. Hidden tests, reference material and private service state are never agent mounts.

## 5. Hidden ground truth

For 269-constrained-shopping-cart-update, the protected evidence `hb_tools/README.md`, `hb_tools/browser_snapshot.py`, `hb_tools/cart_tool.py`, `hb_tools/tool_contracts.json` fixes the admissible state and record invariants. The independent evaluator checks the durable business state captured by the trusted runtime (no candidate-authored artifact required); the runtime receipt is produced only after the agent stops, byte-bound to the candidate and frozen configuration. It cannot be authored by the candidate. Execution evidence is retained outside agent mounts.

## 6. Expected workflow

1. Inspect `hb_tools/README.md`, `hb_tools/browser_snapshot.py`, `hb_tools/cart_tool.py`, `hb_tools/tool_contracts.json`, resolve the entities and rule precedence before changing state.
2. Perform 满足约束的目标购物车更新；精确审计记录对应本次购物车变更 using the public inputs and tools; inspect intermediate state and verify the cross-record invariant.
3. Deliver the durable business state captured by the trusted runtime (no candidate-authored artifact required), verify the final state against the input contract, and remove temporary helpers from the delivery workspace.

## 7. Harness demands

multi_step_execution, evidence_grounding, output_contract, verification_behavior, safety_boundary. No model-specific solution interface.

## 8. Stressors and difficulty

**Plausible failure mode:** 269-constrained-shopping-cart-update: an apparently valid artifact misses one coupled business condition in 满足约束的目标购物车更新；精确审计记录对应本次购物车变更; a plan without durable state earns no execution credit.

**Difficulty rationale:** 需要读取固定网页状态、组合五项筛选条件、比较多个合格商品并执行一次受限写操作，同时避免多商品、其他用户和结算副作用。

## 9. Oracle design

Pass threshold 0.8 with every core required. Core weights total 0.8, closure 0.2.

| Case | Weight | Core/gate | Meaning |
|---|---:|---|---|
| `requested_cart` | 0.4 | core | All of the coupled business checks must pass: target_cart_exact |
| `audited_transition` | 0.4 | core | All of the coupled business checks must pass: target_cart_exact audit_exact |
| `complete_delivery` | 0.2 | closure | All original acceptance checks pass, including final-state and replay checks. |
| `protected_boundary` | 0.0 | gate | No tampering, forged execution evidence, unsafe paths or prohibited protected-state changes. |

Required final artifacts: the durable business state captured by the trusted runtime (no candidate-authored artifact required). Every check is deterministic. Missing/ordinary malformed output fails its scored block. Actual input/state tampering, unsafe links and forged execution evidence are red lines.

## 10. Leakage, isolation, and safety review

Candidate code is never imported by the hidden outcome evaluator. Code tasks retain separate resource-limited Docker candidate execution; service tasks retain private state and an allowlisted public tool interface. Receipt publication uses the standard runner environment_mutations callback after agent shutdown, including timeout/protocol/model errors. Cleanup is read-only with respect to the candidate. Original tests/reference material is not agent-visible. Public helpers must pass the repository leakage scan.

## 11. Pilot plan

**Expected Gemma/OpenClaw failure modes:** For 269-constrained-shopping-cart-update, inspect failures in 满足约束的目标购物车更新；精确审计记录对应本次购物车变更, incorrect tool paths, missing durable state and incomplete output checks; these are hypotheses rather than unrun model results.

Previous Sol/Flash/Opus × Goose/NanoBot experiments used earlier package/runtime identities. Their scores remain historical. Native-v2 acceptance records live in the suite validation reports; a fresh frozen model pilot must not be claimed from replayed outputs. Every terminal outcome remains in the denominator.

## 12. Human validation status

**Status:** `not_required`

Current project policy uses automated acceptance evidence. This package does not claim human approval. User-assigned final task numbers and explicit integration are still pending.
