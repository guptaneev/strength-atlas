const AUTH_TOKEN_KEY = "atlas_auth_token";
const AUTH_TOKEN_TYPE = "atlas_auth_token_type";
const ASK_ADVANCED_OPEN_KEY = "atlas_ask_advanced_open";
const MAX_QUERY_CHARS = 400;
const DOMAIN_PATTERN = /^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$/i;

const state = {
  activeTab: "ask",
  askCanAsk: true,
  askContactUrl: "",
  currentUserEmail: "",
  pendingAskQuery: "",
  summary: null,
  domains: [],
  activeModal: null,
};

const refs = {
  quotaBadge: document.getElementById("quotaBadge"),
  authActionBtn: document.getElementById("authActionBtn"),
  userMenu: document.getElementById("userMenu"),
  userMenuBtn: document.getElementById("userMenuBtn"),
  userMenuPopup: document.getElementById("userMenuPopup"),
  userEmail: document.getElementById("userEmail"),
  signOutBtn: document.getElementById("signOutBtn"),
  trustChips: document.getElementById("trustChips"),
  globalBanner: document.getElementById("globalBanner"),
  quickQueryForm: document.getElementById("quickQueryForm"),
  quickQuery: document.getElementById("quickQuery"),
  quickSubmit: document.getElementById("quickSubmit"),
  tabs: Array.from(document.querySelectorAll(".tab")),
  tabUnderline: document.getElementById("tabUnderline"),
  panels: {
    ask: document.getElementById("panel-ask"),
    program: document.getElementById("panel-program"),
    source: document.getElementById("panel-source"),
  },
  askGateMessage: document.getElementById("askGateMessage"),
  askResults: document.getElementById("askResults"),
  advancedToggle: document.getElementById("advancedToggle"),
  advancedChevron: document.getElementById("advancedChevron"),
  askAdvanced: document.getElementById("askAdvanced"),
  askDomain: document.getElementById("askDomain"),
  askMaxEvidence: document.getElementById("askMaxEvidence"),
  programDomain: document.getElementById("programDomain"),
  programLimit: document.getElementById("programLimit"),
  programResults: document.getElementById("programResults"),
  sourceDomain: document.getElementById("sourceDomain"),
  sourceLimit: document.getElementById("sourceLimit"),
  sourceResults: document.getElementById("sourceResults"),
  sourceListForm: document.getElementById("sourceListForm"),
  sourceListBtn: document.getElementById("sourceListBtn"),
  listDomain: document.getElementById("listDomain"),
  listStatus: document.getElementById("listStatus"),
  listLimit: document.getElementById("listLimit"),
  sourceListResults: document.getElementById("sourceListResults"),
  sourceDetailOutput: document.getElementById("sourceDetailOutput"),
  openStatusBtn: document.getElementById("openStatusBtn"),
  statusBody: document.getElementById("statusBody"),
  authModal: document.getElementById("authModal"),
  authForm: document.getElementById("authForm"),
  authEmail: document.getElementById("authEmail"),
  authPassword: document.getElementById("authPassword"),
  signInBtn: document.getElementById("signInBtn"),
  signUpBtn: document.getElementById("signUpBtn"),
  authMessage: document.getElementById("authMessage"),
  statusModal: document.getElementById("statusModal"),
};

function getAuthToken() {
  return localStorage.getItem(AUTH_TOKEN_KEY) || "";
}

function getAuthTokenType() {
  const tokenType = (localStorage.getItem(AUTH_TOKEN_TYPE) || "bearer").trim();
  if (!tokenType) return "Bearer";
  return `${tokenType.charAt(0).toUpperCase()}${tokenType.slice(1)}`;
}

function setAuthToken(token, tokenType = "bearer") {
  localStorage.setItem(AUTH_TOKEN_KEY, token);
  localStorage.setItem(AUTH_TOKEN_TYPE, tokenType);
}

function clearAuthToken() {
  localStorage.removeItem(AUTH_TOKEN_KEY);
  localStorage.removeItem(AUTH_TOKEN_TYPE);
}

function getAdvancedOpen() {
  return localStorage.getItem(ASK_ADVANCED_OPEN_KEY) === "1";
}

function setAdvancedOpen(open) {
  localStorage.setItem(ASK_ADVANCED_OPEN_KEY, open ? "1" : "0");
}

function authHeaders(extra = {}) {
  const token = getAuthToken();
  if (!token) return extra;
  return { ...extra, Authorization: `${getAuthTokenType()} ${token}` };
}

async function readJson(response) {
  const text = await response.text();
  let payload = {};
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch (_err) {
      payload = {};
    }
  }
  if (!response.ok) {
    const code =
      (typeof payload.detail === "string" && payload.detail) ||
      (typeof payload.status === "string" && payload.status) ||
      `request_failed_${response.status}`;
    const err = new Error(userMessageFromErrorCode(code, response.status));
    err.status = response.status;
    err.code = code;
    err.payload = payload;
    throw err;
  }
  return payload;
}

