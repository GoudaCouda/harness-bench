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
    remote = bool(REMOTE_OR_FORBIDDEN.search(text))
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


def _select_by_label(page, label: str, value: str) -> None:
    page.get_by_label(re.compile(label, re.IGNORECASE)).first.select_option(value, timeout=5000)


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


def _lane_text(page, lane: str) -> str:
    locator = page.get_by_label(
        re.compile(rf"^{re.escape(lane)}(?: lane)?$", re.IGNORECASE)
    ).first
    return locator.inner_text(timeout=5000)


def _expect_lane_state(page, lane: str, *, present: list[str], absent: list[str], numbers: list[str], problems: list[Any], phase: str) -> str:
    text = _lane_text(page, lane)
    for token in present:
        if not _exact_token_present(text, token):
            problems.append({f"{phase}_lane_missing": {"lane": lane, "token": token}})
    for token in absent:
        if _exact_token_present(text, token):
            problems.append({f"{phase}_lane_unexpected": {"lane": lane, "token": token}})
    found_numbers = _numbers(text)
    for number in numbers:
        if number not in found_numbers:
            problems.append({f"{phase}_lane_number_missing": {"lane": lane, "number": number, "numbers": sorted(found_numbers)}})
    return text


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


def _run_browser_assertions(page) -> tuple[bool, Any]:
    problems: list[Any] = []
    initial_metrics = _numbers(_region_text(page, ["Blocked points", "Review count", "Active WIP", "Last move"]))
    body = _body_text(page)
    for token in ["Backlog", "In Progress", "Review", "Done", "KAN-101", "Move selected to Review", "Undo last move"]:
        if token not in body:
            problems.append({"missing_initial_text": token})
    backlog_before = _lane_text(page, "Backlog")
    review_before = _lane_text(page, "Review")
    if not _exact_token_present(backlog_before, "KAN-101") or _exact_token_present(review_before, "KAN-101"):
        problems.append({"lane_precondition": "KAN-101 should start in Backlog only"})
    _expect_lane_state(page, "Backlog", present=["KAN-101", "KAN-132"], absent=["KAN-108"], numbers=["2", "14"], problems=problems, phase="initial")
    _expect_lane_state(page, "In Progress", present=["KAN-108", "KAN-144"], absent=["KAN-101"], numbers=["2", "9"], problems=problems, phase="initial")
    _expect_lane_state(page, "Review", present=["KAN-117", "KAN-155"], absent=["KAN-101"], numbers=["2", "10"], problems=problems, phase="initial")
    _expect_lane_state(page, "Done", present=["KAN-126", "KAN-166"], absent=["KAN-108"], numbers=["2", "3"], problems=problems, phase="initial")
    _click_button(page, r"KAN-101")
    detail = _region_text(page, ["Selected card", "KAN-101"])
    detail_lower = detail.casefold()
    for token in ["Restore drag fallback", "Kai", "blocked", "Backlog", "8", "3"]:
        if token.casefold() not in detail_lower:
            problems.append({"detail_missing": token})
    _click_button(page, r"move.*review|review.*move")
    page.wait_for_timeout(250)
    review_after = _lane_text(page, "Review")
    backlog_after = _lane_text(page, "Backlog")
    if not _exact_token_present(review_after, "KAN-101"):
        problems.append({"move_failed": "KAN-101 not visible in Review lane"})
    if _exact_token_present(backlog_after, "KAN-101"):
        problems.append({"move_failed": "KAN-101 still visible in Backlog lane"})
    _expect_lane_state(page, "Backlog", present=["KAN-132"], absent=["KAN-101"], numbers=["1", "6"], problems=problems, phase="after_review_move")
    _expect_lane_state(page, "Review", present=["KAN-101", "KAN-117", "KAN-155"], absent=["KAN-108"], numbers=["3", "18"], problems=problems, phase="after_review_move")
    after_metrics = _numbers(_region_text(page, ["Blocked points", "Review count", "Active WIP", "Last move"]))
    if initial_metrics == after_metrics:
        problems.append({"metrics_static": sorted(after_metrics)})
    history_text = _region_text(page, ["Action history", "KAN-101"])
    for token in ["KAN-101", "Backlog", "Review"]:
        if token not in history_text:
            problems.append({"history_missing": token})
    if "review count" not in _body_text(page).casefold():
        problems.append({"missing_after_move": "Review count"})
    _click_button(page, r"undo.*move")
    page.wait_for_timeout(250)
    undo_backlog = _lane_text(page, "Backlog")
    if not _exact_token_present(undo_backlog, "KAN-101"):
        problems.append({"undo_failed": "KAN-101 not restored to Backlog"})
    _expect_lane_state(page, "Backlog", present=["KAN-101", "KAN-132"], absent=["KAN-108"], numbers=["2", "14"], problems=problems, phase="after_undo")
    _click_button(page, r"KAN-108")
    _click_button(page, r"move.*done|done.*move")
    page.wait_for_timeout(250)
    done_text = _lane_text(page, "Done")
    selected = _region_text(page, ["Selected card", "KAN-108"])
    for token in ["KAN-108", "Fix card overflow", "Mira", "Done"]:
        if token not in done_text + "\n" + selected:
            problems.append({"second_move_missing": token})
    _expect_lane_state(page, "In Progress", present=["KAN-144"], absent=["KAN-108"], numbers=["1", "4"], problems=problems, phase="after_done_move")
    _expect_lane_state(page, "Done", present=["KAN-108", "KAN-126", "KAN-166"], absent=["KAN-101"], numbers=["3", "8"], problems=problems, phase="after_done_move")
    second_history = _region_text(page, ["Action history", "KAN-108"])
    for token in ["KAN-108", "In Progress", "Done"]:
        if token.casefold() not in second_history.casefold():
            problems.append({"second_history_missing": token})
    _click_button(page, r"undo.*move")
    page.wait_for_timeout(250)
    _expect_lane_state(page, "In Progress", present=["KAN-108", "KAN-144"], absent=["KAN-101"], numbers=["2", "9"], problems=problems, phase="after_second_undo")
    _expect_lane_state(page, "Done", present=["KAN-126", "KAN-166"], absent=["KAN-108"], numbers=["2", "3"], problems=problems, phase="after_second_undo")
    restored = _region_text(page, ["Selected card", "KAN-108"])
    for token in ["KAN-108", "In Progress"]:
        if token.casefold() not in restored.casefold():
            problems.append({"second_undo_detail_missing": token})
    layout_ok, layout_detail = _layout_ok(page)
    if not layout_ok:
        problems.append({"layout": layout_detail})
    return not problems, {"browser_check": "kanban_probe", "problems": problems}


def _run_mobile_assertions(page) -> tuple[bool, Any]:
    problems: list[Any] = []
    for token in ["KAN-132", "Move selected to Review", "Backlog", "Review"]:
        if token.casefold() not in _body_text(page).casefold():
            problems.append({"mobile_missing_text": token})
    _click_button(page, r"KAN-132")
    _click_button(page, r"move.*review|review.*move")
    page.wait_for_timeout(250)
    review_text = _lane_text(page, "Review")
    backlog_text = _lane_text(page, "Backlog")
    if not _exact_token_present(review_text, "KAN-132"):
        problems.append({"mobile_move_failed": "KAN-132 not visible in Review"})
    if _exact_token_present(backlog_text, "KAN-132"):
        problems.append({"mobile_move_failed": "KAN-132 still visible in Backlog"})
    layout_ok, layout_detail = _layout_ok(page)
    if not layout_ok:
        problems.append({"mobile_layout": layout_detail})
    return not problems, {"browser_check": "kanban_mobile_probe", "problems": problems}



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
