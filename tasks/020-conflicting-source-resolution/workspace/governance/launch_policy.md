# Launch-control policy LC-4

The gate may be `ready_limited` only when the authorized date and scope,
approved capital, certified primary operator, and onboarded cohort are all
resolved from their scoped authorities **and** the customer communication has a
recorded Legal approval. Otherwise the gate must be `hold` and name the open
approval as a blocker.

Queued actions must match the gate. On hold, no customer announcement or
service activation may remain `queued` or `running`. Work outside the current
regulatory authorization must be `blocked` with its prerequisite. Internal
readiness checks may remain `ready` because they create no external effect.

Do not rewrite prior decision events. Append one event for the current review,
referencing evidence by workspace-relative path. Do not treat the press draft
or social digest as approval.
