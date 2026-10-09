#!/usr/bin/env python3
from __future__ import annotations
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")

def git(repo,*args):
    return subprocess.run(["git",*args],cwd=repo,check=True,text=True,
                          stdout=subprocess.PIPE,stderr=subprocess.PIPE)

with tempfile.TemporaryDirectory(prefix="hb-git-worktree-") as raw:
    root=Path(raw); repo=root/"repo"; repo.mkdir()
    git(repo,"init","-q")
    git(repo,"config","user.email","hb@example.invalid")
    git(repo,"config","user.name","HarnessBench")
    (repo/"tracked.txt").write_text("seed\n")
    git(repo,"add","tracked.txt"); git(repo,"commit","-qm","seed")

    stale=root/"stale"
    git(repo,"worktree","add","--detach",str(stale),"HEAD")
    porcelain=git(repo,"worktree","list","--porcelain").stdout
    if f"worktree {stale}" not in porcelain:
        raise SystemExit("worktree porcelain probe failed")
    shutil.rmtree(stale)
    dry=git(repo,"worktree","prune","--dry-run","--verbose","--expire","now")
    if "stale" not in (dry.stdout+dry.stderr):
        raise SystemExit("missing worktree prune dry-run probe failed")

    git(repo,"worktree","prune","--expire","now")
    locked=root/"locked"
    git(repo,"worktree","add","--detach",str(locked),"HEAD")
    git(repo,"worktree","lock","--reason","retain",str(locked))
    shutil.rmtree(locked)
    locked_dry=git(repo,"worktree","prune","--dry-run","--verbose","--expire","now")
    if "locked" in (locked_dry.stdout+locked_dry.stderr):
        raise SystemExit("locked worktree was proposed for prune")

version=subprocess.run(["git","--version"],check=True,text=True,
                       stdout=subprocess.PIPE).stdout.strip()
match=re.fullmatch(r"git version (\d+)\.(\d+)(?:\.\d+)?(?:[.-].*)?", version)
if match is None or not ((2, 39) <= tuple(map(int, match.groups())) < (3, 0)):
    raise SystemExit(f"expected Git >=2.39,<3, found: {version}")
print(json.dumps({"python3":"3.12","git":version,
                  "worktree_porcelain":"passed","prune_dry_run":"passed",
                  "locked_retention":"passed","external_repository":"not_used"},
                 sort_keys=True))
