# 272-video-compression-fidelity-delivery

## 1. Workflow identity

将 input/source.mp4 压缩为 output/compressed.mp4，并满足目标规格中的 MP4 容器、H.264 640×360 24 帧、yuv420p、AAC 48 kHz 双声道、时长误差、文件体积、压缩比例和内容保真要求；保持输入与任务文件不变，只交付该输出文件，并在结束前自行检查可完整解码且画面与声音未被替换。

## 2. Idea provenance

- **Adaptation:** NAMI Gold20 case_18 is adapted as 272-video-compression-fidelity-delivery: retain original fixtures and business invariants, replace deployment-bound execution with portable Office/artifact tools and independent hidden grading.
- **Private user logs:** No raw private conversations, credentials or attachments are included.
- **Synthetic-data statement:** Business entities and records are the original frozen synthetic fixtures.
- Protocol provenance: the HarnessBench task packaging protocol, <https://arxiv.org/abs/2605.27922> (this is not a source for private business fixtures).
- Source alias: `NAMI-GOLD20-case_18`.

## 3. Real-workflow justification

272-video-compression-fidelity-delivery: 任务要求联合满足容器、双轨、编码、尺寸、帧率、像素格式、时长和体积约束，并在失败时根据 ffprobe 结果调整转码参数。
The workflow requires dependent evidence and a durable deliverable, specifically Business result；Evidence and cross-artifact consistency.

## 4. Agent-visible inputs

| Workspace path | Role |
|---|---|
| `task/instruction.md` | Protected task evidence or public contract |
| `task/target_spec.json` | Protected task evidence or public contract |
| `task/tool_contract.json` | Protected task evidence or public contract |

Public helpers are initial workspace files. Hidden tests, reference material and private service state are never agent mounts.

## 5. Hidden ground truth

For 272-video-compression-fidelity-delivery, the protected evidence `task/instruction.md`, `task/target_spec.json`, `task/tool_contract.json` fixes the admissible state and record invariants. The independent evaluator checks `output/compressed.mp4`; original verifier checks, fixture hashes and business-group mapping are frozen under tests/ground_truth; no candidate-authored claim replaces the hidden oracle.

## 6. Expected workflow

1. Inspect `task/instruction.md`, `task/target_spec.json`, `task/tool_contract.json`, resolve the entities and rule precedence before changing state.
2. Perform Business result；Evidence and cross-artifact consistency using the public inputs and tools; inspect intermediate state and verify the cross-record invariant.
3. Deliver `output/compressed.mp4`, verify the final state against the input contract, and remove temporary helpers from the delivery workspace.

## 7. Harness demands

multi_step_execution, evidence_grounding, output_contract, verification_behavior. No model-specific solution interface.

## 8. Stressors and difficulty

**Plausible failure mode:** 272-video-compression-fidelity-delivery: an apparently valid artifact misses one coupled business condition in Business result；Evidence and cross-artifact consistency; a plan without durable state earns no execution credit.

**Difficulty rationale:** 任务要求联合满足容器、双轨、编码、尺寸、帧率、像素格式、时长和体积约束，并在失败时根据 ffprobe 结果调整转码参数。

## 9. Oracle design

Pass threshold 0.8 with every core required. Core weights total 0.8, closure 0.2.

| Case | Weight | Core/gate | Meaning |
|---|---:|---|---|
| `business_result` | 0.4 | core | Original result checks: video_spec audio_spec size_spec |
| `evidence_consistency` | 0.4 | core | Original evidence checks: content_fidelity duration_spec stream_layout |
| `complete_delivery` | 0.2 | closure | All applicable original checks pass, including format, required structure and final-state consistency. |
| `protected_workspace` | 0.0 | gate | Frozen inputs and tools are unchanged; no extra files, unsafe paths, symlinks or special nodes. |

Required final artifacts: `output/compressed.mp4`. Every check is deterministic. Missing/ordinary malformed output fails its scored block. Actual input/state tampering, unsafe links and forged execution evidence are red lines.

## 10. Leakage, isolation, and safety review

The hidden original verifier reads only a bounded copied view; public inputs and helper identities are checked against frozen hashes. ZIP/XML payload safety is checked before parsing. Grading never changes the submission. Runtime dependencies and grader isolation are qualified separately.

## 11. Pilot plan

**Expected Gemma/OpenClaw failure modes:** For 272-video-compression-fidelity-delivery, inspect failures in Business result；Evidence and cross-artifact consistency, incorrect tool paths, missing durable state and incomplete output checks; these are hypotheses rather than unrun model results.

Previous Sol/Flash/Opus × Goose/NanoBot experiments used earlier package/runtime identities. Their scores remain historical. Native-v2 acceptance records live in the suite validation reports; a fresh frozen model pilot must not be claimed from replayed outputs. Every terminal outcome remains in the denominator.

## 12. Human validation status

**Status:** `not_required`

Current project policy uses automated acceptance evidence. This package does not claim human approval. User-assigned final task numbers and explicit integration are still pending.
