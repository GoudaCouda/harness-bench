# GitHub Actions OIDC trust contract

Implement `authorize_tokens(roles, tokens, policy)` without mutating inputs.
Inputs are decoded claim facts; structural violations raise `ValueError`, while
well-formed untrusted requests produce denied decisions.

Roles are sorted unique objects with exact keys `role_id`, `issuer`,
`audiences`, `owner_id`, `repository_ids`, `subject_mode`, `allowed_refs`,
`allowed_environments`, and `required_workflow`. IDs are decimal strings;
audiences/ref/environment lists are sorted unique. Subject mode is `legacy` or
`immutable`. Required workflow is null or a lowercase
`owner/repo/.github/workflows/file.yml@` plus exactly 40 lowercase hex digits.

Tokens are ordered unique requests with exact keys `request_id`, `role_id`,
`iss`, `aud`, `sub`, `repository`, `owner_id`, `repository_id`, `ref`,
`environment`, `job_workflow_ref`, `event_name`, and `id_token_permission`.
Repository is lowercase `owner/name`; environment is null or a lowercase ASCII
context that may contain colon. Event is `push`, `workflow_dispatch`, or
`pull_request`; permission is `none`, `read`, or `write`.

Reconstruct subject exactly from claims. Legacy prefix is `repo:owner/name`.
Immutable prefix is `repo:owner@OWNER_ID/name@REPOSITORY_ID`. If environment is
non-null, suffix is `:environment:ENVIRONMENT` with each colon in the value
encoded as `%3A`; otherwise suffix is `:ref:REF`. No substring or wildcard
matching is allowed.

Deny in precedence: unknown role, ID-token permission not `write`, issuer,
audience, owner ID, repository ID, globally required immutable mode, subject
mismatch, disallowed pull request, disallowed environment/ref, or required
workflow mismatch. A required workflow must match the full pinned SHA string.
Otherwise authorize. Decisions have exact keys `request_id`, `role_id`,
`status`, and `reason`; summary reports exact `request_count`, `authorized`, and
`denied`. No JWT, filesystem, network, GitHub, cloud, clock, process, random, or
environment access is allowed.
