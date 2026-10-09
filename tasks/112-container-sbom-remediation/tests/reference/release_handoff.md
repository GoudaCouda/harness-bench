# Report-worker container remediation handoff

Both original paths, report-worker -> archive-stack -> zip-stream and
report-worker -> document-loader -> zip-stream, retained vulnerable
zip-stream 1.4.2. The least-change repair advances archive-stack from 4.8.0 to
4.9.0 and document-loader from 2.2.0 to 2.3.0, yielding the shared secure
zip-stream 1.5.1 while preserving render-native, pixel-abi, telemetry-core, and
log-helper.

Archive-stack 5.0.0 was rejected because its Node 22 engine exceeds the pinned
Node 20.16 base. Document-loader 2.4.0 was rejected because fast-crc-native
requires glibc 2.38 while the image provides glibc 2.36. The rebuilt SBOM and
independent frozen-advisory scan report zero applicable findings. The native
ABI report confirms platform, Node-API, glibc, and all three smoke profiles.

The new provenance preserves the trusted hermetic-image-v3 builder, offline
build type, source revision, and pinned base material while adding the exact
Containerfile and new package-lock digest and binding the rebuilt image. The
local state is staged pending release approval. No push, deployment, approval,
publication, or external notification occurred.
