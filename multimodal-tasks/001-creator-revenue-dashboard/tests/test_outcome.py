from __future__ import annotations

import contextlib
import json
import re
import socket
import threading
from pathlib import Path
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from harnessbench.grading.task_checks import (
    explicit_external_action_claims,
    norm,
    observation,
    read_json_list,
    sources_unchanged,
)

TASK = Path(__file__).resolve().parent.parent
GROUND_TRUTH = json.loads(
    (TASK / "tests" / "ground_truth" / "ground_truth.json").read_text(encoding="utf-8")
)

ALLOWED_MODIFIED = {
    "web/package.json",
    "web/index.html",
    "web/vite.config.ts",
    "web/tsconfig.json",
    "web/src/main.tsx",
    "web/src/App.tsx",
    "web/src/index.css",
    "web/src/hooks/useReveal.ts",
    "web/src/utils/cn.ts",
}
ALLOWED_CREATED_PREFIXES = (
    "web/dist/",
    "web/src/components/",
    "web/src/hooks/",
    "web/src/utils/",
)
REQUIRED_FILES = [
    "web/package.json",
    "web/index.html",
    "web/vite.config.ts",
    "web/tsconfig.json",
    "web/src/main.tsx",
    "web/src/App.tsx",
    "web/src/index.css",
    "web/src/data/localRecords.json",
]
STARTER_OR_GENERIC = re.compile(
    r"Ready for implementation|Alpha|Beta|Gamma|keyword bank|token bank",
    re.IGNORECASE,
)
REMOTE_OR_FORBIDDEN = re.compile(
    r"https?://(?!www\.w3\.org/2000/svg\b)|fetch\s*\(|XMLHttpRequest|navigator\.sendBeacon",
    re.IGNORECASE,
)


class _QuietStaticHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        return


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _source_files(workspace: Path) -> list[Path]:
    roots = [
        workspace / "web" / "src",
    ]
    files: list[Path] = []
    for root in roots:
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*")):
            if path.is_file() and path.suffix in {".ts", ".tsx", ".css"}:
                files.append(path)
    for rel in ["web/package.json", "web/index.html", "web/vite.config.ts", "web/tsconfig.json"]:
        path = workspace / rel
        if path.is_file():
            files.append(path)
    return files


def _project_text(workspace: Path) -> str:
    return "\n".join(_read(path) for path in _source_files(workspace))


def _missing_groups(text: str, groups: list[list[str]]) -> list[list[str]]:
    low = text.casefold()
    return [group for group in groups if not any(term.casefold() in low for term in group)]


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@contextlib.contextmanager
def _serve_static(directory: Path):
    port = _free_port()
    handler = partial(_QuietStaticHandler, directory=str(directory))
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}/"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def _required_files_ok(workspace: Path) -> bool:
    return all((workspace / rel).is_file() and (workspace / rel).stat().st_size > 80 for rel in REQUIRED_FILES)


def _package_ok(workspace: Path, text: str) -> tuple[bool, Any]:
    package = _read(workspace / "web/package.json")
    try:
        pkg = json.loads(package)
    except json.JSONDecodeError:
        return False, "package.json is not valid JSON"

    deps = {**(pkg.get("dependencies") or {}), **(pkg.get("devDependencies") or {})}
    required_deps = {"vite", "typescript", "react", "react-dom", "@vitejs/plugin-react"}
    missing_deps = sorted(dep for dep in required_deps if dep not in deps)
    latest_deps = sorted(dep for dep, version in deps.items() if str(version).strip() in {"latest", "*"})
    source_imports_data = "localrecords.json" in text.casefold()
    checks = {
        "build_script": "build" in (pkg.get("scripts") or {}),
        "entrypoint": "ReactDOM.createRoot" in _read(workspace / "web/src/main.tsx"),
        "default_export": "export default" in _read(workspace / "web/src/App.tsx"),
        "imports_local_data_from_source": source_imports_data,
        "no_starter": not STARTER_OR_GENERIC.search(text),
        "missing_deps": missing_deps,
        "latest_deps": latest_deps,
    }
    ok = (
        all(value is True for key, value in checks.items() if key not in {"missing_deps", "latest_deps"})
        and not missing_deps
        and not latest_deps
    )
    return ok, checks


