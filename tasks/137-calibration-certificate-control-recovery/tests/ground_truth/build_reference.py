from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path

TASK = Path(__file__).resolve().parents[2]
WORKSPACE = TASK / "workspace"
REFERENCE = TASK / "tests/reference"


def main() -> None:
    spec = importlib.util.spec_from_file_location("metrology_controller", WORKSPACE / "metrologyctl.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load metrology controller")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    plan_path = WORKSPACE / "certificate_control_plan.json"
    module.write_json(plan_path, module.derive()["plan"])
    module.preview(plan_path)
    module.apply(plan_path)
    module.verify(plan_path)
    handoff = """# Calibration-certificate control handoff

## Authority and recovery

All metrology events were verified with the local `lab-qms-events-2026` trust
material, normalized by sequence, and deduplicated by event identity. The
second delivery of `EV-M505-C` was identical and ignored. There was no
conflicting sequence. The stopped `MCR-INTERRUPTED-00` change to JOB-501 was
first restored from its SQLite before-image; the complete six-job projection
was then committed atomically under `MCR-20260815-01`.

## Reference traceability and measurement decisions

- JOB-501 / CERT-501 has an in-limit result (absolute error 0.20, expanded
  uncertainty 0.20, margin 0.10), but the signed `EV-RECALL-P9` makes STD-P9
  unusable from 2026-07-01, before the 2026-07-10 calibration. The certificate
  is locally revoked for reference recall, PRESSURE-P17 is locally quarantined,
  and USE-501-A and USE-501-B enter local recall review.
- JOB-502 / CERT-502 is traceable through STD-T4 and STD-ROOT-A. Its absolute
  error 0.60 plus uncertainty 0.40 equals the 1.00 tolerance, so the published
  inclusive guard-band rule accepts the boundary. The certificate is affirmed
  valid and TORQUE-T08 remains released.
- JOB-503 / CERT-503 used STD-M2 while it was still valid on 2026-07-20. Its
  later 2026-08-01 expiry does not retroactively invalidate the work. Error
  0.25 plus uncertainty 0.20 leaves margin 0.05, so the certificate is valid.
- JOB-504 / CERT-504 has a result attachment whose bytes do not match the signed
  checksum. The result is unavailable rather than guessed: the certificate and
  HUMIDITY-H04 are held for local evidence review.
- JOB-505 / CERT-505 uses the later corrected `RES-505-C`; its duplicated
  delivery does not apply twice. Error 0.45 plus uncertainty 0.10 exceeds the
  0.50 tolerance by 0.05, so the certificate is locally revoked as
  out-of-tolerance, CALIPER-C05 is locally quarantined, and USE-505-A enters
  recall review.
- JOB-506 / CERT-506 has an acceptable measurement but its STD-C3 chain is
  affected by signed recall from 2026-07-12, before calibration. The certificate
  is locally revoked and VOLTAGE-V06 is locally quarantined. Only USE-506-A is
  scoped; USE-506-OLD predates calibration and is preserved.

## Closure and boundary

Verification reconciled the protected source checkpoint, exact decimal
guard-band decisions, six certificate/asset states, four downstream review
records, journal restoration, and revision 74. The review packet is staged
offline and semantic replay leaves the database and packet byte-stable.

No certificate was sent externally, no customer or regulator was contacted,
and no physical asset was released, quarantined, recalled, or adjusted by this
offline workflow. All statuses and recall scopes remain local proposals for
quality-owner review.
"""
    (WORKSPACE / "calibration_control_handoff.md").write_text(handoff, encoding="utf-8")
    module.stage(plan_path)
    module.replay(plan_path)
    REFERENCE.mkdir(parents=True, exist_ok=True)
    for relative in (
        "certificate_control_plan.json", ".metrology_preview.json",
        "state/calibration.db", "state/verification.json",
        "state/review_packet.json", "state/replay_report.json",
        "calibration_control_handoff.md",
    ):
        destination = REFERENCE / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(WORKSPACE / relative, destination)
    for relative in (
        "certificate_control_plan.json", ".metrology_preview.json",
        "state/verification.json", "state/review_packet.json",
        "state/replay_report.json", "calibration_control_handoff.md",
    ):
        (WORKSPACE / relative).unlink()


if __name__ == "__main__":
    main()
