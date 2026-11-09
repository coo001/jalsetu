"use strict";
// Vanilla JS. Shows a status line (not a spinner) while any fetch is pending.
const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
let pending = 0;
function setStatus(text) { const el = $("#status"); if (el) { el.textContent = text || ""; el.hidden = !text; } }
async function getJSON(url, label) {
  pending++; setStatus(label || "Loading…");
  try {
    const r = await fetch(url);
    const body = await r.json();
    if (!r.ok) throw Object.assign(new Error(body.detail || r.statusText), { status: r.status, body });
    return body;
  } finally { pending--; if (!pending) setStatus(""); }
}
const EXTREME_TEXT = "Very high value: check the unit entry with the testing lab. Ratio not verified.";
const fmt = (v) => (v === null || v === undefined ? "—" : v);
const badge = (s) => `<span class="st st-${esc(s)}">${esc(s)}</span>`;
const srcBadges = (item) => item.sources.map((s) => `<a class="src" href="${esc(s.url)}" target="_blank" rel="noopener" title="${esc(s.title)}">${esc(s.id)}</a>`).join(" ") + ` <span class="ref">${esc(item.ref)}</span>`;
function table(el, cols, rows) {
  el.innerHTML = `<thead><tr>${cols.map((c) => `<th>${esc(c[1])}</th>`).join("")}</tr></thead><tbody>` +
    rows.map((r) => `<tr>${cols.map((c) => `<td>${c[2] ? c[2](r) : esc(fmt(r[c[0]]))}</td>`).join("")}</tr>`).join("") + "</tbody>";
}
function fail(e) { setStatus(`Could not load: ${e.message}`); }

async function overview() {
  const d = await getJSON("/api/overview", "Loading overview…");
  $("#caption").textContent = d.caption;
  $("#by-state").innerHTML = Object.entries(d.by_state).map(([st, a]) => `<h3>${esc(a.name)} (${esc(st)})</h3><ul class="kv">
    <li><b>${a.records}</b> contaminated sample records (${Object.entries(a.by_param).map(([k, v]) => `${esc(k)} ${v}`).join(", ")})</li>
    <li><b>${a.villages}</b> villages in <b>${a.districts}</b> districts; <b>${a.l10_labs}</b> labs in this state's L10 list</li>
    <li>Packet status: ${Object.entries(a.by_status).map(([k, v]) => `${badge(k)} ${v}`).join(" ")}</li>
    <li class="muted">Retrieved ${esc(a.retrieved_utc)}</li></ul>`).join("") + `<p><a href="/queue">Open the queue →</a></p>`;
  const cols = ["State", "Fluoride", "Nitrate", "Total_Arsenic", "TotalEcoil", "TotalColiform", "Iron", "TDS"].map((k) => [k, k.replace("_", " ")]);
  table($("#states"), cols, d.states);
}

async function queue() {
  const rows = await getJSON("/api/samples", "Loading samples…");
  rows.forEach((r) => { const m = /^(\d\d)\/(\d\d)\/(\d{4}) (.*)$/.exec(r.tested || ""); r.tested_sort = m ? `${m[3]}${m[2]}${m[1]}${m[4]}` : ""; });
  const params = [...new Set(rows.map((r) => r.param))].sort();
  $("#f-param").innerHTML += params.map((p) => `<option>${esc(p)}</option>`).join("");
  let key = "ratio", dir = -1;
  function render() {
    const fst = $("#f-state").value, fs = $("#f-status").value, fp = $("#f-param").value;
    const shown = rows.filter((r) => (!fst || r.state === fst) && (!fs || r.status === fs) && (!fp || r.param === fp));
    shown.sort((a, b) => {
      const x = a[key], y = b[key];
      if (x === null || x === undefined) return 1; if (y === null || y === undefined) return -1;
      return (x < y ? -1 : x > y ? 1 : 0) * dir;
    });
    $("#count").textContent = `${shown.length} of ${rows.length} records`;
    $("#queue tbody").innerHTML = shown.map((r) => `<tr>
      <td>${esc(r.state)}</td><td><a href="/sample/${encodeURIComponent(r.record_id)}">${esc(r.sample_id || "(missing)")}</a></td>
      <td>${esc(r.village)}</td><td>${esc(r.district)}</td><td>${esc(r.param)}</td>
      <td>${esc(fmt(r.value))} / ${esc(fmt(r.permissible))} ${esc(r.unit || "")}</td>
      <td>${r.ratio === null ? "n/a" : esc(r.ratio.toFixed(2)) + "×"}${r.value_extreme ? `<br><span class="warn">${esc(EXTREME_TEXT)}</span>` : ""}</td><td>${esc(r.tested)}</td><td>${badge(r.status)}</td></tr>`).join("");
    document.querySelectorAll("#queue th").forEach((th) => { th.textContent = th.textContent.replace(/ [▲▼]$/, "") + (th.dataset.k === key ? (dir < 0 ? " ▼" : " ▲") : ""); });
  }
  document.querySelectorAll("#queue th").forEach((th) => th.addEventListener("click", () => { if (key === th.dataset.k) dir = -dir; else { key = th.dataset.k; dir = 1; } render(); }));
  $("#f-state").addEventListener("change", render); $("#f-status").addEventListener("change", render); $("#f-param").addEventListener("change", render);
  render();
}

