# Repair notes

The exact upload ID is the session authority, and every ListParts page is checked before trusting any server part. Part numbers must be consecutive locally and strictly increasing across pagination. A server part is reused only when size and SHA-256 match; missing or stale same-number parts are scheduled for upload and completion is deferred because replacement returns a new ETag. A complete set uses ordered part-number/ETag pairs and the full checksum, while an unknown completion result is probed with object size and checksum instead of replayed.

I ran `PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v`; all tests pass. Residual executor risk includes paginated listing races, credentials, bounded retries, same-number overwrite, Complete response ambiguity, and final HeadObject integrity verification. No object-storage upload, overwrite, complete, abort, delete, or publication action was performed.
