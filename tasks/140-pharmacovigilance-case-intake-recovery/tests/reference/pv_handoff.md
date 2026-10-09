# Pharmacovigilance intake recovery handoff

The PV-RECOVERY-140-R1 local projection was recovered from the interrupted SQLite journal. The ICSR-2402 before-image was restored before the new atomic transaction; the old partial receipt was removed and the interrupted run is marked recovered. All immutable source digests matched the source checkpoint.

ICSR-2401 remains at accepted version 2: MSG-2401-V3 crossed the accepted acknowledgement boundary, so the accepted record is immutable and the message was held rather than applied. ICSR-2408 likewise remains version 1 while its acknowledgement is pending; MSG-2408-V2 was not projected and the next action remains await ACK.

For ICSR-2402, source sequence placed MSG-2402-V2 before MSG-2402-V3 even though file order differed. Both contiguous versions were selected, with final version 3 staged to expedited review. DEL-02-RETRY reused the V2 message identity and was ignored as a duplicate. ICSR-2404 is a new fatal serious case at V1 and is staged for expedited local review under the seven-calendar-day class. ICSR-2407 accepted its non-serious follow-up V2 into routine review.

ICSR-2403 remains held: its nullification has no reason, and the later envelope also uses an unpermitted terminology version, so neither changes the durable case. ICSR-2405 remains held because the patient identity does not match the durable case key. ICSR-2406 is preserved at V1 because its inbound payload is duplicate content. The unknown ICSR-9999 delivery was ignored.

Verification closed the exact case, report-version, receipt, submission, journal, and revision state. The local review packet and manifest are bound to the normalized plan and source checkpoint by SHA-256 hashes, as is the recovery receipt. The equivalent plan changed array order and locator spelling; semantic replay left the database, packet, manifest, and receipt byte stable. A conflicting ICSR-2405 action was rejected with a non-zero exit, and recorded before/after hashes prove no mutation.

This is local review staging only. There was no transmission of any safety report, no acknowledgement, no regulator or sponsor notification, no patient or reporter contact, and no external safety-system update. A human safety reviewer must resolve holds and approve any later regulated action.
