const AUTH_TOKEN_KEY = "atlas_auth_token";
const AUTH_TOKEN_TYPE = "atlas_auth_token_type";

function getAuthToken() {
  return localStorage.getItem(AUTH_TOKEN_KEY) || "";
}

function setAuthToken(token, tokenType = "bearer") {
  localStorage.setItem(AUTH_TOKEN_KEY, token);
  localStorage.setItem(AUTH_TOKEN_TYPE, tokenType);
}

function getAuthTokenType() {
  const tokenType = (localStorage.getItem(AUTH_TOKEN_TYPE) || "bearer").trim();
  if (!tokenType) return "Bearer";
  return `${tokenType.charAt(0).toUpperCase()}${tokenType.slice(1)}`;
}

function clearAuthToken() {
  localStorage.removeItem(AUTH_TOKEN_KEY);
  localStorage.removeItem(AUTH_TOKEN_TYPE);
}

function authHeaders(extra = {}) {
  const token = getAuthToken();
  if (!token) return extra;
  return { ...extra, Authorization: `${getAuthTokenType()} ${token}` };
}

async function readJson(response) {
  const text = await response.text();
  const parsed = text ? JSON.parse(text) : {};
  if (!response.ok) {
    const message = parsed.detail || parsed.status || `request_failed_${response.status}`;
    const err = new Error(typeof message === "string" ? message : JSON.stringify(message));
    err.payload = parsed;
    err.status = response.status;
    throw err;
  }
  return parsed;
}

function setOutput(id, value) {
  const node = document.getElementById(id);
  node.textContent = typeof value === "string" ? value : JSON.stringify(value, null, 2);
}

function setMessage(id, text, mode = "") {
  const node = document.getElementById(id);
  node.textContent = text || "";
  node.className = `inline-message${mode ? ` ${mode}` : ""}`;
}

function renderResults(containerId, rows, renderRow) {
  const container = document.getElementById(containerId);
  container.innerHTML = "";
  if (!rows.length) {
    const empty = document.createElement("div");
    empty.className = "result";
    empty.textContent = "No results.";
    container.appendChild(empty);
    return;
  }
  rows.forEach((row) => container.appendChild(renderRow(row)));
}

function summaryCard(label, value) {
  const card = document.createElement("div");
  card.className = "card";
  const k = document.createElement("div");
  k.className = "k";
  k.textContent = label;
  const v = document.createElement("div");
  v.className = "v";
  v.textContent = `${value}`;
  card.appendChild(k);
  card.appendChild(v);
  return card;
}

function refreshAuthDisplay(isSignedIn) {
  document.getElementById("authState").textContent = isSignedIn ? "Signed in" : "Not signed in";
  document.getElementById("askForm").style.display = isSignedIn ? "grid" : "none";
  setMessage(
    "askGateMessage",
    isSignedIn ? "" : "Sign in to use Ask Atlas. Free tier includes 5 lifetime asks.",
    isSignedIn ? "" : "error",
  );
}

async function loadSummary() {
  try {
    const data = await readJson(await fetch("/dashboard/summary"));
    const node = document.getElementById("summaryCards");
    node.innerHTML = "";
    node.appendChild(summaryCard("Domains", `${data.domains_total} (${data.allowlisted_domains} allowlisted)`));
    node.appendChild(summaryCard("Sources", `${data.sources_total} (${data.sources_pending} pending)`));
    node.appendChild(summaryCard("Programs", data.programs_total));
    node.appendChild(summaryCard("Recent Failures", `${data.recent_crawls_failed}/${data.recent_crawls_analyzed}`));
  } catch (err) {
    setOutput("askOutput", `Summary load failed: ${err.message}`);
  }
}

