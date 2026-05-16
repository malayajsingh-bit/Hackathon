/* ═══════════════════════════════════════════════════════════════════════════
   Indiamart PPT Generator — Frontend Logic
   ═══════════════════════════════════════════════════════════════════════════ */

const SLIDE_TYPES = ["title", "executive_summary", "content", "chart",
                     "diagram", "comparison", "ask"];

const AppState = {
  primaryMode: "text",
  profiles: {},
  leaderKey: "",
  gmailConnected: false,
  gmailUserEmail: "",
  gmailEmails: [],
  gmailSelectedIds: new Set(),
  gmailThreadsExpanded: new Set(),
  plan: [],
  slideContents: [],
  jobId: null,
  pollTimer: null,
  outputFilename: "",
  previewPaths: [],
  previewPage: 0,
  previewJobId: null,
};

// ── Init ──────────────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", async () => {
  setupFileDrop();
  setupRadioGroup();
  setupTabs();
  setupButtonHandlers();
  await loadConfig();
  await loadProfiles();
  await checkGmailStatus();
  checkGmailCallback();
});

// ── Config ────────────────────────────────────────────────────────────────────
async function loadConfig() {
  try {
    const r = await fetch("/api/config");
    const d = await r.json();
    if (d.gateway_url) document.getElementById("sb-url").value = d.gateway_url;
    if (d.api_key)     document.getElementById("sb-key").value = d.api_key;
    if (d.model_name)  document.getElementById("sb-model").value = d.model_name;
    updateConfigStatus(d.configured);
  } catch(e) {}
}

document.getElementById("btn-save-config").addEventListener("click", async () => {
  const url   = document.getElementById("sb-url").value.trim();
  const key   = document.getElementById("sb-key").value.trim();
  const model = document.getElementById("sb-model").value.trim();
  if (!url || !key) {
    updateConfigStatus(false);
    return;
  }
  await fetch("/api/config", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({gateway_url: url, api_key: key, model_name: model}),
  });
  updateConfigStatus(true);
});

function updateConfigStatus(ok) {
  const el = document.getElementById("config-status");
  el.classList.remove("hidden", "ok", "warn");
  if (ok) {
    el.textContent = "✅ Gateway configured";
    el.classList.add("ok");
  } else {
    el.textContent = "⚠️ Both URL and API key are required";
    el.classList.add("warn");
  }
}

// ── Profiles ──────────────────────────────────────────────────────────────────
async function loadProfiles() {
  try {
    const r = await fetch("/api/profiles");
    const d = await r.json();
    AppState.profiles = d.profiles || {};
    const sel = document.getElementById("leader-select");
    sel.innerHTML = "";
    for (const [key, p] of Object.entries(AppState.profiles)) {
      const opt = document.createElement("option");
      opt.value = key;
      opt.textContent = `${p.name} (${p.role})`;
      sel.appendChild(opt);
    }
    if (sel.options.length) {
      AppState.leaderKey = sel.value;
      renderProfileCard(AppState.leaderKey);
    }
  } catch(e) {}
}

document.getElementById("leader-select").addEventListener("change", (e) => {
  AppState.leaderKey = e.target.value;
  renderProfileCard(AppState.leaderKey);
});

function renderProfileCard(key) {
  const p = AppState.profiles[key];
  if (!p) return;
  const prefs = p.content_preferences || {};
  const vis   = p.visual_preferences  || {};
  const tone  = p.tone || {};
  document.getElementById("profile-card").innerHTML = `
    <strong>${p.name}</strong> — ${p.role}<br/>
    <div class="profile-meta">
      <span>📊 Max slides: <strong>${prefs.max_slides || "?"}</strong></span>
      <span>📝 Depth: <strong>${prefs.depth || "?"}</strong></span>
      <span>🔤 Min font: <strong>${vis.font_size_minimum || "?"}pt</strong></span>
    </div>
    <div class="profile-meta">
      <span>🎯 Tone: <strong>${tone.language || "?"}</strong></span>
      <span>📈 Prefers: <strong>${vis.prefers_charts_over_tables ? "Charts" : "Tables"}</strong></span>
    </div>`;
}

// ── Radio group (primary source mode) ────────────────────────────────────────
function setupRadioGroup() {
  document.getElementById("primary-radio").addEventListener("click", (e) => {
    const label = e.target.closest(".radio-option");
    if (!label) return;
    const mode = label.dataset.mode;
    if (!mode) return;
    document.querySelectorAll(".radio-option").forEach(l => l.classList.remove("active"));
    label.classList.add("active");
    label.querySelector("input").checked = true;
    showMode(mode);
  });
}

