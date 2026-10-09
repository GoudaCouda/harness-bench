#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path


TASK = Path(__file__).resolve().parents[2]
REFERENCE = TASK / "tests" / "reference"


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="hb107-reference-") as temporary:
        workspace = Path(temporary) / "workspace"
        shutil.copytree(TASK / "workspace", workspace)
        included_ids = [
            "EXT-ASTER-P12",
            "EXT-BOREALIS-P12-V2",
            "EXT-CEDAR-P12",
            "EXT-DELTA-P12",
            "EXT-ELM-P12",
            "EXT-FLINT-P12",
        ]
        catalog = {
            row["record_id"]: row
            for row in json.loads(
                (workspace / "extraction_catalog.json").read_text(encoding="utf-8")
            )
        }
        excluded_reasons = {
            "EXT-BOREALIS-P12-V1": "superseded by the accepted scoped correction",
            "EXT-BOREALIS-P6": "wrong protocol timepoint",
            "EXT-BOREALIS-QOL12": "wrong protocol outcome",
            "EXT-FLINT-P12-SECONDARY": "duplicate report for an included study",
            "EXT-GARNET-P12": "wrong protocol population",
        }
        manifest = {
            "analysis_id": "SR-NIMBUS-2026-U1",
            "protocol_version": "3.2",
            "included_records": [
                {
                    "study_id": catalog[record_id]["study_id"],
                    "record_id": record_id,
                    "evidence": [catalog[record_id]["evidence_ref"]],
                }
                for record_id in included_ids
            ],
            "excluded_records": [
                {
                    "record_id": record_id,
                    "reason": reason,
                    "evidence": [catalog[record_id]["evidence_ref"]],
                }
                for record_id, reason in excluded_reasons.items()
            ],
            "correction_chain": [
                {
                    "correction_id": "CORR-BOREALIS-2026-02",
                    "superseded_record_id": "EXT-BOREALIS-P12-V1",
                    "replacement_record_id": "EXT-BOREALIS-P12-V2",
                    "evidence": [
                        "correction_notices.json#CORR-BOREALIS-2026-02",
                        "extraction_catalog.json#EXT-BOREALIS-P12-V1",
                        "extraction_catalog.json#EXT-BOREALIS-P12-V2",
                    ],
                }
            ],
        }
        write_json(workspace / "analysis_manifest.json", manifest)
        command = ["python3", "analysisctl.py"]
        subprocess.run(
            [*command, "build", "--manifest", "analysis_manifest.json"],
            cwd=workspace,
            check=True,
        )
        claims = [
            {
                "claim_id": "CLAIM-PRIMARY",
                "prior_status": "no_conclusive_benefit",
                "new_status": "benefit_supported",
                "action": "revise",
                "evidence": [
                    "publication_claims.json#CLAIM-PRIMARY",
                    "meta_analysis.json#pooled_random_effects",
                    "sensitivity.csv#BOREALIS",
                ],
            },
            {
                "claim_id": "CLAIM-HETEROGENEITY",
                "prior_status": "moderate_or_higher",
                "new_status": "low",
                "action": "revise",
                "evidence": [
                    "publication_claims.json#CLAIM-HETEROGENEITY",
                    "meta_analysis.json#heterogeneity",
                ],
            },
            {
                "claim_id": "CLAIM-SAFETY",
                "prior_status": "not_assessed",
                "new_status": "not_assessed",
                "action": "unchanged",
                "evidence": ["publication_claims.json#CLAIM-SAFETY"],
            },
        ]
        write_json(workspace / "claim_updates.json", claims)
        (workspace / "update_handoff.md").write_text(
            """# Nimbus quantitative update handoff

The version 3.2 protocol controls adults, relapse at 12 months, risk ratios,
and the random-effects DerSimonian-Laird inverse-variance model. Accepted
correction CORR-BOREALIS-2026-02 supersedes EXT-BOREALIS-P12-V1 with V2 because
the primary event counts were transposed between arms. The unrelated quality-
of-life clarification does not change this outcome.

Six independent eligible studies are included. The superseded Borealis row,
six-month row, other-outcome row, duplicate Flint report, and adolescent
Garnet report are excluded with local evidence. No report is counted as an
additional study merely because it has a distinct report ID.

The stale random-effects risk ratio was 0.860598 (95% CI 0.593568 to 1.247758)
with I2 59.608978%. The corrected bundle is 0.677309 (95% CI 0.537716 to
0.853141), tau-squared 0, and I2 0%. The leave-Borealis-out row remains below
the null at 0.725466 (95% CI 0.553589 to 0.950706), and every other leave-one-
out row is preserved in sensitivity.csv.

CLAIM-PRIMARY changes to benefit_supported and CLAIM-HETEROGENEITY changes to
low under the published thresholds. CLAIM-SAFETY remains not_assessed because
the update has no safety outcome. The controller regenerated the complete
study and pooled forest plot from protected rows rather than editing the stale
figure.

Validation, hash-bound staging, and two stable verification passes establish
only a local review bundle. No review was published or submitted, no author was
contacted, and no external approval is claimed. A second analyst must review
the corrected extraction and claims before any publication workflow.
""",
            encoding="utf-8",
        )
        subprocess.run(
            [*command, "validate", "--manifest", "analysis_manifest.json"],
            cwd=workspace,
            check=True,
        )
        subprocess.run(
            [*command, "stage", "--manifest", "analysis_manifest.json"],
            cwd=workspace,
            check=True,
        )
        subprocess.run([*command, "verify-stage"], cwd=workspace, check=True)
        subprocess.run([*command, "verify-stage"], cwd=workspace, check=True)
        if REFERENCE.exists():
            shutil.rmtree(REFERENCE)
        REFERENCE.mkdir(parents=True)
        names = [
            "analysis_manifest.json",
            "meta_analysis.json",
            "sensitivity.csv",
            "forest_plot.svg",
            "claim_updates.json",
            "update_handoff.md",
            ".analysis_build_state.json",
            ".analysis_stage_state.json",
            "analysis_stage_receipt.json",
        ]
        for name in names:
            shutil.copy2(workspace / name, REFERENCE / name)


if __name__ == "__main__":
    main()
