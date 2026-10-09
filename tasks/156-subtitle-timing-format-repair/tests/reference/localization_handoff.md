# Harbor Lab subtitle QC handoff

The source contained duplicate/nonconsecutive cue numbering, an overlap between
the first two cues, the transcription error “bacon” instead of approved
“beacon,” missing transcript punctuation, durations beyond policy, and cues
touching or crossing shot boundaries.

The repaired master has four consecutive cues aligned exactly to transcript
segments TX-1 through TX-4. Every cue is 1–3 seconds, every adjacent gap is at
least 100 ms, and cue ends remain before the 2850, 5250, 7850, and 10500 ms
cuts. The controller parse and QC report passed numbering, transcript, gap,
duration, cut, and program-end checks. Re-rendering the same edits was
byte-identical and idempotent.

The transcript is the text authority and the shot file is the timing authority.
This was offline localization work only; no video, caption track, platform,
publication, or live media asset was uploaded or changed.
