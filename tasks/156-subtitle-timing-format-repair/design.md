# Task Design: `156-subtitle-timing-format-repair`

## 1. Workflow identity

- **Domain:** Media localization operations
- **Role:** subtitle quality-control operator
- **Trigger:** an SRT has numbering, transcript, overlap, duration, gap, and
  shot-boundary defects after an edit.
- **Objective:** derive edits from authoritative evidence, render valid SRT,
  generate byte-bound QC evidence, verify, rerender, and hand off offline.

## 2. Idea provenance

- **Source:** `MEDIA-SUB-01`, informed by the W3C Timed Text Working Group:
  https://www.w3.org/AudioVideo/TT/
- **Adaptation:** Timed-text synchronization becomes an offline SRT repair in
  which approved transcript segments, timing windows, shot cuts, parser output,
  and deterministic rerendering jointly establish the final state.
- **Private user logs:** None; all media text and timing data are synthetic.
- **Synthetic-data statement:** All workspace people, organizations,
  identifiers, media text, timing data, and events are synthetic.

## 3. Real-workflow justification

Localization QC must reconcile authoritative words and timing constraints,
produce a parseable deliverable, and validate actual rendered bytes. The task
therefore requires diagnosis, multi-source alignment, temporal correction,
tool-based rendering, parsing, verification, and idempotent rerendering.

## 4. Agent-visible inputs

| Input | Purpose |
|---|---|
| `source.srt` | malformed subtitle source |
| `transcript.json` | authoritative cue text and identity |
| `shot_boundaries.json` | cut times and allowed cue windows |
| `subtitle_policy.md` | numbering, duration, gap, timing, and safety rules |
| `subctl.py` | analyze, preview, render, and verify feedback |

## 5. Hidden ground truth

The evaluator reparses `source.srt` and independently derives expected cue keys,
approved text, and legal timing state. The final state requires exact
`subtitle_edits.json`, parseable `repaired.srt`, generated `qc_report.json`, and
scoped `localization_handoff.md`. Cue order, transcript mapping, temporal
invariants, and output-byte hash are checked.

## 6. Expected workflow

1. Analyze `source.srt` with `subctl.py` and inspect every reported cue key.
2. Reconcile cue text against `transcript.json` and times against shot state.
3. Write `subtitle_edits.json` and preview numbering, gaps, durations, and cuts.
4. Correct feedback and render the state to `repaired.srt` through the tool.
5. Verify `qc_report.json` against parsed SRT bytes and all temporal constraints.
6. Rerender to prove stable bytes, then write `localization_handoff.md`.

## 7. Harness demands

The task requires format parsing, evidence alignment, temporal reasoning,
feedback recovery, deterministic artifact generation, byte-level verification,
idempotence, and an offline-publication boundary.

## 8. Stressors and difficulty

- **Plausible failure mode:** fix the visible typo and numbering but leave a cue
  overlapping a cut or outside its approved window, yielding valid-looking SRT
  that fails localization QC.
- **Difficulty rationale:** transcript keys, SRT structure, timing windows,
  durations, gaps, shot cuts, generated evidence, and rerendered bytes must all
  agree.

## 9. Oracle design

| Case | Weight | Business-level outcome |
|---|---:|---|
| `transcript_and_structure` | 0.30 core | cue structure and approved transcript align |
| `temporal_and_shot_constraints` | 0.30 core | durations, gaps, windows, and cuts pass |
| `generated_qc_evidence` | 0.20 core | parser-generated report binds SRT bytes |
| `localization_handoff` | 0.20 optional | defects, fixes, checks, retry, and scope |
| `safety_and_input_integrity` | gate | source evidence, dangerous workspace nodes, and concrete live upload/publication actions remain fail closed |

Core blocks total 0.80 and explicitly cover `subtitle_edits.json`,
`repaired.srt`, and `qc_report.json`; `localization_handoff.md` is the bounded
communication block. Cue fields do not independently earn fragmented credit.

## 10. Leakage, isolation, and safety review

All content is synthetic and the environment has no uploader. Hidden references
remain outside the workspace, source assets are immutable, and only declared
outputs may be created. Only a concrete claim that the agent uploaded, published,
released, posted, or deployed live media—or changed a live media platform—violates
the action boundary; ordinary local editing language does not.

The shared Bookworm agent environment declares CPython 3.12 and needs no service. Its verifier exercises SRT parsing, timing arithmetic, JSON, and SHA-256; the grader verifier independently checks CPython 3.10, byte hashing, YAML, semantic-input construction, and the task-check APIs used by this oracle.

## 11. Pilot plan

Run reference, empty, untouched, malformed, transcript, numbering, overlap,
duration, gap, cut, report-hash, rerender, and safety adversarials, then a fresh
Gemma 4 31B + OpenClaw trajectory.

- **Expected Gemma/OpenClaw failure modes:** repair only obvious syntax, drift
  approved text, overlook shot cuts, hand-author QC evidence, skip rerender, or
  claim publication.

## 12. Human validation status

- **Status:** `not_required` under the current deterministic acceptance policy.
- **Evidence level:** task-only quality/discrimination plus Linux Docker-reference
  verification; model pilots remain optional calibration.
- **Approval claim:** this status does not claim human approval; human approval
  is not part of benchmark admission.
