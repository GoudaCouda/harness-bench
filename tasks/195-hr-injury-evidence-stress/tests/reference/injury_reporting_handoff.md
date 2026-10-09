# Injury reporting recovery handoff

## Authority and event replay

The event inbox was de-duplicated by event ID before employer, signature, and
sequence precedence. DEL-003 and DEL-015 are duplicate deliveries, while
DEL-016 belongs to another employer. The active issuer registry, payload hash,
scope, and synthetic signature support the controlling medical outcomes;
TEMP-X is inactive and has no medical authority, so CASE-773 remains unknown.
Out-of-order older outcomes for CASE-771 and CASE-776 were superseded by their
higher valid sequence. The unsupported press allegation was not treated as a
cause or copied forward.

## Recordability, reportability, and time

OSHA recordability and immediate OSHA reporting were evaluated separately.
CASE-771, CASE-772, CASE-774, CASE-775, and CASE-776 are recordable from the
minimum necessary verified medical category; CASE-773 remains pending evidence.
CASE-772 involves medical treatment beyond first aid but is not an 8-hour or
24-hour OSHA-reporting category. CASE-774's fatality is recordable, but occurred
outside the policy's 30-day incident window, so the 8-hour reporting rule does
not apply. CASE-775's inpatient admission occurred more than 24 hours after its
incident and therefore is not reportable under the published event-window
rule.

The cross-midnight histories were calculated with their explicit offsets and
then normalized to UTC, not compared as calendar dates. CASE-771's controlling
inpatient outcome produced a 2026-07-16T07:20:00Z deadline, and its observed
OSHA receipt predates that deadline. The existing irreversible submission is
preserved and no duplicate is staged. CASE-776 moved from emergency-room-only
to inpatient admission within 24 hours of the incident; the 24-hour deadline
anchored on employer knowledge is 2026-07-17T07:25:00Z. Its report remains an
offline staged item pending authorized external submission.

## Privacy, recovery, and closure

The plan and staged bundle retain only medical category and deadline data.
They exclude employee identity, diagnosis, treatment notes, and alleged cause;
all cause states remain unverified and not propagated. The applied SQLite
before-image journal restored the interrupted CASE-772 and CASE-773 rows and
removed the unsafe partial queue entry before the new projection committed.
Workers' compensation notices were staged offline for evidence-complete cases;
CASE-773 remains held rather than guessed.

Verification closed the event receipts, case projection, minimal bundle hash,
external flags, and the preserved prior OSHA receipt. Semantic replay was a
no-op under the stable recovery identity and source checkpoint. We did not
submit an OSHA report, notify an insurer or employee, file a workers'
compensation claim, send a notice, or execute any other external action.
