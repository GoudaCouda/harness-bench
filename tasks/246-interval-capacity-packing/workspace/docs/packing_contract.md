# Packing contract

Each job occupies a half-open minute interval `[start, end)` and consumes
`size` capacity on one machine for every overlapping minute.

1. Consider jobs in order of increasing `end`, breaking ties by
   lexicographically smaller `job_id`.
2. For each job, assign the lexicographically smallest `machine_id` whose
   capacity is never exceeded at any minute after the job is added.
3. If no machine can hold the job, append that `job_id` to `unplaced`.
4. `assignments` maps placed `job_id`s to `machine_id`s.

Do not invent identifiers. Intervals that do not overlap may share a
machine even when their sizes sum to more than capacity.
