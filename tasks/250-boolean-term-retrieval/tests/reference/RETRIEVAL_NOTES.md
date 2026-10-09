# Retrieval notes

## Decision

Documents were tokenized by casefolded alphanumeric runs. A document enters
a query ranking only when all terms appear at least once. Remaining hits
sort by descending term-count score, then by doc_id.

## Verification

Re-counting tokens for mill and gate reproduced the ranked doc_id lists.

## Remaining risk

Stemming would merge mill/mills and change ranks. That adapter needs a
check before rollout. No search cluster was contacted.
