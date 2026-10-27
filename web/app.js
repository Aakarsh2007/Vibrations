"use strict";
// VibraLens UI (no build step). All text from the server is escaped before insertion.

const $ = (s, el = document) => el.querySelector(s);
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const uuid = () => (crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) + Math.random().toString(16).slice(2));
const fmt = (v, d = 2) => (v === null || v === undefined || Number.isNaN(v) ? "—" : Number(v).toFixed(d));

function store(k, v) { try { if (v === undefined) return localStorage.getItem(k); localStorage.setItem(k, v); } catch (_) { return null; } }

async function token() {
  let t = store("vl_token");
  if (t) return t;
  const r = await fetch("/api/workspaces", { method: "POST" });
  t = (await r.json()).workspace_token;
  store("vl_token", t);
  return t;
}

async function api(path, opts = {}) {
  const headers = { Authorization: "Bearer " + (await token()), ...(opts.headers || {}) };
  if (opts.body && typeof opts.body !== "string" && !(opts.body instanceof Blob)) {
    headers["Content-Type"] = "application/json"; opts.body = JSON.stringify(opts.body);
  }
  if (opts.idem) headers["Idempotency-Key"] = opts.idem;
  for (let attempt = 0; attempt < 3; attempt++) {
    let r;
    try { r = await fetch(path, { ...opts, headers }); } catch (e) { if (attempt === 2) throw new Error("Network problem. Check your connection and retry."); await sleep(800 * (attempt + 1)); continue; }
    if (r.status === 401 && attempt === 0) { store("vl_token", ""); headers.Authorization = "Bearer " + (await token()); continue; }
    if (r.status >= 500 && attempt < 2) { await sleep(800 * (attempt + 1)); continue; }
    const body = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(typeof body.detail === "string" ? body.detail : "Request failed (" + r.status + ")");
    return body;
  }
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function render(tplId) { const app = $("#app"); app.innerHTML = ""; app.appendChild($(tplId).content.cloneNode(true)); app.focus(); return app; }

// ---------------- routes ----------------
async function route() {
  const h = location.hash || "#/";
  if (h.startsWith("#/ws/")) {             // "continue on another device": token stays in the URL fragment (never sent to the server)
    store("vl_token", decodeURIComponent(h.slice(5).split("/")[0]));
    const rest = h.slice(5).split("/").slice(1).join("/");
    location.replace("#/" + rest);
    return;
  }
  try {
    if (h.startsWith("#/session/")) return await showSession(h.split("/")[2]);
    if (h.startsWith("#/new")) return await showNew(new URLSearchParams(h.split("?")[1] || ""));
    if (h.startsWith("#/asset/")) return await showAsset(h.split("/")[2]);
    return await showHome();
  } catch (e) { $("#app").innerHTML = `<div class="callout bad">${esc(e.message)} <button class="btn" onclick="route()">Retry</button></div>`; }
}
window.addEventListener("hashchange", route);

async function showHome() {
  render("#tpl-home");
  const [samples, assets] = await Promise.all([fetch("/api/samples").then((r) => r.json()).catch(() => []), api("/api/assets")]);
  $("#samples").innerHTML = samples.length ? samples.map((s) => `<button class="btn sample" data-s="${esc(s.name)}"><b>${esc(s.title)}</b><span>${esc(s.desc)}</span></button>`).join("") : `<p class="muted">No samples installed.</p>`;
  $("#samples").querySelectorAll("button").forEach((b) => b.onclick = async () => {
    b.disabled = true; b.querySelector("span").textContent = "Starting…";
    try { const r = await api(`/api/samples/${encodeURIComponent(b.dataset.s)}/run`, { method: "POST", idem: uuid() }); location.hash = "#/session/" + r.session_id; }
    catch (e) { b.disabled = false; b.querySelector("span").textContent = e.message; }
  });
  if (assets.length) $("#assets").innerHTML = "<ul>" + assets.map((a) => `<li><a href="#/asset/${esc(a.asset_id)}">${esc(a.name)}</a> <span class="muted small">${esc(a.machine_type.replace("_", " "))}</span></li>`).join("") + "</ul>";
}

async function showNew(params) {
  render("#tpl-new");
  const assets = await api("/api/assets");
  const sel = $("#asset-select");
  sel.innerHTML = `<option value="">+ New machine</option>` + assets.map((a) => `<option value="${esc(a.asset_id)}">${esc(a.name)}</option>`).join("");
  if (params.get("asset")) sel.value = params.get("asset");
  const toggle = () => { $("#new-asset").style.display = sel.value ? "none" : "block"; };
  sel.onchange = toggle; toggle();
  const form = $("#f-new");
  form.onsubmit = async (ev) => {
    ev.preventDefault();
    const fd = new FormData(form), status = $("#up-status"), btn = form.querySelector("button");
    const file = fd.get("file");
    if (!file || !file.size) return;
    btn.disabled = true;
    try {
      let assetId = sel.value;
      if (!assetId) {
        if (!fd.get("name")) throw new Error("Give the machine a name.");
        const num = (k) => (fd.get(k) ? Number(fd.get(k)) : null);
        const a = await api("/api/assets", { method: "POST", body: { name: fd.get("name"), machine_type: fd.get("machine_type"), coupling: fd.get("coupling"), rated_kw: num("rated_kw"), rated_rpm: num("rated_rpm"), support: fd.get("support") } });
        assetId = a.asset_id;
      }
      const uploadId = await upload(file, "video", (m) => (status.textContent = m));
      status.textContent = "Starting analysis…";
      const s = await api("/api/sessions", { method: "POST", idem: uuid(), body: { asset_id: assetId, upload_id: uploadId, point_id: fd.get("point_id") || "P1", view: "radial", marker_mm: Number(fd.get("marker_mm")) } });
      location.hash = "#/session/" + s.session_id;
    } catch (e) { status.textContent = e.message; btn.disabled = false; }
  };
}

async function upload(file, kind, onStatus) {
  const ct = file.type || (file.name.toLowerCase().endsWith(".mov") ? "video/quicktime" : "video/mp4");
  const t = await api("/api/uploads", { method: "POST", body: { kind, content_type: ct, size: file.size } });
  for (let attempt = 1; attempt <= 3; attempt++) {
    onStatus(`Uploading ${(file.size / 1048576).toFixed(1)} MB…` + (attempt > 1 ? ` (retry ${attempt - 1})` : ""));
    try {
      let r;
      if (t.method === "PUT") r = await fetch(t.url, { method: "PUT", headers: { "Content-Type": ct }, body: file });
      else { const fd = new FormData(); Object.entries(t.fields).forEach(([k, v]) => fd.append(k, v)); fd.append("file", file); r = await fetch(t.url, { method: "POST", body: fd }); }
      if (r.ok) return t.upload_id;
      if (r.status < 500) throw new Error("Upload rejected (" + r.status + "). Check the file type and size.");
    } catch (e) { if (attempt === 3) throw e; }
    await sleep(1000 * attempt);
  }
  throw new Error("Upload failed. Please retry.");
}

// ---------------- session ----------------
const STATES = [["UPLOADED", "Uploaded"], ["CAPTURE_ASSESSED", "Capture checked"], ["VALID_MEASUREMENT", "Measured"], ["DIAGNOSIS_READY", "Diagnosed"], ["COMPLETED", "Completed"]];
let pollTimer = null;

async function showSession(sid) {
  render("#tpl-session");
  $("#export-report").onclick = async () => {
    const button = $("#export-report");
    try {
      const report = await api(`/api/sessions/${encodeURIComponent(sid)}/report`);
      const url = URL.createObjectURL(new Blob([JSON.stringify(report, null, 2)], {type: "application/json"}));
      const link = document.createElement("a"); link.href = url; link.download = `vibralens-${sid}.json`; link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e) { button.textContent = "Export failed: " + e.message; }
  };
  clearTimeout(pollTimer);
  let delay = 1500, lastVersionKey = "";
  const tick = async () => {
    if (!location.hash.startsWith("#/session/" + sid)) return;
    try {
      const s = await api("/api/sessions/" + sid);
      const key = JSON.stringify([s.state, s.trace.length, s.busy, s.pending, s.work_order && s.work_order.status]);
      if (key !== lastVersionKey) { paintSession(s); lastVersionKey = key; }
      delay = s.busy ? 1500 : 5000;
    } catch (e) { $("#pending").innerHTML = `<div class="callout bad">${esc(e.message)} — retrying…</div>`; delay = Math.min(delay * 2, 15000); }
    pollTimer = setTimeout(tick, delay);
  };
  tick();
}

function stateBadge(s) {
  if (s.busy) return ["Working…", "s-info"];
  const map = { RECAPTURE_REQUIRED: ["Better recording needed", "s-warn"], ADDITIONAL_EVIDENCE_REQUIRED: ["Information needed", "s-warn"], HUMAN_APPROVAL_REQUIRED: ["Waiting for approval", "s-warn"], INCONCLUSIVE: ["Inconclusive", "s-bad"] };
  if (s.state === "COMPLETED") return [s.outcome === "inconclusive" ? "Completed: inconclusive" : "Completed", s.outcome === "inconclusive" ? "s-bad" : "s-ok"];
  return map[s.state] || [s.state.replace(/_/g, " ").toLowerCase(), "s-info"];
}

function paintSession(s) {
  const [label, cls] = stateBadge(s);
  const b = $("#s-badge"); b.textContent = label; b.className = "badge " + cls;
  const reached = new Set(s.trace.map((t) => t.state_after).concat([s.state]));
  if (s.diagnosis) reached.add("DIAGNOSIS_READY");
  if (s.measurement && s.measurement.result_class && s.measurement.result_class !== "INCONCLUSIVE") reached.add("VALID_MEASUREMENT");
  $("#timeline").innerHTML = STATES.map(([k, l]) => `<li class="${reached.has(k) ? "done" : ""}">${esc(l)}</li>`).join("") + (s.busy ? `<li class="now"><span class="spinner"></span> processing</li>` : "");
  paintPending(s);
  paintVerdict(s);
  paintDecisions(s);
}

function paintPending(s) {
  const el = $("#pending"); const p = s.pending;
  if (s.error) { el.innerHTML = `<div class="callout bad">${esc(s.error)}</div>`; return; }
  if (!p || s.busy) { el.innerHTML = s.busy ? `<p class="muted"><span class="spinner"></span> Measuring… a 10 s video takes about 30–60 s.</p>` : ""; return; }
  if (p.kind === "recapture") {
    el.innerHTML = `<div class="callout"><b>Please record again.</b><p>${esc(p.instruction)}</p>
      <label class="btn primary">Upload new recording<input type="file" accept="video/mp4,video/quicktime" hidden></label> <span class="muted small" role="status"></span>
      <p class="muted small">Requests used: ${s.recaptures} of 3.</p></div>`;
    const inp = el.querySelector("input"), st = el.querySelector("[role=status]");
    inp.onchange = async () => {
      try { const id = await upload(inp.files[0], "video", (m) => (st.textContent = m)); st.textContent = "Starting…";
        await api(`/api/sessions/${s.session_id}/evidence`, { method: "POST", idem: uuid(), body: { type: "video", upload_id: id } }); }
      catch (e) { st.textContent = e.message; }
    };
  } else if (p.kind === "ask") {
    el.innerHTML = `<div class="callout"><b>One question.</b><p>${esc(p.instruction)}</p>
      <form class="form row"><input name="rpm" type="number" min="60" max="30000" required placeholder="rpm" style="max-width:180px">
      <button class="btn primary">Continue</button><span class="muted small" role="status"></span></form></div>`;
    const f = el.querySelector("form");
    f.onsubmit = async (ev) => { ev.preventDefault(); try { await api(`/api/sessions/${s.session_id}/evidence`, { method: "POST", idem: uuid(), body: { type: "answer", answer: { rpm: Number(f.rpm.value) } } }); } catch (e) { f.querySelector("[role=status]").textContent = e.message; } };
  } else if (p.kind === "approval") {
    el.innerHTML = `<div class="callout info"><b>Work order drafted.</b> A supervisor has been asked to approve or reject it. Nothing is done to the machine automatically.</div>`;
  }
}

function classText(m, mode) {
  const c = m.result_class;
  const v = m.v_band_rms_mm_s, band = `${fmt(m.band_hz?.[0], 0)}–${fmt(m.band_hz?.[1], 0)} Hz`;
  if (c === "INCONCLUSIVE") return ["Inconclusive", "bad", (m.class_reasons || []).join("; ")];
  if (c === "BELOW_DETECTION_LIMIT") return ["Below detection limit", "info", mode === "absolute" ? `less than ${fmt(m.dl_mm_s)} mm/s at 1×` : "vibration too small to measure from this distance"];
  if (mode !== "absolute") return ["Measured (relative level)", "ok", `level index ${fmt(v)} (band ${band}); use it to compare recordings of the same setup`];
  if (c === "LOWER_BOUND") return ["Lower bound", "warn", `at least ${fmt(v)} mm/s RMS (${band})`];
  return ["Measured", "ok", `${fmt(v)} mm/s RMS ± ${fmt(m.uncertainty_pct, 0)}% (${band})`];
}

function paintVerdict(s) {
  const el = $("#verdict"); const m = s.measurement, q = s.quality, d = s.diagnosis, p = s.probe;
  if (!p) { el.innerHTML = `<h2>Result</h2><p class="muted">Waiting for the first check…</p>`; return; }
  let html = `<h2>Result</h2>`;
  if (p.timing_status === "UNRELIABLE") html += `<div class="callout bad"><b>Inconclusive: capture timing.</b> ${esc((p.reasons || []).join("; "))}</div>`;
  if (m) {
    const [title, tone, text] = classText(m, s.display_mode);
    html += `<div class="callout ${tone}"><b>${esc(title)}.</b> ${esc(text)}</div>`;
    html += `<div class="cols"><div><h3>Observed (measured by OpenCV)</h3><dl class="kv">
      <dt>Shaft frequency (1×)</dt><dd>${fmt(m.f1x_hz)} Hz = ${fmt(m.f1x_rpm, 0)} rpm <span class="muted small">(${esc(m.f1x_source)})</span></dd>
      <dt>1× displacement</dt><dd>${s.display_mode === "absolute" ? fmt((m.amp_mm || {})["1"] * 1000, 1) + " µm peak" : fmt(m.px_amp_1x, 3) + " px in the image"}</dd>
      <dt>Signal-to-noise (1×)</dt><dd>${fmt(m.snr_1x, 1)}</dd>
      <dt>Result class</dt><dd>${esc(m.result_class.replace(/_/g, " ").toLowerCase())}</dd>
      <dt>Timing</dt><dd>${esc(p.timing_status.toLowerCase())}, ${fmt(p.capture_fps, 0)} fps</dd>
      <dt>Measured band</dt><dd>${fmt(m.band_hz?.[0], 0)}–${fmt(m.band_hz?.[1], 0)} Hz (camera limit)</dd></dl></div>`;
    html += `<div><h3>Interpreted (screening)</h3>`;
    if (d) {
      html += `<dl class="kv"><dt>ISO 20816-3</dt><dd>${esc(d.iso.label)}</dd>
        <dt>Pattern</dt><dd>${esc(d.fault.pattern || "withheld: " + d.fault.withheld_reason)}${d.fault.confidence ? ` <span class="muted small">(${esc(d.fault.confidence)} confidence)</span>` : ""}</dd>
        <dt>Frequency confidence</dt><dd>${esc(d.confidence.frequency)}</dd></dl>`;
      if ((d.fault.evidence || []).length) html += `<ul class="small">${d.fault.evidence.map((e) => `<li>${esc(e)}</li>`).join("")}</ul>`;
    } else html += `<p class="muted">Not diagnosed yet.</p>`;
    html += `</div></div>`;
    if (m.spectrum) html += `<h3>Spectrum</h3><canvas id="spec" width="880" height="220" role="img" aria-label="Vibration spectrum with the 1x peak marked"></canvas>`;
  }
  if (s.comparison) {
    const c = s.comparison;
    html += `<h3>Compared with the previous recording</h3>` + (c.comparable
      ? `<div class="callout ${c.significant_increase ? "bad" : "ok"}">${c.significant_increase ? "<b>Significant increase.</b> " : "No significant increase. "}${esc((c.evidence || []).join(" · "))}<br><span class="small muted">Criterion: ${esc(c.criterion)}</span></div>`
      : `<div class="callout info"><b>Not comparable:</b> ${esc((c.not_comparable_reasons || []).join("; "))}</div>`);
  }
  if (q) {
    const checks = [["Marker found", !q.flags.includes("marker_lost")], ["Marker big enough", !q.flags.includes("marker_too_small")], ["Sharp", !q.flags.includes("blurry")], ["Light OK", !q.flags.includes("low_light")], ["Reference marker", !q.flags.includes("ref_missing") && !q.flags.includes("ref_vibrating")], ["Camera steady", !q.flags.includes("camera_shake")], ["Real slow motion", !q.flags.includes("duplicated_frames")]];
    html += `<h3>Recording quality</h3><ul class="checklist">${checks.map(([l, ok]) => `<li>${ok ? "✓" : "✗"} ${esc(l)}</li>`).join("")}</ul>`;
    if (q.reasons.length) html += `<ul class="small">${q.reasons.map((r) => `<li>${esc(r)}</li>`).join("")}</ul>`;
  }
  if (d) html += `<h3>Limitations</h3><ul class="small muted">${d.limitations.map((l) => `<li>${esc(l)}</li>`).join("")}</ul>`;
  if (s.work_order) html += `<h3>Work order</h3><p>Status: <b>${esc(s.work_order.status)}</b></p>` + ((s.work_order.audit || []).length ? `<p class="small muted">Decided by ${esc(s.work_order.audit[0].approver_name)}</p>` : "");
  html += `<p class="small muted">Evidence used: ${s.evidence_used.length} recording(s). Agent mode: ${esc(s.mode)}.</p>`;
  el.innerHTML = html;
  if (m && m.spectrum) drawSpectrum($("#spec"), m);
}

function drawSpectrum(cv, m) {
  if (!cv || !m.spectrum?.f?.length) return;
  const ctx = cv.getContext("2d"), W = cv.width, H = cv.height, pad = 34;
  const css = getComputedStyle(document.documentElement);
  const ink = css.getPropertyValue("--muted").trim(), brand = css.getPropertyValue("--brand").trim(), warn = css.getPropertyValue("--warn").trim();
  const f = m.spectrum.f, a = m.spectrum.amp_mm, fmax = f[f.length - 1], amax = Math.max(...a) * 1.1 || 1;
  ctx.clearRect(0, 0, W, H); ctx.strokeStyle = ink; ctx.fillStyle = ink; ctx.font = "12px system-ui";
  ctx.beginPath(); ctx.moveTo(pad, 6); ctx.lineTo(pad, H - pad); ctx.lineTo(W - 6, H - pad); ctx.stroke();
  for (let x = 0; x <= fmax; x += 20) { const px = pad + (x / fmax) * (W - pad - 6); ctx.fillText(String(x), px - 6, H - pad + 16); }
  ctx.fillText("Hz", W - 24, H - 6);
  const X = (v) => pad + (v / fmax) * (W - pad - 6), Y = (v) => H - pad - (v / amax) * (H - pad - 8);
  ctx.strokeStyle = brand; ctx.lineWidth = 1.5; ctx.beginPath();
  f.forEach((v, i) => (i ? ctx.lineTo(X(v), Y(a[i])) : ctx.moveTo(X(v), Y(a[i])))); ctx.stroke();
  [[1, "1×"], [2, "2×"], [3, "3×"]].forEach(([k, l]) => { const fx = k * m.f1x_hz; if (fx < fmax) { ctx.strokeStyle = warn; ctx.setLineDash([4, 4]); ctx.beginPath(); ctx.moveTo(X(fx), 6); ctx.lineTo(X(fx), H - pad); ctx.stroke(); ctx.setLineDash([]); ctx.fillStyle = warn; ctx.fillText(l, X(fx) + 3, 16); } });
}

function describe(t) {
  const reason = (t.input && t.input.reason_code) ? t.input.reason_code.replace(/_/g, " ") : "";
  const names = { probe_video: "Checked the video's real frame rate", check_capture_quality: "Checked recording quality", measure_vibration: "Measured the vibration", diagnose: "Interpreted the measurement", compare_readings: "Compared with the previous recording", request_recapture: "Asked for a new recording" + (reason ? ` (${reason})` : ""), ask_user: "Asked for the machine's rpm", draft_work_order: "Drafted a work order for human approval", finish: "Finished" + (t.input && t.input.outcome === "inconclusive" ? " (inconclusive)" : ""), user_evidence: "Received your new evidence" };
  return names[t.chosen] || t.chosen;
}

function paintDecisions(s) {
  $("#decisions").innerHTML = s.trace.map((t) => `<div class="decision"><div class="what">${t.step}. ${esc(describe(t))}</div>
    <div class="why">${t.note ? esc(t.note) + " · " : ""}state: ${esc((t.state_before || "").toLowerCase())} → ${esc((t.state_after || "").toLowerCase())}${t.allowed && t.allowed.length > 1 ? ` · options: ${esc(t.allowed.join(", "))}` : ""}${t.mode === "bedrock" ? " · decided by the AI assistant" : t.mode === "rules" ? " · rule planner" : ""}${t.error ? " · " + esc(t.error) : ""}</div></div>`).join("") || `<p class="muted">No decisions yet.</p>`;
  $("#trace").innerHTML = `<div class="tablewrap"><table><thead><tr><th>#</th><th>chosen</th><th>rule</th><th>mode</th><th>agreed</th><th>ms</th></tr></thead><tbody>${s.trace.map((t) => `<tr><td>${t.step}</td><td>${esc(t.chosen)}</td><td>${esc(t.rule_choice || "")}</td><td>${esc(t.mode)}</td><td>${t.agreed ? "yes" : "no"}</td><td>${t.latency_ms}</td></tr>`).join("")}</tbody></table></div>`;
}

async function showAsset(aid) {
  const r = await api("/api/assets/" + aid);
  const app = $("#app");
  const rows = r.readings.map((x) => `<tr><td>${new Date(x.ts * 1000).toLocaleString()}</td><td>${esc(x.point_id)} / ${esc(x.view)}</td><td>${fmt(x.measurement.f1x_hz)} Hz</td><td>${r.display_mode === "absolute" ? fmt(x.measurement.v_band_rms_mm_s) + " mm/s" : "Relative trend only"}</td><td>${esc(x.measurement.result_class)}</td><td><a href="#/session/${esc(x.session_id)}">open</a></td></tr>`).join("");
  app.innerHTML = `<section class="card"><h1>${esc(r.asset.name)}</h1><p class="muted">${esc(r.asset.machine_type.replace("_", " "))} · ${r.asset.rated_kw ?? "?"} kW · ${r.asset.rated_rpm ?? "?"} rpm</p>
    <a class="btn primary" href="#/new?asset=${esc(aid)}">New recording of this machine</a>
    <h2>History</h2><div class="tablewrap"><table><thead><tr><th>When</th><th>Point / view</th><th>1×</th><th>Band level</th><th>Class</th><th></th></tr></thead><tbody>${rows || "<tr><td colspan=6 class=muted>No readings yet.</td></tr>"}</tbody></table></div></section>`;
}

route();
