/**
 * MAIN world @ document_start — must load before page JS caches native fetch.
 */
(function () {
  function debug(message, extra) {
    try {
      console.info("[leetcode-tracker]", message, extra || "");
      window.postMessage(
        { source: "leetcode-tracker", type: "debug", message, extra: extra || null },
        "*"
      );
    } catch {
      // ignore
    }
  }

  // If we were injected late once, still allow a forced rewrap.
  const FORCE = true;
  if (window.__leetcodeTrackerInjected && !FORCE) {
    debug("hooks already installed");
    return;
  }
  if (window.__leetcodeTrackerFetchPatched) {
    debug("fetch already patched; listening");
  }

  const pending = new Map();

  function emit(payload) {
    debug("emit submission", {
      submission_id: payload.submission_id,
      problem_id: payload.problem_id,
      status: payload.status,
    });
    window.postMessage(
      { source: "leetcode-tracker", type: "submission", payload },
      "*"
    );
  }

  function parseJsonSafe(text) {
    try {
      return JSON.parse(text);
    } catch {
      return null;
    }
  }

  function difficultyLabel(value) {
    if (value == null) return null;
    if (typeof value === "number") {
      return { 1: "Easy", 2: "Medium", 3: "Hard" }[value] || null;
    }
    const s = String(value).trim();
    const map = {
      easy: "Easy",
      medium: "Medium",
      hard: "Hard",
      Easy: "Easy",
      Medium: "Medium",
      Hard: "Hard",
      简单: "Easy",
      中等: "Medium",
      困难: "Hard",
    };
    return map[s] || map[s.toLowerCase()] || null;
  }

  const STATUS_CODE_MAP = {
    10: "Accepted",
    11: "Wrong Answer",
    12: "Memory Limit Exceeded",
    13: "Output Limit Exceeded",
    14: "Time Limit Exceeded",
    15: "Runtime Error",
    16: "Internal Error",
    20: "Compile Error",
  };

  function normalizeStatus(value) {
    if (value == null) return null;
    const s = String(value).trim();
    const map = {
      通过: "Accepted",
      Accepted: "Accepted",
      "Wrong Answer": "Wrong Answer",
      解答错误: "Wrong Answer",
      "Time Limit Exceeded": "Time Limit Exceeded",
      超时: "Time Limit Exceeded",
      "Memory Limit Exceeded": "Memory Limit Exceeded",
      内存超出: "Memory Limit Exceeded",
      "Runtime Error": "Runtime Error",
      执行出错: "Runtime Error",
      "Compile Error": "Compile Error",
      编译错误: "Compile Error",
      "Output Limit Exceeded": "Output Limit Exceeded",
    };
    return map[s] || s;
  }

  function statusFromCheck(check) {
    if (check.status_code != null && STATUS_CODE_MAP[Number(check.status_code)]) {
      return STATUS_CODE_MAP[Number(check.status_code)];
    }
    return normalizeStatus(check.status_msg || check.statusMsg || check.local_status) || "Unknown";
  }

  function parseTitleText(text) {
    if (!text) return null;
    const cleaned = text.replace(/\s+/g, " ").trim();
    const tm = cleaned.match(/^(\d+)\.\s*(.+)$/);
    if (tm) return { problem_id: Number(tm[1]), title: tm[2].trim() };
    return { problem_id: null, title: cleaned };
  }

  function extractProblemMeta() {
    const meta = {
      problem_id: null,
      title: null,
      slug: null,
      difficulty: null,
      tags: [],
    };

    const path = location.pathname || "";
    const m = path.match(/\/problems\/([^/]+)/);
    if (m) meta.slug = decodeURIComponent(m[1]);

    const nextData = document.getElementById("__NEXT_DATA__");
    if (nextData && nextData.textContent) {
      const data = parseJsonSafe(nextData.textContent);
      const q =
        data?.props?.pageProps?.question ||
        data?.props?.pageProps?.data?.question ||
        null;
      if (q) {
        meta.problem_id = Number(
          q.questionFrontendId || q.frontendQuestionId || q.questionId || meta.problem_id
        );
        meta.title = q.translatedTitle || q.title || meta.title;
        meta.slug = q.titleSlug || meta.slug;
        meta.difficulty = difficultyLabel(q.difficulty);
        if (Array.isArray(q.topicTags)) {
          meta.tags = q.topicTags
            .map((t) => t.translatedName || t.name || t.slug)
            .filter(Boolean);
        }
      }
    }

    try {
      const pd = window.pageData;
      if (pd) {
        meta.problem_id = Number(pd.questionFrontendId || pd.questionId || meta.problem_id);
        meta.title = pd.questionTitle || pd.translateTitle || meta.title;
        meta.slug = pd.questionTitleSlug || meta.slug;
        meta.difficulty = difficultyLabel(pd.difficulty) || meta.difficulty;
      }
    } catch {
      // ignore
    }

    for (const sel of [
      "[data-cy='question-title']",
      ".text-title-large",
      "div[class*='text-title']",
    ]) {
      const el = document.querySelector(sel);
      if (!el) continue;
      const parsed = parseTitleText(el.textContent || "");
      if (parsed) {
        if (parsed.problem_id) meta.problem_id = parsed.problem_id;
        if (parsed.title) meta.title = parsed.title;
        break;
      }
    }

    if (!meta.problem_id || !meta.title) {
      const parsed = parseTitleText((document.title || "").split("-")[0] || "");
      if (parsed) {
        if (!meta.problem_id && parsed.problem_id) meta.problem_id = parsed.problem_id;
        if (!meta.title && parsed.title) meta.title = parsed.title;
      }
    }

    return meta;
  }

  function rememberSubmit(submissionId, bodyObj, meta) {
    const key = String(submissionId);
    const code =
      bodyObj?.typed_code ||
      bodyObj?.code ||
      bodyObj?.typedCode ||
      bodyObj?.variables?.typed_code ||
      bodyObj?.variables?.typedCode ||
      null;
    const language =
      bodyObj?.lang ||
      bodyObj?.langSlug ||
      bodyObj?.language ||
      bodyObj?.variables?.lang ||
      bodyObj?.variables?.langSlug ||
      null;
    pending.set(key, {
      submission_id: key,
      code,
      language,
      meta: meta || extractProblemMeta(),
      createdAt: Date.now(),
    });
    debug("remember submit", { submissionId: key, hasCode: Boolean(code), lang: language });
  }

  function findSubmissionId(obj, depth) {
    if (!obj || depth > 6) return null;
    if (typeof obj !== "object") return null;
    for (const key of [
      "submission_id",
      "submissionId",
      "interpret_id",
      "interpretId",
    ]) {
      if (obj[key] != null && String(obj[key]).trim() !== "") {
        return obj[key];
      }
    }
    for (const value of Object.values(obj)) {
      if (value && typeof value === "object") {
        const found = findSubmissionId(value, depth + 1);
        if (found != null) return found;
      }
    }
    return null;
  }

  function isFinishedCheck(check) {
    const state = String(check.state || "").toUpperCase();
    if (state === "PENDING" || state === "STARTED") return false;
    if (check.finished === false) return false;
    if (state === "SUCCESS") return true;
    if (check.finished === true) return true;
    if (check.status_code != null && Number(check.status_code) > 0) return true;
    if (check.status_msg || check.statusMsg) return true;
    return false;
  }

  function finalizeFromCheck(submissionId, check) {
    const key = String(submissionId);
    if (!isFinishedCheck(check)) {
      debug("check pending", { submissionId: key, state: check.state });
      return;
    }

    const pendingItem = pending.get(key) || {
      submission_id: key,
      code: check.code || null,
      language: null,
      meta: extractProblemMeta(),
      createdAt: Date.now(),
    };

    const status = statusFromCheck(check);

    let runtimeMs = null;
    const runtime = check.status_runtime || check.runtime || check.runtime_ms;
    if (typeof runtime === "string") {
      const rm = runtime.match(/([\d.]+)/);
      if (rm) runtimeMs = Math.round(parseFloat(rm[1]));
    } else if (typeof runtime === "number") {
      runtimeMs = runtime;
    }

    let memoryMb = null;
    const memory = check.status_memory || check.memory || check.memory_mb;
    if (typeof memory === "string") {
      const mm = memory.match(/([\d.]+)/);
      if (mm) memoryMb = parseFloat(mm[1]);
    } else if (typeof memory === "number") {
      memoryMb = memory;
    }

    const meta = { ...(pendingItem.meta || {}), ...extractProblemMeta() };
    let finalProblemId = Number(meta.problem_id) || null;
    if (!finalProblemId) {
      const qid = check.question_id || check.questionId;
      if (qid != null && String(qid).trim() !== "") finalProblemId = Number(qid);
    }

    if (!finalProblemId) {
      debug("drop: missing problem_id", { submissionId: key, slug: meta.slug });
      return;
    }

    emit({
      submission_id: pendingItem.submission_id,
      problem_id: finalProblemId,
      title: meta.title || `Problem ${finalProblemId}`,
      slug: meta.slug || `problem-${finalProblemId}`,
      difficulty: meta.difficulty,
      tags: meta.tags || [],
      status,
      code: pendingItem.code || check.code || null,
      runtime_ms: runtimeMs,
      memory_mb: memoryMb,
      language:
        pendingItem.language || check.lang || check.pretty_lang || check.lang_name || null,
    });
    pending.delete(key);
  }

  function absoluteUrl(url) {
    try {
      return new URL(url, location.origin).href;
    } catch {
      return String(url || "");
    }
  }

  function interesting(url) {
    return /submit|submission|graphql|judge|interpret/i.test(url);
  }

  function handleSubmitUrl(url, requestBodyText, responseText) {
    const full = absoluteUrl(url);
    const bodyText = requestBodyText || "";
    const isSubmitPath = /\/problems\/[^/]+\/submit\/?/i.test(full);
    const isGraphqlSubmit =
      /\/graphql\/?/i.test(full) &&
      /submitCode|SubmitCode|submit\.code|interpretSolution/i.test(bodyText);
    const isAnySubmitHint =
      /submit/i.test(full) ||
      (interesting(full) && /typed_code|typedCode/i.test(bodyText));

    if (!isSubmitPath && !isGraphqlSubmit && !isAnySubmitHint) {
      return;
    }

    debug("seen candidate submit", {
      url: full.slice(0, 180),
      bodyPreview: bodyText.slice(0, 120),
    });

    const resp = parseJsonSafe(responseText);
    const body = parseJsonSafe(bodyText) || {};
    const meta = extractProblemMeta();
    const submissionId = findSubmissionId(resp, 0);

    if (submissionId != null) {
      // Ignore interpret (run) ids if URL says interpret and not submit — still OK to track? skip interpret
      if (/interpret/i.test(full) && !/submit/i.test(full) && !isGraphqlSubmit) {
        debug("skip interpret run", { submissionId });
        return;
      }
      rememberSubmit(submissionId, body, meta);
    } else {
      debug("submit-like response without id", {
        url: full.slice(0, 180),
        respPreview: String(responseText || "").slice(0, 200),
      });
    }
  }

  function handleCheckUrl(url, responseText) {
    const full = absoluteUrl(url);
    const resp = parseJsonSafe(responseText);
    if (!resp) return;

    const m = full.match(/\/submissions\/detail\/(\d+)\/check\/?/i);
    if (m) {
      debug("seen check", {
        submissionId: m[1],
        state: resp.state,
        status_code: resp.status_code,
      });
      finalizeFromCheck(m[1], resp);
      return;
    }

    if (
      resp.submission_id &&
      (resp.state || resp.status_code || resp.status_msg || resp.finished != null)
    ) {
      debug("seen check-like payload", {
        submissionId: resp.submission_id,
        state: resp.state,
      });
      finalizeFromCheck(resp.submission_id, resp);
      return;
    }

    const detail =
      resp?.data?.submissionDetails ||
      resp?.data?.submissionDetail ||
      resp?.data?.submissionCheck ||
      resp?.data?.checkSubmission ||
      null;
    if (detail && (detail.id || detail.submissionId)) {
      finalizeFromCheck(detail.id || detail.submissionId, {
        state: detail.statusDisplay ? "SUCCESS" : detail.state,
        status_msg: detail.statusDisplay || detail.status_msg,
        status_code: detail.statusCode || detail.status_code,
        status_runtime: detail.runtime,
        status_memory: detail.memory,
        lang: detail.langName || detail.lang?.name || detail.lang,
        code: detail.code,
        question_id:
          detail.question?.questionFrontendId || detail.question?.questionId || null,
      });
    }
  }

  function observeResponse(url, method, requestBodyText, responseText) {
    try {
      const full = absoluteUrl(url);
      if (interesting(full)) {
        debug("net", { method, url: full.slice(0, 160) });
      }
      if (String(method).toUpperCase() === "POST") {
        handleSubmitUrl(url, requestBodyText || "", responseText || "");
      }
      handleCheckUrl(url, responseText || "");
    } catch (err) {
      debug("observe error", { error: String(err) });
    }
  }

  // Patch fetch once (keep deepest original).
  if (!window.__leetcodeTrackerFetchPatched) {
    const originalFetch = window.fetch.bind(window);
    window.__leetcodeTrackerOriginalFetch = originalFetch;
    window.fetch = async function patchedFetch(input, init) {
      const response = await originalFetch(input, init);
      try {
        const url = typeof input === "string" ? input : input && input.url ? input.url : "";
        const method = (
          (init && init.method) ||
          (typeof input !== "string" && input && input.method) ||
          "GET"
        ).toUpperCase();
        const requestBodyText =
          init && typeof init.body === "string" ? init.body : null;
        const clone = response.clone();
        clone
          .text()
          .then((text) => observeResponse(url, method, requestBodyText, text))
          .catch(() => {});
      } catch {
        // ignore
      }
      return response;
    };
    window.__leetcodeTrackerFetchPatched = true;
  }

  if (!window.__leetcodeTrackerXhrPatched) {
    const originalOpen = XMLHttpRequest.prototype.open;
    const originalSend = XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.open = function (method, url) {
      this.__ltMethod = method;
      this.__ltUrl = url;
      return originalOpen.apply(this, arguments);
    };
    XMLHttpRequest.prototype.send = function (body) {
      this.addEventListener("load", function () {
        const url = String(this.__ltUrl || "");
        const method = String(this.__ltMethod || "GET").toUpperCase();
        const text = this.responseText || "";
        const requestBodyText = typeof body === "string" ? body : "";
        observeResponse(url, method, requestBodyText, text);
      });
      return originalSend.apply(this, arguments);
    };
    window.__leetcodeTrackerXhrPatched = true;
  }

  window.__leetcodeTrackerInjected = true;
  debug("hooks ready @ document_start", { href: String(location.href) });
})();
