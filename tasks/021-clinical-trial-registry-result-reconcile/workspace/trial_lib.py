from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
INPUTS = (
    "evidence/registry_history.json",
    "evidence/statistical_analysis_plan.json",
    "evidence/results_submission.json",
    "evidence/csr_tables.json",
    "evidence/review_materials.json",
    "policy/reconciliation_policy.json",
)


def load(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def write_json(relative: str, value: object) -> None:
    path = ROOT / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def canonical_sha(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def input_digests() -> dict[str, str]:
    return {relative: file_sha(ROOT / relative) for relative in INPUTS}


def _keyed(rows: object, key: str) -> dict[str, dict]:
    if not isinstance(rows, list):
        return {}
    result = {
        row.get(key): row
        for row in rows
        if isinstance(row, dict) and isinstance(row.get(key), str)
    }
    return result if len(result) == len(rows) else {}


def _case_inputs() -> dict[str, object]:
    registry = load("evidence/registry_history.json")
    sap = load("evidence/statistical_analysis_plan.json")
    submission = load("evidence/results_submission.json")
    csr = load("evidence/csr_tables.json")
    review = load("evidence/review_materials.json")
    policy = load("policy/reconciliation_policy.json")
    versions = sorted(registry["versions"], key=lambda row: row["posted_date"])
    eligible = [
        row
        for row in versions
        if row["posted_date"] <= registry["primary_completion_date"]
    ]
    controlling = max(eligible, key=lambda row: row["posted_date"])
    current = max(versions, key=lambda row: row["posted_date"])
    submission_outcomes = _keyed(submission["outcomes"], "outcome_id")
    csr_outcomes = _keyed(csr["outcome_tables"], "outcome_id")
    primary = next(
        row
        for row in submission["outcomes"]
        if (row["measure"], row["time_frame"])
        == (
            controlling["primary_outcome"]["measure"],
            controlling["primary_outcome"]["time_frame"],
        )
    )
    additional = next(
        row
        for row in submission["outcomes"]
        if row["outcome_id"] != primary["outcome_id"]
        and (row["measure"], row["time_frame"])
        == (
            sap["additional_analysis"]["measure"],
            sap["additional_analysis"]["time_frame"],
        )
    )
    return {
        "registry": registry,
        "sap": sap,
        "submission": submission,
        "csr": csr,
        "review": review,
        "policy": policy,
        "versions": versions,
        "controlling": controlling,
        "current": current,
        "submission_outcomes": submission_outcomes,
        "csr_outcomes": csr_outcomes,
        "primary": primary,
        "additional": additional,
    }


def graph_validation_errors(graph: dict) -> list[str]:
    case = _case_inputs()
    registry = case["registry"]
    versions = case["versions"]
    controlling = case["controlling"]
    sap = case["sap"]
    submission = case["submission"]
    csr = case["csr"]
    review = case["review"]
    assert isinstance(registry, dict)
    assert isinstance(versions, list)
    assert isinstance(controlling, dict)
    assert isinstance(sap, dict)
    assert isinstance(submission, dict)
    assert isinstance(csr, dict)
    assert isinstance(review, dict)

    nodes = []
    registry_sha = file_sha(ROOT / "evidence/registry_history.json")
    for version in versions:
        if version["source_id"] == controlling["source_id"]:
            authority = "controlling_prespecification"
            relationship = "latest_posted_before_primary_completion"
        elif version["posted_date"] < controlling["posted_date"]:
            authority = "superseded_historical"
            relationship = "posted_before_primary_completion"
        else:
            authority = "current_but_not_prespecification"
            relationship = "posted_after_primary_completion_and_unblinding"
        nodes.append(
            {
                "source_id": version["source_id"],
                "kind": "registry_protocol_version",
                "source_date": version["posted_date"],
                "authority": authority,
                "relationship": relationship,
                "sha256": registry_sha,
            }
        )

    nodes.extend(
        [
            {
                "source_id": sap["source_id"],
                "kind": "statistical_analysis_plan",
                "source_date": sap["signed_date"],
                "authority": "pre_unblinding_corroboration",
                "relationship": "confirms_prespecified_primary_and_arm_map",
                "sha256": file_sha(
                    ROOT / "evidence/statistical_analysis_plan.json"
                ),
            },
            {
                "source_id": submission["source_id"],
                "kind": "results_submission",
                "source_date": submission["results_first_submitted_date"],
                "authority": "candidate_under_qc",
                "relationship": "submitted_not_posted_requires_correction",
                "sha256": file_sha(ROOT / "evidence/results_submission.json"),
            },
            {
                "source_id": csr["source_id"],
                "kind": "clinical_study_report_tables",
                "source_date": None,
                "authority": "result_and_population_source",
                "relationship": "controls_values_labels_and_denominators",
                "sha256": file_sha(ROOT / "evidence/csr_tables.json"),
            },
            {
                "source_id": review["qc"]["source_id"],
                "kind": "registry_qc_comments",
                "source_date": None,
                "authority": "correction_trigger",
                "relationship": "identifies_fields_for_reconciliation",
                "sha256": file_sha(ROOT / "evidence/review_materials.json"),
            },
            {
                "source_id": review["manuscript"]["source_id"],
                "kind": "manuscript_proof",
                "source_date": None,
                "authority": "downstream_candidate",
                "relationship": "claims_must_reconcile_before_publication",
                "sha256": file_sha(ROOT / "evidence/review_materials.json"),
            },
        ]
    )
    derived = {
        "trial_id": registry["trial_id"],
        "primary_completion_date": registry["primary_completion_date"],
        "unblinding_date": registry["unblinding_date"],
        "nodes": nodes,
    }
    found: list[str] = []
    for field in ("trial_id", "primary_completion_date", "unblinding_date"):
        if graph.get(field) != derived[field]:
            found.append(f"source graph {field} is wrong")
    candidate_nodes = graph.get("nodes")
    if not isinstance(candidate_nodes, list):
        return [*found, "source graph requires a nodes array"]
    actual = _keyed(candidate_nodes, "source_id")
    wanted = _keyed(derived["nodes"], "source_id")
    if set(actual) != set(wanted):
        found.append("source graph must include every visible source exactly once")
        return found
    exact_fields = ("kind", "source_date", "authority", "sha256")
    for source_id, derived_row in wanted.items():
        row = actual[source_id]
        relationship = row.get("relationship")
        if any(row.get(field) != derived_row[field] for field in exact_fields):
            found.append(
                f"{source_id}: kind, source date, authority, or evidence digest is wrong"
            )
        if not isinstance(relationship, str) or len(relationship.strip()) < 12:
            found.append(f"{source_id}: relationship is not substantive")
    return found


def _arm_labels(groups: list[dict]) -> dict[str, str]:
    return {row["arm_id"]: row["label"] for row in groups}


def _group_counts(groups: list[dict]) -> dict[str, int]:
    return {row["arm_id"]: row["n"] for row in groups}


def ledger_validation_errors(ledger: dict) -> list[str]:
    case = _case_inputs()
    registry = case["registry"]
    sap = case["sap"]
    submission = case["submission"]
    csr = case["csr"]
    controlling = case["controlling"]
    current = case["current"]
    primary = case["primary"]
    additional = case["additional"]
    csr_outcomes = case["csr_outcomes"]
    assert isinstance(registry, dict)
    assert isinstance(sap, dict)
    assert isinstance(submission, dict)
    assert isinstance(csr, dict)
    assert isinstance(controlling, dict)
    assert isinstance(current, dict)
    assert isinstance(primary, dict)
    assert isinstance(additional, dict)
    assert isinstance(csr_outcomes, dict)

    primary_id = primary["outcome_id"]
    additional_id = additional["outcome_id"]
    submitted_date = submission["results_first_submitted_date"]
    primary_time = controlling["primary_outcome"]["time_frame"]
    additional_time = sap["additional_analysis"]["time_frame"]
    rows = [
        {
            "artifact": "results_submission",
            "field": f"{primary_id}.classification",
            "observed": primary["classification"],
            "corrected": "primary_prespecified",
            "authority_ids": [controlling["source_id"], sap["source_id"]],
            "classification": "registry_correction",
            "action": "restore the pre-specified primary outcome designation",
        },
        {
            "artifact": "results_submission",
            "field": f"{additional_id}.classification",
            "observed": additional["classification"],
            "corrected": "additional_post_hoc",
            "authority_ids": [
                controlling["source_id"],
                sap["source_id"],
                current["source_id"],
            ],
            "classification": "registry_correction",
            "action": "label the additional reported analysis as post hoc",
        },
        {
            "artifact": "results_submission",
            "field": "arm_labels",
            "observed": _arm_labels(primary["groups"]),
            "corrected": dict(sap["arm_map"]),
            "authority_ids": [
                controlling["source_id"],
                sap["source_id"],
                csr["source_id"],
            ],
            "classification": "registry_correction",
            "action": "restore stable arm identity without swapping numeric values",
        },
        {
            "artifact": "results_submission",
            "field": f"{primary_id}.analysis_denominator",
            "observed": _group_counts(primary["groups"]),
            "corrected": _group_counts(csr_outcomes[primary_id]["groups"]),
            "authority_ids": [sap["source_id"], csr["source_id"]],
            "classification": "registry_correction",
            "action": "use the pre-specified outcome analysis population",
        },
        {
            "artifact": "results_submission",
            "field": "serious_adverse_events.denominator",
            "observed": submission["serious_adverse_events"]["denominator"],
            "corrected": csr["safety_table"]["denominator"],
            "authority_ids": [csr["source_id"]],
            "classification": "registry_correction",
            "action": "use the treated safety population and retain event counts",
        },
        {
            "artifact": "manuscript_proof",
            "field": "prespecified_primary_claim",
            "observed": additional_time,
            "corrected": f"{primary_time}; {additional_time} is post hoc",
            "authority_ids": [controlling["source_id"], sap["source_id"]],
            "classification": "manuscript_correction",
            "action": "revise the proof before publication review",
        },
        {
            "artifact": "manuscript_proof",
            "field": "registry_posting_claim",
            "observed": f"posted {submitted_date}",
            "corrected": (
                f"submitted {submitted_date} and still under QC; not posted"
            ),
            "authority_ids": [submission["source_id"]],
            "classification": "manuscript_correction",
            "action": "replace the posted claim with the accurate submission state",
        },
    ]
    for index, row in enumerate(rows, start=1):
        row["finding_id"] = f"F-{index:02d}"
    derived = {"trial_id": registry["trial_id"], "findings": rows}
    found: list[str] = []
    if ledger.get("trial_id") != derived["trial_id"]:
        found.append("discrepancy ledger trial_id is wrong")
    candidate_rows = ledger.get("findings")
    if not isinstance(candidate_rows, list):
        return [*found, "discrepancy ledger requires a findings array"]
    actual = _keyed(candidate_rows, "field")
    wanted = _keyed(derived["findings"], "field")
    ids = [row.get("finding_id") for row in candidate_rows if isinstance(row, dict)]
    if set(actual) != set(wanted):
        found.append("findings must contain each correction target exactly once")
        return found
    if (
        len(ids) != len(candidate_rows)
        or len(set(ids)) != len(candidate_rows)
        or any(not isinstance(value, str) or not value for value in ids)
    ):
        found.append("finding_id values must be non-empty and unique")
    for field, derived_row in wanted.items():
        row = actual[field]
        if any(
            row.get(key) != derived_row[key]
            for key in ("artifact", "field", "classification")
        ):
            found.append(f"{field}: artifact or correction classification is wrong")
        if not _ledger_values_ok(field, row, derived_row):
            found.append(f"{field}: observed or corrected value does not close")
        authority_ids = row.get("authority_ids")
        if (
            not isinstance(authority_ids, list)
            or any(not isinstance(value, str) for value in authority_ids)
            or sorted(authority_ids) != sorted(derived_row["authority_ids"])
        ):
            found.append(f"{field}: authority_ids do not close")
        action = row.get("action")
        if not isinstance(action, str) or len(action.split()) < 4:
            found.append(f"{field}: action must be a substantive correction instruction")
    return found


def results_validation_errors(results: dict) -> list[str]:
    case = _case_inputs()
    registry = case["registry"]
    sap = case["sap"]
    submission = case["submission"]
    csr = case["csr"]
    primary = case["primary"]
    csr_outcomes = case["csr_outcomes"]
    submission_outcomes = case["submission_outcomes"]
    assert isinstance(registry, dict)
    assert isinstance(sap, dict)
    assert isinstance(submission, dict)
    assert isinstance(csr, dict)
    assert isinstance(primary, dict)
    assert isinstance(csr_outcomes, dict)
    assert isinstance(submission_outcomes, dict)

    outcomes = []
    for outcome_id, table in csr_outcomes.items():
        source = submission_outcomes[outcome_id]
        groups = [
            {**group, "label": sap["arm_map"][group["arm_id"]]}
            for group in table["groups"]
        ]
        outcomes.append(
            {
                "outcome_id": outcome_id,
                "classification": (
                    "primary_prespecified"
                    if outcome_id == primary["outcome_id"]
                    else "additional_post_hoc"
                ),
                "measure": source["measure"],
                "time_frame": source["time_frame"],
                "population": table["population"],
                "groups": groups,
            }
        )
    derived = {
        "trial_id": registry["trial_id"],
        "registry_status": {
            "results_first_submitted_date": submission[
                "results_first_submitted_date"
            ],
            "results_first_posted_date": submission["results_first_posted_date"],
            "state": submission["submission_state"],
        },
        "arms": [
            {"arm_id": arm_id, "label": label}
            for arm_id, label in sap["arm_map"].items()
        ],
        "participant_flow": csr["participant_flow"],
        "outcomes": outcomes,
        "serious_adverse_events": {
            "population": csr["safety_table"]["population"],
            "denominator": csr["safety_table"]["denominator"],
            "participants_with_event": csr["safety_table"][
                "participants_with_serious_event"
            ],
        },
    }
    found: list[str] = []
    for field in (
        "trial_id",
        "registry_status",
        "participant_flow",
        "serious_adverse_events",
    ):
        if results.get(field) != derived[field]:
            found.append(f"corrected results {field} is wrong")
    if _keyed(results.get("arms"), "arm_id") != _keyed(
        derived["arms"], "arm_id"
    ):
        found.append("arms must be keyed by arm_id with source-derived labels")
    actual_outcomes = _keyed(results.get("outcomes"), "outcome_id")
    wanted_outcomes = _keyed(derived["outcomes"], "outcome_id")
    if set(actual_outcomes) != set(wanted_outcomes):
        found.append("outcomes must contain each source outcome exactly once")
        return found
    for outcome_id, wanted in wanted_outcomes.items():
        actual = dict(actual_outcomes[outcome_id])
        derived_row = dict(wanted)
        groups = _keyed(actual.pop("groups", None), "arm_id")
        wanted_groups = _keyed(derived_row.pop("groups", None), "arm_id")
        if actual != derived_row:
            found.append(
                f"{outcome_id}: classification, measure, time frame, or population is wrong"
            )
        if groups != wanted_groups:
            found.append(f"{outcome_id}: source-derived groups are wrong")
    return found


def _ledger_values_ok(field: str, actual: dict, derived: dict) -> bool:
    case = _case_inputs()
    primary = case["primary"]
    additional = case["additional"]
    submission = case["submission"]
    assert isinstance(primary, dict)
    assert isinstance(additional, dict)
    assert isinstance(submission, dict)
    if field == "prespecified_primary_claim":
        observed = str(actual.get("observed") or "").casefold()
        corrected = str(actual.get("corrected") or "").casefold()
        primary_time = str(primary["time_frame"]).casefold()
        additional_time = str(additional["time_frame"]).casefold()
        return (
            additional_time in observed
            and primary_time in corrected
            and additional_time in corrected
            and ("post hoc" in corrected or "post-hoc" in corrected)
        )
    if field == "registry_posting_claim":
        observed = str(actual.get("observed") or "").casefold()
        corrected = str(actual.get("corrected") or "").casefold()
        date = str(submission["results_first_submitted_date"]).casefold()
        return (
            "post" in observed
            and date in observed
            and "submit" in corrected
            and date in corrected
            and "qc" in corrected
            and "not" in corrected
            and "post" in corrected
        )
    return all(actual.get(key) == derived[key] for key in ("observed", "corrected"))


def errors(graph: dict, ledger: dict, results: dict) -> list[str]:
    return [
        *graph_validation_errors(graph),
        *ledger_validation_errors(ledger),
        *results_validation_errors(results),
    ]


def _semantic_graph(graph: dict) -> dict:
    rows = [
        {
            key: node[key]
            for key in ("source_id", "kind", "source_date", "authority", "sha256")
        }
        for node in graph["nodes"]
    ]
    return {
        "trial_id": graph["trial_id"],
        "primary_completion_date": graph["primary_completion_date"],
        "unblinding_date": graph["unblinding_date"],
        "nodes": sorted(rows, key=lambda row: row["source_id"]),
    }


def _semantic_ledger(ledger: dict) -> dict:
    case = _case_inputs()
    primary = case["primary"]
    additional = case["additional"]
    submission = case["submission"]
    assert isinstance(primary, dict)
    assert isinstance(additional, dict)
    assert isinstance(submission, dict)
    rows = []
    for finding in ledger["findings"]:
        field = finding["field"]
        row = {
            key: finding[key]
            for key in ("artifact", "field", "classification")
        }
        row["authority_ids"] = sorted(finding["authority_ids"])
        if field == "prespecified_primary_claim":
            row["observed"] = additional["time_frame"]
            row["corrected"] = (
                f"{primary['time_frame']}; {additional['time_frame']} is post hoc"
            )
        elif field == "registry_posting_claim":
            date = submission["results_first_submitted_date"]
            row["observed"] = f"posted {date}"
            row["corrected"] = f"submitted {date} and still under QC; not posted"
        else:
            row["observed"] = finding["observed"]
            row["corrected"] = finding["corrected"]
        rows.append(row)
    return {
        "trial_id": ledger["trial_id"],
        "findings": sorted(rows, key=lambda row: row["field"]),
    }


def _semantic_results(results: dict) -> dict:
    normalized = json.loads(json.dumps(results))
    normalized["arms"] = sorted(normalized["arms"], key=lambda row: row["arm_id"])
    for outcome in normalized["outcomes"]:
        outcome["groups"] = sorted(outcome["groups"], key=lambda row: row["arm_id"])
    normalized["outcomes"] = sorted(
        normalized["outcomes"], key=lambda row: row["outcome_id"]
    )
    return normalized


def packet_identity(graph: dict, ledger: dict, results: dict) -> dict[str, str]:
    case = _case_inputs()
    registry = case["registry"]
    policy = case["policy"]
    assert isinstance(registry, dict)
    assert isinstance(policy, dict)
    recovery_id = (
        f"trial-results-qc:{registry['trial_id']}:{policy['policy_version']}"
    )
    checkpoint = canonical_sha(input_digests())
    semantic_plan = canonical_sha(
        {
            "graph": _semantic_graph(graph),
            "ledger": _semantic_ledger(ledger),
            "results": _semantic_results(results),
        }
    )
    return {
        "recovery_id": recovery_id,
        "source_checkpoint_sha256": checkpoint,
        "semantic_plan_sha256": semantic_plan,
    }


def initial_state() -> dict:
    case = _case_inputs()
    registry = case["registry"]
    policy = case["policy"]
    assert isinstance(registry, dict)
    assert isinstance(policy, dict)
    return {
        "trial_id": registry["trial_id"],
        "policy_version": policy["policy_version"],
        "status": "qc_reconciliation_open",
        "graph_sha256": None,
        "ledger_sha256": None,
        "payload_sha256": None,
        "input_sha256": None,
        "replay_verified": False,
        "submitted": False,
        "posted": False,
        "manuscript_changed": False,
        "external_communication": False,
    }


def final_state(graph: dict, ledger: dict, results: dict, replay: bool) -> dict:
    case = _case_inputs()
    registry = case["registry"]
    policy = case["policy"]
    assert isinstance(registry, dict)
    assert isinstance(policy, dict)
    identity = packet_identity(graph, ledger, results)
    return {
        "trial_id": registry["trial_id"],
        "policy_version": policy["policy_version"],
        "status": policy["final_state"],
        **identity,
        "graph_sha256": canonical_sha(_semantic_graph(graph)),
        "ledger_sha256": canonical_sha(_semantic_ledger(ledger)),
        "payload_sha256": canonical_sha(_semantic_results(results)),
        "input_sha256": input_digests(),
        "replay_verified": replay,
        "submitted": False,
        "posted": False,
        "manuscript_changed": False,
        "external_communication": False,
    }


def receipt(graph: dict, ledger: dict, results: dict, replay: bool) -> dict:
    state = final_state(graph, ledger, results, replay)
    value = {
        "tool": "trialctl/2",
        "trial_id": state["trial_id"],
        "policy_version": state["policy_version"],
        "status": state["status"],
        "recovery_id": state["recovery_id"],
        "source_checkpoint_sha256": state["source_checkpoint_sha256"],
        "semantic_plan_sha256": state["semantic_plan_sha256"],
        "graph_sha256": state["graph_sha256"],
        "ledger_sha256": state["ledger_sha256"],
        "payload_sha256": state["payload_sha256"],
        "input_sha256": state["input_sha256"],
        "finding_count": len(ledger["findings"]),
        "replay_verified": replay,
        "external_action": "none_staged_review_only",
    }
    value["receipt_sha256"] = canonical_sha(value)
    return value
