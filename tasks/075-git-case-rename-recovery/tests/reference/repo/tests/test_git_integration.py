import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.case_rename import plan_case_renames  # noqa: E402


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        text=True,
        capture_output=True,
    )
    return result.stdout.strip()


class RealGitRenameTests(unittest.TestCase):
    def test_case_only_plan_preserves_real_index_blob(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            git(repo, "init", "-q")
            git(repo, "config", "user.email", "fixture@example.invalid")
            git(repo, "config", "user.name", "Fixture")
            git(repo, "config", "core.ignoreCase", "true")
            (repo / "src").mkdir()
            (repo / "src" / "API.py").write_text("VALUE = 1\n", encoding="utf-8")
            git(repo, "add", "src/API.py")
            git(repo, "commit", "-qm", "seed")
            oid = git(repo, "rev-parse", "HEAD:src/API.py")

            plan = plan_case_renames(
                [{"path": "src/API.py", "oid": oid, "stage": 0}],
                [{"from": "src/API.py", "to": "src/api.py"}],
                True,
            )
            for operation in plan["operations"]:
                self.assertEqual(operation["op"], "git_mv")
                git(repo, "mv", operation["from"], operation["to"])

            self.assertEqual(git(repo, "ls-files"), "src/api.py")
            self.assertEqual(git(repo, "hash-object", "src/api.py"), oid)


if __name__ == "__main__":
    unittest.main()