function setGlobalBanner(message, mode = "") {
  refs.globalBanner.textContent = message || "";
  refs.globalBanner.className = `global-banner${mode ? ` ${mode}` : ""}`;
}

function setInlineMessage(node, message, mode = "") {
  node.textContent = message || "";
  node.className = `inline-message${mode ? ` ${mode}` : ""}`;
}

function clearNode(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
}

function createText(className, text) {
  const node = document.createElement("div");
  node.className = className;
  node.textContent = text;
  return node;
}

function createMetaPill(text) {
  const node = document.createElement("span");
  node.className = "meta-pill";
  node.textContent = text;
  return node;
}

function createTrustChip(text) {
  const node = document.createElement("span");
  node.className = "trust-chip";
  node.textContent = text;
  return node;
}

function formatDate(value) {
  if (!value) return "n/a";
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return value;
  return date.toLocaleString();
}

function domainFromUrl(url) {
  const safeUrl = toSafeExternalUrl(url);
  if (!safeUrl) return "source";
  try {
    return new URL(safeUrl).hostname;
  } catch (_err) {
    return "source";
  }
}

function toSafeExternalUrl(value) {
  const raw = String(value || "").trim();
  if (!raw) return "";
  try {
    const parsed = new URL(raw);
    if (parsed.protocol === "http:" || parsed.protocol === "https:") {
      return parsed.toString();
    }
    return "";
  } catch (_err) {
    return "";
  }
}

function userMessageFromErrorCode(code, status) {
  if (code === "invalid_email_or_password") return "Invalid email or password.";
  if (code === "auth_provider_unavailable") return "Authentication service is temporarily unavailable.";
  if (code === "missing_authorization_header") return "Sign in is required.";
  if (code === "token_verification_failed") return "Session expired. Sign in again.";
  if (code === "quota_exceeded") return "Free ask quota reached.";
  if (code === "too_many_requests") return "Rate limit reached. Try again shortly.";
  if (code === "request_body_too_large") return "Request too large.";
  if (status >= 500) return "Server error. Try again in a moment.";
  if (status === 404) return "Requested resource was not found.";
  return "Request failed. Please try again.";
}

function isValidDomain(value) {
  const normalized = String(value || "").trim().toLowerCase();
  if (!normalized) return true;
  return DOMAIN_PATTERN.test(normalized);
}

function parseBoundedInt(rawValue, { defaultValue, min, max }) {
  const parsed = Number(rawValue);
  if (!Number.isFinite(parsed)) return defaultValue;
  if (parsed < min) return min;
  if (parsed > max) return max;
  return Math.trunc(parsed);
}

function setLoadingButton(button, busy, busyText, idleText) {
  if (!button) return;
  button.disabled = busy;
  button.textContent = busy ? busyText : idleText;
}

function renderSkeleton(container, count = 3) {
  clearNode(container);
  for (let i = 0; i < count; i += 1) {
    const shell = document.createElement("div");
    shell.className = "skeleton";
    for (let j = 0; j < 3; j += 1) {
      const line = document.createElement("div");
      line.className = "skeleton-line";
      shell.appendChild(line);
    }
    container.appendChild(shell);
  }
}

function renderEmpty(container, message) {
  clearNode(container);
  const node = document.createElement("div");
  node.className = "empty-state";
  node.textContent = message;
  container.appendChild(node);
}

function renderError(container, message) {
  clearNode(container);
  const node = document.createElement("div");
  node.className = "error-state";
  node.textContent = message;
  container.appendChild(node);
}

function renderTrustChips() {
  clearNode(refs.trustChips);

  if (!state.summary) {
    refs.trustChips.appendChild(createTrustChip("Corpus summary unavailable"));
    return;
  }

  refs.trustChips.appendChild(createTrustChip(`${state.summary.programs_total} programs indexed`));

  if (state.domains.length) {
    refs.trustChips.appendChild(createTrustChip(`Sources include ${state.domains.slice(0, 2).join(", ")}`));
  } else {
    refs.trustChips.appendChild(createTrustChip(`${state.summary.allowlisted_domains} allowlisted domains`));
  }

  refs.trustChips.appendChild(
    createTrustChip(`Last indexed ${formatDate(state.summary.latest_successful_crawl_at)}`),
  );
}

