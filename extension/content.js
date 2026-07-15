(function () {
  function relay(data) {
    try {
      chrome.runtime.sendMessage(data);
    } catch {
      // extension context invalidated
    }
  }

  window.addEventListener("message", (event) => {
    if (event.source !== window) return;
    const data = event.data;
    if (!data || data.source !== "leetcode-tracker") return;
    if (data.type === "submission") {
      relay({ type: "submission", payload: data.payload });
    } else if (data.type === "debug") {
      relay({ type: "debug", message: data.message, extra: data.extra });
    }
  });

  // Probe: confirm isolated content script is alive on this page.
  relay({
    type: "debug",
    message: "content script alive",
    extra: { href: location.href },
  });
})();
