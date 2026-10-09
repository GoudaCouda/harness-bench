# Vendor renewal recovery handoff

The malformed `primary_registry_export.json.part` was rejected as truncated; no
missing fact was inferred from it. The offline registry snapshot
`REG-SNAP-20260818-2200Z` and both correction records passed their local key and
signature checks. Registry versions and effective dates control each field.
`LNC-ALP-013` is effective and changes VND-ALP-17 to Alpine Field Systems LLC;
the Borealis version 10 correction is future-dated and therefore does not yet
supersede the snapshot name.

VND-ALP-17 and VND-BOR-22 are ready for internal approval. Borealis requires an
owner attestation under the entity/risk rule and the signed snapshot supplies
only the permitted minimum: status, dates, owner count, and source reference.
No owner identity attributes were requested or copied. VND-CYP-31 is held for a
minimum owner attestation because its high-risk private-corporation record has
none. VND-DEL-40 does not require that attestation, but its registration is
expired, so it remains pending external registry-renewal evidence.

The prior SQLite journal for VRR-INTERRUPTED-20260817 restored the partially
changed Alpine row before this batch committed. The local vendor-master update
then advanced one revision atomically. Preview and verification bind the
protected source checkpoint, normalized semantic plan, and final logical vendor
state. The pending-review receipt is local evidence only; replay confirmed the
same renewal identity is database- and receipt-byte-stable.

Every vendor retained its inactive-pending-activation state. No vendor was
activated. No registry filing, approval, supplier outreach, message, payment,
or external account action was executed. No banking information was collected,
copied, exposed, or included in this handoff. Compliance and vendor-master
reviewers must perform any later authorized action outside this recovery.
