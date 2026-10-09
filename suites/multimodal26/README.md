# Multimodal 001–026 suite

This lightweight suite reuses all 26 packages from `multimodal-tasks/`
through relative task-directory links. Run it with:

```bash
python tools/run_benchmark.py \
  --suite-root suites/multimodal26 \
  --base-url "$HB_MODEL_URL" \
  --model MODEL_ID \
  --model-service-id "$HB_MODEL_SERVICE_ID" \
  --harness openclaw \
  --workers 4 \
  --temperature 1 \
  --run-root artifacts/evaluations/multimodal26-shard-0
```

The frontend runtime (Node.js, Vite/React dependencies, Playwright and
Chromium) is embedded directly in the harness and grader images, so do not
pass `--experimental-task-environments` for this suite. For an authenticated
upstream, additionally pass `--upstream-api-key-file` with the path to a
one-line secret file outside the repository.
