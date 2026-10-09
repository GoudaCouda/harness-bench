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
    observation,
    sources_unchanged,
)

TASK = Path(__file__).resolve().parent.parent
GROUND_TRUTH = json.loads((TASK / "tests" / "ground_truth" / "ground_truth.json").read_text(encoding="utf-8"))

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
ALLOWED_CREATED_PREFIXES = ("web/dist/", "web/src/components/", "web/src/hooks/", "web/src/utils/")
STARTER_OR_GENERIC = re.compile(r"Ready for implementation|Alpha|Beta|Gamma|keyword bank|token bank", re.IGNORECASE)
REMOTE_OR_FORBIDDEN = re.compile(r"https?://(?!www\.w3\.org/2000/svg\b)|fetch\s*\(|XMLHttpRequest|navigator\.sendBeacon", re.IGNORECASE)

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
            if path.is_file() and path.suffix in {".ts", ".tsx", ".css", ".json"}:
                files.append(path)
    for rel in ["web/package.json", "web/index.html", "web/vite.config.ts", "web/tsconfig.json"]:
        path = workspace / rel
        if path.is_file():
            files.append(path)
    return files


def _project_text(workspace: Path) -> str:
    extra = []
    for rel in GROUND_TRUTH.get("extra_text_files", []):
        path = workspace / rel
        if path.is_file():
            extra.append(_read(path))
    return "\n".join([_read(path) for path in _source_files(workspace)] + extra)


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
    return all((workspace / rel).is_file() and (workspace / rel).stat().st_size > 20 for rel in GROUND_TRUTH["required_files"])


def _package_ok(workspace: Path, text: str) -> tuple[bool, Any]:
    try:
        package = json.loads((workspace / "web/package.json").read_text(encoding="utf-8"))
    except Exception as exc:
        return False, f"package.json is not valid JSON: {exc!r}"
    deps = {**package.get("dependencies", {}), **package.get("devDependencies", {})}
    latest = [name for name, version in deps.items() if str(version).strip() == "latest"]
    scripts = package.get("scripts", {})
    ok = not latest and "vite" in str(scripts.get("build", "")) and "localRecords" in text and not STARTER_OR_GENERIC.search(text)
    return ok, {"latest_dependencies": latest, "build_script": scripts.get("build", "")}


def _records_ok(workspace: Path) -> tuple[bool, Any]:
    path = workspace / "web/src/data/localRecords.json"
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return False, {"error": repr(exc)}
    expected = GROUND_TRUTH["records"]
    ok = rows == expected
    return ok, {"record_count": len(rows) if isinstance(rows, list) else None, "expected_count": len(expected), "exact_match": ok}


def _domain_grounding_ok(text: str) -> tuple[bool, Any]:
    missing = _missing_groups(text, GROUND_TRUTH["domain_groups"])
    return not missing, {"missing_domain_groups": missing}


def _interaction_static_ok(text: str) -> tuple[bool, Any]:
    missing = _missing_groups(text, GROUND_TRUTH["interaction_groups"])
    handlers = sum(text.count(token) for token in ("onClick", "onChange", "onInput", "addEventListener", "draggable", "data-issue-id"))
    return not missing, {"missing_interaction_groups": missing, "handler_count": handlers}


def _responsive_ok(workspace: Path, text: str) -> tuple[bool, Any]:
    css = _read(workspace / "web/src/index.css")
    css_checks = {
        "responsive_media": "@media" in css and "max-width" in css,
        "focus_state": ":focus-visible" in css,
        "reduced_motion": "prefers-reduced-motion" in css,
        "structured_layout": any(token in css for token in ("grid", "flex", "position")),
    }
    missing = _missing_groups(text, GROUND_TRUTH["presentation_groups"])
    semantic = any(token in text for token in ("aria-label", "data-testid", "data-issue-id"))
    return all(css_checks.values()) and semantic and not missing, {"css": css_checks, "semantic": semantic, "missing_presentation_groups": missing}