def _records_ok(workspace: Path) -> tuple[bool, Any]:
    rows = read_json_list(workspace / "web/src/data/localRecords.json")
    expected = GROUND_TRUTH["records"]
    by_id = {str(row.get("id")): row for row in rows if isinstance(row, dict)}
    schema_ok = (
        len(rows) == len(expected)
        and set(by_id) == set(expected)
        and len(by_id) == len(rows)
        and all(
            isinstance(row.get("name"), str)
            and norm(row.get("category")) in {"video", "newsletter", "shorts", "community"}
            and isinstance(row.get("owner"), str)
            and norm(row.get("status")) in {"clear", "watch", "review"}
            and isinstance(row.get("primary"), int)
            and isinstance(row.get("secondary"), int)
            for row in by_id.values()
        )
    )
    values_ok = all(
        by_id.get(record_id, {}).get(key) == value
        for record_id, expected_row in expected.items()
        for key, value in expected_row.items()
    )
    return schema_ok and values_ok, {
        "schema_ok": schema_ok,
        "values_ok": values_ok,
        "record_count": len(rows),
        "missing_or_extra_ids": sorted(set(by_id) ^ set(expected)),
    }


def _domain_grounding_ok(text: str) -> tuple[bool, Any]:
    missing_domain = _missing_groups(text, GROUND_TRUTH["domain_groups"])
    missing_controls = _missing_groups(text, GROUND_TRUTH["control_groups"])
    missing_summaries = _missing_groups(text, GROUND_TRUTH["summary_groups"])
    ok = not missing_domain and not missing_controls and not missing_summaries
    return ok, {
        "missing_domain_groups": missing_domain,
        "missing_control_groups": missing_controls,
        "missing_summary_groups": missing_summaries,
    }


def _interaction_ok(text: str) -> tuple[bool, Any]:
    low = text.casefold()
    handler_count = sum(low.count(token) for token in ("onclick", "onchange", "oninput", "onsubmit"))
    missing_interactions = _missing_groups(text, GROUND_TRUTH["interaction_groups"])
    missing_calculations = _missing_groups(text, GROUND_TRUTH["calculation_groups"])
    record_field_usage = all(token in low for token in ("category", "owner", "status", "primary", "secondary"))
    ok = (
        handler_count >= 4
        and not missing_interactions
        and not missing_calculations
        and record_field_usage
    )
    return ok, {
        "handler_count": handler_count,
        "minimum_handlers": 4,
        "missing_interaction_groups": missing_interactions,
        "missing_calculation_groups": missing_calculations,
        "record_field_usage": record_field_usage,
    }


def _first(locator):
    return locator.first


def _select_option_by_label(page, label: str, value: str) -> None:
    control = _first(page.get_by_role("combobox", name=re.compile(label, re.IGNORECASE)))
    try:
        control.select_option(value, timeout=5000)
    except Exception:
        control.select_option(label=value, timeout=5000)


def _select_non_default_option_by_label(page, label: str) -> str:
    control = _first(page.get_by_role("combobox", name=re.compile(label, re.IGNORECASE)))
    current_value = control.input_value(timeout=5000)
    options = control.locator("option").evaluate_all(
        """elements => elements.map(element => ({
            value: element.value,
            label: element.textContent || element.label || element.value,
            disabled: element.disabled
        }))"""
    )
    candidates = [
        option
        for option in options
        if not option["disabled"] and option["value"] != current_value
    ]
    if not candidates:
        raise AssertionError(f"{label} must provide an enabled non-default option")
    selected = candidates[0]
    control.select_option(value=selected["value"], timeout=5000)
    return str(selected["label"]).strip() or str(selected["value"])


