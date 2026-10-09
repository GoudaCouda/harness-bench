# Repair DMARC alignment and disposition decisions contract

Evaluate DMARC over synthetic domains whose public-suffix result is supplied by `organizational_domains`. SPF aligns only when result is pass and its domain aligns under `aspf`; any passing DKIM signature may align under `adkim`. Strict alignment is exact after lowercase/trailing-dot normalization; relaxed alignment requires equal mapped organizational domains. DMARC passes if either mechanism aligns. On failure choose `sp` for a subdomain and `p` otherwise, then apply it only when `sample_bucket < pct`; outside sampling returns none. Return sorted decisions with pass/alignment/disposition/reason fields and pass/quarantine/reject counts. Unknown From domains, malformed signatures/buckets, bad policy, and duplicate ids raise `ValueError`.

The output object has exactly `decisions,summary`. Each id-sorted decision has exactly `id,pass,spf_aligned,dkim_aligned,disposition,reason`; disposition is `none`, `quarantine`, or `reject`, and reason is `dmarc_pass`, `outside_sample`, or `policy_applied`. Summary has exactly `pass,quarantine,reject`.

The function must not mutate inputs. Run `python3 -m unittest discover -s tests -v` and `python3 bin/run_repair.py`, re-open `out/result.json`, and document verification evidence plus the offline boundary in `REPAIR_NOTES.md`.