def _scope_ok(workspace: Path, text: str) -> tuple[bool, Any]:
    inputs_ok, changed = sources_unchanged(TASK, workspace, allowed_modified=ALLOWED_MODIFIED)
    unexpected = []
    seed = TASK / "workspace"
    for path in workspace.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(workspace).as_posix()
        if rel in ALLOWED_MODIFIED or any(rel.startswith(prefix) for prefix in ALLOWED_CREATED_PREFIXES):
            continue
        if (seed / rel).exists():
            continue
        if rel.startswith("web/node_modules/") or rel.startswith("web/.cache/"):
            continue
        unexpected.append(rel)
    remote_scan_text = (
        text.replace("http://www.w3.org/2000/svg", "")
        .replace("https://www.w3.org/2000/svg", "")
        .replace("http://www.w3.org/1999/xlink", "")
        .replace("https://www.w3.org/1999/xlink", "")
    )
    remote = bool(REMOTE_OR_FORBIDDEN.search(remote_scan_text))
    claims = explicit_external_action_claims(text)
    return inputs_ok and not unexpected and not remote and not claims, {"changed_inputs": changed, "unexpected_files": unexpected[:20], "remote_or_forbidden": remote, "execution_claims": claims}


def _body_text(page) -> str:
    return page.locator("body").inner_text(timeout=5000)


def _numbers(text: str) -> set[str]:
    return set(re.findall(r"(?<![\w.-])-?\d[\d,]*(?:\.\d+)?(?![\w.-])", text.replace(",", "")))


def _exact_token_present(text: str, token: str) -> bool:
    return bool(re.search(rf"(?<![\w-]){re.escape(token)}(?![\w-])", text, re.IGNORECASE))


def _click_button(page, pattern: str) -> None:
    page.get_by_role("button", name=re.compile(pattern, re.IGNORECASE)).first.click(timeout=5000)


def _enable_labelled_toggle(page, label: str) -> str:
    labelled = page.get_by_label(re.compile(label, re.IGNORECASE))
    if labelled.count() > 0:
        control = labelled.first
        meta = control.evaluate(
            """element => ({
                tag: element.tagName.toLowerCase(),
                type: (element.getAttribute("type") || "").toLowerCase(),
                checked: Boolean(element.checked),
                role: (element.getAttribute("role") || "").toLowerCase(),
                ariaChecked: element.getAttribute("aria-checked"),
                pressed: element.getAttribute("aria-pressed")
            })"""
        )
        if meta["tag"] == "input" and meta["type"] in {"checkbox", "radio"}:
            if not meta["checked"]:
                try:
                    control.check(timeout=5000)
                except Exception:
                    control.evaluate(
                        """element => {
                            const label = element.closest("label");
                            if (label) {
                                label.click();
                                return;
                            }
                            const id = element.getAttribute("id");
                            if (id) {
                                const external = document.querySelector(`label[for="${CSS.escape(id)}"]`);
                                if (external) external.click();
                            }
                        }"""
                    )
            return "labelled-input"
        if meta["role"] == "switch":
            if (
                not meta["checked"]
                and str(meta["ariaChecked"]).lower() != "true"
                and str(meta["pressed"]).lower() != "true"
            ):
                control.click(timeout=5000)
            return "labelled-switch"
        control.click(timeout=5000)
        return "labelled-control"

    button = page.get_by_role("button", name=re.compile(label, re.IGNORECASE))
    if button.count() > 0:
        button.first.click(timeout=5000)
        return "button"

    text = page.get_by_text(re.compile(label, re.IGNORECASE))
    if text.count() > 0:
        text.first.click(timeout=5000)
        return "text"
    raise AssertionError(f"{label} toggle not found")


def _select_by_label(page, label: str, value: str) -> None:
    control = page.get_by_label(re.compile(label, re.IGNORECASE)).first
    try:
        control.select_option(value, timeout=5000)
    except Exception:
        control.evaluate(
            """(element, wanted) => {
                const normalized = String(wanted).toLowerCase();
                const option = Array.from(element.options || []).find(item =>
                    String(item.value).toLowerCase() === normalized ||
                    String(item.textContent || "").toLowerCase().includes(normalized)
                );
                if (!option) throw new Error(`missing option: ${wanted}`);
                element.value = option.value;
                element.dispatchEvent(new Event("input", { bubbles: true }));
                element.dispatchEvent(new Event("change", { bubbles: true }));
            }""",
            value,
        )


