async function getBridgeBase() {
  // Prefer common default; future: sync from storage if needed.
  return "http://127.0.0.1:8763";
}

async function setBadge(text, color) {
  try {
    await chrome.action.setBadgeText({ text: text || "" });
    if (color) await chrome.action.setBadgeBackgroundColor({ color });
  } catch {
    // ignore
  }
}

async function clearBadgeLater() {
  chrome.alarms.create("clear-badge", { delayInMinutes: 0.25 });
}

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === "clear-badge") setBadge("", "#000000");
});

async function remember(event) {
  await chrome.storage.local.set({ lastEvent: { ...event, at: Date.now() } });
}

async function notify(title, message) {
  try {
    await chrome.notifications.create({
      type: "basic",
      iconUrl: "icons/icon128.png",
      title,
      message,
      priority: 1,
    });
  } catch (err) {
    console.warn("[leetcode-tracker] notification failed", err);
  }
}

async function postSubmission(payload) {
  const base = await getBridgeBase();
  const response = await fetch(`${base}/submit`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const text = await response.text();
  let data = null;
  try {
    data = JSON.parse(text);
  } catch {
    data = { message: text };
  }
  if (!response.ok) {
    const err = new Error(data?.message || `HTTP ${response.status}`);
    err.status = response.status;
    throw err;
  }
  return data;
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (!message || message.type !== "submission") return;

  const payload = message.payload;
  postSubmission(payload)
    .then(async (data) => {
      await setBadge(data?.created === false ? "dup" : "ok", "#0a7");
      clearBadgeLater();
      const summary = `${payload.problem_id}. ${payload.title} (${payload.status})`;
      await remember({ ok: true, summary, data });
      await notify(
        data?.created === false ? "已存在该提交" : "提交已记录",
        summary
      );
      sendResponse({ ok: true, data });
    })
    .catch(async (err) => {
      await setBadge("!", "#c00");
      await remember({
        ok: false,
        error: String(err.message || err),
        summary: payload?.title || "",
      });
      await notify(
        "投递失败",
        `${err.message || err}。请先运行 leetcode-tracker serve 或 app`
      );
      sendResponse({ ok: false, error: String(err.message || err) });
    });

  return true;
});
