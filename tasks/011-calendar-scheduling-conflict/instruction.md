Prepare the scheduling handoff for customer escalation request `CAL-NW-482`
using only `$WORKSPACE/meeting_request.json` and the calendar snapshots under
`$WORKSPACE/calendars/`.

Apply every constraint in the request: time-zone working hours, busy intervals,
minimum notice, busy-event buffer, start grid, customer preference, ranking
policy, and non-overlapping candidate windows. A buffer is required immediately
before and after every busy event, but not at the start or end of working hours.

Create `$WORKSPACE/scheduling_plan.json` containing:

- `request_id`, `status`, and `timezone`;
- one `recommended` candidate and two ordered `fallbacks`;
- for each candidate: `start`, `end`, and a concise `selection_reason`;
- a `participant_local_times` object for the recommended candidate, keyed by
  participant email, with a human-readable local date and start/end time;
- `evidence`, listing the workspace-relative request/calendar files used.

Use `ready_for_confirmation` as the status when three eligible candidates can
be produced. Times must be ISO 8601 values with offsets.

Draft `$WORKSPACE/customer_reply.md` to Dana. It should recommend the first
candidate, offer the fallbacks in the same order, state the 45-minute purpose
and required attendee roles, show each option in both New York and Chicago
time, and ask for confirmation. This is a draft: do not claim an invite or hold
was sent, booked, or placed, and do not make pricing, legal, delivery, or
incident-resolution promises.

Do not modify the request or calendar snapshots and do not use the network.
