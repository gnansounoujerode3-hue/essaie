const $ = (s) => document.querySelector(s);
const $$ = (s) => Array.from(document.querySelectorAll(s));

let state = { skills: [], renders: [], specs: [], jobs: [] };

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[c]));
}

function mdToHtml(md) {
  // Rendu markdown minimal (titres, listes, tableaux, code, gras, italique)
  const lines = String(md || "").split("\n");
  let html = "", inCode = false, inTable = false, listType = null;
  const inline = (t) => esc(t)
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/(^|\s)\*([^*\n]+)\*/g, "$1<em>$2</em>");
  const closeList = () => { if (listType) { html += `</${listType}>`; listType = null; } };
  const closeTable = () => { if (inTable) { html += "</tbody></table>"; inTable = false; } };

  for (let i = 0; i < lines.length; i++) {
    const raw = lines[i];
    if (raw.trim().startsWith("```")) {
      if (inCode) { html += "</code></pre>"; inCode = false; }
      else { closeList(); closeTable(); html += "<pre><code>"; inCode = true; }
      continue;
    }
    if (inCode) { html += esc(raw) + "\n"; continue; }
    if (/^\s*\|/.test(raw)) {
      const cells = raw.trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim());
      if (/^[\s|:-]+$/.test(raw)) continue;
      if (!inTable) {
        closeList();
        html += "<table><thead><tr>" + cells.map((c) => `<th>${inline(c)}</th>`).join("") + "</tr></thead><tbody>";
        inTable = true;
      } else {
        html += "<tr>" + cells.map((c) => `<td>${inline(c)}</td>`).join("") + "</tr>";
      }
      continue;
    }
    closeTable();
    const h = raw.match(/^(#{1,6})\s+(.*)$/);
    if (h) { closeList(); html += `<h${h[1].length}>${inline(h[2])}</h${h[1].length}>`; continue; }
    if (/^\s*[-*]\s+/.test(raw)) {
      if (listType !== "ul") { closeList(); html += "<ul>"; listType = "ul"; }
      html += `<li>${inline(raw.replace(/^\s*[-*]\s+/, ""))}</li>`;
      continue;
    }
    if (/^\s*\d+\.\s+/.test(raw)) {
      if (listType !== "ol") { closeList(); html += "<ol>"; listType = "ol"; }
      html += `<li>${inline(raw.replace(/^\s*\d+\.\s+/, ""))}</li>`;
      continue;
    }
    if (/^\s*>\s?/.test(raw)) { closeList(); html += `<blockquote>${inline(raw.replace(/^\s*>\s?/, ""))}</blockquote>`; continue; }
    if (!raw.trim()) { closeList(); continue; }
    closeList();
    html += `<p>${inline(raw)}</p>`;
  }
  closeList(); closeTable();
  if (inCode) html += "</code></pre>";
  return html;
}

async function load() {
  const res = await fetch("/api/state");
  state = await res.json();
  renderRenders();
  renderSkills();
  renderSpecs();
  $("#skills-count").textContent = `${state.skills.length} disponibles`;
  $("#env").textContent = `${state.renders.length} rendu(s) · ${state.specs.length} spec(s)`;
  if (state.jobs.some((j) => j.status === "running")) setTimeout(load, 2500);
}

function renderRenders() {
  const box = $("#renders");
  if (!state.renders.length) {
    box.innerHTML = `<p class="hint">Aucun rendu pour l'instant. Onglet « Rendre » pour produire un Short.</p>`;
    return;
  }
  box.innerHTML = state.renders.map((r) => `
    <div class="render" data-url="${esc(r.url)}" data-name="${esc(r.name)}" data-slug="${esc(r.slug)}">
      ${r.thumb ? `<img src="${esc(r.thumb)}" alt="">` : `<div class="ph">▶</div>`}
      ${r.qa ? `<span class="badge ${esc(r.qa.grade)}">${r.qa.score}</span>` : ""}
      <div class="name">${esc(r.slug)}</div>
    </div>`).join("");
  $$(".render").forEach((el) => el.addEventListener("click", () => selectRender(el)));
}

