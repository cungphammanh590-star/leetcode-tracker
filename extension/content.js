(function () {
  const recentRelay = new Map();

  function relay(data) {
    try {
      // v0.2 经过实际使用验证的路径：只转发，不等待 background 回包。
      chrome.runtime.sendMessage(data);
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
