"use strict";

const DEFAULT_PORT = 8763;
let bridgePort = DEFAULT_PORT;

console.info("[leetcode-tracker] background loaded", {
  version: chrome.runtime.getManifest().version,
});

async function bridgeBase() {
  return `http://127.0.0.1:${bridgePort}`;
}

async function refreshBridge() {
  try {
    const response = await fetch(`http://127.0.0.1:${DEFAULT_PORT}/health`);
    if (!response.ok) return null;
    const health = await response.json();
    bridgePort = Number(health.port) || DEFAULT_PORT;
    return health;
  } catch (_error) {
    return null;
  }
}

async function postSubmission(payload) {
  const post = async (port) => {
    const response = await fetch(`http://127.0.0.1:${port}/submit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const text = await response.text();
    let data;
    try {
      data = JSON.parse(text);
    } catch {
      data = { message: text };
    }
    if (!response.ok) {
      throw new Error(data.message || `HTTP ${response.status}`);
    }
    return data;
  };

  try {
    return await post(bridgePort);
  } catch (firstError) {
    const health = await refreshBridge();
    if (!health) throw firstError;
    return post(bridgePort);
  }
}

async function setBadge(text, color) {
  try {
    await chrome.action.setBadgeText({ text });
    await chrome.action.setBadgeBackgroundColor({ color });
  } catch (_error) {
    // Cosmetic only.
  }
}

function clearBadgeLater() {
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

async function notify(title, message) {
  try {
    await chrome.notifications.create({
      type: "basic",
      iconUrl: "icons/icon128.png",
      title,
      message,
      priority: 1,
    });
  } catch (_error) {
    // Notification permission or OS state must not affect capture.
  }
}

chrome.runtime.onStartup.addListener(() => {
  refreshBridge().catch(() => {});
});

chrome.runtime.onInstalled.addListener(() => {
  refreshBridge().catch(() => {});
});

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (!message || !message.type) return false;

  if (message.type === "get_bridge_health") {
    refreshBridge()
      .then(async (health) => {
        sendResponse({
          ok: Boolean(health),
          base: await bridgeBase(),
          health,
        });
      })
      .catch((error) => sendResponse({ ok: false, error: String(error) }));
    return true;
  }

  if (message.type === "get_current_problem") {
    chrome.storage.local
      .get(["currentProblem"])
      .then((stored) =>
        sendResponse({ ok: true, problem: stored.currentProblem || null })
      )
      .catch((error) => sendResponse({ ok: false, error: String(error) }));
    return true;
  }

  if (message.type === "problem_context") {
    chrome.storage.local
      .set({ currentProblem: { ...message.payload, at: Date.now() } })
      .then(() => sendResponse({ ok: true }))
      .catch((error) => sendResponse({ ok: false, error: String(error) }));
    return true;
  }

  if (message.type !== "submission") return false;

  const payload = message.payload;
  console.info("[leetcode-tracker] background received", {
    submission_id: payload?.submission_id,
    problem_id: payload?.problem_id,
  });

  // This is deliberately the only capture side effect:
  // content message -> bridge /submit -> SQLite. No coach, queue, or LLM work.
  postSubmission(payload)
    .then(async (data) => {
      const isNew = data.created === true;
      const summary = `${payload.problem_id}. ${payload.title || "题目"} (${payload.status})`;
      await remember({ ok: true, summary, data });
      setBadge(isNew ? "ok" : "dup", "#0a7");
      clearBadgeLater();
      notify(isNew ? "提交已记录" : "已存在该提交", summary);
      console.info("[leetcode-tracker] saved", {
        submission_id: payload.submission_id,
        created: data.created,
      });
      sendResponse({ ok: true, data });
    })
    .catch(async (error) => {
      const messageText = String(error.message || error);
      await remember({ ok: false, error: messageText, summary: payload?.title || "" });
      setBadge("!", "#c00");
      notify("投递失败", messageText);
      console.error("[leetcode-tracker] submit failed", messageText);
      sendResponse({ ok: false, error: messageText });
    });

  return true;
});