function showMode(mode) {
  AppState.primaryMode = mode;
  document.querySelectorAll(".mode-panel").forEach(p => p.classList.add("hidden"));
  const panelMap = {
    text: "mode-text", files: "mode-files", topic: "mode-topic",
    url: "mode-url", update_ppt: "mode-update-ppt",
  };
  const pid = panelMap[mode];
  if (pid) document.getElementById(pid).classList.remove("hidden");
}

// ── Tabs (integrations) ───────────────────────────────────────────────────────
function setupTabs() {
  document.querySelectorAll(".tab-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const targetId = btn.dataset.tab;
      btn.closest(".integrations-body").querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
      btn.closest(".integrations-body").querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));
      btn.classList.add("active");
      document.getElementById(targetId).classList.add("active");
    });
  });
}

// ── File drop zones ───────────────────────────────────────────────────────────
function setupFileDrop() {
  document.querySelectorAll(".file-drop").forEach(zone => {
    const targetId = zone.dataset.target;
    const input = document.getElementById(targetId) || zone.querySelector("input[type=file]");
    if (!input) return;

    zone.addEventListener("click", () => input.click());

    zone.addEventListener("dragover", e => { e.preventDefault(); zone.classList.add("dragover"); });
    zone.addEventListener("dragleave", () => zone.classList.remove("dragover"));
    zone.addEventListener("drop", e => {
      e.preventDefault();
      zone.classList.remove("dragover");
      addFiles(input, e.dataTransfer.files);
    });

    input.addEventListener("change", () => addFiles(input, input.files));
  });
}

function addFiles(input, newFiles) {
  const dt = new DataTransfer();
  if (input.files) Array.from(input.files).forEach(f => dt.items.add(f));
  Array.from(newFiles).forEach(f => dt.items.add(f));
  input.files = dt.files;
  renderFileList(input);
}

function renderFileList(input) {
  const listId = input.id + "-list";
  const list = document.getElementById(listId);
  if (!list) return;
  list.innerHTML = "";
  Array.from(input.files).forEach((f, i) => {
    const pill = document.createElement("span");
    pill.className = "file-pill";
    pill.innerHTML = `📄 ${f.name} <span class="remove" data-idx="${i}">×</span>`;
    pill.querySelector(".remove").addEventListener("click", (e) => {
      e.stopPropagation();
      removeFile(input, i);
    });
    list.appendChild(pill);
  });

  // Proof info
  if (input.id === "proof-files") {
    const info = document.getElementById("proof-info");
    if (input.files.length) {
      info.textContent = `${input.files.length} screenshot(s) uploaded — will be appended as proof slides after the main deck.`;
      info.classList.remove("hidden");
    } else {
      info.classList.add("hidden");
    }
  }
}

function removeFile(input, idx) {
  const dt = new DataTransfer();
  Array.from(input.files).forEach((f, i) => { if (i !== idx) dt.items.add(f); });
  input.files = dt.files;
  renderFileList(input);
}

// ── Gmail ─────────────────────────────────────────────────────────────────────
async function checkGmailStatus() {
  try {
    const r = await fetch("/api/gmail/status");
    const d = await r.json();
    if (d.connected) {
      AppState.gmailConnected = true;
      AppState.gmailUserEmail = d.email;
      showGmailConnected();
    } else if (d.has_credentials_file) {
      showGmailHasCreds();
    } else {
      showGmailNoCreds();
    }
  } catch(e) {}
}

function checkGmailCallback() {
  const params = new URLSearchParams(window.location.search);
  if (params.get("gmail_connected") === "true") {
    history.replaceState({}, "", "/");
    checkGmailStatus();
  }
  if (params.get("gmail_error")) {
    showAlert("global-alert", `Gmail authorisation denied: ${params.get("gmail_error")}`, "error");
    history.replaceState({}, "", "/");
  }
}

function showGmailNoCreds() {
  document.getElementById("gmail-not-connected").classList.remove("hidden");
  document.getElementById("gmail-no-creds").classList.remove("hidden");
  document.getElementById("gmail-has-creds").classList.add("hidden");
  document.getElementById("gmail-connected").classList.add("hidden");
}

