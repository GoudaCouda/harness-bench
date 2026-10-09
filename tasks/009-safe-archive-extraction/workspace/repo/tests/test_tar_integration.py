import io
import sys
import tarfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.archive_preflight import plan_extraction  # noqa: E402


POLICY = {
    "case_sensitive": True,
    "allowed_types": ["file", "dir"],
    "max_files": 10,
    "max_file_bytes": 1024,
    "max_total_bytes": 2048,
}


def tar_entries(name: str) -> list[dict[str, object]]:
    payload = io.BytesIO()
    with tarfile.open(fileobj=payload, mode="w") as archive:
        member = tarfile.TarInfo(name)
        member.size = 4
        archive.addfile(member, io.BytesIO(b"data"))
    payload.seek(0)
    with tarfile.open(fileobj=payload, mode="r:") as archive:
        return [
            {
                "path": member.name,
                "type": "file" if member.isfile() else "dir",
                "size": member.size,
            }
            for member in archive.getmembers()
        ]


class RealTarPreflightTests(unittest.TestCase):
    def test_real_tar_member_is_planned(self):
        entries = tar_entries("release/app.txt")
        self.assertEqual(plan_extraction(entries, POLICY), entries)

    def test_real_tar_escape_is_rejected(self):
        with self.assertRaises(ValueError):
            plan_extraction(tar_entries("../escape.txt"), POLICY)


if __name__ == "__main__":
    unittest.main()
