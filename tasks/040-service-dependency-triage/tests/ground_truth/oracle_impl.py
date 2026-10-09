from __future__ import annotations

import json
import math
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

_TASK_DIR = Path(__file__).resolve().parents[2]
_GT = _TASK_DIR / "tests" / "ground_truth" / "ground_truth.json"
_OBSERVATION_SIGNALS = {
    "topology.json": (
        "auth-2026-0318",
        "auth-gateway",
        "checkout-web",
        "dependency",
        "payment-api",
    ),
    "metrics/service_metrics.csv": (
        "401",
        "auth-gateway",
        "checkout-web",
        "payment-api",
    ),
    "logs/checkout-web.log": ("401", "checkout", "payment-api"),
    "logs/payment-api.log": ("401", "auth-gateway", "issuer", "token"),
    "logs/auth-gateway.log": ("auth-2026-0318", "issuer", "jwks", "partner-v"),
}


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _norm(value: Any) -> str:
    return str(value or "").strip().lower()


def _contains_all(text: str, tokens: list[str]) -> int:
    low = " ".join(re.sub(r"[_-]+", " ", text.casefold()).split())
    return sum(
        1
        for token in tokens
        if " ".join(re.sub(r"[_-]+", " ", token.casefold()).split()) in low
    )


def _source_unchanged(workspace: Path) -> bool:
    root = _TASK_DIR / "workspace"
    src = workspace.resolve()
    if not src.is_dir():
        return True
    for original in root.rglob("*"):
        if not original.is_file():
            continue
        rel = original.relative_to(root)
        if rel.as_posix() == "service_repo/auth_gateway_config.json":
            continue
        candidate = src / rel
        if not candidate.is_file() or candidate.read_bytes() != original.read_bytes():
            return False
    return True


def _canonical_source_path(value: Any, allowed: set[str]) -> str | None:
    source = str(value or "").strip().replace("\\", "/").casefold()
    for prefix in ("/workspace/", "$workspace/", "${workspace}/", "./"):
        if source.startswith(prefix):
            source = source[len(prefix) :]
            break
    return source if source in allowed else None


def _observation_is_concrete(source: str, value: Any) -> bool:
    observation = " ".join(str(value or "").casefold().split())
    return len(observation) >= 12 and any(
        signal in observation for signal in _OBSERVATION_SIGNALS[source]
    )


def _evidence_sources(value: Any, allowed: set[str]) -> tuple[set[str], bool]:
    sources: set[str] = set()
    structured = isinstance(value, list) and bool(value)
    if not isinstance(value, list):
        return sources, False
    for item in value:
        if not isinstance(item, dict):
            structured = False
            continue
        source = _canonical_source_path(
            item.get("source_file") or item.get("source"),
            allowed,
        )
        observation = item.get("observation") or item.get("finding")
        if source is None or not _observation_is_concrete(source, observation):
            structured = False
            continue
        sources.add(source)
    return sources, structured


def _causal_chain_ok(text: str) -> bool:
    low = " ".join(text.casefold().replace("\\rightarrow", "->").split())

    checkout_positions = [
        match.start() for match in re.finditer(r"\bcheckout(?:-web)?\b", low)
    ]
    payment_positions = [
        match.start() for match in re.finditer(r"\bpayment(?:-api)?\b", low)
    ]
    auth_positions = [match.start() for match in re.finditer(r"\bauth-gateway\b", low)]
    ordered_path = any(
        checkout < payment < auth
        for checkout in checkout_positions
        for payment in payment_positions
        for auth in auth_positions
    )
    path_language = any(
        marker in low
        for marker in (
            "->",
            "dependency path",
            "depends on",
            "upstream",
        )
    )
    causal_language = bool(
        re.search(
            r"\b(?:because|caus(?:al|e|ed|ing)|creating|due to|"
            r"led to|result(?:ed|ing)|root cause)\b",
            low,
        )
    )
    causal_signal = any(
        signal in low for signal in ("auth-2026-0318", "issuer", "jwks")
    )
    return ordered_path and path_language and causal_language and causal_signal


