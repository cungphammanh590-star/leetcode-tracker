const BRIDGE_URL = "http://127.0.0.1:8763/submit";
const HEALTH_URL = "http://127.0.0.1:8763/health";

async function setBadge(text, color) {
  try {
    await chrome.action.setBadgeText({ text: text || "" });
    if (color) {
      await chrome.action.setBadgeBackgroundColor({ color });
    }
    await chrome.action.setTitle({
      title: text ? `LeetCode Tracker: ${text}` : "LeetCode Tracker",
    });
  } catch {
    // ignore
  }
}

async function clearBadgeLater() {
  chrome.alarms.create("clear-badge", { delayInMinutes: 0.25 });
}

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === "clear-badge") {
    setBadge("", "#000000");
  }
});

async function remember(event) {
  await chrome.storage.local.set({
    lastEvent: { ...event, at: Date.now() },
  });
}

async function rememberDebug(message, extra) {
  await chrome.storage.local.set({
    lastDebug: { message, extra: extra || null, at: Date.now() },
  });
}

async function postSubmission(payload) {
  const response = await fetch(BRIDGE_URL, {
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
  if (!message) return;

  if (message.type === "debug") {
    console.info("[leetcode-tracker:debug]", message.message, message.extra || "");
    rememberDebug(message.message, message.extra);
    return;
  }

  if (message.type !== "submission") {
    return;
  }

  const payload = message.payload;
  console.log("[leetcode-tracker] captured submission", payload);

  postSubmission(payload)
    .then(async (data) => {
      console.log("[leetcode-tracker] saved", data);
      await setBadge(data?.created === false ? "dup" : "ok", "#0a7");
      clearBadgeLater();
      await remember({
        ok: true,
        summary: `${payload.problem_id}. ${payload.title} (${payload.status})`,
        data,
      });
      sendResponse({ ok: true, data });
    })
    .catch(async (err) => {
      console.error("[leetcode-tracker] bridge error", err);
      await setBadge("!", "#c00");
      await chrome.action.setTitle({
        title: `投递失败：${err.message || err}。请先运行 leetcode-tracker serve`,
      });
      await remember({
        ok: false,
        error: String(err.message || err),
        summary: payload?.title || "",
      });
      sendResponse({ ok: false, error: String(err.message || err) });
    });

  return true;
});

fetch(HEALTH_URL).catch(() => {});
