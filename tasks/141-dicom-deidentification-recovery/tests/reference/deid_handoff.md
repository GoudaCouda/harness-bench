# DICOM de-identification recovery handoff

## Delivery authority and quarantine

The nine-delivery queue was adjudicated by first SOP Instance UID authority, not file name or date. DEL-02 CT-141-A, DEL-07 SEG-141-A, and DEL-04 MR-141-B were eligible and generated locally. DEL-04-RETRY was an exact duplicate redelivery and was ignored. DEL-05 reused the MR SOP UID with different content and was quarantined as a collision. DEL-03 was quarantined because BurnedInAnnotation was YES, so removing metadata alone could not address pixel text. DEL-06 was an unsupported encapsulated document. DEL-09 belonged to an unknown study. DEL-08 was ignored at the already-exported protected study boundary; its protected export was preserved.

## Transformation and referential integrity

Direct identifier tags PatientName, PatientBirthDate, AccessionNumber, InstitutionName, and ReferringPhysicianName were removed. PatientID was replaced by the study pseudonym. Non-allowlisted private tag 0043,1029 was removed while approved calibration tag 0019,1001 remained. Study and acquisition dates shifted by -37 days for PAT-A and +62 days for PAT-B. Study, series, SOP, and referenced SOP UIDs were remapped under namespace 2.25. The SEG reference resolves to the remapped CT SOP UID; it was not invented or left clinical.

## Recovery, verification, and local boundary

The J-DICOM-141 before-image journal was restored, the partial export record was rolled back, and PHI-bearing orphan INTERRUPTED-141.dcm was replaced by a non-PHI rollback tombstone before one local projection committed. Independent verification reparsed all three emitted DICOM datasets and confirmed identifier removal, date shifts, private-tag policy, UID graph, file hashes, and the protected boundary. The local research review packet and packet manifest bind the checkpoint, generated instances, quarantine set, handoff, and artifact hashes.

An array- and evidence-order-equivalent plan replayed as a semantic no-op with the SQLite database and export tree unchanged. A conflict probe changed DEL-03's quarantine reason; apply rejected it with a non-zero exit and unchanged database and export-tree hashes. Nothing was uploaded, transmitted, published, sent to PACS, or sent to a research repository. No patient was contacted, no clinical system was updated, and no source study was deleted.