function renderStatusBody() {
  clearNode(refs.statusBody);

  if (!state.summary) {
    refs.statusBody.appendChild(createText("empty-state", "Status unavailable right now."));
    return;
  }

  const rows = [
    ["Domains", `${state.summary.domains_total} total (${state.summary.allowlisted_domains} allowlisted)`],
    ["Sources", `${state.summary.sources_total} total (${state.summary.sources_pending} pending)`],
    ["Programs", `${state.summary.programs_total}`],
    ["Claims", `${state.summary.claims_total}`],
    ["Recent failures", `${state.summary.recent_crawls_failed}/${state.summary.recent_crawls_analyzed}`],
    ["Latest successful crawl", formatDate(state.summary.latest_successful_crawl_at)],
  ];

  rows.forEach(([label, value]) => {
    const row = document.createElement("div");
    row.className = "status-row";
    row.appendChild(createText("status-label", label));
    row.appendChild(createText("status-value", value));
    refs.statusBody.appendChild(row);
  });
}

function updateQuickInputForTab() {
  if (state.activeTab === "ask") {
    refs.quickQuery.placeholder = "How often should I bench as an intermediate?";
    refs.quickSubmit.textContent = state.askCanAsk && getAuthToken() ? "Ask" : "Ask";
    refs.advancedToggle.classList.remove("hidden");
  } else if (state.activeTab === "program") {
    refs.quickQuery.placeholder = "Search programs (e.g., bench hypertrophy novice)";
    refs.quickSubmit.textContent = "Search Programs";
    refs.advancedToggle.classList.add("hidden");
  } else {
    refs.quickQuery.placeholder = "Search sources (e.g., deadlift setup)";
    refs.quickSubmit.textContent = "Search Sources";
    refs.advancedToggle.classList.add("hidden");
  }

  if (state.activeTab === "ask" && getAuthToken() && !state.askCanAsk) {
    refs.quickSubmit.disabled = true;
    refs.quickSubmit.textContent = "Upgrade";
  } else {
    refs.quickSubmit.disabled = false;
  }
}

function moveTabUnderline() {
  const activeTab = refs.tabs.find((tab) => tab.dataset.tab === state.activeTab);
  if (!activeTab) return;

  const navRect = activeTab.parentElement.getBoundingClientRect();
  const tabRect = activeTab.getBoundingClientRect();
  refs.tabUnderline.style.width = `${tabRect.width}px`;
  refs.tabUnderline.style.transform = `translateX(${tabRect.left - navRect.left}px)`;
}

function setTab(tabName, focusTab = false) {
  state.activeTab = tabName;

  refs.tabs.forEach((tab) => {
    const active = tab.dataset.tab === tabName;
    tab.setAttribute("aria-selected", active ? "true" : "false");
    tab.tabIndex = active ? 0 : -1;
    if (active && focusTab) tab.focus();
  });

  Object.entries(refs.panels).forEach(([key, panel]) => {
    panel.classList.toggle("hidden", key !== tabName);
  });

  updateQuickInputForTab();
  moveTabUnderline();
}

function setAdvancedVisibility(open) {
  refs.askAdvanced.classList.toggle("hidden", !open);
  refs.advancedToggle.setAttribute("aria-expanded", open ? "true" : "false");
  refs.advancedChevron.classList.toggle("open", open);
  setAdvancedOpen(open);
}

function openModal(kind) {
  closeUserMenu();
  const modal = kind === "auth" ? refs.authModal : refs.statusModal;
  if (!modal) return;

  state.activeModal = modal;
  modal.classList.remove("hidden");

  if (kind === "auth") {
    refs.authEmail.focus();
  }
}

function closeModal(kind) {
  const modal = kind === "auth" ? refs.authModal : refs.statusModal;
  if (!modal) return;

  modal.classList.add("hidden");
  if (state.activeModal === modal) {
    state.activeModal = null;
  }
}

function closeAllModals() {
  closeModal("auth");
  closeModal("status");
}

function openUserMenu() {
  refs.userMenuPopup.classList.remove("hidden");
  refs.userMenuBtn.setAttribute("aria-expanded", "true");
}

function closeUserMenu() {
  refs.userMenuPopup.classList.add("hidden");
  refs.userMenuBtn.setAttribute("aria-expanded", "false");
}

function updateAuthUI() {
  const token = getAuthToken();
  const signedIn = Boolean(token);

  if (!signedIn) {
    refs.authActionBtn.classList.remove("hidden");
    refs.userMenu.classList.add("hidden");
    state.currentUserEmail = "";
    if (state.activeTab === "ask") {
      setInlineMessage(refs.askGateMessage, "Sign in to use Ask Atlas. Free tier includes 5 lifetime asks.", "");
    }
    return;
  }

  refs.authActionBtn.classList.add("hidden");
  refs.userMenu.classList.remove("hidden");
  const label = (state.currentUserEmail || "U").trim();
  refs.userMenuBtn.textContent = label ? label.charAt(0).toUpperCase() : "U";
  refs.userEmail.textContent = state.currentUserEmail || "Signed in";
}

