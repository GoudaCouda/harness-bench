# Exact source-ID aliases

This file resolves every `provenance.source_ids` entry in task metadata to the
public workflow material it adapts, or to the retrospective record described in
the task's `design.md`. It does not add new provenance claims.

## Workflow family cards

Family IDs name a public, documented work practice from which a task family was
derived. Fixtures are synthetic; the references describe the workflow, not the
task data.

| Family ID | Workflow | Public references | Tasks |
|---|---|---|---|
| `SE-01` | Pull request review with merge gates | [Pull request reviews](https://docs.github.com/en/pull-requests/reference/pull-request-reviews); [Protected branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches) | `074`, `079` |
| `SE-02` | CI failure diagnosis, selective re-runs and result archiving | [Re-running workflows and jobs](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/re-run-workflows-and-jobs) | `070` |
| `SE-03` | Triage, upgrade and verification of dependency security updates | [Dependabot version updates](https://docs.github.com/en/code-security/concepts/supply-chain-security/dependabot-version-updates); [Managing Dependabot pull requests](https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/manage-your-dependency-security/manage-dependabot-prs) | `076` |
| `SE-04` | Conflict repair and reversibility of schema and data migrations | [Django migrations](https://docs.djangoproject.com/en/5.2/topics/migrations/) | `072` |
| `SE-05` | From versioning decisions to trusted package releases | [Semantic Versioning](https://semver.org/); [Python packaging flow](https://packaging.python.org/en/latest/flow/); [Publishing with GitHub Actions](https://packaging.python.org/en/latest/guides/publishing-package-distribution-releases-using-github-actions-ci-cd-workflows/) | `078` |
| `DA-01` | Geographic and variable alignment across Census datasets | [Census API core concepts](https://www.census.gov/data/developers/guidance/api-user-guide.Core_Concepts.html); [Census datasets](https://www.census.gov/data/developers/data-sets.html) | `083` |
| `DA-02` | Source, unit and time-series reconciliation of World Bank indicators | [World Bank indicator API](https://datahelpdesk.worldbank.org/knowledgebase/articles/889392); [Indicator API queries](https://datahelpdesk.worldbank.org/knowledgebase/articles/898599-indicator-api-queries) | `084` |
| `DA-03` | Quality flags, coverage and anomaly handling in station time series | [GHCN-Daily](https://www.ncei.noaa.gov/products/land-based-station/global-historical-climatology-network-daily) | `085` |
| `DA-04` | Versioned analysis of initial, revised and seasonally adjusted figures | [CPI seasonal adjustment](https://www.bls.gov/cpi/seasonal-adjustment/); [CES revisions](https://www.bls.gov/sae/tables/revisions/home.htm) | `086` |
| `DA-06` | Cardinality guards for messy multi-table joins | [pandas merge](https://pandas.pydata.org/docs/reference/api/pandas.merge.html); [Duplicate labels](https://pandas.pydata.org/docs/user_guide/duplicates.html) | `088` |
| `IT-01` | Kubernetes Pod and Service failure diagnosis | [Debug applications](https://kubernetes.io/docs/tasks/debug/debug-application/); [Debug Services](https://kubernetes.io/docs/tasks/debug/debug-application/debug-service/) | `096` |
| `IT-04` | Alert grouping, inhibition and routing repair | [Alertmanager](https://prometheus.io/docs/alerting/latest/alertmanager/); [Alertmanager configuration](https://prometheus.io/docs/alerting/latest/configuration/) | `094` |
| `IT-05` | Classification, containment, recovery and evidence handoff for security incidents | [NIST SP 800-61r3](https://csrc.nist.gov/pubs/sp/800/61/r3/final); [CISA incident response playbooks](https://www.cisa.gov/resources-tools/resources/federal-government-cybersecurity-incident-and-vulnerability-response-playbooks) | `095`, `099` |
| `OP-01` | Item-by-item adjudication and merging of multi-reviewer document revisions | [Accepting or rejecting changes (LibreOffice)](https://help.libreoffice.org/latest/en-GB/text/shared/guide/redlining_accept.html) | `110` |
| `RE-01` | Auditable systematic-review screening and the PRISMA flow | [PRISMA 2020](https://www.prisma-statement.org/prisma-2020); [PRISMA 2020 flow diagram](https://www.prisma-statement.org/prisma-2020-flow-diagram) | `100` |
| `RE-03` | Cross-source research evidence graphs and coverage audits | [About the OpenAlex data](https://help.openalex.org/hc/en-us/articles/24397285563671-About-the-data); [OpenAlex API](https://developers.openalex.org/api-reference/introduction) | `102` |
| `RE-05` | Version chains and citation relations for research-data DOIs | [DataCite versioning](https://support.datacite.org/docs/versioning); [Citations and references](https://support.datacite.org/docs/citations-and-references) | `104` |
| `BO-01` | Three-way match of purchase orders, receipts and invoices | [Oracle Procurement match approval](https://docs.oracle.com/en/cloud/saas/procurement/26a/oapro/match-approval-level-options.html) | `121` |
| `BO-04` | Contract completion and file closeout | [FAR Subpart 4.8](https://www.acquisition.gov/far/subpart-4.8); [DFARS PGI 204.8](https://www.acquisition.gov/dfarspgi/pgi-204.8-contract-files) | `124` |
| `CS-02` | Impact and urgency prioritization, routing and escalation | [Jira Service Management priority levels](https://support.atlassian.com/jira-service-management-cloud/docs/what-are-priority-levels-in-jira-service-management/); [Escalation policies](https://support.atlassian.com/jira-service-management-cloud/docs/what-are-escalation-policies/) | `170` |
| `HR-03` | FMLA leave intake, eligibility notices and supporting documentation | [FMLA leave process](https://www.dol.gov/agencies/whd/fmla/FMLA-leave-process) | `111` |
| `HR-06` | Recording and time-limited reporting of serious workplace injuries | [OSHA severe injury reporting](https://www.osha.gov/report/); [OSHA recordkeeping](https://www.osha.gov/recordkeeping) | `195` |
| `HR-08` | Access revocation on employee departure or transfer | [NIST SP 800-171r3](https://nvlpubs.nist.gov/nistpubs/SpecialPublications/800-171r3/NIST.SP.800-171r3.html) | `200` |

## Retrospective source records

The task packages carrying `HB-RETRO-*` IDs did not retain external workflow
citations. Each exact ID below therefore maps only to a private historical
HarnessBench authoring record with no public URL, plus the retrospective,
evidence-limited provenance statement in that task's `design.md`.

| Exact source ID | Retained task package |
|---|---|
| `HB-RETRO-001` | `001-meeting-summary` |
| `HB-RETRO-002` | `002-email-triage` |
| `HB-RETRO-003` | `003-git-pr-merge` |
| `HB-RETRO-004` | `004-office-docs` |
| `GIT-BISECT-01` | `005-repository-regression-bisect-repair` |
| `NARA-TRANSFER-01` | `006-digital-record-transfer-staging` |
| `NARA-QM-01` | `006-digital-record-transfer-staging` |
| `HB-RETRO-007` | `007-security-injection-defense` |
| `PG-PITR` | `007-database-point-in-time-recovery-drill` |
| `PG-VERIFYBACKUP` | `007-database-point-in-time-recovery-drill` |
| `HB-RETRO-008` | `008-db-doc-consistency` |
| `HB-RETRO-009` | `009-provider-failover-audit` |
| `HB-RETRO-010` | `010-incident-runbook-synthesis` |
| `HB-RETRO-011` | `011-calendar-scheduling-conflict` |
| `HB-RETRO-012` | `012-meeting-action-tracker` |
| `HB-RETRO-013` | `013-ppt-brief-generation` |
| `HB-RETRO-014` | `014-contract-summary-risk` |
| `HB-RETRO-015` | `015-email-thread-merge` |
| `HB-RETRO-016` | `016-expense-packet-review` |
| `HB-RETRO-017` | `017-word-revision-plan` |
| `HB-RETRO-018` | `018-cross-doc-citation-check` |
| `HB-RETRO-019` | `019-customer-followup-draft` |
| `HB-RETRO-020` | `020-conflicting-source-resolution` |
| `KUBERNETES-LEASE-V1` | `033-rate-limit-lease-reconciliation` |
| `KUBERNETES-API-CONCURRENCY` | `033-rate-limit-lease-reconciliation` |
| `NPM-PACKAGE-JSON` | `035-workspace-dependency-resolution` |
| `NPM-PACKAGE-LOCK` | `035-workspace-dependency-resolution` |
| `OPENAPI-3.1.2` | `036-consumer-api-compatibility` |
| `JSON-SCHEMA-2020-12-VALIDATION` | `036-consumer-api-compatibility` |
| `PYTEST-FIXTURE-SCOPE` | `042-integration-test-isolation` |
| `PYTEST-FLAKY-TESTS` | `042-integration-test-isolation` |
| `UNICODE-LDML-TR35` | `043-localization-fallback-repair` |
| `CLDR-PLURAL-RULES` | `043-localization-fallback-repair` |
| `ICU-MESSAGE-FORMAT` | `043-localization-fallback-repair` |
| `HB-RETRO-021` | `021-citation-consistency-audit` |
| `CTG-STUDY-DATA` | `021-clinical-trial-registry-result-reconcile` |
| `FDA-CTG-ROLE` | `021-clinical-trial-registry-result-reconcile` |
| `HB-RETRO-022` | `022-policy-clause-retrieval` |
| `HB-RETRO-023` | `023-research-brief-synthesis` |
| `HB-RETRO-024` | `024-repo-architecture-map` |
| `HB-RETRO-025` | `025-dependency-upgrade-compat` |
| `HB-RETRO-026` | `026-code-review-risk-report` |
| `HB-RETRO-027` | `027-release-note-changelog` |
| `HB-RETRO-028` | `028-excel-like-cleaning` |
| `HB-RETRO-029` | `029-multitable-join-analysis` |
| `HB-RETRO-030` | `030-sql-query-report` |
| `W3C-CONFORMANCE` | `031-accessibility-conformance-sample-repair` |
| `W3C-EM` | `031-accessibility-conformance-sample-repair` |
| `CISA-SBOM-CONSUMPTION` | `071-sbom-vex-consumption-gate` |
| `CISA-VEX-MIN` | `071-sbom-vex-consumption-gate` |
| `CISA-KEV` | `071-sbom-vex-consumption-gate` |
| `NTIA-SBOM-MIN` | `071-sbom-vex-consumption-gate` |
| `NPM-PACKAGE-LOCK` | `112-container-sbom-remediation` |
| `OCI-IMAGE-MANIFEST` | `112-container-sbom-remediation` |
| `NODE-NAPI-ABI` | `112-container-sbom-remediation` |
| `SLSA-PROVENANCE` | `112-container-sbom-remediation` |
| `K8S-CA-ROTATION` | `097-kubernetes-ca-trust-rotation-recovery` |
| `K8S-PKI` | `097-kubernetes-ca-trust-rotation-recovery` |
| `HB-RETRO-032` | `032-anomalous-transaction-detect` |
| `HB-RETRO-033` | `033-budget-variance-analysis` |
| `HB-RETRO-034` | `034-funnel-dropoff-analysis` |
| `HB-RETRO-035` | `035-inventory-forecast` |
| `HB-RETRO-036` | `036-interruption-resume` |
| `HB-RETRO-037` | `037-multiday-project-state` |
| `HB-RETRO-038` | `038-event-update-replan` |
| `FEMA-VAYGO` | `038-public-assistance-validation-repair` |
| `FEMA-PAPPG-V5` | `038-public-assistance-validation-repair` |
| `HB-RETRO-039` | `039-task-cancellation-cleanup` |
| `HB-RETRO-040` | `040-service-dependency-triage` |
| `HB-RETRO-041` | `041-capacity-planning` |
| `HB-RETRO-042` | `042-rollback-readiness` |
| `HB-RETRO-043` | `043-canary-release-check` |
| `HB-RETRO-044` | `044-legal-compliance-review` |
| `HB-RETRO-045` | `045-hr-resume-screening` |
| `HB-RETRO-046` | `046-ecommerce-support-routing` |
| `HB-RETRO-047` | `047-logistics-delay-response` |
| `HB-RETRO-048` | `048-research-repro-package` |
| `HB-RETRO-049` | `049-platform-appeal-review` |
| `HB-RETRO-050` | `050-medical-admin-claim-check` |
| `HB-RETRO-051` | `051-smallfile-batch-reject-ledger` |
| `HB-RETRO-052` | `052-local-html-dom-form-extract` |
| `HB-RETRO-053` | `053-ab-test-caveat-analysis` |
| `HB-RETRO-054` | `054-timeseries-anomaly-attribution` |
| `HB-RETRO-055` | `055-financial-close-reconciliation` |
| `HB-RETRO-056` | `056-jsonl-sessionization-analysis` |
| `HB-RETRO-057` | `057-metric-definition-migration-diff` |
| `HB-RETRO-058` | `058-policy-version-conflict-resolution` |
| `HB-RETRO-059` | `059-offline-knowledge-qa-insufficient-evidence` |
| `HB-RETRO-060` | `060-research-claims-batch-evidence-audit` |
| `HB-RETRO-061` | `061-three-source-decision-record-synthesis` |
| `HB-RETRO-062` | `062-privacy-dsar-intake-review` |
| `HB-RETRO-063` | `063-marketing-sensitive-commitment-review` |
| `HB-RETRO-064` | `064-internal-doc-retrieval-injection-defense` |
| `HB-RETRO-065` | `065-policy-update-replan-diff` |
| `HB-RETRO-066` | `066-async-ops-window-rollup` |
| `HB-RETRO-067` | `067-partial-batch-resume-ledger` |
| `HB-RETRO-068` | `068-release-approval-gate-plan` |

## Second-hundred cross-domain workflow sources

| `LOGROTATE-STATE` | [logrotate state and rotation workflow](https://man7.org/linux/man-pages/man8/logrotate.8.html) |

| `PYTHON-PEP-420` | [PEP 420: Implicit Namespace Packages](https://peps.python.org/pep-0420/) |

| `DOCKERIGNORE-BUILD-CONTEXT` | [Docker build context and .dockerignore files](https://docs.docker.com/build/building/context/#dockerignore-files) |

| Exact source ID | Public workflow source |
|---|---|
| `CYBER-PKI-01` | NIST SP 800-57 certificate lifecycle and key-management guidance |
| `SUPPLY-WMS-01` | GS1 EPCIS supply-chain visibility and event workflow standard |
| `MFG-ECN-01` | NIST product lifecycle and bill-of-materials research |
| `HEALTH-PA-01` | CMS electronic prior-authorization workflow materials |
| `PUBLIC-PERMIT-01` | OGC geospatial data and interoperability standards |
| `SALES-CRM-01` | Salesforce duplicate-account merge workflow documentation |
| `MEDIA-SUB-01` | W3C timed-text and caption workflow specifications |
| `EDU-DEGREE-01` | U.S. Department of Education accreditation and transfer-credit materials |
| `CFR-CARRIER-CLAIMS` | [49 CFR Part 370, Principles Governing the Processing of Claims](https://www.ecfr.gov/current/title-49/subtitle-B/chapter-III/subchapter-B/part-370) |
| `NMFTA-CLAIMS` | [National Motor Freight Traffic Association](https://nmfta.org/) freight operations context |
| `USPS-DOMESTIC-CLAIMS` | [USPS Domestic Mail Manual 609](https://pe.usps.com/text/dmm300/609.htm) |
| `CDC-VACCINE-STORAGE-HANDLING` | [CDC Vaccine Storage and Handling Toolkit](https://www.cdc.gov/vaccines/hcp/storage-handling/) |
| `NIST-CALIBRATION` | [NIST policy on metrological traceability](https://www.nist.gov/calibrations/traceability) |
| `NIH-DMS-REPOSITORY` | NIH Data Management and Sharing repository-selection guidance |
| `NIH-DMS-CONTROLLED-ACCESS` | NIH participant-privacy and controlled-access guidance |
| `OWASP-CRS-TUNING` | OWASP Core Rule Set false-positive tuning documentation |
| `OWASP-CRS-TESTING` | OWASP Core Rule Set regression-testing documentation |
| `COCHRANE-META-ANALYSIS` | Cochrane Handbook chapter 10 guidance for effect synthesis, heterogeneity, sensitivity analysis, and forest plots |
| `COCHRANE-REVIEW-UPDATE` | Cochrane Handbook chapter IV guidance for incorporating corrected study data into review updates |
| `PRISMA-2020-SYNTHESIS` | PRISMA 2020 synthesis-method and graphical-reporting guidance |
| `GITHUB-SENSITIVE-DATA-REMOVAL` | GitHub documentation for revoking exposed credentials, rewriting repository history, and coordinating clone cleanup |
| `OWASP-SECRETS-INCIDENT-RESPONSE` | OWASP Secrets Management Cheat Sheet guidance for secret lifecycle, revocation, rotation, deletion, logging, and incident containment |
| `GITLAB-ARTIFACT-DELETE` | GitLab Job Artifacts API and retention documentation for independently deleting retained build artifacts |
| `DEBEZIUM-CDC` | Debezium change-event format and delivery-semantics documentation |
| `KAFKA-EOS` | Apache Kafka idempotent producer and transactional processing documentation |
| `KIMBALL-SCD2` | Kimball Group slowly changing dimension Type 2 workflow guidance |
| `SQLITE-TRANSACTIONS` | SQLite transaction and atomic-commit documentation |
| `STRIPE-WEBHOOK-ORDERING` | Stripe webhook delivery, duplicate-event, and event-ordering documentation |
| `STRIPE-IDEMPOTENT-REQUESTS` | Stripe API idempotent-request documentation |
| `RFC-3464-DSN` | RFC 3464 delivery-status notification message format and correlation semantics |
| `PYTHON-EMAIL-PARSER` | Python standard-library MIME and email parser documentation |
| `RFC5545-RECURRENCE-ID` | RFC 5545 recurrence-instance and `RECURRENCE-ID` calendar semantics |
| `CALDAV-ETAG` | RFC 4791 CalDAV ETag and conditional calendar-object synchronization semantics |
| `GAO-PCARD` | U.S. GAO purchase-card control and improper-use audit guidance |
| `IRS-RECEIPTS` | IRS Publication 463 substantiation and receipt-record guidance |
| `GLEIF-DATA-QUALITY` | GLEIF legal-entity data-quality and versioned-identity guidance |
| `FATF-BENEFICIAL-OWNERSHIP` | FATF beneficial-ownership transparency and verification guidance |
| `FDA-RECALL-OPERATIONS` | FDA industry guidance for product recalls, recall strategy, and effectiveness checks |
| `GS1-TRACEABILITY` | GS1 Global Traceability Standard for product, lot, location, and event genealogy |
| `1EDTECH-LTI-AGS-20` | 1EdTech Learning Tools Interoperability Assignment and Grade Services 2.0 specification |
| `1EDTECH-ONEROSTER-12-GRADEBOOK` | 1EdTech OneRoster 1.2 roster and gradebook exchange specification |
| `EPA-SAMPLE-CUSTODY-PRESERVATION` | U.S. EPA quality-system guidance for sample custody, handling, preservation, receipt condition, and holding time |
| `NIST-HB-150-3` | NIST Handbook 150-3 laboratory sample identification, receipt, handling, records, and traceability requirements |
| `GREEN-BUTTON-ESPI` | NAESB Energy Services Provider Interface / Green Button interval-usage data exchange specification |
| `NIST-SMART-GRID` | NIST Smart Grid interoperability and trustworthy-measurement program materials |
| `DDEX-DSR` | DDEX Digital Sales Reporting and royalty-reporting message-suite specifications |
| `DDEX-RIN` | DDEX Recording Information Notification specification for recording, work, contributor, and identifier metadata |
| `X12-850` | [X12 850 Purchase Order transaction set](https://x12.org/products/transaction-sets) |
| `X12-855` | [X12 855 Purchase Order Acknowledgment transaction set](https://x12.org/products/transaction-sets) |
| `X12-856` | [X12 856 Ship Notice/Manifest transaction set](https://x12.org/products/transaction-sets) |
| `X12-810` | [X12 810 Invoice transaction set](https://x12.org/products/transaction-sets) |
| `ISO-55000-ASSET-MANAGEMENT` | [ISO 55001:2024 asset-management-system requirements](https://www.iso.org/cms/live/live/en/sites/isoorg/contents/data/standard/08/30/83054.html) |
| `ISO-IEC-17025-CALIBRATION` | [ISO/IEC 17025 testing and calibration laboratory competence](https://www.iso.org/ISO-IEC-17025-testing-and-calibration-laboratories.html) |
| `OSHA-1910-147-LOTO` | [OSHA 29 CFR 1910.147 control of hazardous energy](https://www.osha.gov/laws-regs/regulations/standardnumber/1910/1910.147) |
| `ALTA-BEST-PRACTICES` | [ALTA Best Practices for title and settlement companies](https://www.alta.org/policies-and-standards/best-practices/) |
| `CFPB-CLOSING-DISCLOSURE` | [CFPB Closing Disclosure guidance](https://www.consumerfinance.gov/owning-a-home/closing-disclosure/) |
| `FDA-21-CFR-117-CGMP` | [FDA 21 CFR Part 117 current good manufacturing practice and preventive controls](https://www.ecfr.gov/current/title-21/chapter-I/subchapter-B/part-117) |
| `FDA-FOOD-ALLERGEN-LABELING` | [FDA food-allergy and allergen-labeling guidance](https://www.fda.gov/food/nutrition-food-labeling-and-critical-foods/food-allergies) |
| `ICH-E2B-R3` | [ICH E2B(R3) electronic transmission of individual case safety reports](https://database.ich.org/sites/default/files/E2B_R3_Guideline.pdf) |
| `EMA-GVP-MODULE-VI` | [EMA good pharmacovigilance practices Module VI](https://www.ema.europa.eu/en/documents/regulatory-procedural-guideline/guideline-good-pharmacovigilance-practices-gvp-module-vi-collection-management-submission-reports-suspected-adverse-reactions-rev-2_en.pdf) |
| `DICOM-PS3-15` | [DICOM PS3.15 security and system management profiles](https://dicom.nema.org/medical/dicom/current/output/html/part15.html) |
| `DICOM-PS3-10` | [DICOM PS3.10 media storage and file format](https://dicom.nema.org/medical/dicom/current/output/html/part10.html) |
| `FAA-MEL-GUIDANCE` | [FAA AC 120-125 minimum equipment requirements for operations](https://www.faa.gov/regulations_policies/advisory_circulars/index.cfm/go/document.information/documentID/1042238) |
| `FAA-MAINTENANCE-RECORDS` | [14 CFR 43.9 maintenance-record content requirements](https://www.ecfr.gov/current/title-14/chapter-I/subchapter-C/part-43/section-43.9) |
| `EPA-AWIA-EMERGENCY-RESPONSE` | [EPA water-resilience and America's Water Infrastructure Act emergency-response resources](https://www.epa.gov/waterresilience) |
| `AWWA-WATER-AUDITS` | [AWWA water-system operations and auditing resources](https://www.awwa.org/) |
| `CMS-PART-D-FORMULARY` | [CMS Prescription Drug Benefit Manual, Chapter 6](https://www.cms.gov/medicare/prescription-drug-coverage/prescriptiondrugcovcontra/downloads/part-d-benefits-manual-chapter-6.pdf) |
| `FDA-ORANGE-BOOK` | [FDA Approved Drug Products with Therapeutic Equivalence Evaluations (Orange Book)](https://www.fda.gov/drugs/drug-approvals-and-databases/approved-drug-products-therapeutic-equivalence-evaluations-orange-book) |
| `RFC-6781` | [RFC 6781 DNSSEC Operational Practices, Version 2](https://www.rfc-editor.org/rfc/rfc6781.html) |
| `RFC-7583` | [RFC 7583 DNSSEC Key Rollover Timing Considerations](https://www.rfc-editor.org/rfc/rfc7583.html) |
| `FBI-BEC-PAYMENT-DIVERSION` | [FBI Internet Crime Complaint Center business-email-compromise controls](https://www.ic3.gov/CrimeInfo/BEC) |
| `NACHA-ACCOUNT-VALIDATION` | [Nacha Account Validation Resource Center](https://www.nacha.org/content/account-validation-resource-center) |
| `DOL-COBRA-EMPLOYER-GUIDE` | [U.S. Department of Labor employer guide to COBRA continuation coverage](https://www.dol.gov/agencies/ebsa/about-ebsa/our-activities/resource-center/publications/an-employers-guide-to-group-health-continuation-coverage-under-cobra?lang=en) |
| `EBSA-CONTINUATION-COVERAGE` | [U.S. Department of Labor COBRA continuation-coverage resources](https://www.dol.gov/agencies/ebsa/laws-and-regulations/laws/cobra?lang=en) |
| `NIST-SP-800-122` | [NIST SP 800-122, Guide to Protecting the Confidentiality of Personally Identifiable Information](https://csrc.nist.gov/pubs/sp/800/122/final) |
| `PYTHON-WAVE` | [Python standard-library `wave` module](https://docs.python.org/3/library/wave.html) |
| `POSIX-TAR` | [POSIX `pax` portable archive utility](https://pubs.opengroup.org/onlinepubs/9799919799/utilities/pax.html) |
| `MS-SHARED-MAILBOX` | [Microsoft 365 shared mailbox configuration and shared sent-item behavior](https://learn.microsoft.com/en-us/microsoft-365/admin/email/configure-a-shared-mailbox?view=o365-worldwide) |
| `POSTGRES-BACKUP-RESTORE` | [PostgreSQL current backup and restore documentation](https://www.postgresql.org/docs/current/backup.html) |
| `GOOGLE-SRE-INCIDENT` | [Google SRE Workbook incident-response roles, working records, coordination, and communication](https://sre.google/workbook/incident-response/) |
| `NIST-SP-800-34` | [NIST SP 800-34 Rev. 1 contingency planning guide](https://csrc.nist.gov/pubs/sp/800/34/r1/upd1/final) |
| `ONET-PROJECT-MANAGEMENT` | [O*NET Project Management Specialists task profile](https://www.onetonline.org/link/details/13-1082.00) |
| `ICO-CONTROLLER-PROCESSOR` | [ICO controller-processor contract clauses and liabilities guidance](https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/accountability-and-governance/contracts-and-liabilities-between-controllers-and-processors-multi/) |
| `HTTP-SEMANTICS-RFC9110` | [RFC 9110 HTTP Semantics](https://www.rfc-editor.org/rfc/rfc9110.html) |
| `HTTP-STATUS-RFC6585` | [RFC 6585 additional HTTP status codes](https://www.rfc-editor.org/rfc/rfc6585.html) |
| `HTTP-CACHING-RFC9111` | [RFC 9111 HTTP Caching](https://www.rfc-editor.org/rfc/rfc9111.html) |
| `HTTP-PROBLEM-RFC9457` | [RFC 9457 Problem Details for HTTP APIs](https://www.rfc-editor.org/rfc/rfc9457.html) |
| `BEAM-MODEL-EVENT-TIME` | [Apache Beam event-time and watermark model](https://beam.apache.org/documentation/programming-guide/#event-time-and-watermarks) |
| `FLINK-EVENT-TIME` | [Apache Flink event-time documentation](https://nightlies.apache.org/flink/flink-docs-stable/docs/concepts/time/) |
| `PYTHON-OS-ISATTY` | [Python `os.isatty` documentation](https://docs.python.org/3/library/os.html#os.isatty) |
| `POSIX-UTILITY-STDIN` | [POSIX utility descriptions and standard-input conventions](https://pubs.opengroup.org/onlinepubs/9699919799/utilities/V3_chap01.html) |
| `CLI-GUIDELINES-INTERACTIVITY` | [Command Line Interface Guidelines: Interactivity](https://clig.dev/#interactivity) |
| `REPRO-SOURCE-DATE-EPOCH` | [SOURCE_DATE_EPOCH specification](https://reproducible-builds.org/specs/source-date-epoch/) |
| `REPRO-TIMESTAMPS` | [Reproducible Builds timestamp guidance](https://reproducible-builds.org/docs/timestamps/) |
| `PYTHON-ZIPFILE` | [Python `zipfile` documentation](https://docs.python.org/3/library/zipfile.html) |
| `GIT-SUBMODULE` | [Git submodule command documentation](https://git-scm.com/docs/git-submodule) |
| `GIT-STATUS-SUBMODULE` | [Git status submodule documentation](https://git-scm.com/docs/git-status) |
| `GIT-SUBMODULES` | [Git submodule data-model documentation](https://git-scm.com/docs/gitsubmodules) |
| `OPENAPI-32` | [OpenAPI Specification 3.2](https://spec.openapis.org/oas/v3.2.0.html) |
| `BAZEL-BUILD-SYSTEMS` | [Bazel build-system concepts](https://bazel.build/basics/build-systems) |
| `NX-AFFECTED` | [Nx affected-project documentation](https://nx.dev/ci/features/affected) |
| `GIT-DIFF` | [Git diff documentation](https://git-scm.com/docs/git-diff) |
| `PYTHON-TARFILE-FILTERS` | [Python `tarfile` extraction filters](https://docs.python.org/3/library/tarfile.html#extraction-filters) |
| `POSIX-PATHNAME-RESOLUTION` | [POSIX.1-2024 pathname resolution](https://pubs.opengroup.org/onlinepubs/9799919799/basedefs/V1_chap04.html#tag_04_16) |
| `DOCKER-COMPOSE-ENV-PRECEDENCE` | [Docker Compose environment-variable precedence](https://docs.docker.com/compose/how-tos/environment-variables/envvars-precedence/) |
| `DOCKER-ENV-SECRETS` | [Docker Compose environment-variable best practices](https://docs.docker.com/compose/how-tos/environment-variables/best-practices/) |
| `OPENFEATURE-EVALUATION-CONTEXT` | [OpenFeature evaluation-context specification](https://openfeature.dev/specification/sections/evaluation-context/) |
| `OPENFEATURE-FLAG-EVALUATION` | [OpenFeature flag-evaluation API specification](https://openfeature.dev/specification/sections/flag-evaluation/) |
| `PYPA-WHEEL-SPEC` | [PyPA binary distribution format](https://packaging.python.org/en/latest/specifications/binary-distribution-format/) |
| `PYPA-COMPATIBILITY-TAGS` | [PyPA platform compatibility tags](https://packaging.python.org/en/latest/specifications/platform-compatibility-tags/) |
| `PYPA-INSTALLED-PROJECTS` | [PyPA recording installed projects](https://packaging.python.org/en/latest/specifications/recording-installed-packages/) |
| `OAUTH-RFC6749` | [RFC 6749 OAuth 2.0 Authorization Framework](https://www.rfc-editor.org/rfc/rfc6749.html) |
| `OAUTH-SECURITY-RFC9700` | [RFC 9700 OAuth 2.0 Security Best Current Practice](https://www.rfc-editor.org/rfc/rfc9700.html) |
| `PYPA-VERSION` | [PyPA version specifiers](https://packaging.python.org/en/latest/specifications/version-specifiers/) |
| `NPM-PACKAGE-VERSION` | [npm package.json version field](https://docs.npmjs.com/cli/v7/configuring-npm/package-json/#version) |
| `CARGO-MANIFEST-VERSION` | [Cargo manifest version field](https://doc.rust-lang.org/cargo/reference/manifest.html#the-version-field) |
| `GIT-MV` | [Git mv documentation](https://git-scm.com/docs/git-mv.html) |
| `GIT-CORE-IGNORECASE` | [Git core.ignoreCase documentation](https://git-scm.com/docs/git-config#Documentation/git-config.txt-coreignoreCase) |
| `SQLITE-TRANSACTION` | [SQLite transaction documentation](https://sqlite.org/lang_transaction.html) |
| `SQLITE-BUSY` | [SQLite BUSY result code](https://sqlite.org/rescode.html#busy) |
| `SQLITE-STEP` | [SQLite statement evaluation guidance](https://sqlite.org/c3ref/step.html) |
| `S3-MULTIPART` | [Amazon S3 multipart upload overview](https://docs.aws.amazon.com/AmazonS3/latest/userguide/mpuoverview.html) |
| `S3-CHECKSUMS` | [Amazon S3 object integrity checks](https://docs.aws.amazon.com/AmazonS3/latest/userguide/checking-object-integrity-upload.html) |
| `S3-COMPLETE-MULTIPART` | [Amazon S3 CompleteMultipartUpload API](https://docs.aws.amazon.com/AmazonS3/latest/API/API_CompleteMultipartUpload.html) |
| `OWASP-LOGGING-CHEATSHEET` | [OWASP Logging Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html) |
| `NODE-FS-WATCH` | [Node.js `fs.watch` documentation and platform caveats](https://nodejs.org/api/fs.html#fswatchfilename-options-listener) |
| `PYTHON-ASYNCIO-QUEUE` | [Python `asyncio` queue documentation](https://docs.python.org/3/library/asyncio-queue.html) |
| `PYTHON-ASYNCIO-TASKS` | [Python `asyncio` task and cancellation documentation](https://docs.python.org/3/library/asyncio-task.html) |
| `JSON-SCHEMA-2020-12` | [JSON Schema Draft 2020-12 validation specification](https://json-schema.org/draft/2020-12/json-schema-validation) |
| `RFC-8259` | [RFC 8259, The JavaScript Object Notation Data Interchange Format](https://www.rfc-editor.org/rfc/rfc8259) |
| `PYTHON-FUNCTOOLS-LRU` | [Python `functools.lru_cache` documentation](https://docs.python.org/3/library/functools.html#functools.lru_cache) |
| `PYTHON-JSON` | [Python `json` documentation](https://docs.python.org/3/library/json.html) |
| `PYTHON-IO` | [Python `io` stream documentation](https://docs.python.org/3/library/io.html) |
| `STRIPE-WEBHOOKS` | [Stripe webhook signature documentation](https://docs.stripe.com/webhooks) |
| `RFC-2104` | [RFC 2104 HMAC](https://www.rfc-editor.org/rfc/rfc2104) |
| `PLUGGY-DOCS` | [Pluggy documentation](https://pluggy.readthedocs.io/en/stable/) |
| `PYTHON-IMPORTLIB-METADATA` | [Python `importlib.metadata` documentation](https://docs.python.org/3/library/importlib.metadata.html) |
| `RFC-5545` | [RFC 5545 iCalendar](https://www.rfc-editor.org/rfc/rfc5545) |
| `PEP-495` | [PEP 495 local-time disambiguation](https://peps.python.org/pep-0495/) |
| `PYTHON-ZONEINFO` | [Python `zoneinfo` documentation](https://docs.python.org/3/library/zoneinfo.html) |
| `UNICODE-UAX15` | [Unicode Standard Annex #15: normalization forms](https://www.unicode.org/reports/tr15/) |
| `UNICODE-UAX31` | [Unicode Standard Annex #31: identifiers](https://www.unicode.org/reports/tr31/) |
| `RESTIC-RESTORE` | [Restic restore documentation](https://restic.readthedocs.io/en/stable/050_restore.html) |
| `RFC-6265` | [RFC 6265 HTTP State Management Mechanism](https://www.rfc-editor.org/rfc/rfc6265.html) |
| `OCI-IMAGE-LAYER` | [OCI Image Format layer changesets](https://specs.opencontainers.org/image-spec/layer/) |
| `W3C-TRACE-CONTEXT` | [W3C Trace Context Recommendation](https://www.w3.org/TR/trace-context/) |
| `W3C-BAGGAGE` | [W3C Baggage specification](https://www.w3.org/TR/baggage/) |
| `DEBEZIUM-OUTBOX` | [Debezium Outbox Event Router documentation](https://debezium.io/documentation/reference/stable/transformations/outbox-event-router.html) |
| `TERRAFORM-LIFECYCLE` | [Terraform lifecycle meta-argument reference](https://developer.hashicorp.com/terraform/language/meta-arguments/lifecycle) |
| `KUBERNETES-SSA` | [Kubernetes Server-Side Apply](https://kubernetes.io/docs/reference/using-api/server-side-apply/) |
| `APOLLO-NORMALIZED-CACHE` | [Apollo Client caching overview](https://www.apollographql.com/docs/react/caching/overview) |
| `APOLLO-OPTIMISTIC-UI` | [Apollo Client optimistic mutation results](https://www.apollographql.com/docs/react/performance/optimistic-ui) |
| `W3C-WEBAUTHN` | [W3C Web Authentication Level 3](https://www.w3.org/TR/webauthn-3/) |
| `POSTGRES-REPLICATION-SLOTS` | [PostgreSQL 19 replication-slot view](https://www.postgresql.org/docs/19/view-pg-replication-slots.html) |
| `GITHUB-ACTIONS-WORKFLOW` | [GitHub Actions workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax) |
| `POSTGRES-ALTER-TABLE` | [PostgreSQL 19 `ALTER TABLE`](https://www.postgresql.org/docs/19/sql-altertable.html) |
| `GITHUB-ACTIONS-OIDC` | [GitHub Actions OpenID Connect reference](https://docs.github.com/en/actions/reference/security/oidc) |
| `KAFKA-PRODUCER-TRANSACTIONS` | [Apache Kafka 4.0 `KafkaProducer` transaction API](https://kafka.apache.org/40/javadoc/org/apache/kafka/clients/producer/KafkaProducer.html) |
| `RFC9113-GOAWAY` | [RFC 9113 HTTP/2 GOAWAY and error handling](https://www.rfc-editor.org/rfc/rfc9113) |
| `PROMETHEUS-NATIVE-HISTOGRAMS` | [Prometheus native histogram specification](https://prometheus.io/docs/specs/native_histograms/) |
| `GRPC-DEADLINES` | [gRPC deadlines guide](https://grpc.io/docs/guides/deadlines/) |
| `GRPC-CANCELLATION` | [gRPC cancellation guide](https://grpc.io/docs/guides/cancellation/) |
| `GRPC-RETRY` | [gRPC retry guide](https://grpc.io/docs/guides/retry/) |
| `AWS-S3-EVENT-NOTIFICATIONS` | [Amazon S3 event notification types, ordering, and duplicates](https://docs.aws.amazon.com/AmazonS3/latest/userguide/notification-how-to-event-types-and-destinations.html) |
| `KUBERNETES-ADMISSION-WEBHOOKS` | [Kubernetes admission webhook good practices](https://kubernetes.io/docs/concepts/cluster-administration/admission-webhooks-good-practices/) |
| `SIGSTORE-BUNDLE` | [Sigstore bundle format](https://docs.sigstore.dev/about/bundle/) |
| `SIGSTORE-TRUSTED-ROOT` | [Sigstore TrustedRoot protobuf specification](https://github.com/sigstore/protobuf-specs/blob/main/protos/sigstore_trustroot.proto) |
| `RFC9001-QUIC-0RTT` | [RFC 9001 QUIC 0-RTT](https://www.rfc-editor.org/rfc/rfc9001.html) |
| `RFC8470-HTTP-EARLY-DATA` | [RFC 8470 HTTP Early Data](https://www.rfc-editor.org/rfc/rfc8470.html) |
| `REDIS-CLUSTER-SPEC` | [Redis Cluster specification](https://redis.io/docs/latest/operate/oss_and_stack/reference/cluster-spec/) |
| `OPENAPI-3.1.1` | [OpenAPI Specification 3.1.1](https://spec.openapis.org/oas/v3.1.1.html) |
| `RFC9449-DPOP` | [RFC 9449 OAuth 2.0 Demonstrating Proof of Possession](https://www.rfc-editor.org/rfc/rfc9449.html) |
| `KUBERNETES-API-WATCH` | [Kubernetes API concepts: efficient change detection](https://kubernetes.io/docs/reference/using-api/api-concepts/) |
| `RFC8767-DNS-STALE` | [RFC 8767 Serving Stale Data to Improve DNS Resiliency](https://www.rfc-editor.org/rfc/rfc8767.html) |
| `RFC2308-DNS-NEGATIVE` | [RFC 2308 Negative Caching of DNS Queries](https://www.rfc-editor.org/rfc/rfc2308.html) |
| `RFC8914-EDE` | [RFC 8914 Extended DNS Errors](https://www.rfc-editor.org/rfc/rfc8914.html) |

## Finance and compliance source variants

These exact metadata IDs select one primary public document for a finance
workflow family.

| Exact source ID | Family | Primary document |
|---|---|---|
| `FI-01-IRS-463` | `FI-01` accountable-plan expense review | [IRS Publication 463](https://www.irs.gov/publications/p463) |
| `FI-02-GSA-PERDIEM` | `FI-02` per-diem, receipts and exceptions | [GSA per diem FAQs](https://www.gsa.gov/travel/plan-a-trip/per-diem-rates/faqs) |
| `FI-03-PCAOB-2301` | `FI-03` month-end reconciliation controls | [PCAOB AS 2301](https://pcaobus.org/oversight/standards/auditing-standards/details/AS2301) |
| `FI-03-TREASURY-CARS` | `FI-03` reporting reconciliation |
| `FI-04-TREASURY-DNP` | `FI-04` pre-payment screening |
| `FI-05-TREASURY-RATES` | `FI-05` reporting-rate versioning |
| `FI-06-IRS-TIN` | `FI-06` TIN/name matching |
| `FI-07-SEC-XBRL` | `FI-07` XBRL validation |
| `FI-08-PCAOB-1105` | `FI-08` audit evidence |
| `FI-08-GAO-FAM` | `FI-08` misstatement roll-forward |
| `CO-01-ICO-SAR` | `CO-01` subject access |
| `CO-02-HHS-ACCESS` | `CO-02` health-record access |
| `CO-03-EU-ARTICLE33` | `CO-03` breach notification |
| `CO-03-FTC-BREACH` | `CO-03` breach response |
| `CO-04-NARA-HOLD` | `CO-04` records hold |
| `CO-05-BIS-DPL` | `CO-05` restricted-party screening |
| `CO-06-OFAC-FRAMEWORK` | `CO-06` sanctions alert handling |

## Standard200 interaction-shape source families

These IDs record the six public-workflow families used by the final text/code gap batch. Exact primary references and access dates are retained in the Standard200 release ledger.

| Exact source ID | Workflow family |
|---|---|
| `HB-S200-EVENT-STATE` | event-sourced state and checkpoint recovery |
| `HB-S200-POLICY-PRECEDENCE` | ordered policy and configuration precedence |
| `HB-S200-BOUNDED-ALLOCATION` | bounded-capacity scheduling and conservation |
| `HB-S200-DEPENDENCY-GRAPH` | dependency graph ordering and cycle recovery |
| `HB-S200-PROTOCOL-RECOVERY` | retry, ambiguity, idempotency, and budget handling |
| `HB-S200-THREE-WAY-MERGE` | base/local/remote semantic reconciliation |

## Multimodal20 handcrafted provenance labels

These IDs identify the independently handcrafted frontend briefs. They are
provenance labels, not claims that the tasks were copied from an external page.

| Exact source ID | Workflow |
|---|---|
| `FE-201` | creator revenue dashboard |
| `FE-202` | studio task board |
| `FE-203` | pet-care game |
| `FE-204` | incident command console |
| `FE-205` | research lab site |
| `FE-206` | appointment finder |
| `FE-207` | budget planning workspace |
| `FE-208` | media timeline editor |
| `FE-209` | course builder |
| `FE-210` | support ticket router |
| `FE-211` | local data explorer |
| `FE-212` | policy diff viewer |
| `FE-213` | kanban build repair |
| `FE-214` | accessibility retrofit |
| `FE-215` | responsive redesign |
| `FE-216` | feature-flag admin |
| `FE-217` | travel itinerary planner |
| `FE-218` | scientific simulation controls |
| `FE-219` | portfolio reference rebuild |
| `FE-220` | form builder validation |
| `FE-221` | choropleth map selection |
| `FE-222` | waveform audio cue editor |
| `FE-223` | spreadsheet grid formula |
| `FE-224` | image pair diff annotation |
| `FE-225` | network graph explorer |
| `FE-226` | wysiwyg print preview |

## Standard237 collaborator packages (208-237)

These exact IDs are cited by Standard237 tasks 208-237 under `tasks/`. They map
to public specifications already named in those packages' `design.md` files.
The integration preserves each collaborator-authored workflow's intended decision.

| Exact source ID | Public record |
|---|---|
| `JSONRPC-20` | [JSON-RPC 2.0 specification](https://www.jsonrpc.org/specification) |
| `OPENRPC-SPEC` | [OpenRPC specification](https://spec.open-rpc.org/) |
| `SIGSTORE-COSIGN` | [Sigstore Cosign verification](https://docs.sigstore.dev/cosign/verifying/verify/) |
| `IN-TOTO-ATTESTATION` | [in-toto attestation specification](https://github.com/in-toto/attestation/tree/main/spec) |
| `REDIS-RATE-LIMIT` | [Redis rate-limiting glossary](https://redis.io/glossary/rate-limiting/) |
| `STRIPE-RATE-LIMITS` | [Stripe rate-limit documentation](https://docs.stripe.com/rate-limits) |
| `TEMPORAL-WORKFLOWS` | [Temporal workflow documentation](https://docs.temporal.io/workflows) |
| `CELERY-TASK-STATES` | [Celery task states](https://docs.celeryq.dev/en/stable/userguide/tasks.html#states) |
| `MS-CIRCUIT-BREAKER` | [Azure Architecture Center circuit-breaker pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/circuit-breaker) |
| `FASTMCP-RETRY` | [FastMCP client retry and backoff](https://gofastmcp.com/clients/executing-tools) |
| `TIKV-PD-SCHEDULER` | [TiKV Placement Driver architecture](https://tikv.org/docs/latest/concepts/architecture/) |
| `K8S-POD-PRIORITY` | [Kubernetes pod priority and preemption](https://kubernetes.io/docs/concepts/scheduling-eviction/pod-priority-preemption/) |
| `AUTHELIA-TELEMETRY` | [Authelia telemetry and audit configuration](https://www.authelia.com/configuration/miscellaneous/telemetry/) |
| `RFC-6749-TOKEN` | [RFC 6749 OAuth 2.0 authorization framework](https://www.rfc-editor.org/rfc/rfc6749) |
| `GITHUB-CODEOWNERS` | [GitHub CODEOWNERS](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners) |
| `GITHUB-STATUS-CHECKS` | [GitHub required status checks](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/collaborating-on-repositories-with-code-quality-features/about-status-checks) |
| `OPENMDAO-CASE-RECORDING` | [OpenMDAO case recording](https://openmdao.org/newdocs/versions/latest/features/recording/case_recording.html) |
| `OCI-CONTENT-ADDRESSABLE` | [OCI image spec content addressability](https://github.com/opencontainers/image-spec/blob/main/descriptor.md) |
| `STAC-SPEC` | [SpatioTemporal Asset Catalog specification](https://stacspec.org/en/about/stac-spec/) |
| `EARTHKIT-DATA` | [EarthKit data sources](https://earthkit-data.readthedocs.io/en/latest/) |
| `FERPA-DIRECTORY-INFO` | [Family Educational Rights and Privacy Act directory-information guidance](https://studentprivacy.ed.gov/ferpa) |
| `USCIS-I9-HANDBOOK` | [USCIS Handbook for Employers M-274](https://www.uscis.gov/i-9-central/form-i-9-resources/handbook-for-employers-m-274) |
| `USCIS-I9-FORM` | [USCIS Form I-9 employment eligibility verification](https://www.uscis.gov/i-9) |

## Standard254 additive packages (238-254)

Tasks `238`–`254` reuse the public source IDs already listed above. Clerk probes
`238`, `244`, `247`, and `249` still adapt those records into stream-drain
workflows. Replacement packages `239`, `240`, `241`, `242`, `243`, `245`,
`246`, `248`, `250`, `251`, `252`, `253`, and `254` reuse
`K8S-POD-PRIORITY`, `TIKV-PD-SCHEDULER`, `GIT-DIFF`, `GITHUB-STATUS-CHECKS`,
`SQLITE-TRANSACTIONS`, `SQLITE-STEP`, `HB-S200-BOUNDED-ALLOCATION`,
`HB-S200-EVENT-STATE`, `OCI-CONTENT-ADDRESSABLE`, `CELERY-TASK-STATES`,
`TEMPORAL-WORKFLOWS`, `JSONRPC-20`, `OPENRPC-SPEC`, `GITHUB-CODEOWNERS`,
`STAC-SPEC`, `EARTHKIT-DATA`, `UNICODE-LDML-TR35`, `ICU-MESSAGE-FORMAT`, and
`OPENMDAO-CASE-RECORDING`. No new exact IDs are introduced.



## Standard274 additive packages (255-274)

Tasks `255`–`274` declare one exact source ID each. These IDs name the adapted
synthetic NAMI Gold20 cases recorded in each package `design.md`. They are not
new public-source claims and are not part of `multimodal-tasks`.

| Exact source ID | Retained task package |
|---|---|
| `NAMI-GOLD20-case_01` | `255-construction-implementation-plan` |
| `NAMI-GOLD20-case_02` | `256-incident-evidence-postmortem` |
| `NAMI-GOLD20-case_03` | `257-equipment-inspection-word-form` |
| `NAMI-GOLD20-case_04` | `258-policy-document-contradiction-review` |
| `NAMI-GOLD20-case_05` | `259-editable-management-review-deck` |
| `NAMI-GOLD20-case_06` | `260-batch-presentation-standardization` |
| `NAMI-GOLD20-case_07` | `261-sales-analysis-formula-workbook` |
| `NAMI-GOLD20-case_08` | `262-user-service-registration-repair` |
| `NAMI-GOLD20-case_09` | `263-stateful-python-rpc-service` |
| `NAMI-GOLD20-case_10` | `264-node-record-processing-contract` |
| `NAMI-GOLD20-case_11` | `265-weekly-operations-brief-generator` |
| `NAMI-GOLD20-case_12` | `266-evidence-grounded-travel-plan` |
| `NAMI-GOLD20-case_13` | `267-eldercare-research-evidence-report` |
| `NAMI-GOLD20-case_14` | `268-sla-credit-evidence-assessment` |
| `NAMI-GOLD20-case_15` | `269-constrained-shopping-cart-update` |
| `NAMI-GOLD20-case_16` | `270-idempotent-family-hotel-booking` |
| `NAMI-GOLD20-case_17` | `271-itemized-shared-expense-requests` |
| `NAMI-GOLD20-case_18` | `272-video-compression-fidelity-delivery` |
| `NAMI-GOLD20-case_19` | `273-safe-skill-archive-packaging` |
| `NAMI-GOLD20-case_20` | `274-collaboration-materials-reminder-close` |