function showGmailHasCreds() {
  document.getElementById("gmail-not-connected").classList.remove("hidden");
  document.getElementById("gmail-no-creds").classList.add("hidden");
  document.getElementById("gmail-has-creds").classList.remove("hidden");
  document.getElementById("gmail-connected").classList.add("hidden");
}

function showGmailConnected() {
  document.getElementById("gmail-not-connected").classList.add("hidden");
  document.getElementById("gmail-connected").classList.remove("hidden");
  document.getElementById("gmail-email").textContent = AppState.gmailUserEmail;
}

// Gmail credentials upload
document.getElementById("gmail-creds-file").addEventListener("change", async function() {
  if (!this.files.length) return;
  const fd = new FormData();
  fd.append("file", this.files[0]);
  const r = await fetch("/api/gmail/upload-credentials", {method: "POST", body: fd});
  const d = await r.json();
  if (d.ok) {
    showGmailHasCreds();
  } else {
    showAlert("global-alert", d.error || "Failed to upload credentials", "error");
  }
});

// Gmail login
document.getElementById("btn-gmail-login").addEventListener("click", async () => {
  const r = await fetch("/api/gmail/auth-url", {method: "POST"});
  const d = await r.json();
  if (d.error) {
    showAlert("global-alert", d.error, "error");
    return;
  }
  window.location.href = d.auth_url;
});

// Gmail disconnect
document.getElementById("btn-gmail-disconnect").addEventListener("click", async () => {
  await fetch("/api/gmail/disconnect", {method: "POST"});
  AppState.gmailConnected = false;
  AppState.gmailUserEmail = "";
  AppState.gmailEmails = [];
  AppState.gmailSelectedIds = new Set();
  AppState.gmailThreadsExpanded = new Set();
  document.getElementById("gmail-email-list").innerHTML = "";
  document.getElementById("gmail-sel-count").classList.add("hidden");
  checkGmailStatus();
});

// Gmail search
document.getElementById("btn-gmail-search").addEventListener("click", async () => {
  const btn = document.getElementById("btn-gmail-search");
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span>Searching…';
  try {
    const r = await fetch("/api/gmail/search", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        keyword:    document.getElementById("gmail-kw").value,
        from_email: document.getElementById("gmail-from").value,
        after_date: document.getElementById("gmail-after").value || null,
        before_date:document.getElementById("gmail-before").value || null,
        label:      document.getElementById("gmail-label").value,
        max_results:parseInt(document.getElementById("gmail-max").value),
      }),
    });
    const d = await r.json();
    if (d.error) {
      showAlert("global-alert", d.error, "error"); return;
    }
    AppState.gmailEmails = d.emails || [];
    AppState.gmailSelectedIds = new Set();
    AppState.gmailThreadsExpanded = new Set();
    renderEmailList(AppState.gmailEmails);
  } finally {
    btn.disabled = false;
    btn.textContent = "Search";
  }
});

function renderEmailList(emails) {
  const container = document.getElementById("gmail-email-list");
  const countEl   = document.getElementById("gmail-sel-count");
  container.innerHTML = "";

  if (!emails.length) {
    container.innerHTML = '<div class="alert alert-info"><span class="alert-icon">ℹ️</span>No emails found matching your search.</div>';
    countEl.classList.add("hidden");
    return;
  }

  container.innerHTML = `<p style="font-weight:600;margin-bottom:8px;">Results — ${emails.length} thread(s)</p>`;

  emails.forEach(em => {
    const tid    = em.threadId;
    const tcount = em.thread_count || 1;
    const row    = document.createElement("div");
    row.className = "email-row";
    row.dataset.tid = tid;

    const badge = tcount > 1 ? `<span class="thread-badge">🔗 ${tcount}</span>` : "";
    const threadBtn = tcount > 1
      ? `<button class="btn btn-secondary btn-sm gmail-thread-toggle" data-tid="${tid}">▼ Show thread</button>`
      : "";

    row.innerHTML = `
      <div class="email-header">
        <input type="checkbox" class="gmail-chk" data-tid="${tid}" />
        <div class="email-meta">
          <div class="email-from">${escHtml(em.from || "")} ${badge}</div>
          <div class="email-subject">${escHtml(em.subject || "(no subject)")}</div>
          <div class="email-date">${escHtml(em.date || "")}</div>
          <div class="email-snippet">${escHtml(em.snippet || "")}</div>
          ${threadBtn}
        </div>
      </div>
      <div class="thread-replies hidden" id="replies-${tid}"></div>`;

    row.querySelector(".gmail-chk").addEventListener("change", (e) => {
      if (e.target.checked) {
        AppState.gmailSelectedIds.add(tid);
        row.classList.add("checked");
      } else {
        AppState.gmailSelectedIds.delete(tid);
        row.classList.remove("checked");
      }
      updateGmailSelCount();
    });

    const toggleBtn = row.querySelector(".gmail-thread-toggle");
    if (toggleBtn) {
      toggleBtn.addEventListener("click", () => toggleThread(tid, toggleBtn));
    }

    container.appendChild(row);
  });
  updateGmailSelCount();
}