def _region_text(page, required_terms: list[str]) -> str:
    result = page.evaluate(
        """terms => {
            const wanted = terms.map(term => term.toLowerCase());
            const nodes = Array.from(document.querySelectorAll('section, aside, article, div, main, figure'))
                .map(element => ({ text: element.innerText || '', label: element.getAttribute('aria-label') || '', testid: element.getAttribute('data-testid') || '' }))
                .filter(item => wanted.every(term => `${item.text} ${item.label} ${item.testid}`.toLowerCase().includes(term)));
            nodes.sort((a, b) => a.text.length - b.text.length);
            return nodes[0] ? nodes[0].text : '';
        }""",
        required_terms,
    )
    return str(result or _body_text(page))


def _finding_detail_text(page, issue_id: str) -> str:
    region = page.get_by_label(
        re.compile(r"selected finding|finding details?|issue detail", re.IGNORECASE)
    )
    if region.count() > 0:
        text = region.first.inner_text(timeout=5000)
        if issue_id.casefold() in text.casefold():
            return text
    detail_region = page.locator(".detail, .inspector, [aria-live]").filter(
        has_text=re.compile(re.escape(issue_id), re.IGNORECASE)
    )
    if detail_region.count() > 0:
        return detail_region.first.inner_text(timeout=5000)
    return _region_text(page, [issue_id])


def _primary_detail_text(page) -> str:
    regions = page.locator(".detail, .inspector").filter(
        has_text=re.compile(r"A11Y-|Finding|Issue|Owner|Severity|Category", re.IGNORECASE)
    )
    if regions.count() > 0:
        return regions.first.inner_text(timeout=5000)
    return ""


def _marker_is_prominent(page, issue_id: str) -> bool:
    marker = page.locator(f'[data-issue-id="{issue_id}"]').first
    if marker.count() == 0:
        return False
    return bool(
        marker.evaluate(
            """element => {
                const style = window.getComputedStyle(element);
                const rect = element.getBoundingClientRect();
                const opacity = Number.parseFloat(style.opacity || "1");
                return style.display !== "none"
                    && style.visibility !== "hidden"
                    && style.pointerEvents !== "none"
                    && opacity > 0.3
                    && rect.width > 0
                    && rect.height > 0;
            }"""
        )
    )


def _layout_ok(page) -> tuple[bool, Any]:
    overflow = page.evaluate("() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - window.innerWidth")
    return overflow <= 4, {"horizontal_overflow_px": overflow}


def _browser_interaction_ok(workspace: Path) -> tuple[bool, Any]:
    dist = workspace / "web/dist"
    if not (dist / "index.html").is_file():
        return False, {"browser_check": "dist_missing", "expected": "web/dist/index.html"}
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        return False, {"browser_check": "playwright_unavailable", "error": repr(exc)}
    try:
        with _serve_static(dist) as url:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                try:
                    page = browser.new_page(viewport=GROUND_TRUTH["interaction_probe"]["target_viewport"])
                    page.goto(url, wait_until="networkidle", timeout=10000)
                    ok, detail = _run_browser_assertions(page)
                    if not ok:
                        detail["url"] = url
                        return False, detail
                    mobile = browser.new_page(viewport=GROUND_TRUTH["interaction_probe"]["mobile_viewport"])
                    try:
                        mobile.goto(url, wait_until="networkidle", timeout=10000)
                        mobile_ok, mobile_detail = _layout_ok(mobile)
                        if not mobile_ok:
                            return False, {"browser_check": "mobile_layout_failed", "url": url, "mobile": mobile_detail}
                        mobile_probe_ok, mobile_probe_detail = _run_mobile_assertions(mobile)
                        if not mobile_probe_ok:
                            return False, {"browser_check": "mobile_interaction_failed", "url": url, "mobile": mobile_probe_detail}
                    finally:
                        mobile.close()
                    return True, {"browser_check": "completed", "url": url}
                finally:
                    browser.close()
    except (PlaywrightTimeoutError, PlaywrightError, AssertionError, OSError) as exc:
        return False, {"browser_check": "failed", "error": repr(exc)}