function selectRender(el) {
  const url = el.dataset.url, name = el.dataset.name, slug = el.dataset.slug;
  $("#player").src = url;
  $("#player-empty").classList.add("hide");
  $("#m-title").textContent = slug;
  const item = state.renders.find((r) => r.name === name);
  $("#m-duration").textContent = item && item.duration ? `${item.duration.toFixed(1)} s` : "—";
  $("#m-format").textContent = item && item.width && item.height
    ? `${item.width} × ${item.height} · ${item.height / item.width === 16 / 9 ? "9:16" : "vidéo"}`
    : "1080 × 1920 · 9:16";
  $("#m-warn").textContent = item && item.warnings && item.warnings.length ? item.warnings.join(" · ") : "aucune";
  const qa = $("#qa");
  if (item && item.qa) {
    $("#m-score").textContent = `${item.qa.score}/100 (${item.qa.grade})`;
    qa.innerHTML = item.qa.checks.map((c) => `
      <div class="qa-item ${c.status}">
        <span class="ico">${c.status === "ok" ? "✅" : c.status === "warn" ? "⚠️" : "❌"}</span>
        <span>${esc(c.name)}</span>
        <span class="score">${c.score}</span>
        <span class="detail">${esc(c.detail)}${c.advice && c.status !== "ok" ? " — " + esc(c.advice) : ""}</span>
      </div>`).join("");
  } else {
    $("#m-score").textContent = "—";
    qa.innerHTML = `<p class="hint">Pas encore de rapport QA pour ce rendu. Lancez « qa » depuis la CLI ou re-rendez le spec.</p>`;
  }
}

function renderSkills() {
  $("#skills").innerHTML = state.skills.map((s) => `
    <div class="skill" data-id="${esc(s.id)}">
      <h3>${esc(s.name)}</h3>
      <p>${esc(s.description)}</p>
      <div class="tags">${(s.tags || []).map((t) => `<span class="tag">${esc(t)}</span>`).join("")}</div>
    </div>`).join("");
  $$(".skill").forEach((el) => el.addEventListener("click", () => showSkill(el.dataset.id)));
}

async function showSkill(id) {
  $$(".skill").forEach((e) => e.classList.toggle("sel", e.dataset.id === id));
  const res = await fetch(`/api/skill/${id}`);
  const s = await res.json();
  const box = $("#skill-detail");
  box.classList.add("show");
  box.innerHTML = `
    <h1>${esc(s.name)}</h1>
    <p style="color:#8b8b9e;margin-top:0">${esc(s.description)}</p>
    ${s.when_to_use ? `<p><em>${esc(s.when_to_use)}</em></p>` : ""}
    ${mdToHtml(s.body)}
    ${s.checklist && s.checklist.length ? `<h2>Checklist</h2><ul>${s.checklist.map((c) => `<li>${esc(c)}</li>`).join("")}</ul>` : ""}
  `;
  box.scrollIntoView({ behavior: "smooth", block: "start" });
}

function renderSpecs() {
  const sel = $("#spec-select");
  sel.innerHTML = state.specs.map((s) => `<option value="${esc(s.path)}">${esc(s.path)}</option>`).join("")
    || `<option value="">(aucun spec trouvé)</option>`;
}

$("#render-btn").addEventListener("click", async () => {
  const spec = $("#spec-select").value;
  const log = $("#render-log");
  if (!spec) { log.textContent = "Aucun spec disponible."; return; }
  const btn = $("#render-btn");
  btn.disabled = true;
  log.textContent = `Rendu de ${spec}…`;
  const res = await fetch("/api/render", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ spec }) });
  const job = await res.json();
  const poll = setInterval(async () => {
    const st = await (await fetch("/api/state")).json();
    const j = st.jobs.find((x) => x.id === job.id);
    if (!j) return;
    if (j.status === "running") { log.textContent = `Rendu en cours…\n${(j.log || []).join("\n")}`; return; }
    clearInterval(poll);
    btn.disabled = false;
    log.textContent = (j.log || []).join("\n") + (j.error ? `\n✖ ${j.error}` : "");
    load();
  }, 1200);
});

$("#refresh").addEventListener("click", load);
$$(".tab").forEach((t) => t.addEventListener("click", () => {
  $$(".tab").forEach((x) => x.classList.remove("active"));
  $$(".view").forEach((x) => x.classList.remove("active"));
  t.classList.add("active");
  $("#view-" + t.dataset.view).classList.add("active");
}));

load();
