# Northstar revision recovery handoff

The package used the highest current event for every change. EV-114 is the
later verified signed legal correction for CH-01 and supersedes EV-107; it was
accepted with CH-02, CH-05, CH-08, and CH-09. CH-03, CH-06, and CH-10 were
rejected because campaign scope, controlled-retention deletion, and public
portal publication lack governing authority. CH-04 and CH-07 were dependency-
invalidated after their prerequisites failed, rather than being applied on
their own.

TX-04 had already durably recorded CH-05/EV-508 before the document checkpoint
was lost. Recovery reconciled that contact decision into the DOCX without a
second journal row. TX-05 appended the other nine outcomes in deterministic
topological order and closed one recovery transaction.

The controller resolved the actual OOXML w:ins/w:del pairs in
approved_bulletin.docx. The title, unaffected control note, paragraph order,
bookmarks, styles, comments, header, footer, relationships, and all other
non-document package parts were preserved. The clean document has no remaining
tracked insertion or deletion markup.

Preview, apply, and hash-bound verification passed. Reapplying the normalized
plan and verifying again were idempotent: document bytes, journal rows,
transaction count, database logical state, and verification receipt remained
stable. The package is staged only for internal approval. No publication,
portal export, message send, notification, external approval, or other
external action occurred.
