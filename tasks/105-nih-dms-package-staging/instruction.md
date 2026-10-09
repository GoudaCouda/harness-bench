# Reconcile and stage a consent-safe NIH-style data-sharing package

You are the research data steward for a synthetic participant study. A draft
plan routes every file to one open repository six months after publication. A
previous build then copied a consent-prohibited transcript before it was
interrupted. Current consent, repository capabilities, publication timing, and
the physical staged bytes must now agree.

Work only in `$WORKSPACE`. Read `policy_2026-01.md` first. Then:

1. Run `python3 dmsctl.py --help`, `python3 dmsctl.py status`, and
   `python3 dmsctl.py scan`.
2. Inspect `project.json`, `repositories.json`,
   `prior_build_checkpoint.json`, every file under `assets/`, and the preserved
   `interrupted_staging/` tree. A copied file is not proof that its route is allowed.
3. Create `deposit_plan.json` using the exact public schema in the policy. Use
   each project `asset_id` exactly once, select only capability-compatible
   external repositories, retain explicit exclusions, increment interrupted
   revision 1, and keep all approval and external-action states pending/false.
4. Run `python3 dmsctl.py build`. It validates the candidate plan, rebuilds
   `staging/` atomically from protected source bytes, writes
   `package_manifest.csv`, and replaces the interrupted build state. Revise the
   plan from its errors when necessary.

## Required result

- C1 participant survey data is a controlled file at an external repository
  that supports controlled files, DUA workflow, and access-committee review.
  The survey dictionary may be public.
- C2 voice and transcript files remain `excluded_external_file` with
  `repository: internal_only`; neither byte stream may occur anywhere in the
  final external staging tree. Audio metadata is staged only as a public
  metadata record at a capable external repository.
- Analysis code and its environment inventory travel together to one
  code-capable external repository. Aggregate outputs use a public-file route.
- The package uses a real repository split and releases participant data no
  later than the planned publication date. `plan_revision`, `privacy_review`,
  and `institutional_review` all remain `pending`.
- `package_manifest.csv` is controller-generated and contains every asset,
  including exclusions, exact source hashes, staged hashes and local evidence.
  Do not hand-edit it or place extra files under `staging/`.

Equivalent valid repository choices are allowed where the visible catalog
provides all required capabilities. Evidence references are local
`basename#identifier` values; do not cite generated outputs, hidden files,
URLs, absolute paths, or parent paths.

Create `revised_plan.md` explaining controlling-policy precedence, inventory,
consent decisions, each repository route, the repository split, publication
timing, reconciliation of the interrupted prohibited copy, byte/hash
verification, pending review gates, and offline/no-deposit status.

Finally run:

```text
python3 dmsctl.py validate
python3 dmsctl.py stage
python3 dmsctl.py verify-stage
python3 dmsctl.py verify-stage
```

The local stage creates `.dms_stage_state.json` and
`dms_stage_receipt.json`, bound to protected source bytes and the exact plan,
manifest, and handoff. Both verification runs must pass without changing state
or receipt.

Keep `policy_2026-01.md`, `project.json`, `repositories.json`,
`prior_build_checkpoint.json`, `assets/`, and `dmsctl.py` unchanged. Do not use
the network, expose excluded participant bytes, upload or deposit data, contact
a repository, or claim privacy/institutional approval.
