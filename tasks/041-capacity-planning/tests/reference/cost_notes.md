# Cost notes

For checkout-api, the maximum of the latest seven peaks is 1,960 RPS. Applying the 1.22 launch multiplier gives 2,391.2 RPS, and 30% headroom raises required capacity to 3,108.56 RPS. Three on-demand c7g.xlarge instances provide 3,660 RPS for $0.456/hour across two zones. Six c7g.large instances cost the same $0.456, so the published tie-break selects the three-instance plan; five m7i.large instances would cost $0.480.

For pricing-worker, the maximum of the latest seven peaks is 500 RPS. Applying 1.15 gives 575 RPS, and 20% headroom gives 690 RPS. One on-demand m7i.large provides 700 RPS for $0.096/hour. A one-on-demand/one-spot c7g.large mix would cost $0.108 and is therefore rejected even though its 50% spot share is allowed.

The combined cost is $0.552/hour, below both service budgets ($0.600 and $0.200) and the $0.780 total budget.