def _set_range_by_label(page, label: str, value: int) -> None:
    control = _first(page.get_by_label(re.compile(label, re.IGNORECASE)))
    control.evaluate(
        """(element, value) => {
            element.value = String(value);
            element.dispatchEvent(new Event("input", { bubbles: true }));
            element.dispatchEvent(new Event("change", { bubbles: true }));
        }""",
        value,
        timeout=5000,
    )


def _missing_visible_text(body_text: str, tokens: list[str]) -> list[str]:
    low = body_text.casefold()
    numeric_normalized = low.replace(",", "")
    return [
        token
        for token in tokens
        if token.casefold() not in low and token.casefold() not in numeric_normalized
    ]


def _numeric_tokens(text: str) -> set[str]:
    return {
        token.replace(",", "")
        for token in re.findall(r"(?<![\w.-])-?\d[\d,]*(?:\.\d+)?(?![\w.-])", text)
    }


def _summary_numeric_snapshots(page, required_terms: list[str]) -> list[list[str]]:
    texts = page.evaluate(
        """terms => {
            const wanted = terms.map(term => term.toLowerCase());
            const candidates = Array.from(
                document.querySelectorAll("section, aside, article, div, main")
            ).filter(element => {
                const text = (element.innerText || "").toLowerCase();
                return wanted.every(term => text.includes(term));
            });
            const smallest = candidates.filter(element =>
                !candidates.some(other => other !== element && element.contains(other))
            );
            return smallest.map(element => element.innerText || "");
        }""",
        required_terms,
    )
    return sorted(
        [sorted(_numeric_tokens(str(text))) for text in texts],
        key=lambda tokens: (len(tokens), tokens),
    )


def _exact_token_present(text: str, token: str) -> bool:
    return bool(re.search(rf"(?<![\w-]){re.escape(token)}(?![\w-])", text, re.IGNORECASE))




def _record_id_locator(page, record_id: str):
    pattern = re.compile(rf"(?<![A-Za-z0-9-]){re.escape(record_id)}(?![A-Za-z0-9-])", re.IGNORECASE)
    return page.get_by_text(pattern)


def _click_record_id(page, record_id: str) -> None:
    _first(_record_id_locator(page, record_id)).click(timeout=5000)

def _smallest_region_text(page, required_terms: list[str]) -> tuple[str, str]:
    result = page.evaluate(
        """terms => {
            const wanted = terms.map(term => term.toLowerCase());
            const candidates = Array.from(document.querySelectorAll("section, aside, article, div, main"))
                .map(element => ({
                    text: element.innerText || "",
                    tag: element.tagName.toLowerCase(),
                    label: element.getAttribute("aria-label") || "",
                    className: typeof element.className === "string" ? element.className : ""
                }))
                .filter(item => wanted.every(term => item.text.toLowerCase().includes(term)));
            candidates.sort((a, b) => a.text.length - b.text.length);
            return candidates[0] || null;
        }""",
        required_terms,
    )
    if result and result.get("text"):
        source = result.get("label") or result.get("className") or result.get("tag") or "region"
        return str(result["text"]), str(source)
    return page.locator("body").inner_text(timeout=5000), "body"


def _region_text(page, aria_label: str, required_terms: list[str]) -> tuple[str, str]:
    locator = page.get_by_label(re.compile(aria_label, re.IGNORECASE))
    matches = locator.count()
    if matches > 0:
        wanted = [term.casefold() for term in required_terms]
        fallback_text = ""
        for index in range(matches):
            candidate = locator.nth(index)
            try:
                text = candidate.inner_text(timeout=1500)
            except Exception:
                continue
            if index == 0:
                fallback_text = text
            low = text.casefold()
            if all(term in low for term in wanted):
                return text, f"aria:{aria_label}"
        if fallback_text:
            return fallback_text, f"aria:{aria_label}:fallback"
    return _smallest_region_text(page, required_terms)


