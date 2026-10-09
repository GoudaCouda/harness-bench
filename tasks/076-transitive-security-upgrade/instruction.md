# Repair a coupled monorepo dependency incident

The offline `dispatch-console` monorepo lock graph is affected by multiple advisories reached through the root application and its upload worker. Production and CI remain on Node 18. Inspect the advisory bundle, registry metadata, runtime policy, both manifests, the shared lock graph, and compatibility fixtures.

Choose the least-change coherent set of supported direct-parent upgrades across both workspaces that clears every applicable advisory, satisfies peer/runtime constraints, and preserves every required compatibility profile. Do not patch vulnerable transitive entries in isolation or add overrides. Update `repo/package.json`, `repo/packages/worker/package.json`, and the complete shared `repo/package-lock.json`, including recursive dependency, peer, integrity, workspace-root, and repository metadata. Preserve unrelated development tooling.

Run `python3 -B repo/check_upgrade.py repo/package.json repo/package-lock.json` until it passes. Create `upgrade_handoff.md` documenting all vulnerable paths in both workspaces, alternatives rejected and why, the selected direct and recursive graph, peer/profile reasoning, lock coherence, fixture results, preserved scope, and release-review boundary. Local verification is not publication or deployment.
