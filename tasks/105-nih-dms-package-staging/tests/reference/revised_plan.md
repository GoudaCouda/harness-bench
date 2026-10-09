# Revised local DMS package plan

## Authority, inventory, and timing

The 2026-01-25 policy snapshot controls over the older draft. All eight source
assets are represented exactly once. Participant survey availability is moved
from publication plus six months to the planned publication date, 2026-05-15.
That timing correction and the repository split remain pending institutional
review and plan revision.

## Consent-safe routes

`survey_raw` is participant data under C1 and is staged as a controlled file in
SafeRepo, whose catalog entry supports controlled bytes, DUA workflow and an
access committee. The non-participant survey dictionary is public in OpenBox.

C2 audio is minimized. The raw voice payload and de-identified transcript are
excluded external files and remain internal-only source evidence. The earlier
interrupted attempt copied the transcript into OpenBox, but the reconciled
build replaces that tree and proves that neither prohibited byte stream occurs
in staging. Only `audio_metadata` is staged as a public metadata-only record.

Analysis code and its environment inventory travel together to CodeArchive.
Aggregate model outputs are public in OpenBox. No one repository satisfies the
controlled, public-metadata and code responsibilities, so this is a deliberate
repository split rather than a preference-based duplication.

## Verification and review boundary

The controller rebuilt staging from protected source bytes and generated a
manifest with source and staged SHA-256 values. Every staged file is byte-equal
to its declared source; exclusions have no staged path. The final inventory,
manifest, plan revision and hashes close against one build state.

The package is staged offline for plan revision, privacy review, and
institutional review; every gate is pending. There was no deposit, upload,
repository contact, participant-data release, or external approval. A later
authorized operator must review this local package before any real action.
