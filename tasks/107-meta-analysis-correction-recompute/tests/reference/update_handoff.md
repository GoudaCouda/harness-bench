# Nimbus quantitative update handoff

The version 3.2 protocol controls adults, relapse at 12 months, risk ratios,
and the random-effects DerSimonian-Laird inverse-variance model. Accepted
correction CORR-BOREALIS-2026-02 supersedes EXT-BOREALIS-P12-V1 with V2 because
the primary event counts were transposed between arms. The unrelated quality-
of-life clarification does not change this outcome.

Six independent eligible studies are included. The superseded Borealis row,
six-month row, other-outcome row, duplicate Flint report, and adolescent
Garnet report are excluded with local evidence. No report is counted as an
additional study merely because it has a distinct report ID.

The stale random-effects risk ratio was 0.860598 (95% CI 0.593568 to 1.247758)
with I2 59.608978%. The corrected bundle is 0.677309 (95% CI 0.537716 to
0.853141), tau-squared 0, and I2 0%. The leave-Borealis-out row remains below
the null at 0.725466 (95% CI 0.553589 to 0.950706), and every other leave-one-
out row is preserved in sensitivity.csv.

CLAIM-PRIMARY changes to benefit_supported and CLAIM-HETEROGENEITY changes to
low under the published thresholds. CLAIM-SAFETY remains not_assessed because
the update has no safety outcome. The controller regenerated the complete
study and pooled forest plot from protected rows rather than editing the stale
figure.

Validation, hash-bound staging, and two stable verification passes establish
only a local review bundle. No review was published or submitted, no author was
contacted, and no external approval is claimed. A second analyst must review
the corrected extraction and claims before any publication workflow.
