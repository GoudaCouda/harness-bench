# Registrar grade-passback recovery handoff

## Identity and assignment resolution

Checkpoint `GP-CHECKPOINT-20260818-012` was reconciled under stable recovery
identity `GP-20260818-DISTRICT-01`. The legacy section `lms-math-legacy` was
rekeyed to `SEC-MATH-8A`; the current English section remained `SEC-ENG-8B`.
Learners `lms-alice-old` and `lms-carol-old` used SIS rekeys, while temporary
identity `lms-temp-440` was merged into canonical learner `STU-1004`. Every
accepted learner has an active enrollment in the resolved section.

The current line-item bindings are `li-alg-q1` version 2 at 20 points and
`li-essay-2` version 3 at 50 points. Event `evt-result-alice-v1` was quarantined
because assignment version 1 is archived; it could not replace the current
grade. Exact repeated delivery `evt-result-alice-v2` was deduplicated and
journaled once. Unknown section/user event `evt-result-unknown` was quarantined
without inventing a roster identity.

## Score and time decisions

The attempt-backed current scores for Alice, Bob, and merged learner Devon were
accepted on time into the local projection. Bob's separate 85/100 event
`evt-result-bob-badscale` was quarantined as an invalid score scale before the
corrected 18/20 result was applied. Carol's 44/50 essay arrived after its due
time but within the published late-acceptance window, so it is recorded as
late. Emery's 48/50 result arrived after the late window and was quarantined;
the registrar's existing manual 46/50 override remains untouched.

## Recovery and control closure

The controller restored the partially changed Alice row from interrupted run
`GP-INTERRUPTED-20260817` before performing one atomic SQLite recovery. The
local gradebook, processed-event journal, quarantine journal, normalized plan
hash, source-bundle hash, and revision 42 all verified exactly. Staging produced
only a pending-registrar-review receipt. Replay of the semantically same plan
was a database-byte-stable and receipt-byte-stable no-op; the stable passback ID
also rejects a conflicting plan.

No LMS score POST, SIS API publish, parent-portal update, learner or instructor
message, registrar notification, email, or other external action was executed.
This handoff records an offline local projection and review boundary only.
