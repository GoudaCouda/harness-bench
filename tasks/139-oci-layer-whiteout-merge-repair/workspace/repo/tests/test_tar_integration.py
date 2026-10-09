import io
import tarfile
import unittest

from src.layer_merge import merge_layers


def layer_from_tar(digest, members):
    payload = io.BytesIO()
    with tarfile.open(fileobj=payload, mode="w") as archive:
        for path, kind, body, mode in members:
            info = tarfile.TarInfo(path)
            info.mode = mode
            if kind == "dir":
                info.type = tarfile.DIRTYPE
                archive.addfile(info)
            else:
                data = body.encode("utf-8")
                info.size = len(data)
                archive.addfile(info, io.BytesIO(data))
    payload.seek(0)
    entries = []
    with tarfile.open(fileobj=payload, mode="r:") as archive:
        for member in archive.getmembers():
            marker = member.name.rsplit("/", 1)[-1].startswith(".wh.")
            entries.append(
                {
                    "path": member.name,
                    "kind": "dir" if member.isdir() else "file",
                    "digest": None if member.isdir() else "sha256:empty" if marker else "sha256:fixture",
                    "target": None,
                    "mode": member.mode,
                }
            )
    return {"digest": digest, "entries": entries}


class TarIntegrationTests(unittest.TestCase):
    def test_real_tar_headers_preserve_same_layer_file_after_opaque_marker(self):
        lower = layer_from_tar("sha256:lower", [("app", "dir", "", 0o755), ("app/old", "file", "old", 0o644)])
        upper = layer_from_tar("sha256:upper", [("app/.wh..wh..opq", "file", "", 0), ("app/new", "file", "new", 0o644)])
        paths = [row["path"] for row in merge_layers([lower, upper], {"implicit_dir_mode": 0o755})["rootfs"]]
        self.assertIn("app/new", paths)
        self.assertNotIn("app/old", paths)


if __name__ == "__main__":
    unittest.main()