async function toggleThread(tid, btn) {
  const repliesDiv = document.getElementById(`replies-${tid}`);
  if (!repliesDiv) return;

  const isExpanded = AppState.gmailThreadsExpanded.has(tid);
  if (isExpanded) {
    AppState.gmailThreadsExpanded.delete(tid);
    repliesDiv.classList.add("hidden");
    btn.textContent = "▼ Show thread";
    return;
  }

  AppState.gmailThreadsExpanded.add(tid);
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span>';

  try {
    const r = await fetch(`/api/gmail/thread/${encodeURIComponent(tid)}`);
    const d = await r.json();
    const msgs = d.messages || [];
    repliesDiv.innerHTML = "";
    msgs.slice(1).forEach(m => {
      const div = document.createElement("div");
      div.className = "reply-row";
      div.innerHTML = `└─ <strong>${escHtml(m.from || "")}</strong> <em>(${escHtml(m.date || "")})</em><br/><span>${escHtml((m.snippet || "").substring(0,150))}</span>`;
      repliesDiv.appendChild(div);
    });
    repliesDiv.classList.remove("hidden");
    btn.textContent = "▲ Hide thread";
  } catch(e) {
    btn.textContent = "▼ Show thread";
    AppState.gmailThreadsExpanded.delete(tid);
  }
  btn.disabled = false;
}

function updateGmailSelCount() {
  const el = document.getElementById("gmail-sel-count");
  const n = AppState.gmailSelectedIds.size;
  if (n > 0) {
    el.textContent = `Selected: ${n} email thread(s)`;
    el.classList.remove("hidden");
  } else {
    el.textContent = "No emails selected yet — check boxes above to select.";
    el.classList.remove("hidden");
  }
}

// ── Analyze ───────────────────────────────────────────────────────────────────
function setupButtonHandlers() {
  document.getElementById("btn-analyze").addEventListener("click", submitAnalyze);
  document.getElementById("btn-generate").addEventListener("click", submitGenerate);
  document.getElementById("btn-preview").addEventListener("click", openPreview);
  document.getElementById("btn-close-preview").addEventListener("click", closePreview);
  document.getElementById("btn-prev-page").addEventListener("click", prevPreviewPage);
  document.getElementById("btn-next-page").addEventListener("click", nextPreviewPage);
}

async function submitAnalyze() {
  const btn = document.getElementById("btn-analyze");
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span>Analyzing…';
  document.getElementById("analyze-progress").classList.remove("hidden");
  document.getElementById("analyze-alert").innerHTML = "";
  setProgress("analyze", 0, "Building request…");

  // Save config first
  const url   = document.getElementById("sb-url").value.trim();
  const key   = document.getElementById("sb-key").value.trim();
  const model = document.getElementById("sb-model").value.trim();
  if (!url || !key) {
    showAlert("analyze-alert", "Configure the LLM Gateway in the sidebar first.", "error");
    btn.disabled = false; btn.textContent = "🚀 Analyze Content & Create Plan";
    return;
  }
  await fetch("/api/config", {
    method: "POST", headers: {"Content-Type": "application/json"},
    body: JSON.stringify({gateway_url: url, api_key: key, model_name: model}),
  });

  const fd = buildFormData();
  if (!fd) {
    btn.disabled = false; btn.textContent = "🚀 Analyze Content & Create Plan";
    document.getElementById("analyze-progress").classList.add("hidden");
    return;
  }

  try {
    const r = await fetch("/api/analyze", {method: "POST", body: fd});
    const d = await r.json();
    if (d.error) {
      showAlert("analyze-alert", d.error, "error");
      btn.disabled = false; btn.textContent = "🚀 Analyze Content & Create Plan";
      document.getElementById("analyze-progress").classList.add("hidden");
      return;
    }
    AppState.jobId = d.job_id;
    startPolling(d.job_id, "analyze", (result) => {
      onAnalyzeDone(result);
      btn.disabled = false;
      btn.textContent = "🚀 Analyze Content & Create Plan";
    }, (err) => {
      showAlert("analyze-alert", err, "error");
      btn.disabled = false;
      btn.textContent = "🚀 Analyze Content & Create Plan";
    });
  } catch(e) {
    showAlert("analyze-alert", `Request failed: ${e}`, "error");
    btn.disabled = false; btn.textContent = "🚀 Analyze Content & Create Plan";
    document.getElementById("analyze-progress").classList.add("hidden");
  }
}

