# Active tasks

This directory contains the 254 packages in the current Standard254 release.
It preserves the frozen Standard237 packages (`001`–`237`) and adds the
additive policy-drain packages `238`–`254`. The default runner and active
validators scan only this directory.

Do not edit a locked Standard237 package in place. Numeric continuation starts
at `255`. Publish a new versioned manifest and lock when membership changes.

Package structure and acceptance rules are in
`docs/TASK_AUTHORING_AND_ACCEPTANCE.md`.
