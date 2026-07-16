const BRIDGE_BASE = "http://127.0.0.1:8763";

const bridgeEl = document.getElementById("bridge");
const countEl = document.getElementById("count");
const lastEl = document.getElementById("last");
const dashboardBtn = document.getElementById("open-dashboard");

let bridgeOnline = false;

function setDashboardEnabled(online) {
  bridgeOnline = online;
  dashboardBtn.disabled = !online;
  dashboardBtn.title = online
    ? "在新标签页打开本机仪表盘"
    : "本机桥接离线，请先启动 App 或 leetcode-tracker serve";
}

async function refresh() {
  bridgeEl.textContent = "检测中…";
  bridgeEl.className = "";
  countEl.textContent = "—";
  setDashboardEnabled(false);

  try {
    const res = await fetch(`${BRIDGE_BASE}/health`);
    const data = await res.json();
    if (!res.ok || data.status !== "ok") throw new Error(data.message || res.status);
    bridgeEl.textContent = "在线";
    bridgeEl.className = "ok";
    countEl.textContent = String(data.submissions_count ?? "—");
    setDashboardEnabled(true);
  } catch (err) {
    bridgeEl.textContent = "离线";
    bridgeEl.className = "bad";
    setDashboardEnabled(false);
  }

  const stored = await chrome.storage.local.get(["lastEvent"]);
  const last = stored.lastEvent;
  if (!last) {
    lastEl.textContent = "最近一次：尚无记录";
    return;
  }
  const when = last.at ? new Date(last.at).toLocaleString() : "";
  lastEl.textContent = last.ok
    ? `最近一次成功：${last.summary || ""} ${when}`
    : `最近一次失败：${last.error || "unknown"} ${when}`;
}

dashboardBtn.addEventListener("click", async () => {
  if (!bridgeOnline) return;
  await chrome.tabs.create({ url: `${BRIDGE_BASE}/` });
});

document.getElementById("refresh").addEventListener("click", refresh);
refresh();
