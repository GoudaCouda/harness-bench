# Privacy request intake policy

Effective 2026-05-01. This procedure covers administrative intake only. It does
not authorize production routing, deletion, requester contact, or resolution of
a retention hold.

## P-1 — Authority for a self-service request

A self-service requester has authority when either:

- the submitted email exactly matches the target account's primary email; or
- the evidence packet contains an unexpired account token whose account ID
  matches the target account.

Use `verified_self` when authority is established. Otherwise use
`needs_identity_evidence`, do not inspect or disclose account contents beyond
what is needed for the identity check, set scope to `pending_authority`, and ask
for login verification or a valid account token.

## P-2 — Authority for an authorized agent

An agent's email is not expected to match the account holder's email. Agent
authority is established only when the packet has both:

1. a completed agent identity check; and
2. an unexpired signed authorization that identifies the target account holder
   and explicitly authorizes the requested action.

Use `verified_agent` when both conditions hold. If the authorization is absent,
expired, identifies a different holder, or authorizes a different action, use
`needs_agent_authorization`, set scope to `pending_authority`, and request a
corrected authorization. Do not substitute the agent's own account token for
the holder's authorization.

## P-3 — Scope and third-party records

Use `in_scope` for a verified request limited to the holder's own personal
data. A request solely for a household member's, emergency contact's, or other
person's data is `out_of_scope` and must be rejected without exposing that
person's details.

When a verified requester asks for both their own account data and linked
third-party data, use `partial_scope`: route only the holder's own eligible data
and exclude all linked-person records. The response may describe the exclusion
generically, but must not identify the other person.

## P-4 — Retention review

Authority and a retention hold are separate questions. For a verified in-scope
or partial-scope request, current holds do not block intake of otherwise
eligible systems. Route eligible systems for administrative deletion review and
list each present system protected by a current hold under `retained_systems`.
The review owner and hold-to-system mapping are in `data_map.md`.

Never promise that a hold will be lifted or that retained data will be deleted.

## P-5 — Disposition and queue codebook

Choose one disposition and its queue:

| Condition | `intake_disposition` | `queue` |
|---|---|---|
| authority missing or defective | `needs_more_information` | `identity_followup` |
| verified request wholly outside requester scope | `reject_out_of_scope` | `scope_response` |
| verified in-scope/partial-scope request, no current retained system | `route_for_deletion_review` | `deletion_review` |
| verified in-scope/partial-scope request with at least one current retained system | `route_with_retention` | `retention_review` |

For an authority or scope rejection, both system columns are `none`. For an
accepted request, `eligible_systems` contains only present holder-owned systems
classified as deletion-review eligible by the data map. A partial-scope request
must exclude linked-person systems.

## P-6 — Communication minimization

Requester-facing drafts must not contain full emails, phone numbers, account
IDs, linked-person names or identifiers, internal analyst notes, fraud/security
signals, internal queue names, or internal system codes. They may state the
request ID, a generic retention category, the evidence still required, the
scope boundary, and the next administrative step.

The internal intake register and handoff may use request IDs, account IDs,
queue codes, system codes, and source filenames. Do not copy raw emails, phone
numbers, linked-person identities, or internal narrative notes into any output.

## P-7 — Review-only boundary

All outputs are proposals for a privacy lead. Do not state or imply that a
requester was contacted, a message was sent, a production job was routed, a
hold was resolved, or data was deleted, erased, purged, or removed.

## Register status values

- `authority_status`: `verified_self`, `verified_agent`,
  `needs_identity_evidence`, `needs_agent_authorization`
- `scope_status`: `in_scope`, `partial_scope`, `out_of_scope`,
  `pending_authority`
