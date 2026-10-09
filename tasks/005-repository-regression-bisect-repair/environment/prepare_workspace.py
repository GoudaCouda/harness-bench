from __future__ import annotations

import os
import subprocess
from pathlib import Path


V1 = '''"""Collection eligibility policy."""

ALLOWED_REGIONS = {"US", "CA"}


def collection_decision(invoice):
    """Return (eligible, reason) without causing an external action."""
    if invoice.get("region") not in ALLOWED_REGIONS:
        return False, "region_blocked"
    if invoice.get("trial") is True:
        return False, "trial_account"
    if invoice.get("status") not in {"active", "delinquent"}:
        return False, "account_status"
    if invoice.get("amount_due", 0) <= 0:
        return False, "no_balance"
    return True, "eligible"
'''

V2 = V1.replace(
    'ALLOWED_REGIONS = {"US", "CA"}',
    'ALLOWED_REGIONS = {"US", "CA", "GB"}',
)

V3 = V2.replace(
    '{"active", "delinquent"}',
    '{"active", "suspended"}',
)

V4 = V3.replace(
    'return True, "eligible"',
    'return True, "eligible_balance"',
)

COMMITS = (
    ("seed invoice collection policy", V1, "2026-07-01T09:00:00+00:00"),
    ("enable GB collection routing", V2, "2026-07-02T09:00:00+00:00"),
    ("refactor account status eligibility", V3, "2026-07-03T09:00:00+00:00"),
    ("clarify eligible audit reason", V4, "2026-07-04T09:00:00+00:00"),
)


def _git(repo: Path, *args: str, env: dict[str, str] | None = None) -> None:
    subprocess.run(
        ["git", *args],
        cwd=repo,
        env=env,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )


def main() -> None:
    workspace = Path(os.environ.get("HB_WORKSPACE", "/workspace"))
    repo = workspace / "repo"
    source = repo / "src/ledger_router/eligibility.py"
    if (repo / ".git").exists():
        print('{"status":"already_prepared"}')
        return

    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.name", "HarnessBench")
    _git(repo, "config", "user.email", "benchmark@example.invalid")

    base_env = os.environ.copy()
    base_env.update(
        {
            "GIT_AUTHOR_NAME": "HarnessBench",
            "GIT_AUTHOR_EMAIL": "benchmark@example.invalid",
            "GIT_COMMITTER_NAME": "HarnessBench",
            "GIT_COMMITTER_EMAIL": "benchmark@example.invalid",
        }
    )
    for index, (subject, content, timestamp) in enumerate(COMMITS):
        source.write_text(content, encoding="utf-8")
        if index == 0:
            _git(repo, "add", ".")
        else:
            _git(repo, "add", "src/ledger_router/eligibility.py")
        env = {**base_env, "GIT_AUTHOR_DATE": timestamp, "GIT_COMMITTER_DATE": timestamp}
        _git(repo, "commit", "-q", "-m", subject, env=env)
    print('{"status":"prepared","commits":4}')


if __name__ == "__main__":
    main()
