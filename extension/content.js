(function () {
  function relay(data) {
    try {
      chrome.runtime.sendMessage(data);
    } catch {
      // ignore
    }
  }

  window.addEventListener("message", (event) => {
    if (event.source !== window) return;
    const data = event.data;
    if (!data || data.source !== "leetcode-tracker") return;
    if (data.type === "submission") {
      relay({ type: "submission", payload: data.payload });
    }
  });
})();
