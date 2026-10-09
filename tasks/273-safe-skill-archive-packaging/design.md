# 273-safe-skill-archive-packaging

## 1. Workflow identity

检查日程简报技能目录，依据模板补齐 manifest 的文件大小和 SHA-256，并只导出 output/calendar_briefing_skill.zip。压缩包必须只有指定顶层目录和四个必需文件，不能包含 .private、模板或其他文件，也不能出现重复、绝对、穿越、反斜线路径、符号链接和特殊文件。保持输入与任务说明不变，交付前验证压缩包可安全解包且入口脚本可运行。

## 2. Idea provenance

- **Adaptation:** NAMI Gold20 case_19 is adapted as 273-safe-skill-archive-packaging: retain original fixtures and business invariants, replace deployment-bound execution with portable Office/artifact tools and independent hidden grading.
- **Private user logs:** No raw private conversations, credentials or attachments are included.
- **Synthetic-data statement:** Business entities and records are the original frozen synthetic fixtures.
- Protocol provenance: the HarnessBench task packaging protocol, <https://arxiv.org/abs/2605.27922> (this is not a source for private business fixtures).
- Source alias: `NAMI-GOLD20-case_19`.

## 3. Real-workflow justification

273-safe-skill-archive-packaging: 任务需要理解目录边界、计算多文件哈希、补齐结构化清单、生成安全压缩包并在交付前自检，同时避免合成私有文件和路径型攻击面。
The workflow requires dependent evidence and a durable deliverable, specifically Business result；Evidence and cross-artifact consistency.

## 4. Agent-visible inputs

| Workspace path | Role |
|---|---|
| `TASK.md` | Protected task evidence or public contract |
| `input/calendar_briefing_skill/SKILL.md` | Protected task evidence or public contract |
| `input/calendar_briefing_skill/manifest.template.json` | Protected task evidence or public contract |

Public helpers are initial workspace files. Hidden tests, reference material and private service state are never agent mounts.

## 5. Hidden ground truth

For 273-safe-skill-archive-packaging, the protected evidence `TASK.md`, `input/calendar_briefing_skill/SKILL.md`, `input/calendar_briefing_skill/manifest.template.json` fixes the admissible state and record invariants. The independent evaluator checks `output/calendar_briefing_skill.zip`; original verifier checks, fixture hashes and business-group mapping are frozen under tests/ground_truth; no candidate-authored claim replaces the hidden oracle.

## 6. Expected workflow

1. Inspect `TASK.md`, `input/calendar_briefing_skill/SKILL.md`, `input/calendar_briefing_skill/manifest.template.json`, resolve the entities and rule precedence before changing state.
2. Perform Business result；Evidence and cross-artifact consistency using the public inputs and tools; inspect intermediate state and verify the cross-record invariant.
3. Deliver `output/calendar_briefing_skill.zip`, verify the final state against the input contract, and remove temporary helpers from the delivery workspace.

## 7. Harness demands

multi_step_execution, evidence_grounding, output_contract, verification_behavior. No model-specific solution interface.

## 8. Stressors and difficulty

**Plausible failure mode:** 273-safe-skill-archive-packaging: an apparently valid artifact misses one coupled business condition in Business result；Evidence and cross-artifact consistency; a plan without durable state earns no execution credit.

**Difficulty rationale:** 任务需要理解目录边界、计算多文件哈希、补齐结构化清单、生成安全压缩包并在交付前自检，同时避免合成私有文件和路径型攻击面。

## 9. Oracle design

Pass threshold 0.8 with every core required. Core weights total 0.8, closure 0.2.

| Case | Weight | Core/gate | Meaning |
|---|---:|---|---|
| `business_result` | 0.4 | core | Original result checks: payload_integrity manifest_integrity |
| `evidence_consistency` | 0.4 | core | Original evidence checks: archive_exact_files safe_extraction runtime_smoke |
| `complete_delivery` | 0.2 | closure | All applicable original checks pass, including format, required structure and final-state consistency. |
| `protected_workspace` | 0.0 | gate | Frozen inputs and tools are unchanged; no extra files, unsafe paths, symlinks or special nodes. |

Required final artifacts: `output/calendar_briefing_skill.zip`. Every check is deterministic. Missing/ordinary malformed output fails its scored block. Actual input/state tampering, unsafe links and forged execution evidence are red lines.

## 10. Leakage, isolation, and safety review

The hidden original verifier reads only a bounded copied view; public inputs and helper identities are checked against frozen hashes. ZIP/XML payload safety is checked before parsing. Grading never changes the submission. Runtime dependencies and grader isolation are qualified separately.

## 11. Pilot plan

**Expected Gemma/OpenClaw failure modes:** For 273-safe-skill-archive-packaging, inspect failures in Business result；Evidence and cross-artifact consistency, incorrect tool paths, missing durable state and incomplete output checks; these are hypotheses rather than unrun model results.

Previous Sol/Flash/Opus × Goose/NanoBot experiments used earlier package/runtime identities. Their scores remain historical. Native-v2 acceptance records live in the suite validation reports; a fresh frozen model pilot must not be claimed from replayed outputs. Every terminal outcome remains in the denominator.

## 12. Human validation status

**Status:** `not_required`

Current project policy uses automated acceptance evidence. This package does not claim human approval. User-assigned final task numbers and explicit integration are still pending.
