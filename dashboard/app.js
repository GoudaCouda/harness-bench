const $ = (id) => document.getElementById(id);
let state = window.HARNESSBENCH_SUMMARY || null;

const labels = {
  not_selected: "Not assigned", queued: "Queued", running: "Running", completed: "Completed",
  protocol_error: "Tool protocol error", model_error: "Model error", timeout: "Timeout",
  infrastructure_error: "Infrastructure error"
};
const terminalStatuses = new Set([
  "completed", "protocol_error", "model_error", "timeout", "infrastructure_error"
]);
// Keep this in lock-step with tools/run_benchmark.py:SCOREABLE_STATUSES.
const scoreableStatuses = new Set([
  "completed", "protocol_error", "model_error", "timeout"
]);
const fmtScore = (x) => typeof x === "number" ? (x * 100).toFixed(1) : "—";
const fmtPass = (x) => x === true ? "PASS" : x === false ? "FAIL" : "—";
const countOrNull = (x) => Number.isInteger(x) && x >= 0 ? x : null;
const escapeHtml = (value) => String(value ?? "").replace(
  /[&<>"']/g,
  char => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"}[char])
);
const fmtDuration = (seconds) => {
  if (typeof seconds !== "number") return "—";
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const h = Math.floor(seconds / 3600);
  const m = Math.round((seconds % 3600) / 60);
  return h ? `${h}h ${m}m` : `${m}m`;
};
const scoreClass = (x) => typeof x !== "number"
  ? "unscored"
  : x >= .75 ? "high" : x >= .4 ? "mid" : "low";
const difficultyOf = (task) => task.difficulty || "(unspecified)";

function groupSummary(rows) {
  const selected = rows.filter(x => x.status !== "not_selected");
  const scoreable = selected.filter(x => scoreableStatuses.has(x.status));
  const scored = scoreable.filter(x => typeof x.outcome_score === "number");
  return {
    selected,
    scored,
    safetyEvaluated: scoreable.length,
    safetyFailed: scoreable.filter(x => x.safety_gate_failed === true).length,
    mean: scored.length
      ? scored.reduce((total, task) => total + task.outcome_score, 0) / scored.length
      : null,
    finished: selected.filter(x => terminalStatuses.has(x.status)).length
  };
}

function renderDomains(tasks) {
  const groups = new Map();
  for (const task of tasks) {
    const domain = task.domain || "(unspecified)";
    if (!groups.has(domain)) groups.set(domain, []);
    groups.get(domain).push(task);
  }
  $("domains").innerHTML = [...groups.entries()].map(([domain, rows]) => {
    const {selected, scored, mean, finished, safetyFailed} = groupSummary(rows);
    return `<article class="domain">
      <div class="domain-top"><strong>${escapeHtml(domain)}</strong><b>${fmtScore(mean)}</b></div>
      <p>${finished}/${selected.length} finished · ${scored.length} scored · ${safetyFailed} gate fail</p>
      <div class="mini-track"><i style="width:${selected.length ? finished / selected.length * 100 : 0}%"></i></div>
    </article>`;
  }).join("");

  const current = $("domainFilter").value;
  const options = [...groups.keys()].sort();
  $("domainFilter").innerHTML = `<option value="">All domains</option>` +
    options.map(x => `<option ${x === current ? "selected" : ""}>${escapeHtml(x)}</option>`).join("");
}

function renderDifficulties(tasks) {
  const groups = new Map([
    ["easy", []],
    ["medium", []],
    ["hard", []]
  ]);
  for (const task of tasks) {
    const difficulty = difficultyOf(task);
    if (!groups.has(difficulty)) groups.set(difficulty, []);
    groups.get(difficulty).push(task);
  }
  $("difficulties").innerHTML = [...groups.entries()].map(([difficulty, rows]) => {
    const {selected, scored, mean, finished, safetyFailed} = groupSummary(rows);
    return `<article class="difficulty">
      <div class="difficulty-top"><strong>${escapeHtml(difficulty)}</strong><b>${fmtScore(mean)}</b></div>
      <p>${selected.length} selected · ${finished} finished · ${scored.length} scored · ${safetyFailed} gate fail</p>
      <div class="mini-track"><i style="width:${selected.length ? finished / selected.length * 100 : 0}%"></i></div>
    </article>`;
  }).join("");

  const current = $("difficultyFilter").value;
  $("difficultyFilter").innerHTML = `<option value="">All difficulties</option>` +
    [...groups.keys()].map(difficulty =>
      `<option value="${escapeHtml(difficulty)}" ${difficulty === current ? "selected" : ""}>${escapeHtml(difficulty)}</option>`
    ).join("");
}

function renderRows() {
  const query = $("search").value.trim().toLowerCase();
  const domain = $("domainFilter").value;
  const difficulty = $("difficultyFilter").value;
  const status = $("statusFilter").value;
  const reviewOnly = $("reviewOnly").checked;
  const rows = state.tasks.filter(task => {
    const text = `${task.task_id} ${task.title}`.toLowerCase();
    return (!query || text.includes(query)) &&
      (!domain || task.domain === domain) &&
      (!difficulty || difficultyOf(task) === difficulty) &&
      (!status || task.status === status) &&
      (!reviewOnly || task.review_flag);
  });
  $("taskRows").innerHTML = rows.length ? rows.map(task => {
    const artifact = task.required_artifacts;
    const artifactText = artifact
      ? `${artifact.present?.length || 0}/${artifact.declared?.length || 0}`
      : "—";
    const safetyScoreable = scoreableStatuses.has(task.status);
    const failedGates = countOrNull(task.failed_gate_count) ?? 0;
    const failedCore = countOrNull(task.failed_core_count) ?? 0;
    const safetyText = safetyScoreable
      ? `${task.safety_gate_failed === true ? `${failedGates} GATE FAIL` : "0 gate"}<span class="meta">${failedCore} core</span>`
      : "—";
    return `<tr>
      <td class="task-title"><b>${escapeHtml(task.task_id)}</b><span>${escapeHtml(task.title)}</span></td>
      <td><b>${escapeHtml(task.domain || "(unspecified)")}</b><br><span class="meta">${escapeHtml(task.difficulty || "(unspecified)")}</span></td>
      <td><span class="pill ${escapeHtml(task.status)}">${escapeHtml(labels[task.status] || task.status)}</span></td>
      <td><span class="score ${scoreClass(task.outcome_score)}">${fmtScore(task.outcome_score)}</span></td>
      <td><span class="pass ${task.task_success === true ? "yes" : task.task_success === false ? "no" : "unknown"}">${fmtPass(task.task_success)}</span></td>
      <td><span class="safety ${task.safety_gate_failed === true ? "failed" : "clear"}">${safetyText}</span></td>
      <td>${artifactText}</td>
      <td>${task.tool_calls ?? "—"}<span class="meta">${task.tool_failures ? ` / ${task.tool_failures} fail` : ""}</span></td>
      <td>${fmtDuration(task.elapsed_sec)}</td>
      <td class="flag">${escapeHtml(task.review_flag || "—")}</td>
    </tr>`;
  }).join("") : `<tr><td class="empty" colspan="10">No tasks match the current filters</td></tr>`;
}

function render(data) {
  state = data;
  const tasks = Array.isArray(data.tasks) ? data.tasks : [];
  const selectedCount = countOrNull(data.selected_count);
  const suiteSize = countOrNull(data.suite_size);
  const inferredSelected = tasks.filter(task => task.status !== "not_selected").length;
  const total = selectedCount ?? suiteSize ?? inferredSelected;
  const done = countOrNull(data.completed_count) ?? 0;
  const suite = data.suite || "unversioned";
  const benchmark = data.benchmark || "HarnessBench";
  const historical = suite !== "main";
  const isolation = data.isolation && typeof data.isolation === "object"
    ? data.isolation
    : null;
  const isolationLevel = isolation?.level || null;
  const progress = typeof data.progress === "number"
    ? data.progress
    : total ? done / total : 0;

  document.title = `${benchmark} · ${historical ? "Historical " : ""}${suite}`;
  $("suiteTitle").textContent = historical ? `${benchmark} Historical` : `${benchmark} Main`;
  $("runIdentity").textContent = [
    data.model,
    data.harness,
    data.grading ? String(data.grading).replaceAll("_", " ") : null
  ].filter(Boolean).join(" × ") || "Run metadata unavailable";
  $("snapshotNotice").hidden = !historical;
  $("snapshotCopy").textContent = historical
    ? `suite=${suite}, suite_size=${suiteSize ?? "unknown"}; this result is a historical record and not part of the current main suite.`
    : "";
  $("isolationNotice").hidden = !isolationLevel;
  $("isolationTitle").textContent = isolationLevel
    ? `Isolation level ${isolationLevel}`
    : "Isolation";
  $("isolationCopy").textContent = isolationLevel
    ? [
      `${isolation.engine || "OCI"} ${isolation.server_version || "unknown"}`,
      isolation.rootless ? "rootless" : "rootful",
      isolation.default_runtime || "runtime unknown",
      isolation.network_policy || null
    ].filter(Boolean).join(" · ")
    : "";
  $("progressText").textContent = `${done} / ${total}`;
  $("progressBar").style.width = `${Math.max(0, Math.min(1, progress)) * 100}%`;
  $("completed").textContent = done;
  $("completedScope").textContent = selectedCount !== null
    ? `of ${selectedCount} selected tasks`
    : `of ${suiteSize ?? total} suite tasks`;
  $("meanScore").textContent = fmtScore(data.mean_oracle_completed);
  $("passRate").textContent = fmtScore(data.pass_rate_completed);
  const strictEvaluated = countOrNull(data.strict_pass_evaluated_count);
  const strictPassed = countOrNull(data.strict_passed_count);
  $("strictPassScope").textContent = strictEvaluated === null
    ? "new-protocol results only"
    : `${strictPassed ?? 0} / ${strictEvaluated} new-protocol results`;
  const scoreableTasks = tasks.filter(task => scoreableStatuses.has(task.status));
  const safetyEvaluated = countOrNull(data.safety_gate_evaluated_count)
    ?? scoreableTasks.length;
  const safetyFailed = countOrNull(data.safety_gate_failed_count)
    ?? scoreableTasks.filter(task => task.safety_gate_failed === true).length;
  const failedCore = countOrNull(data.failed_core_total)
    ?? scoreableTasks.reduce(
      (total, task) => total + (countOrNull(task.failed_core_count) ?? 0),
      0
    );
  const safetyRate = typeof data.safety_gate_failure_rate === "number"
    ? data.safety_gate_failure_rate
    : safetyEvaluated ? safetyFailed / safetyEvaluated : null;
  $("safetyGateRate").textContent = fmtScore(safetyRate);
  $("safetyGateScope").textContent = `${safetyFailed} / ${safetyEvaluated} scoreable · ${failedCore} core`;
  $("headlineScore").textContent = fmtScore(data.headline_oracle_score);
  $("headlineScope").textContent = selectedCount !== null && suiteSize !== null && selectedCount !== suiteSize
    ? `selection ${selectedCount} / suite ${suiteSize}`
    : `available when ${total} tasks finish`;
  $("reviewCount").textContent = tasks.filter(x => x.review_flag).length;
  $("eta").textContent = fmtDuration(data.eta_sec);
  $("updatedAt").textContent = typeof data.updated_epoch === "number"
    ? `updated ${new Date(data.updated_epoch * 1000).toLocaleTimeString()}`
    : "Update time unavailable";
  $("runId").textContent = data.run_id || "run id unavailable";
  $("suiteMeta").textContent = [
    historical ? "historical snapshot" : "current release",
    `suite ${suite}`,
    `${suiteSize ?? "unknown"} tasks`,
    isolationLevel ? `isolation ${isolationLevel}` : null
  ].filter(Boolean).join(" · ");
  const running = data.counts?.running || 0;
  $("runState").textContent = total > 0 && done === total ? "Run complete" : `${running} workers active`;
  renderDomains(tasks);
  renderDifficulties(tasks);
  renderRows();
}

async function refresh() {
  try {
    const response = await fetch(`../summary.json?t=${Date.now()}`, {cache: "no-store"});
    if (!response.ok) throw new Error(`${response.status}`);
    render(await response.json());
    document.querySelector(".live").classList.remove("error");
  } catch (error) {
    if (!state) {
      $("runState").textContent = "Data connection lost";
      document.querySelector(".live").classList.add("error");
    }
  }
}

["search", "domainFilter", "difficultyFilter", "statusFilter", "reviewOnly"].forEach(id => {
  $(id).addEventListener("input", () => state && renderRows());
});
if (state) render(state);
if (window.location.protocol === "file:") {
  if (!state) {
    $("runState").textContent = "Local summary.js not found";
    document.querySelector(".live").classList.add("error");
  }
} else {
  refresh();
  setInterval(refresh, 5000);
}
