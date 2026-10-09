# Retrieval contract

1. Each `corpus/*.txt` file is a document. `doc_id` is the filename without
   `.txt`.
2. Tokens are maximal casefolded alphanumeric runs.
3. A document matches a query only when **all** `terms` appear at least once.
4. Score is the sum of token counts for those terms.
5. `ranked[query_id]` lists matching `doc_id`s by descending score, then
   lexicographic `doc_id`.
6. `scores[query_id]` maps those `doc_id`s to their integer scores.

Use the `query_id` and `doc_id` values from the inputs.
