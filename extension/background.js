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

/** /submit 成功之后另一次调用；失败静默，绝不影响采集成功态。 */
async function prepareCoach(submissionId, problemId) {
  if (!submissionId && !problemId) return;
  try {
    const response = await fetch(
      `http://127.0.0.1:${bridgePort}/api/coach/prepare`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          submission_id: submissionId ? String(submissionId) : "",
          problem_id: problemId == null ? null : Number(problemId),
        }),
      }
    );
    if (!response.ok) {
      const text = await response.text();
      console.warn("[leetcode-tracker] prepare skipped", response.status, text);
      return;
    }
    const data = await response.json();
    console.info("[leetcode-tracker] prepare ok", {
      session_id: data.session_id,
      opening_source: data.opening_source,
      reused: data.reused,
    });
  } catch (error) {
    console.warn("[leetcode-tracker] prepare failed (ignored)", String(error));
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

async function notify(title, message, submissionId, problemId) {
  try {
    const notificationId = submissionId
      ? `coach:${submissionId}:${problemId || ""}`
      : `evt:${Date.now()}`;
    await chrome.notifications.create(notificationId, {
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

async function openCoachPage(submissionId, problemId) {
  const base = await bridgeBase();
  const params = new URLSearchParams();
  if (submissionId) params.set("submission", String(submissionId));
  if (problemId != null) params.set("problem_id", String(problemId));
  const query = params.toString();
  const url = query ? `${base}/coach?${query}` : `${base}/coach`;
  await chrome.tabs.create({ url });
}

chrome.notifications.onClicked.addListener((notificationId) => {
  if (notificationId.startsWith("coach:")) {
    const [, submissionId, problemId] = notificationId.split(":");
    openCoachPage(submissionId, problemId || null).catch(() => {});
  }
});

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

  // 采集热路径唯一副作用：POST /submit。不在此调用 LLM / prepare / SSE。
  postSubmission(payload)
    .then(async (data) => {
      const isNew = data.created === true;
      const submissionId = String(
        data.submission_id || payload.submission_id || ""
      );
      const summary = `${payload.problem_id}. ${payload.title || "题目"} (${payload.status})`;
      await remember({ ok: true, summary, data });
      setBadge(isNew ? "ok" : "dup", "#0a7");
      clearBadgeLater();
      notify(
        isNew ? "提交已记录 · 点击打开陪练" : "已存在该提交 · 点击打开陪练",
        summary,
        submissionId,
        payload.problem_id
      );
      console.info("[leetcode-tracker] saved", {
        submission_id: submissionId,
        created: data.created,
      });
      // 先回包固定采集成功态。prepare 完全 fire-and-forget：
      // 勿 await，避免 MV3 SW 在长 LLM 调用期间被挂起/打断采集体感。
      sendResponse({ ok: true, data });
      void prepareCoach(submissionId, payload.problem_id);
    })
    .catch(async (error) => {
      const messageText = String(error.message || error);
      await remember({ ok: false, error: messageText, summary: payload?.title || "" });
      setBadge("!", "#c00");
      notify("投递失败", messageText, null, null);
      console.error("[leetcode-tracker] submit failed", messageText);
      sendResponse({ ok: false, error: messageText });
    });

  return true;
});
