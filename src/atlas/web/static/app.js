async function readJson(response) {
  const text = await response.text();
  if (!response.ok) {
    throw new Error(text || `request_failed_${response.status}`);
  }
  return text ? JSON.parse(text) : {};
}

function setOutput(id, value) {
  const node = document.getElementById(id);
  node.textContent = typeof value === "string" ? value : JSON.stringify(value, null, 2);
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

async function runAsk(event) {
  event.preventDefault();
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
  try {
    const data = await readJson(
      await fetch("/ask/answer", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(payload),
      }),
    );
    setOutput("askOutput", data);
  } catch (err) {
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

document.getElementById("askForm").addEventListener("submit", runAsk);
document.getElementById("programForm").addEventListener("submit", runProgramSearch);
document.getElementById("sourceSearchForm").addEventListener("submit", runSourceSearch);
document.getElementById("sourceListForm").addEventListener("submit", runSourceList);
document.getElementById("refreshSummary").addEventListener("click", loadSummary);

loadSummary();
