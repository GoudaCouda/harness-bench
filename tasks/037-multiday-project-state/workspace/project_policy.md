# Northstar change-control policy

- Completed milestones are immutable history. A failed checkpoint remains failed but must be rescheduled as planned work under the same milestone ID.
- Every unfinished milestone must start at least one day after all dependencies finish. `day` is its start day and `duration_days` is inclusive work duration.
- Owners must be eligible and available for the milestone's full duration; one owner cannot cover overlapping milestones.
- Choose exactly one documented connector recovery option. Its incremental cost counts toward the plan. Planned cost is the sum of all milestone costs plus that increment and may not exceed USD 92,000.
- Pending gates must appear in the affected milestone condition with their evidence ID. Approval cannot be inferred from future work.
- A general launch cannot fall in the Day 28–31 customer freeze.
- Keep conflicting Sales and Privacy requests open for steering. Existing decision rows are append-only; supersede tentative decisions with a new row citing authoritative evidence.
