(function () {
  const recentRelay = new Map();

  function relay(data) {
    try {
      // 必须带 response callback：否则 MV3 SW 可能在 /submit 完成前休眠，
      // 表现为 emit/relay 有日志但库无记录。仍只走单次 sendMessage，无双队列。
      chrome.runtime.sendMessage(data, (response) => {
        if (chrome.runtime.lastError) {
          console.warn(
            "[leetcode-tracker] relay lastError:",
            chrome.runtime.lastError.message
          );
          return;
        }
        if (response && response.ok === false) {
          console.warn("[leetcode-tracker] relay nack:", response.error || response);
        }
      });
    } catch (err) {
      console.warn("[leetcode-tracker] relay exception:", err);
    }
  }

  window.addEventListener("message", (event) => {
    if (event.source !== window) return;
    const data = event.data;
    if (!data || data.source !== "leetcode-tracker") return;

    if (data.type === "submission" && data.payload) {
      const sid = String(data.payload.submission_id || "");
      const now = Date.now();
      if (sid && now - (recentRelay.get(sid) || 0) < 8000) return;
      if (sid) recentRelay.set(sid, now);
      console.info("[leetcode-tracker] content relay submission", {
        submission_id: data.payload.submission_id,
        problem_id: data.payload.problem_id,
      });
      relay({ type: "submission", payload: data.payload });
      return;
    }

    if (data.type === "problem_context") {
      relay({ type: "problem_context", payload: data.payload });
    }
  });
})();
