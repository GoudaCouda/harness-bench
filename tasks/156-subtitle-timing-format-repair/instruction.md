# Repair the Harbor Lab subtitle master

You are a media-localization QC operator. The supplied SRT has numbering,
overlap, transcription, duration, and shot-boundary defects.

1. Read `subtitle_policy.md`, `transcript.json`, `shot_boundaries.json`, and run
   `python3 subctl.py analyze source.srt`.
2. Create `subtitle_edits.json` with an ordered `cues` list. Each cue has
   `number`, `start_ms`, `end_ms`, and `text`. Align exact approved transcript
   segments while satisfying minimum gaps, duration, and cut boundaries.
3. Run `python3 subctl.py preview subtitle_edits.json`; use every failed
   temporal/text constraint to correct the edit list.
4. Run `python3 subctl.py render subtitle_edits.json`, which writes
   `repaired.srt`; then run `python3 subctl.py verify repaired.srt`, which writes
   `qc_report.json`.
5. Render the same edit list again and confirm byte-identical idempotency.
6. Write `localization_handoff.md` describing each repaired defect, timing and
   shot-boundary checks, transcript authority, verification, and offline scope.

Do not edit source evidence or hand-author `qc_report.json`. Do not claim a
video-platform upload, publication, or live media change.
