const bridgeEl = document.getElementById("bridge");
const countEl = document.getElementById("count");
const lastEl = document.getElementById("last");
const debugEl = document.getElementById("debug");

async function refresh() {
  bridgeEl.textContent = "检测中…";
  bridgeEl.className = "";
  countEl.textContent = "—";

  try {
    const res = await fetch("http://127.0.0.1:8763/health", { method: "GET" });
    const data = await res.json();
    if (!res.ok || data.status !== "ok") {
      throw new Error(data.message || `HTTP ${res.status}`);
    }
    bridgeEl.textContent = "在线";
    bridgeEl.className = "ok";
    countEl.textContent = String(data.submissions_count ?? "—");
  } catch (err) {
    bridgeEl.textContent = "离线";
    bridgeEl.className = "bad";
    countEl.textContent = "—";
    console.warn(err);
  }

  const stored = await chrome.storage.local.get(["lastEvent", "lastDebug"]);
  const last = stored.lastEvent;
  if (!last) {
    lastEl.textContent = "最近一次：尚无记录（在题目页提交后会出现）";
  } else {
    const when = last.at ? new Date(last.at).toLocaleString() : "";
    if (last.ok) {
      lastEl.textContent = `最近一次成功：${last.summary || ""} ${when}`;
    } else {
      lastEl.textContent = `最近一次失败：${last.error || "unknown"} ${when}`;
    }
  }

  const dbg = stored.lastDebug;
  if (!dbg) {
    debugEl.textContent = "调试：尚无（请打开 leetcode.cn 题目页并刷新扩展后再提交）";
  } else {
    const when = dbg.at ? new Date(dbg.at).toLocaleString() : "";
    debugEl.textContent = `调试：${dbg.message} ${when}`;
  }
}

document.getElementById("refresh").addEventListener("click", refresh);
refresh();
