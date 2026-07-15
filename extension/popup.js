const bridgeEl = document.getElementById("bridge");
const countEl = document.getElementById("count");
const lastEl = document.getElementById("last");

async function refresh() {
  bridgeEl.textContent = "检测中…";
  bridgeEl.className = "";
  countEl.textContent = "—";

  try {
    const res = await fetch("http://127.0.0.1:8763/health");
    const data = await res.json();
    if (!res.ok || data.status !== "ok") throw new Error(data.message || res.status);
    bridgeEl.textContent = "在线";
    bridgeEl.className = "ok";
    countEl.textContent = String(data.submissions_count ?? "—");
  } catch (err) {
    bridgeEl.textContent = "离线";
    bridgeEl.className = "bad";
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

document.getElementById("refresh").addEventListener("click", refresh);
refresh();