async function loadTrustAndStatus() {
  try {
    const [summary, sourceRows] = await Promise.all([
      readJson(await fetch("/dashboard/summary")),
      readJson(await fetch("/sources?limit=30")),
    ]);

    state.summary = summary;
    const distinctDomains = [];
    const seen = new Set();
    sourceRows.forEach((row) => {
      if (!row || !row.domain) return;
      if (seen.has(row.domain)) return;
      seen.add(row.domain);
      distinctDomains.push(row.domain);
    });
    state.domains = distinctDomains;
  } catch (_err) {
    state.summary = null;
    state.domains = [];
  }

  renderTrustChips();
  renderStatusBody();
}

async function loadQuota(options = {}) {
  const { surfaceAuthError = false } = options;
  const token = getAuthToken();
  if (!token) {
    refs.quotaBadge.classList.remove("exhausted");
    refs.quotaBadge.textContent = "Ask quota: sign in required";
    state.askCanAsk = true;
    state.askContactUrl = "";
    updateAuthUI();
    updateQuickInputForTab();
    return { ok: true, authError: null };
  }

  try {
    const data = await readJson(await fetch("/me/quota", { headers: authHeaders() }));
    refs.quotaBadge.textContent = `Ask quota: ${data.remaining} left`;
    refs.quotaBadge.classList.toggle("exhausted", !data.can_ask);
    state.askCanAsk = Boolean(data.can_ask);
    state.askContactUrl = data.contact_url || "";
    updateQuickInputForTab();

    if (!data.can_ask && state.activeTab === "ask") {
      setInlineMessage(
        refs.askGateMessage,
        `You've used all ${data.limit} free asks. Contact: ${data.contact_url || "support"}`,
        "error",
      );
    } else {
      setInlineMessage(refs.askGateMessage, "", "");
    }
  } catch (err) {
    if (err.status === 401) {
      clearAuthToken();
      state.currentUserEmail = "";
      refs.quotaBadge.textContent = "Ask quota: auth expired";
      state.askCanAsk = true;
      updateAuthUI();
      updateQuickInputForTab();
      if (surfaceAuthError) {
        return { ok: false, authError: err.payload?.detail || err.message || "auth_error" };
      }
      return { ok: false, authError: null };
    }
    refs.quotaBadge.textContent = "Ask quota: unavailable";
    state.askCanAsk = true;
    return { ok: false, authError: err.payload?.detail || err.message || "quota_unavailable" };
  }

  updateAuthUI();
  return { ok: true, authError: null };
}

function renderAskResponse(payload) {
  clearNode(refs.askResults);

  const card = document.createElement("article");
  card.className = "result-card";

  const title = document.createElement("h2");
  title.className = "result-title";
  title.textContent = payload.status === "ok" ? "Grounded Answer" : "Insufficient Evidence";
  card.appendChild(title);

  const answer = document.createElement("p");
  answer.className = "result-text";
  answer.textContent = payload.answer || "No answer available.";
  card.appendChild(answer);

  const meta = document.createElement("div");
  meta.className = "result-meta";
  const evidenceCount = Array.isArray(payload.evidence) ? payload.evidence.length : 0;
  meta.appendChild(createMetaPill(`Evidence: ${evidenceCount}`));
  if (typeof payload.confidence === "number") {
    meta.appendChild(createMetaPill(`Confidence: ${payload.confidence.toFixed(2)}`));
  }
  meta.appendChild(createMetaPill(`Status: ${payload.status || "unknown"}`));
  card.appendChild(meta);

  if (evidenceCount > 0) {
    payload.evidence.forEach((item, idx) => {
      const wrapper = document.createElement("div");
      wrapper.className = "evidence-item";
      wrapper.appendChild(
        createText(
          "evidence-ref",
          `[${idx + 1}] ${domainFromUrl(item.canonical_url || "")} · source ${item.source_id} · doc ${item.document_id}`,
        ),
      );

      if (item.title) {
        wrapper.appendChild(createText("result-text", item.title));
      }

      if (item.canonical_url) {
        const safeUrl = toSafeExternalUrl(item.canonical_url);
        if (safeUrl) {
          const link = document.createElement("a");
          link.href = safeUrl;
          link.target = "_blank";
          link.rel = "noopener noreferrer";
          link.textContent = "Open source";
          wrapper.appendChild(link);
        }
      }
      card.appendChild(wrapper);
    });
  }

  refs.askResults.appendChild(card);
}