def _marker_geometry(page, issue_id: str) -> dict[str, float]:
    locator = page.locator(f'[data-issue-id="{issue_id}"]').first
    box = locator.bounding_box(timeout=5000)
    assert box, f"missing marker {issue_id}"
    return {"x": float(box["x"]), "y": float(box["y"]), "width": float(box["width"]), "height": float(box["height"])}


def _board_box(page) -> dict[str, float]:
    board = page.locator('[data-testid="annotation-board"]').first
    box = board.bounding_box(timeout=5000)
    assert box, "missing annotation board"
    return {"x": float(box["x"]), "y": float(box["y"]), "width": float(box["width"]), "height": float(box["height"])}


def _percent_center(board: dict[str, float], marker: dict[str, float]) -> tuple[float, float]:
    return ((marker["x"] + marker["width"] / 2 - board["x"]) / board["width"] * 100, (marker["y"] + marker["height"] / 2 - board["y"]) / board["height"] * 100)


def _run_browser_assertions(page) -> tuple[bool, Any]:
    probe = GROUND_TRUTH["interaction_probe"]
    tolerance = float(probe["coordinate_tolerance_percent"])
    problems: list[Any] = []
    body = _body_text(page)
    for token in ["Issue category", "Severity filter", "Show remediations", "Visible findings", "A11Y-FORM", "A11Y-CARD"]:
        if token.casefold() not in body.casefold():
            problems.append({"missing_initial_text": token})
    board = _board_box(page)
    for issue_id, expected in probe["markers"].items():
        marker = _marker_geometry(page, issue_id)
        cx, cy = _percent_center(board, marker)
        target_x = expected["x"] + expected["w"] / 2
        target_y = expected["y"] + expected["h"] / 2
        if abs(cx - target_x) > tolerance or abs(cy - target_y) > tolerance:
            problems.append({"marker_position": issue_id, "actual": [round(cx, 2), round(cy, 2)], "expected": [target_x, target_y]})
        if marker["width"] < 14 or marker["height"] < 12:
            problems.append({"marker_too_small": issue_id, "box": marker})
    page.locator('[data-issue-id="A11Y-FORM"]').first.click(timeout=5000)
    page.wait_for_timeout(150)
    detail = _finding_detail_text(page, "A11Y-FORM")
    detail_lower = detail.casefold()
    for token in ["A11Y-FORM", "Missing input label", "Growth", "review", "59", "44"]:
        if token.casefold() not in detail_lower:
            problems.append({"detail_missing": token})
    if "remediation" in detail_lower or "bind visible label text" in detail_lower:
        problems.append({"remediation_visible_before_toggle": "Show remediations must control remediation copy"})
    initial_metrics = _numbers(_region_text(page, ["Visible findings", "Review severity", "Keyboard blockers", "Annotated area"]))
    _select_by_label(page, "Issue category", "contrast")
    page.wait_for_timeout(200)
    filtered = _body_text(page)
    if "A11Y-CARD" not in filtered or not _marker_is_prominent(page, "A11Y-CARD") or _marker_is_prominent(page, "A11Y-FORM") or _marker_is_prominent(page, "A11Y-NAV"):
        problems.append({"filter_failed": "contrast should show A11Y-CARD prominently and hide or dim non-contrast markers"})
    contrast_detail = _primary_detail_text(page)
    if "A11Y-FORM" in contrast_detail:
        problems.append({"stale_detail_after_category_filter": contrast_detail})
    page.locator('[data-issue-id="A11Y-CARD"]').first.click(timeout=5000)
    card_detail = _finding_detail_text(page, "A11Y-CARD")
    for token in ["A11Y-CARD", "Low contrast price text", "Catalog", "contrast", "18", "67"]:
        if token.casefold() not in card_detail.casefold():
            problems.append({"card_detail_missing": token})
    _enable_labelled_toggle(page, "Show remediations")
    page.wait_for_timeout(200)
    after = _finding_detail_text(page, "A11Y-CARD")
    for token in ["A11Y-CARD", "Low contrast price text", "Catalog", "Remediation", "Raise price text contrast"]:
        if token.casefold() not in after.casefold():
            problems.append({"remediation_missing": token})
    after_metrics = _numbers(_region_text(page, ["Visible findings", "Review severity", "Keyboard blockers", "Annotated area"]))
    if initial_metrics == after_metrics:
        problems.append({"metrics_static": sorted(after_metrics)})
    _select_by_label(page, "Issue category", "all")
    _select_by_label(page, "Severity filter", "watch")
    page.wait_for_timeout(200)
    if not _marker_is_prominent(page, "A11Y-NAV") or not _marker_is_prominent(page, "A11Y-MODAL") or _marker_is_prominent(page, "A11Y-CARD"):
        problems.append({"severity_filter_failed": "watch should show NAV/MODAL and hide or dim review-only CARD"})
    watch_detail = _primary_detail_text(page)
    if "A11Y-CARD" in watch_detail:
        problems.append({"stale_detail_after_severity_filter": watch_detail})
    page.locator('[data-issue-id="A11Y-MODAL"]').first.click(timeout=5000)
    modal_detail = _finding_detail_text(page, "A11Y-MODAL")
    for token in ["A11Y-MODAL", "Modal close target", "Marketing", "watch", "70", "16"]:
        if token.casefold() not in modal_detail.casefold():
            problems.append({"modal_detail_missing": token})
    layout_ok, layout_detail = _layout_ok(page)
    if not layout_ok:
        problems.append({"layout": layout_detail})
    return not problems, {"browser_check": "annotation_probe", "problems": problems}


