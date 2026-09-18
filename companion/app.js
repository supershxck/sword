const RING_RADIUS = 42;
const RING_CIRCUMFERENCE = 2 * Math.PI * RING_RADIUS;

const els = {
  syncTime: document.getElementById("sync-time"),
  gpuInfo: document.getElementById("gpu-info"),
  gpuSync: document.getElementById("gpu-sync"),
  neglectBody: document.getElementById("neglect-body"),
  forgeDigest: document.getElementById("forge-digest"),
  forgeCards: document.getElementById("forge-cards"),
  sprintFill: document.getElementById("sprint-fill"),
  sprintLabel: document.getElementById("sprint-label"),
  dockerBody: document.getElementById("docker-body"),
  signalBody: document.getElementById("signal-body"),
};

function setRing(id, percent) {
  const value = document.querySelector(`#${id} .ring-value`);
  const pct = document.querySelector(`#${id} .gauge-pct`);
  const offset = RING_CIRCUMFERENCE * (1 - Math.min(100, Math.max(0, percent)) / 100);
  value.style.strokeDasharray = `${RING_CIRCUMFERENCE}`;
  value.style.strokeDashoffset = `${offset}`;
  pct.textContent = `${Math.round(percent)}%`;
}

function tierClass(tier) {
  return `tier-${tier || "cool"}`;
}

function esc(text) {
  return String(text ?? "")
    .replaceAll("&", "&")
    .replaceAll("<", "<")
    .replaceAll(">", ">");
}

function renderNeglect(items) {
  if (!items.length) {
    els.neglectBody.innerHTML = `<tr><td colspan="3" class="empty">No neglected targets in scan range.</td></tr>`;
    return;
  }
  els.neglectBody.innerHTML = items.map((item) => `
    <tr>
      <td class="${tierClass(item.tier)}">${esc(item.name)}</td>
      <td>${item.kind === "sprint" ? "SPRINT" : "REPO"}</td>
      <td class="${tierClass(item.tier)}">${item.days}d</td>
    </tr>
  `).join("");
}

function stageClass(stage) {
  const key = (stage || "").toLowerCase();
  if (key.includes("build")) return "building";
  if (key.includes("scope")) return "scoping";
  if (key.includes("review")) return "review";
  return "";
}

function renderForge(forge) {
  const slots = forge.slots_used || 0;
  const max = forge.slots_max || 10;
  const pct = max ? (slots / max) * 100 : 0;
  els.sprintFill.style.width = `${pct}%`;
  els.sprintLabel.textContent = `SPRINT LOAD ${slots}/${max}`;
  const lines = forge.digest_lines || [];
  els.forgeDigest.innerHTML = lines.map((line) => `
    <div class="digest-line ${line.startsWith("ORIENTATION") ? "orientation" : ""}">${esc(line)}</div>
  `).join("");
  const cards = forge.active_cards || [];
  if (!cards.length) {
    els.forgeCards.innerHTML = `<div class="empty">No active pipeline cards.</div>`;
    return;
  }
  els.forgeCards.innerHTML = cards.slice(0, 6).map((card) => `
    <article class="forge-card ${stageClass(card.stage)}">
      <h3>\u25b8 ${esc(card.name)} <span class="tier-warm">\u00b7 ${esc(card.stage)}</span></h3>
      <p>${esc(card.goal)}</p>
    </article>
  `).join("");
}

function renderDocker(containers) {
  if (!containers.length) {
    els.dockerBody.innerHTML = `<tr><td colspan="3" class="empty">No active containers</td></tr>`;
    return;
  }
  els.dockerBody.innerHTML = containers.map((c) => `
    <tr>
      <td>${esc(c.name)}</td>
      <td>${esc(c.image)}</td>
      <td>${esc(c.status)}</td>
    </tr>
  `).join("");
}

function renderSignals(signals) {
  if (!signals.length) {
    els.signalBody.innerHTML = `<tr><td colspan="3" class="empty">No markdown signals detected</td></tr>`;
    return;
  }
  els.signalBody.innerHTML = signals.map((f) => `
    <tr>
      <td>${esc(f.modified)}</td>
      <td>${esc(f.name)}</td>
      <td>${esc(f.path)}</td>
    </tr>
  `).join("");
}

function renderStatus(data) {
  const sys = data.system || {};
  setRing("cpu-gauge", sys.cpu_percent || 0);
  setRing("ram-gauge", sys.mem_percent || 0);
  setRing("disk-gauge", sys.disk_percent || 0);
  document.querySelector("#ram-gauge .gauge-sub").textContent =
    `${sys.mem_used_gb || 0}/${sys.mem_total_gb || 0}G`;
  document.querySelector("#disk-gauge .gauge-sub").textContent =
    `${sys.disk_used_gb || 0}/${sys.disk_total_gb || 0}G`;
  els.gpuInfo.textContent = sys.gpu_info || "unavailable";
  els.gpuSync.textContent = `SYNC ${sys.timestamp || "--:--:--"}`;
  els.syncTime.textContent = new Date(data.timestamp || Date.now()).toLocaleString();
  renderNeglect(data.neglect || []);
  renderForge(data.forge || {});
  renderDocker(data.docker || []);
  renderSignals(data.signals || []);
}

async function refresh() {
  try {
    const res = await fetch("/api/status", { cache: "no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    renderStatus(await res.json());
  } catch (err) {
    els.syncTime.textContent = `link fault: ${err.message}`;
  }
}

refresh();
setInterval(refresh, 5000);
