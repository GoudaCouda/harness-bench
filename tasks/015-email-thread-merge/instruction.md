You are covering the Northwind onboarding account after its coordinator became
unavailable. Reconstruct the current account state from the JSON messages in
`$WORKSPACE/emails/` as of the latest message.

Treat repeated `message_id` values and forwarded copies of the same substantive
message as one event. Do not mix the unrelated billing notification into the
onboarding state. A customer's “if possible” request is a preference, not a new
commitment unless the owner accepts it. Internal team availability does not make
a kickoff confirmed while a stated customer approval is still pending.

Create `$WORKSPACE/onboarding_state.json` with:

- `account`, `as_of`, and `overall_status`;
- a `milestones` object with keys `security_questionnaire`,
  `procurement_approval`, and `pilot_kickoff`;
- for each milestone: `owner`, `status`, `target_date` (JSON null if none),
  `blocked_by` (an array), `next_action`, and `evidence_message_ids`; and
- `ignored_message_ids` for messages unrelated to this onboarding.

Use milestone statuses `in_progress`, `blocked`, or `tentative`, and use ISO
dates. Evidence IDs must refer to unique substantive messages.

Draft `$WORKSPACE/customer_reply.md` to Morgan Lee. Acknowledge the request for
the questionnaire today, state the actual latest committed deadline, keep the
August 18 kickoff contingent on procurement, and ask Morgan to confirm when
procurement review completes. Do not claim that a questionnaire or invitation
was sent, that procurement approved, or that the kickoff was booked.

Do not modify source messages, use the network, or perform external actions.