def _next_steps_ok(value: Any) -> bool:
    if isinstance(value, list):
        text = " ".join(str(item) for item in value)
    else:
        text = str(value or "")
    low = " ".join(re.sub(r"[_-]+", " ", text.casefold()).split())
    mitigation = any(
        term in low
        for term in ("rollback", "revert", "restore", "allowed issuers", "issuer")
    )
    verification = any(
        term in low for term in ("verify", "validate", "confirm", "monitor", "recheck")
    )
    return mitigation and verification


def _confidence_is_declared(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return math.isfinite(float(value)) and 0.0 <= float(value) <= 1.0
    return bool(str(value or "").strip())


def _red_herrings_explained(value: Any, expected: list[str]) -> bool:
    """Require a reason for each named red herring without fixing its prose."""
    if not isinstance(value, list) or not value:
        return False
    explanations: dict[str, str] = {}
    for item in value:
        if isinstance(item, dict):
            signal = str(item.get("signal") or item.get("name") or "").casefold()
            reason = str(item.get("reason") or item.get("explanation") or "").strip()
            if signal and reason:
                for name in expected:
                    if name.casefold() in signal:
                        explanations[name.casefold()] = reason
            else:
                for name, mapped_reason in item.items():
                    explanations[_norm(name)] = str(mapped_reason or "").strip()
        elif isinstance(item, str):
            low = item.casefold()
            for name in expected:
                if name.casefold() in low:
                    explanations[name.casefold()] = item.strip()
    return all(
        name.casefold() in explanations
        and len(explanations[name.casefold()].split()) >= 3
        for name in expected
    )


def _notes_concept_present(text: str, alternatives: list[str]) -> bool:
    """Accept the phrasal verb ``roll back`` while preserving polarity."""
    low = text.casefold()
    if any(term.casefold() in low for term in alternatives):
        return True
    if "rollback" not in {term.casefold() for term in alternatives}:
        return False
    for match in re.finditer(r"\broll\s+back\b", low):
        prefix = low[max(0, match.start() - 32) : match.start()]
        if not re.search(
            r"\b(?:do\s+not|don't|never|not|avoid)\b[^.!?;]{0,24}$", prefix
        ):
            return True
    return False


def score_workspace(workspace: Path) -> dict[str, Any]:
    w = workspace.resolve()
    gt = _load_json(_GT)
    exp = gt["expected"]
    weights = gt["scoring"]["weights"]
    checks: list[dict[str, Any]] = []
    notes_path = w / "triage_notes.md"
    notes_text = (
        notes_path.read_text(encoding="utf-8", errors="replace")
        if notes_path.is_file()
        else ""
    )

    def add(cid: str, label: str, ok: bool, weight: float, detail: Any = None) -> None:
        checks.append(
            {
                "id": cid,
                "label": label,
                "pass": bool(ok),
                "weight": weight,
                "detail": detail,
            }
        )

    config_path = w / "service_repo" / "auth_gateway_config.json"
    verifier_path = w / "service_repo" / "verify_checkout.py"
    seed_config_path = (
        _TASK_DIR / "workspace" / "service_repo" / "auth_gateway_config.json"
    )
    runtime_recovery_ok = False
    runtime_detail: dict[str, Any] = {}
    try:
        config = _load_json(config_path)
        seed_config = _load_json(seed_config_path)
        expected_issuers = set(exp["allowed_issuers"])
        actual_issuers = config.get("allowed_issuers")
        issuer_scope_ok = bool(
            isinstance(actual_issuers, list)
            and len(actual_issuers) == len(set(actual_issuers))
            and set(actual_issuers) == expected_issuers
        )
        unchanged_fields = {
            key: config.get(key) == value
            for key, value in seed_config.items()
            if key != "allowed_issuers"
        }
        minimal_change_ok = bool(unchanged_fields and all(unchanged_fields.values()))
        completed = subprocess.run(
            [sys.executable, str(verifier_path), "--config", str(config_path)],
            cwd=w,
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        report = json.loads(completed.stdout)
        verifier_ok = bool(
            completed.returncode == 0
            and report.get("status") == "pass"
            and report.get("passed") == 6
            and report.get("total") == 6
        )
        runtime_recovery_ok = issuer_scope_ok and minimal_change_ok and verifier_ok
        runtime_detail = {
            "allowed_issuers": actual_issuers,
            "issuer_scope_ok": issuer_scope_ok,
            "unchanged_fields": unchanged_fields,
            "verifier_returncode": completed.returncode,
            "verifier_status": report.get("status"),
            "verifier_passed": report.get("passed"),
            "verifier_total": report.get("total"),
        }
    except Exception as exc:
        runtime_detail = {"error": f"{type(exc).__name__}: {exc}"}
    add(
        "runtime_recovery",
        "the minimal issuer repair passes all positive and negative checkout cases",
        runtime_recovery_ok,
        0.0,
        runtime_detail,
    )

    json_score = 0.0
    root_cause_data: dict[str, Any] = {}
    diagnosis_identity_ok = False
    evidence_package_ok = False
    path = w / "root_cause.json"
    if path.is_file():
        try:
            data = _load_json(path)
            root_cause_data = data if isinstance(data, dict) else {}
            affected_values = data.get("affected_services", [])
            affected = (
                {str(x).lower() for x in affected_values}
                if isinstance(affected_values, list)
                else set()
            )
            allowed_sources = {
                str(source).casefold() for source in exp["evidence_sources"]
            }
            sources, evidence_structured = _evidence_sources(
                data.get("evidence"),
                allowed_sources,
            )
            red_text = json.dumps(
                data.get("excluded_red_herrings", ""), ensure_ascii=False
            ).lower()
            source_hits = len(sources & allowed_sources)
            affected_hits = len(
                affected & {x.lower() for x in exp["affected_services"]}
            )
            red_hits = _contains_all(red_text, exp["red_herrings"])
            confidence_ok = str(data.get("confidence", "")).lower() in {
                "high",
                "medium",
                "0.8",
                "0.9",
                "0.95",
            } or isinstance(data.get("confidence"), (int, float))
            incident_id = str(data.get("incident_id", "")).strip()
            incident_ok = 0 < len(incident_id) <= 128
            steps_ok = _next_steps_ok(data.get("recommended_next_steps"))
            expected_affected = {
                str(value).strip().casefold() for value in exp["affected_services"]
            }
            # Teams reasonably differ on whether the misconfigured origin service
            # is itself listed as "affected".  Require the customer-impacting
            # downstream boundary and reject unrelated services, while accepting
            # either convention for the diagnosed root service.
            allowed_affected = {
                *expected_affected,
                str(exp["root_cause_service"]).strip().casefold(),
            }
            affected_boundary_ok = bool(
                isinstance(affected_values, list)
                and len(affected_values) == len(affected)
                and expected_affected <= affected <= allowed_affected
            )
            required_keys = {
                "incident_id",
                "root_cause_service",
                "root_cause_change_id",
                "confidence",
                "affected_services",
                "evidence",
                "excluded_red_herrings",
                "recommended_next_steps",
            }
            diagnosis_identity_ok = bool(
                required_keys <= set(data)
                and incident_ok
                and _confidence_is_declared(data.get("confidence"))
                and _norm(data.get("root_cause_service")) == exp["root_cause_service"]
                and _norm(data.get("root_cause_change_id"))
                == exp["root_cause_change_id"].casefold()
                and affected_boundary_ok
            )
            evidence_package_ok = bool(
                evidence_structured
                and source_hits >= 3
                and _red_herrings_explained(
                    data.get("excluded_red_herrings"), exp["red_herrings"]
                )
            )
            json_score = (
                0.05 * incident_ok
                + 0.27
                * (_norm(data.get("root_cause_service")) == exp["root_cause_service"])
                + 0.20
                * (
                    _norm(data.get("root_cause_change_id"))
                    == exp["root_cause_change_id"].lower()
                )
                + 0.14 * (affected_hits / len(exp["affected_services"]))
                + 0.16 * (min(source_hits / 3, 1) * evidence_structured)
                + 0.07 * min(red_hits / len(exp["red_herrings"]), 1)
                + 0.08 * steps_ok
                + 0.03 * confidence_ok
            )
            add(
                "root_cause_json",
                "root_cause.json identifies root cause, source-bound evidence, mitigation, and red herrings",
                json_score >= 0.70 and evidence_structured and source_hits >= 3,
                weights["root_cause_json"],
                {
                    "score": round(json_score, 4),
                    "source_hits": source_hits,
                    "evidence_structured": evidence_structured,
                    "red_hits": red_hits,
                    "recommended_next_steps": steps_ok,
                },
            )
        except Exception as exc:
            add(
                "root_cause_parse",
                "root_cause.json parseable",
                False,
                weights["root_cause_json"],
                str(exc),
            )
    else:
        add(
            "root_cause_missing",
            "root_cause.json exists",
            False,
            weights["root_cause_json"],
            "missing",
        )
    add(
        "diagnosis_identity",
        "root cause service, change, and affected-service boundary are correct",
        diagnosis_identity_ok,
        0.0,
    )
    add(
        "evidence_package",
        "three source-bound observations, explained red herrings, and recovery steps are present",
        evidence_package_ok,
        0.0,
    )

    notes_score = 0.0
    notes = notes_path
    if notes.is_file():
        text = notes_text
        concept_hits = sum(
            _notes_concept_present(text, group) for group in gt["notes_concepts"]
        )
        file_hits = _contains_all(text, exp["evidence_sources"])
        fact_inference_ok = bool(
            re.search(r"fact|observed|inference|inferred", text, re.IGNORECASE)
        )
        causal_chain_ok = _causal_chain_ok(text)
        notes_score = (
            0.35 * (concept_hits / len(gt["notes_concepts"]))
            + 0.25 * min(file_hits / 3, 1)
            + 0.25 * causal_chain_ok
            + 0.15 * fact_inference_ok
        )
        add(
            "triage_notes",
            "triage_notes.md cites sources, covers mitigation/verification, and separates facts from inference",
            notes_score >= 0.70 and file_hits >= 3 and causal_chain_ok,
            weights["triage_notes"],
            {
                "score": round(notes_score, 4),
                "concept_hits": concept_hits,
                "source_hits": file_hits,
                "causal_chain": causal_chain_ok,
            },
        )
    else:
        add(
            "triage_notes_missing",
            "triage_notes.md exists",
            False,
            weights["triage_notes"],
            "missing",
        )

    normalized_notes = " ".join(re.sub(r"[_-]+", " ", notes_text.casefold()).split())
    actual_service = _norm(root_cause_data.get("root_cause_service"))
    actual_change = _norm(root_cause_data.get("root_cause_change_id"))
    actual_affected = root_cause_data.get("affected_services")
    affected_names = (
        [str(value).strip().casefold() for value in actual_affected]
        if isinstance(actual_affected, list)
        else []
    )
    cross_artifact_consistency = bool(
        actual_service
        and actual_change
        and affected_names
        and " ".join(re.sub(r"[_-]+", " ", actual_service).split()) in normalized_notes
        and " ".join(re.sub(r"[_-]+", " ", actual_change).split()) in normalized_notes
        and all(
            " ".join(re.sub(r"[_-]+", " ", name).split()) in normalized_notes
            for name in affected_names
        )
    )
    add(
        "cross_artifact_consistency",
        "structured diagnosis and operator notes describe the same causal chain",
        cross_artifact_consistency,
        0.0,
        {
            "root_cause_service": actual_service,
            "root_cause_change_id": actual_change,
            "affected_services": affected_names,
        },
    )

    unchanged = _source_unchanged(w)
    add(
        "source_unchanged",
        "fixtures are not modified",
        unchanged,
        weights["source_unchanged"],
    )
    total = (
        json_score * weights["root_cause_json"]
        + notes_score * weights["triage_notes"]
        + float(unchanged) * weights["source_unchanged"]
    )
    thresholds = gt["scoring"]["thresholds"]
    level = (
        "excellent"
        if total >= thresholds["excellent"]
        else "good"
        if total >= thresholds["good"]
        else "pass"
        if total >= thresholds["pass"]
        else "fail"
    )
    return {
        "task": "040-service-dependency-triage",
        "workspace": str(w),
        "outcome_score": round(total, 4),
        "level": level,
        "checks": checks,
    }
