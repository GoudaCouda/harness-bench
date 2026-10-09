# Runtime and scheduling

## Trusted execution lifecycle

For every run, the controller:

1. loads the active release from `catalog/release.yaml` (currently
   `catalog/standard274.yaml`) and verifies all 274 active packages; an
   independent suite can be selected with `--suite-root`;
2. freezes the task tree, selected manifest, controller/runtime identities,
   image IDs, and model-service ID under a unique run root;
3. stages one independent workspace and OpenClaw state volume per trial;
4. starts the agent as UID/GID 1000 with read-only rootfs, all capabilities
   dropped, `no-new-privileges`, resource limits, and only current mounts;
5. removes the agent, freezes the terminal workspace, and starts the grader with
   `--network none`, read-only workspace, and hidden evaluator bundle;
6. writes result, grade, trace-integrity, isolation, and mutation evidence.

The agent never receives the repository, host home, Docker socket, task tests,
ground truth, reference output, other trials, or grader bundle.

## Parallel execution

`--workers N` controls independent trials inside one controller. It does not
create vLLM data-parallel ranks. Multiple controllers use disjoint shard
indices, distinct run roots, and identical frozen suite/controller/runtime/
image/grader/model-service identities. A multi-rank vLLM service also requires
the rank appropriate to each endpoint.

Start with four workers per TP4 Gemma endpoint, probe at intended concurrency,
and increase only if queue/KV/cache metrics and deadlines are healthy. Static
shards can have uneven long tails; never let two controllers write one run root.

Freeze services with `tools/freeze_model_service.py` or
`tools/freeze_model_service_pool.py`, probe with
`tools/probe_model_service.py`, and merge with `tools/merge_shards.py`. The merge
tool rejects incompatible identities.

## Monitoring and adjudication

Monitor `summary.json`, per-task `result.json`/`grade.json`, endpoint health,
vLLM waiting/running requests, Docker disk, and container liveness. At run end,
audit every trajectory with its grade blocks. Grade intact timeout and model
error workspaces rather than replacing them with automatic zeros or excluding
them. Rerun only infrastructure failures or explicit diagnostics; never merge
partial artifacts from attempts.

Run roots and raw trajectories are operational evidence under `artifacts/` and
are intentionally not versioned with the collaborator repository.
