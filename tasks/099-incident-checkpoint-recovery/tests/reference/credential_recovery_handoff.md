# Credential rotation incident recovery handoff

Incident INC-CR-204 was reconstructed offline under recovery
REC-INC-CR-204-02. Durable markers, not checkpoint claims or expected
validation targets, control completion. The checkpoint correctly records
svc-api but falsely marks svc-billing complete; it omits the durable completion
for svc-search. It also misclassifies clean svc-catalog, while svc-metrics is
correctly absent. The missing svc-vault entry remains pending.

svc-api version 8 and svc-search version 12 have incident-scoped durable
markers and observed validation, so both are preserve_committed and were not
replayed. svc-billing remains at version 12 for target 13, svc-vault remains at
version 3 for target 4, and svc-worker was restored from its recovery_journal
before-image to version 4 for target 5. These three accounts each have exactly
one local staged request. svc-catalog version 7 and svc-metrics version 2 are
clean preserve_unchanged accounts and were not queued.

Journal J-401 restored the svc-worker account before-image. Journal J-402
removed the partial queue insertion before the replacement queue was committed
atomically. The local rotation_queue bundle, queue_manifest, recovery_receipt,
and verification report close over the same semantic plan and state hashes.
The reordered-plan replay completed as an idempotent_noop with zero database
mutation.

No credential was rotated or revoked. No external service, account,
notification, production system, or incident state was changed, and the
incident remains open for an authorized future operator to execute, validate,
and monitor the three pending rotations.
