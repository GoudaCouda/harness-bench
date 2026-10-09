# Ownership and review policy

The current pull-request SHA is `e4b201`. The last matching CODEOWNER pattern
wins. Every changed path needs one approval from its resolved owner team on the
current SHA. If a review has a `paths` array, it covers only matching paths;
without that array it is team-wide. A current-SHA `changes_requested` review
from the owner blocks that path. Old-SHA and dismissed reviews do not qualify.
