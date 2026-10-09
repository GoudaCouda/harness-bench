from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any


def prepare_runtime(runtime: dict[str, Any]) -> dict[str, Any]:
    sandbox = Path(runtime["sandbox"])
    workspace = Path(runtime["workspace"])
    helper = runtime.get("run_trusted_helper")
    if not callable(helper):
        raise RuntimeError("runner did not provide the isolated setup helper")

    if workspace.exists():
        shutil.rmtree(workspace)
    workspace.mkdir(parents=True)
    workspace.chmod(0o777)
    sandbox.chmod(0o777)

    script = r'''
import os
import shutil
import subprocess
from pathlib import Path

runtime = Path(os.environ["HB_RUNTIME"])
workspace = Path(os.environ["HB_WORKSPACE"])
init_repo = runtime / "init-repo"
remote = runtime / "remote.git"
clone_repo = runtime / "workspace-clone"

def git(*args: str, cwd: Path | None = None) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=str(cwd) if cwd else None,
        text=True, capture_output=True, check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError(f"git {args!r} cwd={cwd}: {detail}")
    return completed.stdout

git("init", "--bare", str(remote))
git("init", "-b", "main", str(init_repo))
git("config", "user.name", "Bench User", cwd=init_repo)
git("config", "user.email", "bench-cutover@local", cwd=init_repo)
(init_repo / "README.md").write_text("# Helix mill cutover\n", encoding="utf-8")
(init_repo / "HISTORY_POLICY.md").write_text(
    "# History policy\n\n"
    "A change may be delivered only when every reachable commit is free of "
    "credential-shaped additions such as API_TOKEN. Deleting a secret in a "
    "later commit does not remove it from Git history. When a leaked commit "
    "sits between two legitimate commits, rebuild main from the legitimate "
    "snapshots and prove `python3 tools/hist_check.py main` passes.\n",
    encoding="utf-8",
)
(init_repo / "tools").mkdir()
(init_repo / "tools" / "hist_check.py").write_text(
    """#!/usr/bin/env python3
import re
import subprocess
import sys

ref = sys.argv[1] if len(sys.argv) > 1 else "HEAD"

def git(*args):
    p = subprocess.run(["git", *args], text=True, capture_output=True)
    if p.returncode:
        print(p.stderr.strip() or p.stdout.strip())
        raise SystemExit(2)
    return p.stdout

root = git("rev-list", "--max-parents=0", ref).strip().split()[-1]
commits = git("rev-list", "--reverse", root + ".." + ref).split()
if root:
    commits = [root, *commits]
violations = []
credential = re.compile(r"(?im)^\\+.*(?:api[_-]?token|access[_-]?key|client[_-]?secret)\\s*[:=]")
for commit in commits:
    patch = git("show", "--format=", "--no-ext-diff", commit)
    if credential.search(patch):
        violations.append(commit)
tree = git("ls-tree", "-r", "--name-only", ref).splitlines()
if "secrets.env" in tree:
    print("FAIL: secrets.env is present in the tree")
    raise SystemExit(1)
if "src/app.py" not in tree or "docs/runbook.md" not in tree:
    print("FAIL: required later work is missing from the tree")
    raise SystemExit(1)
if violations:
    print("FAIL: credential-shaped addition in reachable history: " + " ".join(x[:12] for x in violations))
    raise SystemExit(1)
print("PASS: " + str(len(commits)) + " reachable commit(s) are clean and required paths exist")
""",
    encoding="utf-8",
)
(init_repo / "tools" / "hist_check.py").chmod(0o755)
git("add", ".", cwd=init_repo)
git("commit", "-m", "chore: initialize cutover policy and checker", cwd=init_repo)
git("remote", "add", "origin", str(remote), cwd=init_repo)
git("push", "-u", "origin", "main", cwd=init_repo)
git("--git-dir", str(remote), "symbolic-ref", "HEAD", "refs/heads/main")

git("checkout", "-b", "work/cutover", cwd=init_repo)
(init_repo / "src").mkdir()
(init_repo / "src" / "app.py").write_text(
    '"""Helix mill cutover helper."""\n\nSTATUS = "HELIX_APP_READY"\n',
    encoding="utf-8",
)
git("add", "src/app.py", cwd=init_repo)
git("commit", "-m", "feat: add mill cutover helper", cwd=init_repo)
git("tag", "good-app", cwd=init_repo)
(init_repo / "secrets.env").write_text("API_TOKEN=hb-cutover-leak-4417\n", encoding="utf-8")
git("add", "secrets.env", cwd=init_repo)
git("commit", "-m", "chore: stash cutover debug token", cwd=init_repo)
git("tag", "leak-secret", cwd=init_repo)
(init_repo / "docs").mkdir()
(init_repo / "docs" / "runbook.md").write_text(
    "# Cutover runbook\n\nHELIX_RUNBOOK_OK: run the mill helper before opening the gate.\n",
    encoding="utf-8",
)
git("add", "docs/runbook.md", cwd=init_repo)
git("commit", "-m", "docs: add mill cutover runbook", cwd=init_repo)
git("tag", "good-docs", cwd=init_repo)
git("push", "-u", "origin", "work/cutover", cwd=init_repo)
git("push", "origin", "good-app", "good-docs", cwd=init_repo)

git("clone", str(remote), str(clone_repo))
git("checkout", "work/cutover", cwd=clone_repo)
for source in sorted(clone_repo.rglob("*")):
    relative = source.relative_to(clone_repo)
    if ".git" in relative.parts:
        continue
    destination = workspace / relative
    if source.is_dir():
        destination.mkdir(parents=True, exist_ok=True)
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
(workspace / ".git").write_text(f"gitdir: {clone_repo / '.git'}\n", encoding="utf-8")
workspace_git = clone_repo / ".git"
git("--git-dir", str(workspace_git), "config", "core.worktree", str(workspace))
git("--git-dir", str(workspace_git), "config", "user.name", "Bench User")
git("--git-dir", str(workspace_git), "config", "user.email", "bench-cutover@local")
'''
    helper(["python3", "-c", script])
    remote_path = str(sandbox / "remote.git") if runtime.get("reference_mode") else "/runtime/remote.git"
    return {"REMOTE_PATH": remote_path, "_RUN_TRUSTED_HELPER": helper}