function renderProgramResults(rows) {
  clearNode(refs.programResults);
  if (!rows.length) {
    renderEmpty(refs.programResults, "No matching programs. Try a broader query.");
    return;
  }

  rows.forEach((row) => {
    const card = document.createElement("article");
    card.className = "result-card";
    const title = document.createElement("h2");
    title.className = "result-title";
    title.textContent = row.name || `Program #${row.id}`;
    card.appendChild(title);

    const meta = document.createElement("div");
    meta.className = "result-meta";
    meta.appendChild(createMetaPill(`Program: ${row.id}`));
    meta.appendChild(createMetaPill(`Source: ${row.source_id || "n/a"}`));
    if (typeof row.confidence === "number") {
      meta.appendChild(createMetaPill(`Confidence: ${row.confidence.toFixed(2)}`));
    }
    card.appendChild(meta);

    if (row.canonical_url) {
      const safeUrl = toSafeExternalUrl(row.canonical_url);
      if (safeUrl) {
        const link = document.createElement("a");
        link.href = safeUrl;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.textContent = "Open source";
        card.appendChild(link);
      }
    }

    refs.programResults.appendChild(card);
  });
}

function renderSourceResults(rows) {
  clearNode(refs.sourceResults);
  if (!rows.length) {
    renderEmpty(refs.sourceResults, "No matching sources. Try a different phrase.");
    return;
  }

  rows.forEach((row) => {
    const card = document.createElement("article");
    card.className = "result-card";
    const title = document.createElement("h2");
    title.className = "result-title";
    title.textContent = `Source #${row.id}`;
    card.appendChild(title);
    card.appendChild(createText("result-text", row.canonical_url));

    const meta = document.createElement("div");
    meta.className = "result-meta";
    meta.appendChild(createMetaPill(`Status: ${row.status || "n/a"}`));
    meta.appendChild(createMetaPill(`Last crawled: ${formatDate(row.last_crawled_at)}`));
    card.appendChild(meta);

    refs.sourceResults.appendChild(card);
  });
}

function renderSourceList(rows) {
  clearNode(refs.sourceListResults);
  if (!rows.length) {
    renderEmpty(refs.sourceListResults, "No sources found for this filter.");
    return;
  }

  rows.forEach((row) => {
    const card = document.createElement("article");
    card.className = "result-card";
    const title = document.createElement("h2");
    title.className = "result-title";
    title.textContent = row.title || `Source #${row.id}`;
    card.appendChild(title);

    const meta = document.createElement("div");
    meta.className = "result-meta";
    meta.appendChild(createMetaPill(`Domain: ${row.domain || "n/a"}`));
    meta.appendChild(createMetaPill(`Status: ${row.status || "n/a"}`));
    meta.appendChild(createMetaPill(`Last crawled: ${formatDate(row.last_crawled_at)}`));
    card.appendChild(meta);

    card.appendChild(createText("result-text", row.canonical_url));

    const inspectBtn = document.createElement("button");
    inspectBtn.className = "btn-secondary";
    inspectBtn.type = "button";
    inspectBtn.textContent = "Inspect";
    inspectBtn.addEventListener("click", () => loadSourceDetail(row.id));
    card.appendChild(inspectBtn);

    refs.sourceListResults.appendChild(card);
  });
}

function renderSourceDetail(data) {
  clearNode(refs.sourceDetailOutput);

  if (!data || typeof data !== "object") {
    renderEmpty(refs.sourceDetailOutput, "No source selected.");
    return;
  }

  const card = document.createElement("article");
  card.className = "result-card";
  const title = document.createElement("h2");
  title.className = "result-title";
  title.textContent = data.title || `Source #${data.id}`;
  card.appendChild(title);

  const meta = document.createElement("div");
  meta.className = "result-meta";
  meta.appendChild(createMetaPill(`Domain: ${data.domain || "n/a"}`));
  meta.appendChild(createMetaPill(`Status: ${data.status || "n/a"}`));
  meta.appendChild(createMetaPill(`Type: ${data.source_type || "n/a"}`));
  card.appendChild(meta);

  card.appendChild(createText("result-text", `Last crawled: ${formatDate(data.last_crawled_at)}`));

  if (data.canonical_url) {
    const safeUrl = toSafeExternalUrl(data.canonical_url);
    if (safeUrl) {
      const link = document.createElement("a");
      link.href = safeUrl;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.textContent = "Open source";
      card.appendChild(link);
    }
  }

  if (Array.isArray(data.programs) && data.programs.length) {
    const label = document.createElement("div");
    label.className = "evidence-ref";
    label.textContent = "Programs:";
    card.appendChild(label);

    data.programs.slice(0, 8).forEach((program) => {
      const row = document.createElement("div");
      row.className = "evidence-item";
      row.appendChild(createText("result-text", program.name || `Program #${program.id}`));
      if (typeof program.confidence === "number") {
        row.appendChild(createText("evidence-ref", `Confidence: ${program.confidence.toFixed(2)}`));
      }
      card.appendChild(row);
    });
  }

  refs.sourceDetailOutput.appendChild(card);
}

