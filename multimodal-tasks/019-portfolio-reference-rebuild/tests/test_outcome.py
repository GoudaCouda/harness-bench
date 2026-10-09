from __future__ import annotations

import contextlib
import json
import re
import socket
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
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
UI = GROUND_TRUTH["ui"]

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
    files: list[Path] = []
    src = workspace / "web" / "src"
    if src.is_dir():
        for path in sorted(src.rglob("*")):
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
    checks = {
        "build_script": "build" in (pkg.get("scripts") or {}),
        "entrypoint": "ReactDOM.createRoot" in _read(workspace / "web/src/main.tsx"),
        "default_export": "export default" in _read(workspace / "web/src/App.tsx"),
        "imports_local_data_from_source": "localrecords.json" in text.casefold(),
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
    expected_categories = {norm(row["category"]) for row in expected.values()}
    schema_ok = (
        len(rows) == len(expected)
        and set(by_id) == set(expected)
        and len(by_id) == len(rows)
        and all(
            isinstance(row.get("name"), str)
            and norm(row.get("category")) in expected_categories
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
        handler_count >= UI["minimum_handlers"]
        and not missing_interactions
        and not missing_calculations
        and record_field_usage
    )
    return ok, {
        "handler_count": handler_count,
        "minimum_handlers": UI["minimum_handlers"],
        "missing_interaction_groups": missing_interactions,
        "missing_calculation_groups": missing_calculations,
        "record_field_usage": record_field_usage,
    }


def _first(locator):
    return locator.first


def _select_option_by_label(page, label: str, value: str) -> None:
    control = _first(page.get_by_label(re.compile(label, re.IGNORECASE)))
    try:
        control.select_option(value, timeout=5000)
    except Exception:
        control.select_option(label=value, timeout=5000)


def _select_option_flexibly(page, label: str, preferred_value: str, fallback_terms: list[str]) -> str:
    control = _first(page.get_by_label(re.compile(label, re.IGNORECASE)))
    try:
        control.select_option(preferred_value, timeout=5000)
        return preferred_value
    except Exception:
        pass
    try:
        control.select_option(label=preferred_value, timeout=5000)
        return preferred_value
    except Exception:
        pass

    options = control.locator("option")
    terms = [term.casefold() for term in fallback_terms]
    fallback_value = ""
    count = options.count()
    for index in range(count):
        option = options.nth(index)
        value = str(option.get_attribute("value") or "")
        text = option.inner_text(timeout=1500)
        haystack = f"{value} {text}".casefold()
        if index > 0 and not fallback_value:
            fallback_value = value or text
        if index > 0 and any(term in haystack for term in terms):
            if value:
                control.select_option(value, timeout=5000)
            else:
                control.select_option(label=text, timeout=5000)
            return value or text
    if fallback_value:
        control.select_option(fallback_value, timeout=5000)
        return fallback_value
    raise AssertionError(f"{label} has no selectable non-default option")


def _select_all_option_by_label(page, label: str) -> str:
    control = _first(page.get_by_label(re.compile(label, re.IGNORECASE)))
    try:
        control.select_option("all", timeout=3000)
        return "all"
    except Exception:
        pass

    options = control.locator("option")
    terms = ["all", "any", "every", "full"]
    count = options.count()
    for index in range(count):
        option = options.nth(index)
        value = str(option.get_attribute("value") or "")
        text = option.inner_text(timeout=1500)
        haystack = f"{value} {text}".casefold()
        if any(term in haystack for term in terms):
            if value:
                control.select_option(value, timeout=5000)
            else:
                control.select_option(label=text, timeout=5000)
            return value or text

    if count > 0:
        first = options.nth(0)
        value = str(first.get_attribute("value") or "")
        text = first.inner_text(timeout=1500)
        if value:
            control.select_option(value, timeout=5000)
        else:
            control.select_option(label=text, timeout=5000)
        return value or text
    raise AssertionError(f"{label} has no selectable all option")


def _set_range_by_label(page, label: str, value: int) -> None:
    control = _first(page.get_by_role("slider", name=re.compile(label, re.IGNORECASE)))
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
        locator = _first(
            page.get_by_role("slider", name=re.compile(label, re.IGNORECASE))
            if label == UI["range_label"]
            else page.get_by_label(re.compile(label, re.IGNORECASE))
        )
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


def _enable_toggle(page) -> str:
    label = re.compile(UI["toggle_regex"], re.IGNORECASE)
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
    raise AssertionError(f"{UI['toggle_label']} control not found")


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
    labels = [UI["filter_label"], UI["search_label"], UI["mode_label"], UI["range_label"]]
    missing_text: list[str] = []
    layout_problems: list[Any] = []
    behavior_problems: list[Any] = []
    controls_used: list[str] = []
    try:
        with _serve_static(dist) as url:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                try:
                    page = browser.new_page(viewport=GROUND_TRUTH["interaction_probe"]["target_viewport"])
                    page.goto(url, wait_until="networkidle", timeout=10000)
                    initial_summary_text, initial_summary_source = _region_text(
                        page,
                        UI["summary_region_regex"],
                        expected["summary_change_labels"],
                    )
                    initial_summary_numbers = _numeric_tokens(initial_summary_text)

                    sane, problems = _control_sanity(page, labels)
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

                    _select_option_by_label(page, UI["filter_label"], expected["category"])
                    controls_used.append(UI["filter_label"])
                    search = _first(page.get_by_label(re.compile(UI["search_label"], re.IGNORECASE)))
                    search.fill(expected["search_value"], timeout=5000)
                    controls_used.append(UI["search_label"])
                    _click_record_id(page, expected["selected_id"])
                    controls_used.append(expected["selected_id"])
                    mode_choice = _select_option_flexibly(
                        page,
                        UI["mode_label"],
                        expected["mode"],
                        UI["mode_fallback_terms"],
                    )
                    controls_used.append(f"{UI['mode_label']} ({mode_choice})")
                    _set_range_by_label(page, UI["range_label"], expected["range_value"])
                    controls_used.append(UI["range_label"])
                    page.wait_for_timeout(250)

                    body_text = page.locator("body").inner_text(timeout=5000)
                    updated_summary_text, updated_summary_source = _region_text(
                        page,
                        UI["summary_region_regex"],
                        expected["summary_change_labels"],
                    )
                    updated_summary_numbers = _numeric_tokens(updated_summary_text)
                    if initial_summary_numbers == updated_summary_numbers:
                        behavior_problems.append(
                            {
                                "check": "summary_numbers_changed_after_controls",
                                "before_source": initial_summary_source,
                                "after_source": updated_summary_source,
                                "numbers": sorted(updated_summary_numbers),
                            }
                        )
                    required_text = [
                        expected["selected_id"],
                        *expected["visible_id_subset"],
                        *expected["summary_change_labels"],
                        *expected["selected_detail_tokens"],
                    ]
                    missing_text = _missing_visible_text(body_text, required_text)

                    search.fill("", timeout=5000)
                    reset_choice = _select_all_option_by_label(page, UI["filter_label"])
                    controls_used.append(f"{UI['filter_label']} reset ({reset_choice})")
                    page.wait_for_timeout(250)
                    reset_text = page.locator("body").inner_text(timeout=5000)
                    missing_text.extend(
                        f"after_clear:{token}"
                        for token in _missing_visible_text(reset_text, expected["after_clearing_search_subset"])
                    )

                    _click_record_id(page, expected["detail_switch_id"])
                    controls_used.append(expected["detail_switch_id"])
                    page.wait_for_timeout(250)
                    switched_text = page.locator("body").inner_text(timeout=5000)
                    missing_text.extend(
                        f"detail_switch:{token}"
                        for token in _missing_visible_text(switched_text, expected["detail_switch_tokens"])
                    )

                    toggle_path = _enable_toggle(page)
                    controls_used.append(f"{UI['toggle_label']} ({toggle_path})")
                    page.wait_for_timeout(250)
                    focus_text, focus_source = _smallest_region_text(page, expected["focus_subset"])
                    missing_text.extend(
                        f"focus_view:{token}"
                        for token in _missing_visible_text(focus_text, expected["focus_subset"])
                    )
                    leaked_forbidden = [
                        token
                        for token in expected["focus_forbidden"]
                        if _exact_token_present(focus_text, token)
                    ]
                    if leaked_forbidden:
                        behavior_problems.append(
                            {
                                "check": "focus_view_hides_clear_records",
                                "source": focus_source,
                                "forbidden_visible": leaked_forbidden,
                            }
                        )

                    mobile = browser.new_page(viewport=expected["mobile_viewport"])
                    try:
                        mobile.goto(url, wait_until="networkidle", timeout=10000)
                        sane, problems = _control_sanity(mobile, labels)
                        if not sane:
                            layout_problems.extend({"viewport": "mobile", **problem} for problem in problems)
                        _select_option_by_label(mobile, UI["filter_label"], expected["category"])
                        _first(mobile.get_by_label(re.compile(UI["search_label"], re.IGNORECASE))).fill(expected["search_value"], timeout=5000)
                        _click_record_id(mobile, expected["selected_id"])
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
    case_ids = GROUND_TRUTH["case_ids"]

    return {
        case_ids[0]: observation(files_ok and package_ok, package_detail),
        case_ids[1]: observation(records_ok and domain_ok, {"records": records_detail, "domain": domain_detail}),
        case_ids[2]: observation(browser_ok, {"browser": browser_detail, "static_diagnostic": interaction_detail}),
        case_ids[3]: observation(responsive_ok, responsive_detail),
        case_ids[4]: observation(scope_ok, scope_detail),
    }
