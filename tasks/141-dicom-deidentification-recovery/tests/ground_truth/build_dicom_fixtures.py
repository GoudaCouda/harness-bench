from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

TASK = Path(__file__).resolve().parents[2]
W = TASK / "workspace"


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def dicom_bytes(dataset: dict[str, object]) -> bytes:
    return bytes(128) + b"DICM" + canonical(dataset)


STUDIES = [
    ("1.2.840.141.1", "ACC-REAL-001", "PAT-A", "RSCH-7H2K", -37, "ingested", None),
    ("1.2.840.141.2", "ACC-REAL-002", "PAT-B", "RSCH-9Q4M", 62, "ingested", None),
    ("1.2.840.141.3", "ACC-REAL-003", "PAT-C", "RSCH-1X8P", -14, "exported_protected", "EXP-PROTECTED-141"),
]


def dataset(study: str, series: str, sop: str, modality: str, patient: str, **extra: object) -> dict[str, object]:
    result: dict[str, object] = {
        "SOPClassUID": "1.2.840.10008.5.1.4.1.1.2" if modality == "CT" else "1.2.840.10008.5.1.4.1.1.4",
        "StudyInstanceUID": study,
        "SeriesInstanceUID": series,
        "SOPInstanceUID": sop,
        "Modality": modality,
        "PatientName": patient,
        "PatientID": "CLINICAL-" + patient[-1],
        "PatientBirthDate": "19760412",
        "StudyDate": "20260115",
        "AcquisitionDate": "20260116",
        "AccessionNumber": "ACC-REAL-" + patient[-1],
        "InstitutionName": "Synthetic General Hospital",
        "ReferringPhysicianName": "Doctor^Source",
        "BurnedInAnnotation": "NO",
        "PrivateTags": {"0019,1001": "CALIBRATION-OK", "0043,1029": "PATIENT-NOTE"},
        "PixelDigest": "sha256:" + digest((study + sop).encode()),
    }
    result.update(extra)
    return result


FILES = {
    "CT-141-A.dcm": dataset("1.2.840.141.1", "1.2.840.141.1.1", "1.2.840.141.1.1.1", "CT", "ALICE^A"),
    "SEG-141-A.dcm": dataset(
        "1.2.840.141.1", "1.2.840.141.1.2", "1.2.840.141.1.2.1", "SEG", "ALICE^A",
        SOPClassUID="1.2.840.10008.5.1.4.1.1.66.4",
        ReferencedSOPInstanceUID="1.2.840.141.1.1.1",
    ),
    "MR-BURNED-141.dcm": dataset("1.2.840.141.1", "1.2.840.141.1.3", "1.2.840.141.1.3.1", "MR", "ALICE^A", BurnedInAnnotation="YES"),
    "MR-141-B.dcm": dataset("1.2.840.141.2", "1.2.840.141.2.1", "1.2.840.141.2.1.1", "MR", "BOB^B"),
    "MR-141-B-COLLISION.dcm": dataset("1.2.840.141.2", "1.2.840.141.2.1", "1.2.840.141.2.1.1", "MR", "MALLORY^X", PixelDigest="sha256:collision"),
    "DOC-141-B.dcm": dataset("1.2.840.141.2", "1.2.840.141.2.2", "1.2.840.141.2.2.1", "DOC", "BOB^B", SOPClassUID="1.2.840.10008.5.1.4.1.1.104.1"),
    "LATE-141-C.dcm": dataset("1.2.840.141.3", "1.2.840.141.3.1", "1.2.840.141.3.1.2", "CT", "CAROL^C"),
    "UNKNOWN-141.dcm": dataset("1.2.840.141.999", "1.2.840.141.999.1", "1.2.840.141.999.1.1", "CT", "UNKNOWN^U"),
}

DELIVERIES = [
    ("DEL-07", "evidence/incoming/SEG-141-A.dcm", 7, "SEG-141-A.dcm"),
    ("DEL-02", "evidence/incoming/CT-141-A.dcm", 2, "CT-141-A.dcm"),
    ("DEL-03", "evidence/incoming/MR-BURNED-141.dcm", 3, "MR-BURNED-141.dcm"),
    ("DEL-04", "evidence/incoming/MR-141-B.dcm", 4, "MR-141-B.dcm"),
    ("DEL-04-RETRY", "evidence/incoming/MR-141-B.dcm", 8, "MR-141-B.dcm"),
    ("DEL-05", "evidence/incoming/MR-141-B-COLLISION.dcm", 9, "MR-141-B.dcm"),
    ("DEL-06", "evidence/incoming/DOC-141-B.dcm", 6, "DOC-141-B.dcm"),
    ("DEL-08", "evidence/incoming/LATE-141-C.dcm", 10, "LATE-141-C.dcm"),
    ("DEL-09", "evidence/incoming/UNKNOWN-141.dcm", 11, "UNKNOWN-141.dcm"),
]