async function runAskQuery(query) {
  if (query.length > MAX_QUERY_CHARS) {
    setInlineMessage(refs.askGateMessage, `Query must be ${MAX_QUERY_CHARS} characters or less.`, "error");
    return;
  }
  if (!isValidDomain(refs.askDomain.value)) {
    setInlineMessage(refs.askGateMessage, "Domain filter must be a valid domain.", "error");
    return;
  }

  const token = getAuthToken();
  if (!token) {
    state.pendingAskQuery = query;
    openModal("auth");
    setInlineMessage(refs.askGateMessage, "Sign in to submit Ask Atlas queries.", "error");
    return;
  }

  if (!state.askCanAsk) {
    setInlineMessage(
      refs.askGateMessage,
      `You've used your free asks. Contact: ${state.askContactUrl || "support"}`,
      "error",
    );
    return;
  }

  const payload = {
    query,
    max_sources: 8,
    max_programs: 20,
    include_evidence: true,
    max_evidence: parseBoundedInt(refs.askMaxEvidence.value || 8, {
      defaultValue: 8,
      min: 1,
      max: 25,
    }),
    filters: {},
  };
  refs.askMaxEvidence.value = String(payload.max_evidence);
  const domain = refs.askDomain.value.trim().toLowerCase();
  if (domain) payload.filters.domain = domain;

  renderSkeleton(refs.askResults, 2);
  setLoadingButton(refs.quickSubmit, true, "Thinking...", "Ask");

  try {
    const response = await readJson(
      await fetch("/ask/answer", {
        method: "POST",
        headers: authHeaders({ "content-type": "application/json" }),
        body: JSON.stringify(payload),
      }),
    );

    renderAskResponse(response);
    setInlineMessage(refs.askGateMessage, "", "");
    setGlobalBanner("", "");
    await loadQuota();
  } catch (err) {
    if (err.payload && err.payload.status === "quota_exceeded") {
      state.askCanAsk = false;
      state.askContactUrl = err.payload.contact_url || "";
      refs.quotaBadge.classList.add("exhausted");
      refs.quotaBadge.textContent = `Ask quota: 0 left`;
      setInlineMessage(
        refs.askGateMessage,
        `Free ask quota reached (${err.payload.used}/${err.payload.limit}). Contact: ${state.askContactUrl || "support"}`,
        "error",
      );
      renderError(refs.askResults, "You've used all 5 free asks. Upgrade to continue.");
      updateQuickInputForTab();
      return;
    }
    renderError(refs.askResults, `Ask failed: ${err.message}`);
  } finally {
    setLoadingButton(refs.quickSubmit, false, "Ask", "Ask");
    updateQuickInputForTab();
  }
}

async function runProgramQuery(query) {
  if (query.length > MAX_QUERY_CHARS) {
    renderError(refs.programResults, `Query must be ${MAX_QUERY_CHARS} characters or less.`);
    return;
  }
  if (!isValidDomain(refs.programDomain.value)) {
    renderError(refs.programResults, "Domain filter must be a valid domain.");
    return;
  }

  const params = new URLSearchParams();
  params.set("query", query);
  const programLimit = parseBoundedInt(refs.programLimit.value || 10, { defaultValue: 10, min: 1, max: 100 });
  refs.programLimit.value = String(programLimit);
  params.set("limit", String(programLimit));
  const domain = refs.programDomain.value.trim().toLowerCase();
  if (domain) params.set("domain", domain);

  renderSkeleton(refs.programResults, 3);
  setLoadingButton(refs.quickSubmit, true, "Searching...", "Search Programs");

  try {
    const rows = await readJson(await fetch(`/search/programs?${params.toString()}`));
    renderProgramResults(rows);
  } catch (err) {
    renderError(refs.programResults, `Program search failed: ${err.message}`);
  } finally {
    setLoadingButton(refs.quickSubmit, false, "Search Programs", "Search Programs");
    updateQuickInputForTab();
  }
}

async function runSourceQuery(query) {
  if (query.length > MAX_QUERY_CHARS) {
    renderError(refs.sourceResults, `Query must be ${MAX_QUERY_CHARS} characters or less.`);
    return;
  }
  if (!isValidDomain(refs.sourceDomain.value)) {
    renderError(refs.sourceResults, "Domain filter must be a valid domain.");
    return;
  }

  const params = new URLSearchParams();
  params.set("query", query);
  const sourceLimit = parseBoundedInt(refs.sourceLimit.value || 10, { defaultValue: 10, min: 1, max: 100 });
  refs.sourceLimit.value = String(sourceLimit);
  params.set("limit", String(sourceLimit));
  const domain = refs.sourceDomain.value.trim().toLowerCase();
  if (domain) params.set("domain", domain);

  renderSkeleton(refs.sourceResults, 3);
  setLoadingButton(refs.quickSubmit, true, "Searching...", "Search Sources");

  try {
    const rows = await readJson(await fetch(`/search/sources?${params.toString()}`));
    renderSourceResults(rows);
  } catch (err) {
    renderError(refs.sourceResults, `Source search failed: ${err.message}`);
  } finally {
    setLoadingButton(refs.quickSubmit, false, "Search Sources", "Search Sources");
    updateQuickInputForTab();
  }
}

