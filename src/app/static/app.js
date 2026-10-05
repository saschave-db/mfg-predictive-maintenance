// Plant Health Live: polls Lakebase-backed API every 2 s. No framework, no build step.
const PLANTS = { "PLT-N": "Plant North", "PLT-S": "Plant South", "PLT-E": "Plant East" };
const MODES = { press: ["seal_leak"], cnc_mill: ["bearing_wear", "overheating"], welder: ["overheating"],
                robot_arm: ["bearing_wear", "overheating"], conveyor: ["bearing_wear"] };
let stations = {}, selected = null, genieConv = null;

const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const pct = (p) => (p == null ? "–" : Math.round(p * 100) + "%");
async function api(path, opts = {}) {
  const r = await fetch(path, { headers: { "Content-Type": "application/json" }, ...opts });
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return r.json();
}

async function refresh() {
  try {
    const d = await api("/api/stations");
    stations = Object.fromEntries(d.stations.map((s) => [s.station_id, s]));
    renderPlants(d.stations);
    const c = { NORMAL: 0, ELEVATED: 0, HIGH: 0, DOWN: 0 };
    d.stations.forEach((s) => c[s.risk_band]++);
    $("#k-normal").textContent = `${c.NORMAL} normal`; $("#k-elevated").textContent = `${c.ELEVATED} elevated`;
    $("#k-high").textContent = `${c.HIGH} high risk`; $("#k-down").textContent = `${c.DOWN} down`;
    $("#fresh").textContent = `data age ${d.data_age_s ?? "–"} s · Lakebase ${d.lakebase_query_ms} ms`;
    if (selected) renderDetailHeader();
  } catch (e) { $("#fresh").textContent = "API error: " + e.message.slice(0, 60); }
}

function renderPlants(list) {
  const byLine = {};
  list.forEach((s) => (byLine[s.line_id] ??= []).push(s));
  let html = "";
  for (const [pid, pname] of Object.entries(PLANTS)) {
    html += `<div class="plant"><h2>${pname}</h2>`;
    for (const L of ["A", "B", "C", "D"]) {
      const lid = `${pid}-${L}`;
      html += `<div class="line"><div class="lbl">Line ${L}</div>`;
      for (const s of byLine[lid] || []) {
        html += `<div class="tile ${s.risk_band} ${s.station_id === selected ? "sel" : ""}" data-id="${s.station_id}"
                  title="${s.station_id} · ${s.station_type} · top signal ${s.top_signal}">
                  ${s.open_work_orders ? '<span class="wo">🔧</span>' : ""}
                  <div class="id">${s.station_id.slice(-3)}</div>
                  <div class="p">${s.risk_band === "DOWN" ? "DOWN" : pct(s.failure_probability)}</div>
                  <div class="t">${s.station_type.replace("_", " ")}</div></div>`;
      }
      html += "</div>";
    }
    html += "</div>";
  }
  $("#plants").innerHTML = html;
  document.querySelectorAll(".tile").forEach((t) => (t.onclick = () => select(t.dataset.id)));
}

async function select(id) {
  selected = id;
  document.querySelectorAll(".tile").forEach((t) => t.classList.toggle("sel", t.dataset.id === id));
  const s = stations[id];
  const modes = MODES[s.station_type] || [];
  $("#detail").innerHTML = `
    <div id="dh"></div>
    <svg class="spark" id="spark" viewBox="0 0 400 70" preserveAspectRatio="none"></svg>
    <div class="legend">last 15 min · <span style="color:#d6453d">■</span> failure probability · <span style="color:#1f6feb">■</span> ${esc(s.top_signal || "vibration_rms")} (relative)</div>
    <div class="row"><select id="mode">${modes.map((m) => `<option>${m}</option>`).join("")}</select>
      <button class="danger" id="b-inject">Inject fault</button></div>
    <div class="row"><select id="prio"><option>P1</option><option selected>P2</option><option>P3</option></select>
      <button id="b-wo">Create work order</button></div>
    <div class="row"><select id="wsensor">${["vibration_rms", "bearing_temp_c", "motor_current_a", "hydraulic_pressure_bar", "acoustic_db", "cycle_time_s"].map((x) => `<option>${x}</option>`).join("")}</select>
      <input id="wpct" type="number" value="25" style="width:70px">%
      <button class="secondary" id="b-whatif">What-if (Model Serving)</button></div>
    <div id="whatif-out" class="muted"></div>`;
  $("#b-inject").onclick = async () => {
    const r = await api("/api/inject", { method: "POST", body: JSON.stringify({ station_id: id, failure_mode: $("#mode").value }) });
    $("#whatif-out").textContent = `Fault command #${r.command_id} queued in Lakebase; the gateway simulator picks it up within ~2 s.`;
  };
  $("#b-wo").onclick = async () => {
    const r = await api("/api/work_orders", { method: "POST", body: JSON.stringify({ station_id: id, priority: $("#prio").value }) });
    $("#whatif-out").textContent = `Work order #${r.work_order_id} created (${r.priority}, risk ${pct(r.failure_probability)}).`;
    loadWOs();
  };
  $("#b-whatif").onclick = async () => {
    $("#whatif-out").textContent = "scoring…";
    const r = await api("/api/whatif", { method: "POST", body: JSON.stringify({ station_id: id, sensor: $("#wsensor").value, change_pct: +$("#wpct").value }) });
    $("#whatif-out").textContent = `${r.sensor} ${r.change_pct > 0 ? "+" : ""}${r.change_pct}% → ${pct(r.scenario_probability)} (now ${pct(r.current_probability)}) · ${r.endpoint} ${r.serving_latency_ms} ms`;
  };
  renderDetailHeader();
  loadHistory();
}

