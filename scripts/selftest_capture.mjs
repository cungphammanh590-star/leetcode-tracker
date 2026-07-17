#!/usr/bin/env node
/**
 * 自测：模拟力扣 submit+check，验证 inject 能 emit，且不弄坏 fetch body。
 * 用法：node scripts/selftest_capture.mjs
 * 需要本机 leetcode-tracker serve（8763）已启动。
 */
import { chromium } from "playwright";
import { readFileSync } from "fs";
import { fileURLToPath } from "url";
import { dirname, join } from "path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");
const INJECT = readFileSync(join(ROOT, "extension/inject.js"), "utf8");
const BRIDGE = "http://127.0.0.1:8763";
const SUBMISSION_ID = String(Date.now()); // 力扣 check URL 用数字 id

async function bridgeHealth() {
  const res = await fetch(`${BRIDGE}/health`);
  if (!res.ok) throw new Error(`bridge health HTTP ${res.status}`);
  return res.json();
}

async function main() {
  console.log("[selftest] checking bridge…");
  const health = await bridgeHealth();
  console.log("[selftest] bridge ok", {
    submissions_count: health.submissions_count,
    port: health.port,
  });

  const browser = await chromium.launch({
    headless: true,
    channel: "chrome",
  });
  const page = await browser.newPage();

  await page.route("**/*", async (route) => {
    const url = route.request().url();
    if (url.includes("/problems/maximum-subarray/submit")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ submission_id: SUBMISSION_ID }),
      });
      return;
    }
    if (url.includes(`/submissions/detail/${SUBMISSION_ID}/v2/check`) ||
        url.includes(`/submissions/detail/${SUBMISSION_ID}/check`)) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          state: "SUCCESS",
          status_code: 11,
          status_msg: "Wrong Answer",
          status_runtime: "12 ms",
          status_memory: "16.2 MB",
          lang: "python3",
        }),
      });
      return;
    }
    // 放行本机桥接页面与 health/submit
    if (url.startsWith("http://127.0.0.1:8763/")) {
      await route.continue();
      return;
    }
    await route.fulfill({ status: 204, body: "" });
  });

  const emitted = [];
  await page.exposeFunction("__ltCaptureEmit", (payload) => {
    emitted.push(payload);
  });

  await page.addInitScript(() => {
    window.addEventListener("message", (event) => {
      const data = event.data;
      if (
        data &&
        data.source === "leetcode-tracker" &&
        data.type === "submission"
      ) {
        window.__ltCaptureEmit(data.payload);
      }
    });
  });

  await page.goto("http://127.0.0.1:8763/", { waitUntil: "domcontentloaded" });
  await page.evaluate(() => {
    history.replaceState({}, "", "/problems/maximum-subarray/");
    document.title = "53. 最大子数组和 - 力扣";
    const el = document.createElement("div");
    el.setAttribute("data-cy", "question-title");
    el.textContent = "53. 最大子数组和";
    document.body.prepend(el);
  });

  await page.addScriptTag({ content: INJECT });

  // 1) Blob body 不得被读穿（旧 bug → InvalidStateError）
  const streamOk = await page.evaluate(async () => {
    const body = new Blob(
      [JSON.stringify({ lang: "python3", question_id: "53", typed_code: "x" })],
      { type: "application/json" }
    );
    try {
      const res = await fetch(
        "https://leetcode.cn/problems/maximum-subarray/submit/",
        {
          method: "POST",
          body,
          headers: { "Content-Type": "application/json" },
        }
      );
      const data = await res.json();
      return { ok: true, data };
    } catch (err) {
      return { ok: false, error: String(err) };
    }
  });
  console.log("[selftest] blob body fetch", streamOk);
  if (!streamOk.ok) {
    throw new Error("fetch body broken: " + streamOk.error);
  }

  // 清空 emitted（上面 blob 提交也可能 emit）
  emitted.length = 0;

  // 2) 标准 string body submit + check（绝对 leetcode.cn URL，匹配 inject 主机过滤）
  await page.evaluate(async (sid) => {
    await fetch("https://leetcode.cn/problems/maximum-subarray/submit/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        lang: "python3",
        question_id: "53",
        typed_code:
          "class Solution:\n    def maxSubArray(self, nums):\n        pass",
      }),
    });
    await fetch(`https://leetcode.cn/submissions/detail/${sid}/v2/check/`);
  }, SUBMISSION_ID);

  for (let i = 0; i < 30 && emitted.length === 0; i++) {
    await page.waitForTimeout(100);
  }

  console.log("[selftest] emitted", emitted);
  if (emitted.length === 0) {
    throw new Error("inject did not emit submission");
  }
  const payload = emitted[0];
  if (String(payload.submission_id) !== String(SUBMISSION_ID)) {
    throw new Error("bad submission_id: " + payload.submission_id);
  }
  if (Number(payload.problem_id) !== 53) {
    throw new Error("bad problem_id: " + payload.problem_id);
  }

  const saveRes = await fetch(`${BRIDGE}/submit`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      ...payload,
      title: payload.title || "最大子数组和",
      slug: payload.slug || "maximum-subarray",
    }),
  });
  const saveData = await saveRes.json();
  console.log("[selftest] bridge save", saveData);
  if (!saveRes.ok || saveData.status !== "success") {
    throw new Error("bridge save failed: " + JSON.stringify(saveData));
  }

  // 3) 确认库里能查到
  const verify = await fetch(`${BRIDGE}/health`).then((r) => r.json());
  console.log("[selftest] health after save", {
    submissions_count: verify.submissions_count,
  });

  await browser.close();
  console.log("[selftest] PASS");
}

main().catch((err) => {
  console.error("[selftest] FAIL", err);
  process.exit(1);
});