async function loadSourceList(event) {
  event.preventDefault();
  if (!isValidDomain(refs.listDomain.value)) {
    renderError(refs.sourceListResults, "Domain filter must be a valid domain.");
    return;
  }

  const params = new URLSearchParams();
  const listLimit = parseBoundedInt(refs.listLimit.value || 20, { defaultValue: 20, min: 1, max: 200 });
  refs.listLimit.value = String(listLimit);
  params.set("limit", String(listLimit));
  const domain = refs.listDomain.value.trim().toLowerCase();
  const status = refs.listStatus.value.trim();
  if (domain) params.set("domain", domain);
  if (status) params.set("status", status);

  renderSkeleton(refs.sourceListResults, 2);
  setLoadingButton(refs.sourceListBtn, true, "Loading...", "Load Sources");

  try {
    const rows = await readJson(await fetch(`/sources?${params.toString()}`));
    renderSourceList(rows);
  } catch (err) {
    renderError(refs.sourceListResults, `Source list failed: ${err.message}`);
  } finally {
    setLoadingButton(refs.sourceListBtn, false, "Load Sources", "Load Sources");
  }
}

async function loadSourceDetail(sourceId) {
  renderSkeleton(refs.sourceDetailOutput, 1);
  try {
    const row = await readJson(await fetch(`/sources/${sourceId}`));
    renderSourceDetail(row);
  } catch (err) {
    renderError(refs.sourceDetailOutput, `Source detail failed: ${err.message}`);
  }
}

async function handleQuickSubmit(event) {
  event.preventDefault();
  const query = refs.quickQuery.value.trim();
  if (!query) {
    setGlobalBanner("Enter a query to continue.", "error");
    return;
  }
  if (query.length > MAX_QUERY_CHARS) {
    setGlobalBanner(`Query must be ${MAX_QUERY_CHARS} characters or less.`, "error");
    return;
  }

  setGlobalBanner("", "");

  if (state.activeTab === "ask") {
    await runAskQuery(query);
    return;
  }
  if (state.activeTab === "program") {
    await runProgramQuery(query);
    return;
  }
  await runSourceQuery(query);
}

async function runSignIn(event) {
  event.preventDefault();

  const email = refs.authEmail.value.trim();
  const password = refs.authPassword.value;
  if (!refs.authEmail.checkValidity() || !refs.authPassword.checkValidity()) {
    refs.authForm.reportValidity();
    setInlineMessage(refs.authMessage, "Enter a valid email and password.", "error");
    return;
  }
  if (!email || !password) {
    setInlineMessage(refs.authMessage, "Provide email and password.", "error");
    return;
  }

  setInlineMessage(refs.authMessage, "Signing in...", "");
  setLoadingButton(refs.signInBtn, true, "Signing In...", "Sign In");

  try {
    const payload = await readJson(
      await fetch("/auth/login", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ email, password }),
      }),
    );

    if (!payload.access_token) {
      throw new Error("missing_access_token");
    }
    setAuthToken(payload.access_token, payload.token_type || "bearer");
    state.currentUserEmail = email;
    const quotaResult = await loadQuota({ surfaceAuthError: true });
    if (!quotaResult.ok) {
      throw new Error("Unable to validate account quota after sign-in.");
    }
    setInlineMessage(refs.authMessage, "Signed in successfully.", "success");
    closeModal("auth");

    if (state.pendingAskQuery) {
      const queued = state.pendingAskQuery;
      state.pendingAskQuery = "";
      refs.quickQuery.value = queued;
      await runAskQuery(queued);
    }
  } catch (err) {
    setInlineMessage(refs.authMessage, `Sign in failed: ${err.message}`, "error");
  } finally {
    setLoadingButton(refs.signInBtn, false, "Sign In", "Sign In");
  }
}

async function runSignUp() {
  const email = refs.authEmail.value.trim();
  const password = refs.authPassword.value;
  if (!refs.authEmail.checkValidity() || !refs.authPassword.checkValidity()) {
    refs.authForm.reportValidity();
    setInlineMessage(refs.authMessage, "Enter a valid email and password.", "error");
    return;
  }
  if (!email || !password) {
    setInlineMessage(refs.authMessage, "Provide email and password.", "error");
    return;
  }

  setInlineMessage(refs.authMessage, "Creating account...", "");
  setLoadingButton(refs.signUpBtn, true, "Creating...", "Sign Up");

  try {
    const payload = await readJson(
      await fetch("/auth/signup", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ email, password }),
      }),
    );

    if (payload.access_token) {
      setAuthToken(payload.access_token, payload.token_type || "bearer");
      state.currentUserEmail = payload.email || email;
      setInlineMessage(refs.authMessage, "Account created and signed in.", "success");
      await loadQuota();
      closeModal("auth");

      if (state.pendingAskQuery) {
        const queued = state.pendingAskQuery;
        state.pendingAskQuery = "";
        refs.quickQuery.value = queued;
        await runAskQuery(queued);
      }
      return;
    }

    setInlineMessage(
      refs.authMessage,
      "Account created. Verify your email, then sign in.",
      "success",
    );
  } catch (err) {
    setInlineMessage(refs.authMessage, `Sign up failed: ${err.message}`, "error");
  } finally {
    setLoadingButton(refs.signUpBtn, false, "Sign Up", "Sign Up");
  }
}

