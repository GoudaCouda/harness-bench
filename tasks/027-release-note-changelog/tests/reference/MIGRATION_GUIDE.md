# 2.4.0 migration guide

## ISSUE-103 — usage response
Replace reads of `units` with `billable_units`. Before upgrading, run an API
contract test that verifies the client consumes `billable_units`.

## ISSUE-104 — authentication
Remove legacy token query parameters and send credentials through the
Authorization header. Before upgrading, scan client requests for query-string
tokens and verify authenticated requests in staging.

## ISSUE-106 — rate limits
Replace `retryAfter` with `retry_after_ms` and interpret the value as
milliseconds. Before upgrading, test retry timing against a staged rate-limit
response.

## ISSUE-110 — webhook signatures
Read `X-Webhook-Signature` instead of `X-Signature`; retain the old header only
for pre-2.4.0 clients. Before upgrading, verify a signed test webhook with the
new header.

## Release-manager disposition
- Reverted before release: ISSUE-105 and ISSUE-107; neither is shipped.
- Deferred to 2.5.0: ISSUE-108; it is not shipped in 2.4.0.
- Supporting documentation only: ISSUE-109; it does not count as product work.
- SEC-EMBARGO-9 remains embargoed; this guide intentionally contains no technical details.
