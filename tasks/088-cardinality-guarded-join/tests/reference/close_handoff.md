# Revenue close join handoff

The failed query joined orders to raw customer and rate rows, so duplicate
dimension keys multiplied the fact table. The repaired SQL first groups each
dimension by its business key, counts current rows, and exposes one usable row
only when exactly one record is current. Missing keys remain unmatched; keys
that exist with zero or multiple current rows are rejected as ambiguous. Null
customer keys are handled before either lookup.

The final ledger preserves all 12 order IDs once. Six orders match and six are
rejected across the five distinct reason categories. Valid negative order o12
remains a refund. Matched revenue ties to USD 585.00 after the refund, and no
rejected row contributes an amount. Both joins therefore retain their intended
many-to-one cardinality.

I ran `python3 bin/run_close.py`; it exited zero and generated the current CSV
and audit with no errors. Because the query resolves grouped keys rather than
listing visible order IDs, new customers, dates, and duplicate patterns follow
the same policy. Rerun the command after any source refresh and require a pass
before using the close ledger.
