# Repair the OCI layer merger

An offline image-inspection service reconstructs the wrong root filesystem when
layers contain whiteouts, opaque directories, or file/directory replacement.
Work only in `/workspace/repo`.

Read `docs/layer_contract.md`, inspect the synthetic layer manifests, policy,
runner, and public tests, then repair `src/layer_merge.py` as a general pure
implementation. Do not hard-code fixture paths or digests.

Run the public unittest suite and `python bin/merge_layers.py`. The final run
must create `out/rootfs.json` and `out/audit.json`; parse both again. Write
`LAYER_NOTES.md` covering lower-layer precedence, explicit and opaque whiteouts,
same-layer survival, type replacement, ancestor rules, symlink/path safety,
strict validation, commands, and results.

Do not extract archives, mount images, invoke a container runtime, edit evidence,
or claim that a live image or filesystem was changed.