function buildFormData() {
  const fd = new FormData();
  const mode = AppState.primaryMode;
  fd.append("primary_mode", mode);
  fd.append("leader_key", document.getElementById("leader-select").value);

  // Gmail emails count as a valid source — skip primary source requirement if threads are selected
  const hasGmailSource = AppState.gmailSelectedIds.size > 0;

  if (mode === "text") {
    const txt = document.getElementById("pasted-text").value.trim();
    if (!txt && !hasGmailSource) { showAlert("analyze-alert", "Please paste some content, or select emails from the Gmail tab.", "error"); return null; }
    if (txt) {
      fd.append("pasted_text", txt);
      fd.append("paste_context", document.getElementById("paste-context").value);
    }
  } else if (mode === "files") {
    const files = document.getElementById("primary-files").files;
    if (!files.length && !hasGmailSource) { showAlert("analyze-alert", "Please upload at least one file.", "error"); return null; }
    Array.from(files).forEach(f => fd.append("primary_files", f));
    fd.append("primary_url_ctx", document.getElementById("primary-file-ctx").value);
  } else if (mode === "topic") {
    const t = document.getElementById("topic-input").value.trim();
    if (!t && !hasGmailSource) { showAlert("analyze-alert", "Please enter a presentation topic.", "error"); return null; }
    if (t) {
      fd.append("topic", t);
      fd.append("topic_context", document.getElementById("topic-context").value);
    }
  } else if (mode === "url") {
    const u = document.getElementById("primary-url").value.trim();
    if (!u && !hasGmailSource) { showAlert("analyze-alert", "Please enter a URL.", "error"); return null; }
    if (u) {
      fd.append("primary_url", u);
      fd.append("primary_url_ctx", document.getElementById("primary-url-ctx").value);
    }
  } else if (mode === "update_ppt") {
    const f = document.getElementById("old-ppt-file").files[0];
    if (!f && !hasGmailSource) { showAlert("analyze-alert", "Please upload the existing PPT file.", "error"); return null; }
    if (f) {
      fd.append("old_ppt", f);
      Array.from(document.getElementById("new-data-files").files).forEach(x => fd.append("new_data_files", x));
      fd.append("new_text_for_ppt", document.getElementById("new-text-ppt").value);
      fd.append("ppt_update_context", document.getElementById("ppt-update-ctx").value);
    }
  }

  // Additional sources
  const extraUrl = document.getElementById("extra-url").value.trim();
  if (extraUrl) { fd.append("extra_url", extraUrl); fd.append("extra_url_ctx", document.getElementById("extra-url-ctx").value); }
  Array.from(document.getElementById("extra-docs").files).forEach(f => fd.append("extra_docs", f));
  Array.from(document.getElementById("extra-images").files).forEach(f => fd.append("extra_images", f));
  Array.from(document.getElementById("extra-data").files).forEach(f => fd.append("extra_data", f));
  const imgCtx = document.getElementById("extra-img-ctx").value;
  if (imgCtx) fd.append("extra_image_ctx", imgCtx);

  // Integrations
  fd.append("github_url",          document.getElementById("github-url").value);
  fd.append("github_context",      document.getElementById("github-context").value);
  fd.append("openproject_url",     document.getElementById("op-url").value);
  fd.append("openproject_project", document.getElementById("op-project").value);
  fd.append("openproject_key",     document.getElementById("op-key").value);
  fd.append("openproject_context", document.getElementById("op-context").value);
  fd.append("gsheet_url",          document.getElementById("gsheet-url").value);
  fd.append("gsheet_context",      document.getElementById("gsheet-context").value);

  // Gmail
  if (AppState.gmailSelectedIds.size > 0) {
    fd.append("gmail_selected_ids", JSON.stringify([...AppState.gmailSelectedIds]));
  }
  fd.append("gmail_focus", document.getElementById("gmail-focus").value);

  // Proof files
  Array.from(document.getElementById("proof-files").files).forEach(f => fd.append("proof_files", f));
  fd.append("proof_caption", document.getElementById("proof-caption").value);

  return fd;
}

