# Stage a permanent electronic-record transfer for review

You are the records-transfer specialist preparing offline transfer
`TR-2026-017`. The source snapshot contains superseded scans, an access audio
derivative, and a checksum discrepancy. Build a review-ready package without
blessing unsupported evidence or claiming submission to an archive.

Work only in `$WORKSPACE`.

1. Read `transfer_request.json`, `format_policy.json`, `inventory.json`,
   `metadata.json`, `qc_results.json`, and `checksum_register.json`.
2. Run `python3 transferctl.py status` and reconcile each required record across
   metadata, format/codec, QC, preservation-master, and SHA-256 evidence.
3. Create `transfer_plan.json`:

   ```json
   {
     "transfer_id": "TR-2026-017",
     "selections": [
       {"record_id": "...", "source_path": "source/..."}
     ],
     "quarantine": [
       {"record_id": "...", "source_path": "source/...", "reason": "..."}
     ]
   }
   ```

   Select exactly one evidence-supported preservation candidate per stageable
   record. An unresolved registered-checksum mismatch must be quarantined with
   reason `checksum_mismatch`; do not rewrite the register or bless a newly
   calculated digest.
4. Run `python3 transferctl.py preview transfer_plan.json` and correct every
   failed item check. Then run `python3 transferctl.py apply transfer_plan.json`.
   The tool creates the staged record copies, manifest, checksum file,
   quarantine ledger, and validation receipt; do not hand-author those outputs.
5. Run `python3 transferctl.py verify`, apply the identical plan once more, and
   verify again to confirm deterministic staging.
6. Write `records_handoff.md` for the records officer. Explain the selected
   scan and audio master, the excluded candidates, the checksum quarantine, the
   metadata/format/QC/checksum validation, and that the package is staged—not
   submitted or accessioned.

Do not edit any source evidence or `transferctl.py`. Do not delete the source
files. Do not claim an ERA submission, archival accession, source-record
disposal, or external communication.
