# 008 Timeline Seek/Trim Design

Replacement prototype for the old media filter task. The oracle serves `web/dist`, checks DOM geometry for a playhead and trim band, and verifies clip selection and timeline summaries after seek/trim actions.

Weights: build 0.22, protected data 0.22, interaction 0.36, responsive 0.20, safety gate.