async function loadQuota() {
  const token = getAuthToken();
  const badge = document.getElementById("quotaBadge");
  if (!token) {
    badge.textContent = "Ask quota: sign in required";
    refreshAuthDisplay(false);
    return;
  }
  try {
    const data = await readJson(
      await fetch("/me/quota", {
        headers: authHeaders(),
      }),
    );
    badge.textContent = `Ask quota: ${data.used}/${data.limit} used (${data.remaining} left)`;
    refreshAuthDisplay(true);
    if (!data.can_ask) {
      setMessage(
        "askGateMessage",
        `Free ask quota reached. Contact: ${data.contact_url || "support"}`,
        "error",
      );
    }
  } catch (err) {
    if (err.status === 401) {
      clearAuthToken();
      refreshAuthDisplay(false);
      badge.textContent = "Ask quota: auth expired";
      return;
    }
    badge.textContent = "Ask quota: unavailable";
  }
}

async function runSignIn(event) {
  event.preventDefault();
  const email = document.getElementById("authEmail").value.trim();
  const password = document.getElementById("authPassword").value;
  setMessage("authMessage", "Signing in...");
  try {
    const data = await readJson(
      await fetch("/auth/login", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ email, password }),
      }),
    );
    setAuthToken(data.access_token, data.token_type || "bearer");
    setMessage("authMessage", "Signed in successfully.", "success");
    await loadQuota();
  } catch (err) {
    setMessage("authMessage", `Sign-in failed: ${err.message}`, "error");
  }
}

async function runSignUp() {
  const email = document.getElementById("authEmail").value.trim();
  const password = document.getElementById("authPassword").value;
  if (!email || !password) {
    setMessage("authMessage", "Provide email and password before signing up.", "error");
    return;
  }
  setMessage("authMessage", "Creating account...");
  try {
    const data = await readJson(
      await fetch("/auth/signup", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ email, password }),
      }),
    );
    if (data.access_token) {
      setAuthToken(data.access_token, data.token_type || "bearer");
      setMessage("authMessage", "Account created and signed in.", "success");
      await loadQuota();
      return;
    }
    setMessage(
      "authMessage",
      "Account created. Check your email for confirmation, then sign in.",
      "success",
    );
  } catch (err) {
    setMessage("authMessage", `Sign-up failed: ${err.message}`, "error");
  }
}

function runSignOut() {
  clearAuthToken();
  setMessage("authMessage", "Signed out.", "success");
  document.getElementById("quotaBadge").textContent = "Ask quota: sign in required";
  refreshAuthDisplay(false);
}

async function runAsk(event) {
  event.preventDefault();
  const token = getAuthToken();
  if (!token) {
    setMessage("askGateMessage", "Sign in required before asking.", "error");
    return;
  }
  const payload = {
    query: document.getElementById("askQuery").value.trim(),
    max_sources: 8,
    max_programs: 20,
    include_evidence: true,
    max_evidence: Number(document.getElementById("askMaxEvidence").value || 8),
    filters: {},
  };
  const domain = document.getElementById("askDomain").value.trim();
  if (domain) {
    payload.filters.domain = domain;
  }
  setOutput("askOutput", "Generating answer...");
  try {
    const data = await readJson(
      await fetch("/ask/answer", {
        method: "POST",
        headers: authHeaders({ "content-type": "application/json" }),
        body: JSON.stringify(payload),
      }),
    );
    setOutput("askOutput", data);
    setMessage("askGateMessage", "", "");
    await loadQuota();
  } catch (err) {
    if (err.payload && err.payload.status === "quota_exceeded") {
      const contact = err.payload.contact_url || "support";
      setMessage(
        "askGateMessage",
        `Free ask quota reached (used ${err.payload.used}/${err.payload.limit}). Contact: ${contact}`,
        "error",
      );
      setOutput("askOutput", err.payload);
      await loadQuota();
      return;
    }
    setOutput("askOutput", `Ask failed: ${err.message}`);
  }
}

