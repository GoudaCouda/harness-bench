# 2.4.0 — 2025-10-14

## Added
- ISSUE-101: Added webhook signatures so integrators can verify outbound events.

## Changed
- ISSUE-103: Renamed the usage response field from `units` to `billable_units`.
- ISSUE-106: Replaced `retryAfter` with millisecond field `retry_after_ms`.
- ISSUE-110: Webhook verification now reads `X-Webhook-Signature` instead of `X-Signature`.

## Fixed
- ISSUE-102: Prevented duplicate invoice rows in CSV exports.

## Security
- ISSUE-104: Removed legacy query-string tokens; clients must use the Authorization header.
- SEC-PUBLIC-4: Includes the published session-fixation mitigation.
- SEC-EMBARGO-9: Includes embargoed security hardening; technical details will follow the advisory process.

## Supporting documentation
- ISSUE-109: Added usage-migration examples. This is documentation support, not a shipped product issue.
