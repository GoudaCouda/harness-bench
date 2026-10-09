# Split namespace plugin repository

The API and metrics teams publish independent source roots under the shared `acme` namespace. Runtime composition supports both source-root orders. Preserve module ownership; do not copy vendor modules into service roots or add path mutation at import time.