function renderDetailHeader() {
  const s = stations[selected];
  if (!s || !$("#dh")) return;
  $("#dh").innerHTML = `<h3>${s.station_id} · ${s.station_type.replace("_", " ")} <span class="badge ${s.risk_band}">${s.risk_band}</span></h3>
    <div class="row"><span class="big">${pct(s.failure_probability)}</span>
    <span class="muted">P(maintenance needed within horizon)<br>top signal: <b>${esc(s.top_signal)}</b> ${s.top_signal_deviation_pct ?? ""}% off nominal · criticality ${s.criticality}</span></div>
    <div class="muted">vibration ${(+s.avg_vibration_rms).toFixed(2)} mm/s · temp ${(+s.avg_bearing_temp_c).toFixed(1)} °C ·
      current ${(+s.avg_motor_current_a).toFixed(1)} A · pressure ${(+s.avg_hydraulic_pressure_bar).toFixed(0)} bar · window ${new Date(s.window_end).toLocaleTimeString()}</div>`;
}

async function loadHistory() {
  if (!selected) return;
  const id = selected;
  const d = await api(`/api/stations/${id}/history?minutes=15`);
  if (id !== selected || !$("#spark")) return;
  const pts = d.points;
  if (pts.length < 2) { $("#spark").innerHTML = ""; return; }
  const sig = "avg_" + (stations[id].top_signal || "vibration_rms");
  const t0 = new Date(pts[0].window_end), t1 = new Date(pts[pts.length - 1].window_end);
  const x = (p) => ((new Date(p.window_end) - t0) / Math.max(1, t1 - t0)) * 400;
  const vals = pts.map((p) => +p[sig] || 0), lo = Math.min(...vals), hi = Math.max(...vals);
  const line = (f, color) => `<polyline fill="none" stroke="${color}" stroke-width="2" points="${pts.map((p, i) => `${x(p).toFixed(1)},${(66 - f(p, i) * 62).toFixed(1)}`).join(" ")}"/>`;
  $("#spark").innerHTML = `<line x1="0" x2="400" y1="${66 - 0.7 * 62}" y2="${66 - 0.7 * 62}" stroke="#d6453d" stroke-dasharray="3 3" stroke-width="1" opacity=".5"/>`
    + line((p, i) => (hi > lo ? (vals[i] - lo) / (hi - lo) : 0.5), "#1f6feb")
    + line((p) => +p.failure_probability, "#d6453d");
}

async function loadWOs() {
  const list = await api("/api/work_orders?limit=12");
  $("#wos").innerHTML = list.length ? `<table><tr><th>#</th><th>station</th><th>prio</th><th>risk</th><th>status</th><th></th></tr>${list.map((w) =>
    `<tr><td>${w.work_order_id}</td><td>${w.station_id}</td><td>${w.priority}</td><td>${pct(+w.failure_probability)}</td><td>${w.status}</td>
     <td>${w.status !== "completed" ? `<button class="secondary" data-wo="${w.work_order_id}">complete</button>` : ""}</td></tr>`).join("")}</table>`
    : '<p class="muted">No work orders yet.</p>';
  document.querySelectorAll("[data-wo]").forEach((b) => (b.onclick = async () => {
    await api(`/api/work_orders/${b.dataset.wo}/complete`, { method: "POST" }); loadWOs();
  }));
}

$("#genie-form").onsubmit = async (e) => {
  e.preventDefault();
  const q = $("#genie-q").value.trim();
  if (!q) return;
  $("#genie-out").innerHTML = '<p class="muted">Genie is thinking…</p>';
  try {
    const r = await api("/api/genie", { method: "POST", body: JSON.stringify({ question: q, conversation_id: genieConv }) });
    genieConv = r.conversation_id;
    $("#genie-out").innerHTML = `<p>${esc(r.text || "")}</p>`
      + (r.rows.length ? `<table><tr>${r.columns.map((c) => `<th>${esc(c)}</th>`).join("")}</tr>${r.rows.slice(0, 12).map((row) => `<tr>${row.map((v) => `<td>${esc(v)}</td>`).join("")}</tr>`).join("")}</table>` : "")
      + (r.sql ? `<details><summary class="muted">SQL</summary><pre>${esc(r.sql)}</pre></details>` : "");
  } catch (err) { $("#genie-out").innerHTML = `<p class="muted">${esc(err.message)}</p>`; }
};

refresh(); loadWOs();
setInterval(refresh, 2000);
setInterval(loadHistory, 5000);
setInterval(loadWOs, 10000);
