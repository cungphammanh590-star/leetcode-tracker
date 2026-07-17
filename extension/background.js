"use strict";

const DEFAULT_PORT = 8763;
let bridgePort = DEFAULT_PORT;

function getStorageArea() {
  try {
    if (chrome.storage && chrome.storage.session) {
      return chrome.storage.session;
    }
  } catch (_err) {
    // session storage unavailable in some builds
  }
  return chrome.storage.local;
}

async function getBridgeBase() {
  return `http://127.0.0.1:${bridgePort}`;
}

async function saveCoachLink(notificationId, url) {
  const store = getStorageArea();
  const key = "coachLinks";
  const stored = await store.get([key]);
  const links = stored[key] || {};
  links[notificationId] = url;
  await store.set({ [key]: links });
}

async function popCoachLink(notificationId) {
  const store = getStorageArea();
  const key = "coachLinks";
  const stored = await store.get([key]);
  const links = stored[key] || {};
  const url = links[notificationId];
  if (url) {
    delete links[notificationId];
    await store.set({ [key]: links });
  }
  return url || null;
}

async function refreshBridgeFromHealth() {
  const ports = [bridgePort, DEFAULT_PORT];
  for (const port of [...new Set(ports)]) {
    try {
      const res = await fetch(`http://127.0.0.1:${port}/health`);
      if (!res.ok) continue;
      const data = await res.json();
      if (data && data.port) {
        bridgePort = Number(data.port) || port;
      } else {
        bridgePort = port;
      }
      return data;
    } catch (_err) {
      // try next port
    }
  }
  return null;
}

chrome.runtime.onStartup.addListener(() => {
  refreshBridgeFromHealth().catch(() => {});
});
chrome.runtime.onInstalled.addListener(() => {
  refreshBridgeFromHealth().catch(() => {});
});

async function setBadge(text, color) {
  try {
    await chrome.action.setBadgeText({ text: text || "" });
    if (color) await chrome.action.setBadgeBackgroundColor({ color });
  } catch (_err) {
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

async function rememberProblemContext(payload) {
  if (!payload) return;
  await chrome.storage.local.set({
    currentProblem: { ...payload, at: Date.now() },
  });
}

async function notify(title, message, submissionId) {
  const notificationId = submissionId
    ? `coach-${submissionId}`
    : `evt-${Date.now()}`;
  if (submissionId) {
    const base = await getBridgeBase();
    await saveCoachLink(
      notificationId,
      `${base}/coach?submission=${encodeURIComponent(submissionId)}`
    );
  }
  try {
    await chrome.notifications.create(notificationId, {
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

chrome.notifications.onClicked.addListener(async (notificationId) => {
  const url = await popCoachLink(notificationId);
  if (!url) return;
  try {
    await chrome.tabs.create({ url });
  } catch (err) {
    console.warn("[leetcode-tracker] open coach tab failed", err);
  }
});

async function postSubmission(payload) {
  await refreshBridgeFromHealth();
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

async function engageCoach(submissionId) {
  try {
    const base = await getBridgeBase();
    await fetch(`${base}/api/coach/engage`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ submission_id: submissionId }),
    });
  } catch (err) {
    console.warn("[leetcode-tracker] coach engage failed", err);
  }
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (!message || !message.type) return false;

  if (message.type === "problem_context") {
    rememberProblemContext(message.payload)
      .then(() => sendResponse({ ok: true }))
      .catch((err) => sendResponse({ ok: false, error: String(err) }));
    return true;
  }

  if (message.type === "get_bridge_health") {
    refreshBridgeFromHealth()
      .then(async (data) => {
        const base = await getBridgeBase();
        sendResponse({ ok: Boolean(data), base, health: data });
      })
      .catch((err) => sendResponse({ ok: false, error: String(err) }));
    return true;
  }

  if (message.type === "get_current_problem") {
    chrome.storage.local
      .get(["currentProblem"])
      .then((stored) => sendResponse({ ok: true, problem: stored.currentProblem || null }))
      .catch((err) => sendResponse({ ok: false, error: String(err) }));
    return true;
  }

  if (message.type !== "submission") return false;

  const payload = message.payload;
  postSubmission(payload)
    .then(async (data) => {
      const isNew = data?.created === true;
      await setBadge(isNew ? "ok" : "dup", "#0a7");
      clearBadgeLater();
      const summary = `${payload.problem_id}. ${payload.title} (${payload.status})`;
      await remember({ ok: true, summary, data });
      if (isNew) {
        const sid = data.submission_id || payload.submission_id;
        engageCoach(sid);
        await notify("提交已记录 · 和陪练聊聊", `${summary}\n点击打开本机陪练页`, sid);
      } else {
        await notify("已存在该提交", summary);
      }
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
        `${err.message || err}。请先运行 leetcode-tracker serve`
      );
      sendResponse({ ok: false, error: String(err.message || err) });
    });

  return true;
});