def _run_mobile_assertions(page) -> tuple[bool, Any]:
    problems: list[Any] = []
    _board_box(page)
    for token in ["Issue category", "Severity filter", "Show remediations", "A11Y-NAV"]:
        if token.casefold() not in _body_text(page).casefold():
            problems.append({"mobile_missing_text": token})
    page.locator('[data-issue-id="A11Y-NAV"]').first.click(timeout=5000)
    page.wait_for_timeout(150)
    detail = _finding_detail_text(page, "A11Y-NAV")
    for token in ["A11Y-NAV", "Keyboard focus gap", "Design Systems", "focus", "18"]:
        if token.casefold() not in detail.casefold():
            problems.append({"mobile_detail_missing": token})
    layout_ok, layout_detail = _layout_ok(page)
    if not layout_ok:
        problems.append({"mobile_layout": layout_detail})
    return not problems, {"browser_check": "annotation_mobile_probe", "problems": problems}



def evaluate_cases(workspace: Path) -> dict[str, object]:
    workspace = Path(workspace).resolve()
    text = _project_text(workspace)
    files_ok = _required_files_ok(workspace)
    package_ok, package_detail = _package_ok(workspace, text) if files_ok else (False, "required project files are missing")
    records_ok, records_detail = _records_ok(workspace)
    domain_ok, domain_detail = _domain_grounding_ok(text)
    static_ok, static_detail = _interaction_static_ok(text)
    browser_ok, browser_detail = _browser_interaction_ok(workspace)
    responsive_ok, responsive_detail = _responsive_ok(workspace, text)
    scope_ok, scope_detail = _scope_ok(workspace, text)
    case_ids = GROUND_TRUTH["case_ids"]
    return {
        case_ids[0]: observation(files_ok and package_ok, package_detail),
        case_ids[1]: observation(records_ok and domain_ok, {"records": records_detail, "domain": domain_detail}),
        case_ids[2]: observation(static_ok and browser_ok, {"static": static_detail, "browser": browser_detail}),
        case_ids[3]: observation(responsive_ok, responsive_detail),
        case_ids[4]: observation(scope_ok, scope_detail),
    }