def _control_sanity(page, labels: list[str]) -> tuple[bool, Any]:
    problems: list[dict[str, Any]] = []
    for label in labels:
        locator = _first(page.get_by_label(re.compile(label, re.IGNORECASE)))
        try:
            locator.wait_for(state="visible", timeout=3000)
            locator.scroll_into_view_if_needed(timeout=3000)
            box = locator.bounding_box(timeout=3000)
            usable = bool(box and box["width"] >= 16 and box["height"] >= 12)
            unobscured = bool(
                locator.evaluate(
                    """element => {
                        const rect = element.getBoundingClientRect();
                        if (!rect.width || !rect.height) return false;
                        const x = rect.left + rect.width / 2;
                        const y = rect.top + rect.height / 2;
                        const top = document.elementFromPoint(x, y);
                        return top === element || element.contains(top) || (top && top.contains(element));
                    }"""
                )
            )
            if not usable or not unobscured:
                problems.append({"label": label, "box": box, "unobscured": unobscured})
        except Exception as exc:
            problems.append({"label": label, "error": repr(exc)})
    overflow = page.evaluate(
        "() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) "
        "- window.innerWidth"
    )
    if overflow > 8:
        problems.append({"layout": "horizontal_overflow", "px": overflow})
    return not problems, problems


def _enable_review_queue_only(page) -> str:
    label = re.compile(r"Review queue only|Risk queue only|Needs review only", re.IGNORECASE)
    control = page.get_by_label(label)
    if control.count() > 0:
        item = _first(control)
        tag_name = str(item.evaluate("element => element.tagName")).casefold()
        input_type = str(item.evaluate("element => element.getAttribute('type') || ''")).casefold()
        if tag_name == "input" and input_type == "checkbox":
            item.check(timeout=5000)
        else:
            item.click(timeout=5000)
        return "label"
    button = page.get_by_role("button", name=label)
    if button.count() > 0:
        _first(button).click(timeout=5000)
        return "button"
    text = page.get_by_text(label)
    if text.count() > 0:
        _first(text).click(timeout=5000)
        return "text"
    raise AssertionError("Review queue only control not found")