POLICY = {
    "schema_version": 1,
    "recovery_id": "DICOM-DEID-141-R1",
    "uid_namespace": "2.25",
    "supported_sop_classes": [
        "1.2.840.10008.5.1.4.1.1.2",
        "1.2.840.10008.5.1.4.1.1.4",
        "1.2.840.10008.5.1.4.1.1.66.4",
    ],
    "direct_identifiers": ["PatientName", "PatientBirthDate", "AccessionNumber", "InstitutionName", "ReferringPhysicianName"],
    "date_fields": ["StudyDate", "AcquisitionDate"],
    "uid_fields": ["StudyInstanceUID", "SeriesInstanceUID", "SOPInstanceUID", "ReferencedSOPInstanceUID"],
    "private_tag_allowlist": ["0019,1001"],
    "rules": {
        "delivery_identity": "first delivery for an SOP Instance UID is authoritative; exact later content is duplicate; different later content is collision",
        "pixel_risk": "only BurnedInAnnotation=NO is eligible",
        "protected_boundary": "exported_protected studies are immutable and late instances are ignored",
        "reference_integrity": "referenced SOP must be eligible in the same export",
        "external_boundary": "local review staging only",
    },
}


def build() -> None:
    incoming = W / "evidence/incoming"
    policy_dir, state = W / "policy", W / "state"
    incoming.mkdir(parents=True, exist_ok=True)
    policy_dir.mkdir(parents=True, exist_ok=True)
    state.mkdir(parents=True, exist_ok=True)
    for name, value in FILES.items():
        (incoming / name).write_bytes(dicom_bytes(value))
    rows = []
    for delivery_id, path, sequence, output_name in DELIVERIES:
        data = (W / path).read_bytes()
        payload = json.loads(data[132:])
        rows.append({
            "delivery_id": delivery_id,
            "path": path,
            "source_sequence": sequence,
            "output_name": output_name,
            "sha256": digest(data),
            "sop_instance_uid": payload["SOPInstanceUID"],
            "study_instance_uid": payload["StudyInstanceUID"],
        })
    (W / "evidence/deliveries.jsonl").write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    (policy_dir / "deid_policy.json").write_text(json.dumps(POLICY, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    db = state / "imaging.db"
    db.unlink(missing_ok=True)
    with sqlite3.connect(db) as con:
        con.executescript("""
        CREATE TABLE studies(study_instance_uid TEXT PRIMARY KEY,accession_number TEXT NOT NULL,patient_key TEXT NOT NULL,pseudonym TEXT NOT NULL,date_shift_days INTEGER NOT NULL,state TEXT NOT NULL,protected_export_id TEXT);
        CREATE TABLE export_records(sop_instance_uid TEXT PRIMARY KEY,study_instance_uid TEXT NOT NULL,output_relpath TEXT NOT NULL,output_sha256 TEXT NOT NULL,recovery_id TEXT NOT NULL,status TEXT NOT NULL);
        CREATE TABLE recovery_runs(recovery_id TEXT PRIMARY KEY,status TEXT NOT NULL,source_checkpoint TEXT,semantic_plan_digest TEXT,external_exports INTEGER NOT NULL);
        CREATE TABLE recovery_journal(journal_id TEXT PRIMARY KEY,recovery_id TEXT NOT NULL,sop_instance_uid TEXT NOT NULL,before_json TEXT NOT NULL,orphan_relpath TEXT NOT NULL,restored INTEGER NOT NULL);
        CREATE TABLE system_state(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        """)
        con.executemany("INSERT INTO studies VALUES(?,?,?,?,?,?,?)", STUDIES)
        protected = dicom_bytes({"ProtectedExportID": "EXP-PROTECTED-141", "StudyInstanceUID": "2.25.141003", "SOPInstanceUID": "2.25.1410031", "PatientID": "RSCH-1X8P"})
        protected_path = W / "exports/protected/PROTECTED-141.dcm"
        protected_path.parent.mkdir(parents=True, exist_ok=True)
        protected_path.write_bytes(protected)
        con.execute("INSERT INTO export_records VALUES(?,?,?,?,?,?)", ("1.2.840.141.3.1.1", "1.2.840.141.3", "exports/protected/PROTECTED-141.dcm", digest(protected), "EXP-PROTECTED-141", "protected"))
        con.execute("INSERT INTO recovery_runs VALUES(?,?,?,?,?)", ("DICOM-INTERRUPTED-OLD", "interrupted", "old", "old", 0))
        orphan = W / "exports/orphan/INTERRUPTED-141.dcm"
        orphan.parent.mkdir(parents=True, exist_ok=True)
        orphan.write_bytes(dicom_bytes({"partial": True, "PatientName": "BOB^B"}))
        partial = ("1.2.840.141.2.1.1", "1.2.840.141.2", "exports/orphan/INTERRUPTED-141.dcm", digest(orphan.read_bytes()), "DICOM-INTERRUPTED-OLD", "partial")
        con.execute("INSERT INTO export_records VALUES(?,?,?,?,?,?)", partial)
        con.execute("INSERT INTO recovery_journal VALUES(?,?,?,?,?,0)", ("J-DICOM-141", "DICOM-INTERRUPTED-OLD", "1.2.840.141.2.1.1", json.dumps({"record_existed": False}, sort_keys=True), "exports/orphan/INTERRUPTED-141.dcm"))
        con.executemany("INSERT INTO system_state VALUES(?,?)", [("source_revision", "17"), ("pipeline_state", "interrupted")])
        con.commit()

    immutable = ["evidence/deliveries.jsonl", "policy/deid_policy.json"] + [f"evidence/incoming/{name}" for name in sorted(FILES)]
    manifest = {"schema_version": 1, "files": {name: digest((W / name).read_bytes()) for name in immutable}}
    (policy_dir / "source_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    build()