function onAnalyzeDone(result) {
  const plan = result.plan || [];
  const leaderKey = result.leader_key || document.getElementById("leader-select").value;
  AppState.plan = plan;
  AppState.leaderKey = leaderKey;

  const profileName = AppState.profiles[leaderKey]?.name || leaderKey;
  showAlert("analyze-alert", `✅ Plan created: ${plan.length} slides for ${profileName}`, "success");

  renderPlanEditor(plan);
  document.getElementById("step-4").removeAttribute("hidden");
  document.getElementById("step-4").scrollIntoView({behavior: "smooth", block: "start"});

  // Load content summary for JSON display
  fetchContentSummary();
}

async function fetchContentSummary() {
  // content is stored server-side; we can just display the plan as a summary hint
  // Leave the JSON block empty unless we add an endpoint for it
}

// ── Plan editor ───────────────────────────────────────────────────────────────
function renderPlanEditor(plan) {
  const container = document.getElementById("plan-editor");
  container.innerHTML = "";

  plan.forEach(slide => {
    const sn = slide.slide_number;
    const row = document.createElement("div");
    row.className = "slide-row";
    row.dataset.sn = sn;

    const typeOptions = SLIDE_TYPES.map(t =>
      `<option value="${t}" ${t === (slide.slide_type || "content") ? "selected" : ""}>${t}</option>`
    ).join("");

    row.innerHTML = `
      <input type="checkbox" class="keep-chk" checked title="Keep this slide" />
      <span class="slide-num">${sn}</span>
      <input type="text" class="slide-title-input" value="${escAttr(slide.title || "")}"
             placeholder="Slide ${sn} (${slide.slide_type || "content"})" />
      <select class="slide-type-select">${typeOptions}</select>`;

    row.querySelector(".keep-chk").addEventListener("change", updateSlidesInfo);
    row.querySelector(".slide-title-input").addEventListener("input", updateSlidesInfo);
    container.appendChild(row);
  });

  updateSlidesInfo();
}

function collectEditedPlan() {
  const rows = document.querySelectorAll(".slide-row");
  const result = [];
  rows.forEach(row => {
    const keep = row.querySelector(".keep-chk").checked;
    if (!keep) return;
    const sn = parseInt(row.dataset.sn);
    const orig = AppState.plan.find(s => s.slide_number === sn) || {};
    result.push({
      ...orig,
      title:      row.querySelector(".slide-title-input").value,
      slide_type: row.querySelector(".slide-type-select").value,
    });
  });
  return result;
}

function updateSlidesInfo() {
  const total = document.querySelectorAll(".slide-row .keep-chk:checked").length;
  document.getElementById("slides-info").textContent = `📝 ${total} slide(s) will be generated`;
}

// ── Generate ──────────────────────────────────────────────────────────────────
async function submitGenerate() {
  const btn = document.getElementById("btn-generate");
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span>Generating…';
  document.getElementById("generate-progress").classList.remove("hidden");
  document.getElementById("generate-alert").innerHTML = "";
  document.getElementById("output-section").classList.add("hidden");
  setProgress("generate", 0, "Starting…");

  const editedPlan = collectEditedPlan();
  if (!editedPlan.length) {
    showAlert("generate-alert", "No slides selected. Keep at least one slide.", "error");
    btn.disabled = false; btn.textContent = "⚡ Generate PPT";
    return;
  }

  try {
    const r = await fetch("/api/generate", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({leader_key: AppState.leaderKey, edited_plan: editedPlan}),
    });
    const d = await r.json();
    if (d.error) {
      showAlert("generate-alert", d.error, "error");
      btn.disabled = false; btn.textContent = "⚡ Generate PPT";
      return;
    }
    startPolling(d.job_id, "generate", (result) => {
      onGenerateDone(result);
      btn.disabled = false;
      btn.textContent = "⚡ Generate PPT";
    }, (err) => {
      showAlert("generate-alert", err, "error");
      btn.disabled = false;
      btn.textContent = "⚡ Generate PPT";
    });
  } catch(e) {
    showAlert("generate-alert", `Request failed: ${e}`, "error");
    btn.disabled = false; btn.textContent = "⚡ Generate PPT";
  }
}

