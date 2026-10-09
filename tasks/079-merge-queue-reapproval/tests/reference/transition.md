# Protected-queue transition

The conflict-resolution commit moved the item from `aaa111` to `bbb222`, so
round-one checks and owner approval cannot carry forward. Current Linux and
Windows builds pass. The current security scan is still pending; the old-SHA
security pass is only history. The current license gate fails on a GPL-only
transitive parser package and requires dependency remediation plus a rerun.

Owner approval exists only for `aaa111`, so current-SHA reapproval is required.
Release reviewer rela did approve `bbb222`, and that gate remains satisfied.
Security, license, and owner_approval are therefore the three pending gates.

Verification reconciled six unique current-SHA gates to a blocked revalidation
state. The PR has not been merged, and no check, review request, production, or
other external action was executed.