function rawRecord(r) { return `<table class="raw">${Object.entries(r).map(([k, v]) => `<tr><th>${esc(k)}</th><td>${esc(v)}</td></tr>`).join("")}</table>`; }

async function sample() {
  $("#print").addEventListener("click", () => { fetch("/api/usage/print", { method: "POST" }).catch(() => {}); window.print(); });
  const rid = decodeURIComponent(location.pathname.split("/").pop());
  let p;
  try { p = await getJSON(`/api/packet/${encodeURIComponent(rid)}`, "Loading packet…"); }
  catch (e) {
    if (e.status === 409) { $("#packet").innerHTML = `<p>This sample id is listed under several parameters:</p><ul>${e.body.record_ids.map((x) => `<li><a href="/sample/${encodeURIComponent(x)}">${esc(x)}</a></li>`).join("")}</ul>`; return; }
    throw e;
  }
  const r = p.record, v = p.verdict;
  let h = `<h1>Sample ${esc(p.sample_id)} ${badge(p.status)}</h1>
    <p>${esc(r.state)} · ${esc(r.village)}, GP ${esc(r.gp)}, Block ${esc(r.block)}, District ${esc(r.district)} · ${esc(r.param)} · tested ${esc(r.tested)}</p>`;
  h += `<details class="trace noprint" open><summary>Agent trace (${p.trace.length} deterministic tool calls)</summary><ol>${p.trace.map((t) => `<li><code>${esc(t.tool)}</code> <span class="io">in: ${esc(JSON.stringify(t.input))}</span><br><span class="io">out: ${esc(JSON.stringify(t.output))}</span></li>`).join("")}</ol></details>`;
  if (v) {
    h += `<section><h2>Verdict vs IS 10500</h2><p class="verdict ${v.exceeds ? "bad" : ""}">${esc(v.param_display)} ${esc(v.value)} ${esc(v.unit)} ${v.exceeds ? "exceeds" : "does not exceed"} the permissible limit ${esc(v.permissible)} ${esc(v.unit)}${v.permissible_note ? ` (${esc(v.permissible_note)})` : ""}.
      ${v.ratio !== null ? `Ratio: <b>${esc(v.ratio.toFixed(2))}×</b>.` : "Ratio not applicable (limit is zero); count shown."}${p.warnings.some((w) => w.code === "VALUE_EXTREME") ? ` <span class="warn">${esc(EXTREME_TEXT)}</span>` : ""}</p>
      <p class="ref">Limit basis: ${esc(v.limit_ref)}</p></section>`;
  }
  if (p.warnings.length) h += `<p class="warn">Warnings: ${p.warnings.map((w) => `<b>${esc(w.code)}</b> ${esc(w.detail)}`).join("; ")}</p>`;
  if (p.status === "needs_review") {
    h += `<section class="review"><h2>Needs review: no advice or letter produced</h2><ul>${p.reasons.map((x) => `<li><b>${esc(x.code)}</b>: ${esc(x.detail)}</li>`).join("")}</ul><h3>Raw record</h3>${rawRecord(r)}</section>`;
    $("#packet").innerHTML = h; return;
  }
  h += `<section><h2>Candidate re-test labs (${p.labs.length} of ${p.labs_total})</h2><div class="limitbox">${esc(p.lab_limit_note)}</div>`;
  if (p.labs.length) h += `<ol class="labs">${p.labs.map((l) => `<li><b>${esc(l.name)}</b> <span class="muted">${esc(l.group)}</span><br><span class="muted">${esc(l.address)}</span><ul>${l.basis.map((b) => `<li>${esc(b)}</li>`).join("")}</ul></li>`).join("")}</ol>`;
  h += `</section>`;
  if (p.status === "ready") {
    h += `<section><h2>Officer actions</h2><ol class="advice">${p.officer_actions.map((a) => `<li>${esc(a.text)}<div>${srcBadges(a)}</div></li>`).join("")}</ol></section>
      <section><h2>Interim household advice</h2><ul class="advice">${p.household_advice.map((a) => `<li>${esc(a.text)}<div>${srcBadges(a)}</div></li>`).join("")}</ul></section>
      <section><h2>Re-test request letter (draft)</h2><p class="muted noprint">${esc(p.letter.method)}: ${esc(p.letter.llm_note)}</p><pre class="letter">${esc(p.letter.text)}</pre>
      <p class="fg ${p.fact_guard.passed ? "ok" : "bad"}">fact_guard: ${p.fact_guard.passed ? "passed (every number, sample id, lab and village matches the record)" : "FAILED: " + esc(p.fact_guard.reasons.join("; "))}</p></section>`;
  }
  $("#packet").innerHTML = h;
}