function runSignOut() {
  clearAuthToken();
  state.currentUserEmail = "";
  state.askCanAsk = true;
  state.askContactUrl = "";
  refs.quotaBadge.classList.remove("exhausted");
  refs.quotaBadge.textContent = "Ask quota: sign in required";
  updateAuthUI();
  updateQuickInputForTab();
  closeUserMenu();
  setInlineMessage(refs.askGateMessage, "Sign in to use Ask Atlas. Free tier includes 5 lifetime asks.", "");
  renderEmpty(refs.askResults, "Sign in and submit a question to get a grounded answer.");
}

function handleTabClick(event) {
  const tabName = event.currentTarget.dataset.tab;
  setTab(tabName, false);
  refs.quickQuery.focus();
}

function handleTabKeydown(event) {
  const idx = refs.tabs.indexOf(event.currentTarget);
  if (idx < 0) return;

  if (event.key === "ArrowRight") {
    event.preventDefault();
    const next = (idx + 1) % refs.tabs.length;
    const tabName = refs.tabs[next].dataset.tab;
    setTab(tabName, true);
    return;
  }

  if (event.key === "ArrowLeft") {
    event.preventDefault();
    const prev = (idx - 1 + refs.tabs.length) % refs.tabs.length;
    const tabName = refs.tabs[prev].dataset.tab;
    setTab(tabName, true);
  }
}

function handleDocumentClick(event) {
  const target = event.target;
  if (!(target instanceof Element)) return;

  if (target.closest("[data-close-modal='auth']")) {
    closeModal("auth");
  }
  if (target.closest("[data-close-modal='status']")) {
    closeModal("status");
  }

  if (target.closest("#userMenuBtn")) {
    if (refs.userMenuPopup.classList.contains("hidden")) openUserMenu();
    else closeUserMenu();
    return;
  }

  if (!target.closest("#userMenu")) {
    closeUserMenu();
  }
}

function trapFocus(modal, event) {
  const focusables = Array.from(
    modal.querySelectorAll(
      "button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex='-1'])",
    ),
  );

  if (!focusables.length) return;

  const first = focusables[0];
  const last = focusables[focusables.length - 1];

  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
    return;
  }

  if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
}

function handleKeydown(event) {
  if (event.key === "Escape") {
    closeAllModals();
    closeUserMenu();
    return;
  }

  if (event.key === "Tab" && state.activeModal && !state.activeModal.classList.contains("hidden")) {
    trapFocus(state.activeModal, event);
  }
}

function bindEvents() {
  refs.quickQueryForm.addEventListener("submit", handleQuickSubmit);
  refs.sourceListForm.addEventListener("submit", loadSourceList);

  refs.tabs.forEach((tab) => {
    tab.addEventListener("click", handleTabClick);
    tab.addEventListener("keydown", handleTabKeydown);
  });

  refs.advancedToggle.addEventListener("click", () => {
    const isOpen = refs.askAdvanced.classList.contains("hidden");
    setAdvancedVisibility(isOpen);
  });

  refs.authActionBtn.addEventListener("click", () => {
    openModal("auth");
    setInlineMessage(refs.authMessage, "", "");
  });

  refs.authForm.addEventListener("submit", runSignIn);
  refs.signUpBtn.addEventListener("click", runSignUp);
  refs.signOutBtn.addEventListener("click", runSignOut);

  refs.openStatusBtn.addEventListener("click", () => {
    renderStatusBody();
    openModal("status");
  });

  document.addEventListener("click", handleDocumentClick);
  document.addEventListener("keydown", handleKeydown);

  window.addEventListener("resize", moveTabUnderline);
}

async function init() {
  bindEvents();
  setAdvancedVisibility(getAdvancedOpen());
  setTab("ask", false);
  renderEmpty(refs.askResults, "Sign in and submit a question to get a grounded answer.");
  renderEmpty(refs.programResults, "Search indexed programs from coaching sources.");
  renderEmpty(refs.sourceResults, "Search sources to inspect provenance.");
  renderEmpty(refs.sourceListResults, "Load sources by domain/status.");
  renderEmpty(refs.sourceDetailOutput, "Select a source to inspect details.");

  await loadTrustAndStatus();
  await loadQuota();
}

init();