def _browser_interaction_ok(workspace: Path) -> tuple[bool, Any]:
    dist = workspace / "web" / "dist"
    if not (dist / "index.html").is_file():
        return False, {"browser_check": "dist_missing", "expected": "web/dist/index.html"}

    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        return False, {"browser_check": "playwright_unavailable", "error": repr(exc)}

    expected = GROUND_TRUTH["interaction_probe"]["expected_state"]
    missing_text: list[str] = []
    layout_problems: list[Any] = []
    controls_used: list[str] = []
    behavior_problems: list[Any] = []
    try:
        with _serve_static(dist) as url:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                try:
                    page = browser.new_page(viewport=GROUND_TRUTH["interaction_probe"]["target_viewport"])
                    page.goto(url, wait_until="networkidle", timeout=10000)
                    initial_summary_snapshots = _summary_numeric_snapshots(
                        page, expected["summary_change_labels"]
                    )

                    sane, problems = _control_sanity(
                        page,
                        ["Channel cohort", "Creator search", "Forecast mode", "Sponsor pressure"],
                    )
                    if not sane:
                        layout_problems.extend({"viewport": "desktop_initial", **problem} for problem in problems)
                        return False, {
                            "browser_check": "layout_or_control_sanity_failed",
                            "url": url,
                            "controls_used": controls_used,
                            "missing_visible_text": missing_text,
                            "layout_problems": layout_problems,
                            "behavior_problems": behavior_problems,
                        }

                    _select_option_by_label(page, "Channel cohort", "video")
                    controls_used.append("Channel cohort")
                    search = _first(page.get_by_label(re.compile("Creator search", re.IGNORECASE)))
                    search.fill("Studio", timeout=5000)
                    controls_used.append("Creator search")
                    _click_record_id(page, "CMP-017")
                    controls_used.append("CMP-017")
                    forecast_option = _select_non_default_option_by_label(page, "Forecast mode")
                    controls_used.append(f"Forecast mode ({forecast_option})")
                    _set_range_by_label(page, "Sponsor pressure", 64)
                    controls_used.append("Sponsor pressure")
                    page.wait_for_timeout(250)

                    body_text = page.locator("body").inner_text(timeout=5000)
                    updated_summary_snapshots = _summary_numeric_snapshots(
                        page, expected["summary_change_labels"]
                    )
                    if initial_summary_snapshots == updated_summary_snapshots:
                        behavior_problems.append(
                            {
                                "check": "summary_numbers_changed_after_controls",
                                "before": initial_summary_snapshots,
                                "after": updated_summary_snapshots,
                            }
                        )
                    required_text = [
                        expected["selected_id"],
                        *expected["visible_id_subset"],
                        "Net revenue",
                        "Audience growth",
                        "Review backlog",
                        "Sponsorship risk review",
                        "Mina Park",
                        "video",
                        "watch",
                        "18420",
                        "12",
                    ]
                    missing_text = _missing_visible_text(body_text, required_text)

                    search.fill("", timeout=5000)
                    _select_option_by_label(page, "Channel cohort", "all")
                    page.wait_for_timeout(250)
                    reset_text = page.locator("body").inner_text(timeout=5000)
                    missing_text.extend(
                        f"after_clear:{token}"
                        for token in _missing_visible_text(
                            reset_text, expected["after_clearing_search_subset"]
                        )
                    )

                    _click_record_id(page, expected["detail_switch_id"])
                    controls_used.append(expected["detail_switch_id"])
                    page.wait_for_timeout(250)
                    switched_text = page.locator("body").inner_text(timeout=5000)
                    missing_text.extend(
                        f"detail_switch:{token}"
                        for token in _missing_visible_text(
                            switched_text, expected["detail_switch_tokens"]
                        )
                    )

                    toggle_path = _enable_review_queue_only(page)
                    controls_used.append(f"Review queue only ({toggle_path})")
                    page.wait_for_timeout(250)
                    review_text, review_source = _region_text(
                        page,
                        "Risk queue|Review queue|campaign list|visible campaigns",
                        expected["review_queue_subset"],
                    )
                    missing_text.extend(
                        f"review_queue:{token}"
                        for token in _missing_visible_text(
                            review_text, expected["review_queue_subset"]
                        )
                    )
                    leaked_forbidden = [
                        token
                        for token in expected["review_queue_forbidden"]
                        if _exact_token_present(review_text, token)
                    ]
                    if leaked_forbidden:
                        behavior_problems.append(
                            {
                                "check": "review_queue_hides_clear_records",
                                "source": review_source,
                                "forbidden_visible": leaked_forbidden,
                            }
                        )

                    mobile = browser.new_page(viewport=expected["mobile_viewport"])
                    try:
                        mobile.goto(url, wait_until="networkidle", timeout=10000)
                        sane, problems = _control_sanity(
                            mobile,
                            ["Channel cohort", "Creator search", "Forecast mode", "Sponsor pressure"],
                        )
                        if not sane:
                            layout_problems.extend({"viewport": "mobile", **problem} for problem in problems)
                        _select_option_by_label(mobile, "Channel cohort", "video")
                        _first(mobile.get_by_label(re.compile("Creator search", re.IGNORECASE))).fill("Studio", timeout=5000)
                        _click_record_id(mobile, "CMP-017")
                    finally:
                        mobile.close()

                    return not missing_text and not layout_problems and not behavior_problems, {
                        "browser_check": "completed",
                        "url": url,
                        "controls_used": controls_used,
                        "missing_visible_text": missing_text,
                        "layout_problems": layout_problems,
                        "behavior_problems": behavior_problems,
                    }
                finally:
                    browser.close()
    except (PlaywrightTimeoutError, PlaywrightError, OSError) as exc:
        return False, {
            "browser_check": "failed",
            "controls_used": controls_used,
            "missing_visible_text": missing_text,
            "layout_problems": layout_problems,
            "behavior_problems": behavior_problems,
            "error": repr(exc),
        }