function onGenerateDone(result) {
  const fname = result.output_filename;
  const total = result.total_slides || 0;
  AppState.outputFilename = fname;

  const profileName = AppState.profiles[AppState.leaderKey]?.name || AppState.leaderKey;
  showAlert("generate-alert", `✅ Presentation generated: ${total} slides for ${profileName}`, "success");

  // Setup download link
  const dl = document.getElementById("btn-download");
  dl.href = `/api/download/${encodeURIComponent(fname)}`;
  dl.download = fname;

  document.getElementById("output-section").classList.remove("hidden");
  document.getElementById("output-section").scrollIntoView({behavior: "smooth"});

  document.getElementById("preview-filename").textContent = fname;
  document.getElementById("preview-section").classList.add("hidden");
}

// ── Preview ───────────────────────────────────────────────────────────────────
async function openPreview() {
  const fname = AppState.outputFilename;
  if (!fname) return;

  document.getElementById("preview-section").classList.remove("hidden");
  document.getElementById("preview-section").scrollIntoView({behavior: "smooth"});
  document.getElementById("preview-grid").innerHTML = "";
  document.getElementById("preview-nav").style.display = "none";
  document.getElementById("preview-progress").classList.remove("hidden");
  setProgress("preview", 10, "Rendering slide previews…");

  // Check if already generated
  const statusR = await fetch(`/api/preview/pages?filename=${encodeURIComponent(fname)}`);
  const statusD = await statusR.json();

  if (statusD.total > 0) {
    document.getElementById("preview-progress").classList.add("hidden");
    AppState.previewPaths = statusD.paths;
    AppState.previewPage = 0;
    renderPreviewPage();
    return;
  }

  // Kick off generation
  const r = await fetch("/api/preview/generate", {
    method: "POST", headers: {"Content-Type": "application/json"},
    body: JSON.stringify({filename: fname}),
  });
  const d = await r.json();
  if (d.error) {
    showAlert("generate-alert", d.error, "error");
    document.getElementById("preview-progress").classList.add("hidden");
    return;
  }

  startPolling(d.job_id, "preview", (result) => {
    document.getElementById("preview-progress").classList.add("hidden");
    AppState.previewPaths = result.paths || [];
    AppState.previewPage = 0;
    if (!AppState.previewPaths.length) {
      document.getElementById("preview-grid").innerHTML =
        '<div class="alert alert-warning">Could not render previews. Please download and open in PowerPoint.</div>';
      return;
    }
    renderPreviewPage();
  }, (err) => {
    document.getElementById("preview-progress").classList.add("hidden");
    document.getElementById("preview-grid").innerHTML =
      `<div class="alert alert-error">Preview failed: ${escHtml(err)}</div>`;
  });
}

function closePreview() {
  document.getElementById("preview-section").classList.add("hidden");
}

function renderPreviewPage() {
  const idx   = AppState.previewPage;   // current slide index (0-based)
  const paths = AppState.previewPaths;
  const total = paths.length;

  const grid = document.getElementById("preview-grid");
  grid.innerHTML = "";

  if (!total) return;

  // Show current slide full-width
  const div = document.createElement("div");
  div.className = "preview-slide";
  div.style.maxWidth = "860px";
  div.style.margin = "0 auto";
  div.innerHTML = `
    <img src="${paths[idx]}" alt="Slide ${idx + 1}" style="width:100%;display:block;" />
    <div class="preview-caption">Slide ${idx + 1} of ${total}</div>`;
  grid.appendChild(div);

  // Always show nav
  const nav = document.getElementById("preview-nav");
  nav.style.display = "flex";
  document.getElementById("preview-page-info").textContent = `${idx + 1} / ${total}`;
  document.getElementById("btn-prev-page").disabled = idx === 0;
  document.getElementById("btn-next-page").disabled = idx >= total - 1;
}

function prevPreviewPage() {
  if (AppState.previewPage > 0) { AppState.previewPage--; renderPreviewPage(); }
}
function nextPreviewPage() {
  if (AppState.previewPage < AppState.previewPaths.length - 1) { AppState.previewPage++; renderPreviewPage(); }
}