async function runProgramSearch(event) {
  event.preventDefault();
  const params = new URLSearchParams();
  params.set("query", document.getElementById("programQuery").value.trim());
  params.set("limit", document.getElementById("programLimit").value);
  const domain = document.getElementById("programDomain").value.trim();
  if (domain) params.set("domain", domain);
  try {
    const rows = await readJson(await fetch(`/search/programs?${params.toString()}`));
    renderResults("programResults", rows, (row) => {
      const node = document.createElement("div");
      node.className = "result";
      node.innerHTML = `
        <div class="title">${row.name || "Unnamed Program"}</div>
        <div class="meta">program_id=${row.id} source_id=${row.source_id || "n/a"} confidence=${row.confidence ?? "n/a"}</div>
        <div class="meta">${row.canonical_url || ""}</div>
      `;
      return node;
    });
  } catch (err) {
    setOutput("askOutput", `Program search failed: ${err.message}`);
  }
}

async function runSourceSearch(event) {
  event.preventDefault();
  const params = new URLSearchParams();
  params.set("query", document.getElementById("sourceQuery").value.trim());
  params.set("limit", document.getElementById("sourceLimit").value);
  const domain = document.getElementById("sourceDomain").value.trim();
  if (domain) params.set("domain", domain);
  try {
    const rows = await readJson(await fetch(`/search/sources?${params.toString()}`));
    renderResults("sourceResults", rows, (row) => {
      const node = document.createElement("div");
      node.className = "result";
      node.innerHTML = `
        <div class="title">source_id=${row.id}</div>
        <div class="meta">${row.canonical_url}</div>
        <div class="meta">status=${row.status || "n/a"} last_crawled=${row.last_crawled_at || "n/a"}</div>
      `;
      return node;
    });
  } catch (err) {
    setOutput("askOutput", `Source search failed: ${err.message}`);
  }
}

async function loadSourceDetail(sourceId) {
  try {
    const data = await readJson(await fetch(`/sources/${sourceId}`));
    setOutput("sourceDetailOutput", data);
  } catch (err) {
    setOutput("sourceDetailOutput", `Source detail failed: ${err.message}`);
  }
}

async function runSourceList(event) {
  event.preventDefault();
  const params = new URLSearchParams();
  params.set("limit", document.getElementById("listLimit").value);
  const domain = document.getElementById("listDomain").value.trim();
  const status = document.getElementById("listStatus").value.trim();
  if (domain) params.set("domain", domain);
  if (status) params.set("status", status);
  try {
    const rows = await readJson(await fetch(`/sources?${params.toString()}`));
    renderResults("sourceListResults", rows, (row) => {
      const node = document.createElement("div");
      node.className = "result";
      node.innerHTML = `
        <div class="title">${row.title || "Untitled Source"}</div>
        <div class="meta">source_id=${row.id} domain=${row.domain || "n/a"} status=${row.status || "n/a"}</div>
        <div class="meta">${row.canonical_url}</div>
      `;
      const btn = document.createElement("button");
      btn.className = "btn btn-quiet";
      btn.type = "button";
      btn.textContent = "Inspect";
      btn.addEventListener("click", () => loadSourceDetail(row.id));
      node.appendChild(btn);
      return node;
    });
  } catch (err) {
    setOutput("sourceDetailOutput", `Source list failed: ${err.message}`);
  }
}

document.getElementById("authForm").addEventListener("submit", runSignIn);
document.getElementById("signUpBtn").addEventListener("click", runSignUp);
document.getElementById("signOutBtn").addEventListener("click", runSignOut);
document.getElementById("askForm").addEventListener("submit", runAsk);
document.getElementById("programForm").addEventListener("submit", runProgramSearch);
document.getElementById("sourceSearchForm").addEventListener("submit", runSourceSearch);
document.getElementById("sourceListForm").addEventListener("submit", runSourceList);
document.getElementById("refreshSummary").addEventListener("click", loadSummary);

refreshAuthDisplay(Boolean(getAuthToken()));
loadSummary();
loadQuota();
