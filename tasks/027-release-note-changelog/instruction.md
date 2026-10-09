Act as release manager for the version/date in `$WORKSPACE/release/commits.json`.
Reconcile commits with `issues.csv` and `breaking_changes.md`.

Create `$WORKSPACE/CHANGELOG.md` with a release heading and concise Added,
Changed, Fixed, Security, and Supporting documentation sections when applicable.
Summarize each shipped product issue once even if it has multiple commits. Do
not present reverted, deferred, or docs-only work as shipped product change.
Mention the public security advisory at a safe high level; acknowledge embargoed
hardening without exploit, endpoint, payload, or implementation details.

Create `$WORKSPACE/MIGRATION_GUIDE.md` for every shipped breaking issue. For
each, identify the old behavior/interface, required new behavior, and a concrete
pre-upgrade validation. Include a release-manager disposition section listing
reverted and deferred issue IDs and the supporting-docs issue, so operators know
they are not shipped features. Do not disclose embargoed details.

Do not modify sources, use the current date, invent issues, claim publication or
deployment, or use the network.
