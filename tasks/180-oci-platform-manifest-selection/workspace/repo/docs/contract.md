# Repair OCI multi-platform manifest selection contract

Filter OCI image-index descriptors by exact `os`, `architecture`, and `variant` (missing variant is a real value), then by target-required `os.features` and required annotations. Rank compatible descriptors by the count of preferred `os.features`. A unique highest score selects its digest; no candidate returns `no_match`; two or more candidates tied at the highest score return `ambiguous` rather than using lexical order as authority. Return exactly `status,selected_digest,reason,compatible,rejected`; compatible digests are ranked by score then digest and rejections are id-sorted with the first failed boundary reason. Malformed descriptors and duplicate ids raise `ValueError`.

The output has exactly `status,selected_digest,reason,compatible,rejected`. Status/reason pairs are `selected/most_preferred_compatible`, `no_match/no_compatible_descriptor`, or `ambiguous/equal_preference_candidates`. Each rejected record has exactly `id,reason`, with reason `os_arch_mismatch`, `variant_mismatch`, `missing_feature`, or `annotation_mismatch`.

The function must not mutate inputs. Run `python3 -m unittest discover -s tests -v` and `python3 bin/run_repair.py`, re-open `out/result.json`, and document verification evidence plus the offline boundary in `REPAIR_NOTES.md`.
