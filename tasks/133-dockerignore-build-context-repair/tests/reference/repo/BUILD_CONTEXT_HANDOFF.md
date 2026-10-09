# Build context containment handoff

The context leak came from ordered negation precedence. Although `config/*` initially excluded both configuration files, the later `!config/*.json` rule re-included the developer-only `config/local.json` together with the required default. A separate `!docs/runbook.md` exception also sent documentation that the Dockerfile never consumes.

I narrowed the configuration exception to `!config/default.json` and removed the documentation reinclusion. Required inputs remain: Dockerfile, package metadata, application code and template, runtime default configuration, the ignore file itself, and the retained runtime license. Local environment data, Git metadata, synthetic secrets, dependencies, generated output, tests, and docs are excluded.

I ran `python3 tools/audit_context.py`, inspected `out/context_manifest.json`, and confirmed no missing-required entries, protected leaks, or prefix leaks. The manifest contains the exact seven intended paths with current SHA-256 values and a valid result. Verification was offline; no image was built or published and no registry was contacted.
