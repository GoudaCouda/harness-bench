#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path


TASK = Path(__file__).resolve().parents[2]
REFERENCE = TASK / "tests" / "reference"


PLAN = {
    "schema_version": 1,
    "plan_id": "DMS-NEURO-042",
    "policy_effective": "2026-01-25",
    "plan_revision": 2,
    "publication_release_date": "2026-05-15",
    "assets": [
        {"asset_id": "survey_raw", "disposition": "controlled_file", "repository": "SafeRepo", "access": "controlled_reuse", "evidence_refs": ["project.json#survey_raw", "repositories.json#SafeRepo", "policy_2026-01.md#consent-and-route-rules"]},
        {"asset_id": "survey_dictionary", "disposition": "public_file", "repository": "OpenBox", "access": "public", "evidence_refs": ["project.json#survey_dictionary", "repositories.json#OpenBox"]},
        {"asset_id": "audio_raw", "disposition": "excluded_external_file", "repository": "internal_only", "access": "no_external_sharing", "evidence_refs": ["project.json#audio_raw", "project.json#IRB-17", "policy_2026-01.md#consent-and-route-rules"]},
        {"asset_id": "audio_transcript_deid", "disposition": "excluded_external_file", "repository": "internal_only", "access": "no_external_sharing", "evidence_refs": ["project.json#audio_transcript_deid", "project.json#IRB-17", "prior_build_checkpoint.json#DMS-NEURO-042-build-attempt-1"]},
        {"asset_id": "audio_metadata", "disposition": "metadata_only_record", "repository": "OpenBox", "access": "public_metadata", "evidence_refs": ["project.json#audio_metadata", "repositories.json#OpenBox"]},
        {"asset_id": "analysis_code", "disposition": "code_file", "repository": "CodeArchive", "access": "public", "evidence_refs": ["project.json#analysis_code", "repositories.json#CodeArchive"]},
        {"asset_id": "analysis_environment", "disposition": "code_file", "repository": "CodeArchive", "access": "public", "evidence_refs": ["project.json#analysis_environment", "repositories.json#CodeArchive"]},
        {"asset_id": "model_outputs", "disposition": "public_file", "repository": "OpenBox", "access": "public", "evidence_refs": ["project.json#model_outputs", "repositories.json#OpenBox"]},
    ],
    "approval_gates": {
        "plan_revision": "pending",
        "privacy_review": "pending",
        "institutional_review": "pending",
    },
    "repository_split_required": True,
    "external_deposit_executed": False,
}


HANDOFF = """# Revised local DMS package plan

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
"""


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="dms-reference-") as temporary:
        workspace = Path(temporary) / "workspace"
        shutil.copytree(TASK / "workspace", workspace)
        (workspace / "deposit_plan.json").write_text(
            json.dumps(PLAN, indent=2) + "\n", encoding="utf-8"
        )
        (workspace / "revised_plan.md").write_text(HANDOFF, encoding="utf-8")
        for command in ("build", "validate", "stage", "verify-stage", "verify-stage"):
            subprocess.run(
                ["python3", "dmsctl.py", command],
                cwd=workspace,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        if REFERENCE.exists():
            shutil.rmtree(REFERENCE)
        REFERENCE.mkdir(parents=True)
        for name in (
            "deposit_plan.json",
            "package_manifest.csv",
            "revised_plan.md",
            ".dms_build_state.json",
            ".dms_stage_state.json",
            "dms_stage_receipt.json",
        ):
            shutil.copy2(workspace / name, REFERENCE / name)
        shutil.copytree(workspace / "staging", REFERENCE / "staging")


if __name__ == "__main__":
    main()