async function sources() {
  const d = await getJSON("/api/sources", "Loading sources…");
  table($("#src"), [["id", "ID"], ["title", "Edition / title"], ["url", "URL", (s) => `<a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.url)}</a>${(s.extra_urls || []).map((x) => `<br><a href="${esc(x.url)}">${esc(x.label)}</a> (${esc(x.note)})`).join("")}${s.consolidated_copy ? `<br><a href="${esc(s.consolidated_copy.url)}">consolidated copy</a>: ${esc(s.consolidated_copy.title)} (sha256 <code>${esc(s.consolidated_copy.sha256_16)}</code>; ${esc(s.consolidated_copy.note)})` : ""}${s.amendment_1 ? `<br>Amendment No.1 (${esc(s.amendment_1.date)}): “${esc(s.amendment_1.text)}” (<a href="${esc(s.amendment_1.scan_url)}">scan</a>; ${esc(s.amendment_1.note)})` : ""}`], ["sha256_16", "sha256 (first 16)", (s) => `<code>${esc(s.sha256_16 || "web page, not hashed")}</code>`]], d.sources);
  table($("#lim"), [["display", "Parameter"], ["names", "Names in data", (l) => esc(l.names.join(", "))], ["unit", "Unit"], ["acceptable", "Acceptable"], ["permissible", "Permissible", (l) => esc(l.permissible) + (l.permissible_note ? ` (${esc(l.permissible_note)})` : "")], ["ref", "Ref"]], Object.values(d.limits));
  table($("#lines"), [["id", "ID"], ["kind", "Kind"], ["text", "Text"], ["source_ids", "Sources", (l) => esc(l.source_ids.join(", "))], ["ref", "Ref"], ["id", "Used for", (l) => esc(Object.entries(d.mapping).filter(([, ids]) => ids.includes(l.id)).map(([k]) => k).join(", "))]], d.lines);
}

async function evaluation() {
  let d;
  try { d = await getJSON("/api/eval/latest", "Loading results…"); }
  catch (e) { setStatus(e.status === 404 ? "No evaluation results yet. Run `make eval`." : `Could not load: ${e.message}`); return; }
  $("#meta").innerHTML = `<p class="muted">Run ${esc(d.timestamp_utc)} · commit ${esc(d.git_commit)} · <code>${esc(d.command)}</code> · snapshot ${esc(d.snapshot)}</p>`;
  table($("#ev"), [["id", "ID"], ["name", "Check"], ["target", "Target"], ["measured", "Measured"], ["passed", "Met target", (r) => (r.passed ? "yes" : "<b>no</b>")], ["note", "Note"]], d.summary);
}

async function counters() {
  const el = $("#usage");
  if (!el) return;
  try {
    const u = await (await fetch("/api/stats")).json();
    const rows = Object.entries(u.counters || {}).flatMap(([day, c]) => Object.entries(c).map(([k, n]) => ({ day, k, n })));
    el.innerHTML = `<p class="notice">${esc(u.note)}</p><p class="muted">Since ${esc(u.since_utc)} (UTC)${u.enabled ? "" : " · counting disabled"}</p>` +
      (rows.length ? `<table>${["<tr><th>Date (UTC)</th><th>Counter</th><th>Count</th></tr>", ...rows.map((r) => `<tr><td>${esc(r.day)}</td><td>${esc(r.k)}</td><td>${esc(r.n)}</td></tr>`)].join("")}</table>` : "<p class='muted'>No counted events yet.</p>");
  } catch (e) { el.textContent = `Could not load counters: ${e.message}`; }
}

const pages = { overview, queue, sample, sources, eval: () => Promise.all([evaluation(), counters()]) };
const fn = pages[document.body.dataset.page];
if (fn) fn().catch(fail);