// ── Fullscreen preview ────────────────────────────────────────────────────────
function openFullscreen() {
  const paths = AppState.previewPaths;
  if (!paths || !paths.length) return;

  const overlay = document.getElementById("fs-overlay");
  overlay.classList.remove("hidden");

  _fsSetSlide(AppState.previewPage);

  // Enter browser fullscreen on the overlay element
  if (overlay.requestFullscreen) overlay.requestFullscreen().catch(() => {});
  else if (overlay.webkitRequestFullscreen) overlay.webkitRequestFullscreen();
}

function closeFullscreen() {
  const overlay = document.getElementById("fs-overlay");
  overlay.classList.add("hidden");
  // Exit browser fullscreen if active
  if (document.fullscreenElement || document.webkitFullscreenElement) {
    (document.exitFullscreen || document.webkitExitFullscreen || (() => {})).call(document);
  }
}

function fsNavigate(dir) {
  const total = AppState.previewPaths.length;
  const next = AppState.previewPage + dir;
  if (next < 0 || next >= total) return;
  AppState.previewPage = next;
  _fsSetSlide(next);
  renderPreviewPage(); // keep the inline viewer in sync
}

function _fsSetSlide(idx) {
  const paths = AppState.previewPaths;
  const total = paths.length;
  const img = document.getElementById("fs-img");
  img.src = paths[idx];
  img.alt = `Slide ${idx + 1}`;
  document.getElementById("fs-title").textContent = `Slide ${idx + 1} of ${total}`;
  document.getElementById("fs-counter").textContent = `${idx + 1} / ${total}`;
  document.getElementById("fs-btn-prev").disabled = idx === 0;
  document.getElementById("fs-btn-next").disabled = idx >= total - 1;
}

// Wire up fullscreen keyboard and button listeners once DOM is ready
document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("fs-btn-close").addEventListener("click", closeFullscreen);
  document.getElementById("fs-btn-prev").addEventListener("click", () => fsNavigate(-1));
  document.getElementById("fs-btn-next").addEventListener("click", () => fsNavigate(+1));
  document.getElementById("btn-fullscreen").addEventListener("click", openFullscreen);

  // Keyboard: arrow keys to navigate, Esc to close
  document.addEventListener("keydown", (e) => {
    const overlay = document.getElementById("fs-overlay");
    if (overlay.classList.contains("hidden")) return;
    if (e.key === "ArrowLeft")  { e.preventDefault(); fsNavigate(-1); }
    if (e.key === "ArrowRight") { e.preventDefault(); fsNavigate(+1); }
    if (e.key === "Escape")     { closeFullscreen(); }
  });

  // If browser exits fullscreen via Esc / its own UI, hide our overlay too
  document.addEventListener("fullscreenchange", () => {
    if (!document.fullscreenElement) {
      document.getElementById("fs-overlay").classList.add("hidden");
    }
  });
  document.addEventListener("webkitfullscreenchange", () => {
    if (!document.webkitFullscreenElement) {
      document.getElementById("fs-overlay").classList.add("hidden");
    }
  });
});

// ── Polling ───────────────────────────────────────────────────────────────────
function startPolling(jobId, prefix, onDone, onError) {
  if (AppState.pollTimer) clearInterval(AppState.pollTimer);
  AppState.pollTimer = setInterval(async () => {
    try {
      const r = await fetch(`/api/job/${jobId}`);
      const j = await r.json();
      setProgress(prefix, j.progress || 0, j.progress_text || "");
      if (j.status === "done") {
        clearInterval(AppState.pollTimer);
        AppState.pollTimer = null;
        onDone(j.result || {});
      }
      if (j.status === "error") {
        clearInterval(AppState.pollTimer);
        AppState.pollTimer = null;
        onError(j.error || "Unknown error");
      }
    } catch(e) {
      // Network blip — keep polling
    }
  }, 1500);
}

// ── Utilities ─────────────────────────────────────────────────────────────────
function setProgress(prefix, pct, text) {
  const bar = document.getElementById(`${prefix}-bar`);
  const txt = document.getElementById(`${prefix}-text`);
  if (bar) bar.style.width = `${pct}%`;
  if (txt) txt.textContent = text;
}

function showAlert(containerId, msg, type) {
  const icons = {info: "ℹ️", success: "✅", warning: "⚠️", error: "❌"};
  const el = document.getElementById(containerId);
  if (!el) return;
  el.innerHTML = `
    <div class="alert alert-${type}">
      <span class="alert-icon">${icons[type] || "ℹ️"}</span>
      <span>${escHtml(String(msg))}</span>
    </div>`;
}

function escHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function escAttr(s) {
  return String(s).replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}
