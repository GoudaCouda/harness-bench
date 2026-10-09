# Bulk export contract

- Every export is scoped to the authenticated tenant. A `request_token` is
  idempotent only within that tenant; another tenant may reuse the same token.
- `exports:read` permits ordinary exports. Requests with `include_pii=true`
  additionally require `customers:pii` before any job is created or reused.
- A queued job may be leased by exactly one worker. Claiming the next job and
  recording its owner/lease is one atomic compare-and-set operation.
- A job becomes `complete` only after the archive is durably uploaded and its
  checksum and object ETag are stored. A transient upload failure must leave a
  retryable, non-complete job.
- Snapshot order is the tuple `(updated_at, id)`. The next page is strictly
  after both cursor components so equal timestamps neither skip nor duplicate
  customers.
- An omitted `ttl_hours` defaults to 24. Explicit integer `0` is meaningful:
  purge immediately after the delivery window closes.
- Signed download URLs are bearer secrets and must never enter application
  logs. Job IDs and expiry timestamps are safe operational metadata.

Severity policy for this review: direct cross-tenant or unauthorized PII
exposure is `critical`; duplicate execution, false completion, bearer-secret
logging, or cross-tenant request suppression is `high`; bounded snapshot or
retention correctness regressions are `medium`.