def _responsive_ok(workspace: Path, text: str) -> tuple[bool, Any]:
    css = _read(workspace / "web/src/index.css")
    css_checks = {
        "responsive_media": "@media" in css and "max-width" in css,
        "focus_state": ":focus-visible" in css,
        "reduced_motion": "prefers-reduced-motion" in css,
        "structured_layout": any(token in css for token in ("grid", "flex")),
    }
    low = text.casefold()
    semantic_controls = all(token in low for token in ("select", "label", "button")) and any(
        token in low for token in ("aria-label", "aria-labelledby", "aria-describedby")
    )
    missing_presentation = _missing_groups(text, GROUND_TRUTH["presentation_groups"])
    ok = all(css_checks.values()) and semantic_controls and not missing_presentation
    return ok, {
        "css": css_checks,
        "semantic_controls": semantic_controls,
        "missing_presentation_groups": missing_presentation,
    }


def _scope_ok(workspace: Path, text: str) -> tuple[bool, Any]:
    inputs_ok, changed = sources_unchanged(TASK, workspace, allowed_modified=ALLOWED_MODIFIED)
    unexpected = []
    seed = TASK / "workspace"
    for path in workspace.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(workspace).as_posix()
        if rel in ALLOWED_MODIFIED:
            continue
        if any(rel.startswith(prefix) for prefix in ALLOWED_CREATED_PREFIXES):
            continue
        if (seed / rel).exists():
            continue
        if rel.startswith("web/node_modules/") or rel.startswith("web/dist/") or rel.startswith("web/."):
            continue
        unexpected.append(rel)

    remote_or_forbidden = bool(REMOTE_OR_FORBIDDEN.search(text))
    action_claims = explicit_external_action_claims(text)
    return inputs_ok and not unexpected and not remote_or_forbidden and not action_claims, {
        "changed_inputs": changed,
        "unexpected_files": unexpected[:20],
        "remote_or_forbidden": remote_or_forbidden,
        "execution_claims": action_claims,
    }


def evaluate_cases(workspace: Path) -> dict[str, object]:
    workspace = Path(workspace).resolve()
    text = _project_text(workspace)
    files_ok = _required_files_ok(workspace)
    package_ok, package_detail = (
        _package_ok(workspace, text)
        if files_ok
        else (False, "required project files are missing or too small")
    )
    records_ok, records_detail = _records_ok(workspace)
    domain_ok, domain_detail = _domain_grounding_ok(text)
    interaction_ok, interaction_detail = _interaction_ok(text)
    browser_ok, browser_detail = _browser_interaction_ok(workspace)
    responsive_ok, responsive_detail = _responsive_ok(workspace, text)
    scope_ok, scope_detail = _scope_ok(workspace, text)

    return {
        "build_and_runtime_integrity": observation(
            files_ok and package_ok,
            package_detail,
        ),
        "creator_revenue_dashboard_protected_local_data": observation(
            records_ok and domain_ok,
            {"records": records_detail, "domain": domain_detail},
        ),
        "creator_revenue_dashboard_dashboard_interaction_model": observation(
            browser_ok,
            {"browser": browser_detail, "static_diagnostic": interaction_detail},
        ),
        "creator_revenue_dashboard_dashboard_responsive_surface": observation(
            responsive_ok,
            responsive_detail,
        ),
        "scope_and_safety_boundary": observation(
            scope_ok,
            scope_detail,
        ),
    }
