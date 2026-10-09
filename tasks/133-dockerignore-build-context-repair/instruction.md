# Repair a leaking Docker build context

Work only in `/workspace/repo`. A local pre-build audit shows that the current `.dockerignore` sends developer-only configuration and documentation while the runtime image needs only the application, default configuration, package metadata, Dockerfile, and retained license.

Inspect the complete tree, the ordered ignore rules, `policy/context_policy.json`, and `tools/audit_context.py`. Repair only `.dockerignore`; do not delete or sanitize source evidence. Run the offline context audit and leave its current machine-readable result at `out/context_manifest.json`. Verify both required runtime inputs and protected exclusions, then write `BUILD_CONTEXT_HANDOFF.md` with the precedence cause, exact scope, commands, and evidence.

Do not build or publish an image, contact a registry, edit protected files, or claim deployment.
