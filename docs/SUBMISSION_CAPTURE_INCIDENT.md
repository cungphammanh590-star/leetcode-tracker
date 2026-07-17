# 提交采集故障复盘（2026-07-17）

## 结论

本次故障**不是 SQLite 新增知识图谱 / 陪练表导致**，也不是 `/submit` 的数据库写入逻辑有问题。

问题发生在浏览器扩展的消息转发层：

```text
力扣页面 inject.js
  → content.js
  → background.js（Chrome Manifest V3 Service Worker）
  → POST http://127.0.0.1:{port}/submit
  → store.save_submission()
  → SQLite
```

页面端已经能正确取得提交结果，但后来为陪练、端口发现、队列和重试加入的多条扩展消息路径，使 `content.js → background.js` 的转发及回包变得不可靠。恢复为经过 v0.2 实际验证的单一、最小转发路径后，提交恢复正常。

## 现象

用户在力扣页面能看到以下日志：

```text
remember submit
seen check
emit submission
content relay submission
```

其中：

- `remember submit`：已经抓到力扣提交 ID、代码和语言。
- `seen check`：已经观察到判题轮询。
- `emit submission`：已经得到最终状态、题号等 payload。
- `content relay submission`：content script 已收到并尝试转发给扩展后台。

但仪表盘和 SQLite 中没有新记录。

这说明故障不在题目解析、判题结果解析或 SQLite，而在 content script 之后的扩展后台投递。

## 已排除的问题

### 数据库 schema / 新增表

`kg_*`、`coach_sessions` 等新增表不会参与提交写入事务。提交写入只涉及：

1. `problems`：`upsert_problem`
2. `submissions`：按 `submission_id` 去重后插入
3. `problem_stats` / `problem_daily_stats`：根据新提交更新派生统计

对用户未入库的真实 payload 直接调用：

```bash
curl -X POST http://127.0.0.1:8763/submit ...
```

均返回 `{"status":"success","created":true}`，并可以在 `leetcode.db` 查到记录。因此服务端和数据库写入逻辑正常。

### 题目 / 判题信息抓取

真实页面日志已证明 payload 正确，例如：

```text
submission_id: 736458066
problem_id: 560
status: Accepted
difficulty: Medium
```

因此不是题号、状态或提交 ID 解析失败。

### 页面 Console 的 source map 404

大量 `*.js.map` / `*.css.map` 的 404 是力扣站点未公开 source map 导致的开发者工具噪音，不影响扩展和数据写入。

## 根因

### 1. 陪练相关改动使采集热路径过度复杂

为了实现提交后陪练入口，扩展中曾依次引入：

- `/health` 端口发现
- `chrome.runtime.Port` 长连接
- content script 直连本机桥接
- content / background 两层待投递队列
- `chrome.storage.onChanged` 冲刷
- 重试、超时和等待回包
- 提交成功后的陪练 engage

这些机制本身不属于“采集并入库”的必要步骤。在 Manifest V3 下，Service Worker 可以休眠或在异步回包前被销毁；多条互相触发的队列和消息路径让问题表现为：

```text
extension timeout
background nack: unknown
```

页面能看到 `emit`，但后台没有稳定执行 `/submit`。

### 2. 旧的网络 hook 观察范围太广

`inject.js` 曾对过多 `fetch` / XHR 请求尝试读取或 clone 响应：

- 可能误把 Google Analytics 等请求识别为提交；
- XHR 的 `responseType` 不是文本时读取 `responseText` 会抛 `InvalidStateError`；
- 不必要地读取请求 body 或 clone 无关响应会增加干扰风险。

最终修复为：只观察 `leetcode.cn` / `leetcode.com` 的提交、判题和必要 GraphQL 请求；对于不适合读取的响应直接跳过，不影响页面原请求。

### 3. 力扣判题 API 路径变化

实际页面使用：

```text
/submissions/detail/{submission_id}/v2/check/
```

而早期逻辑只匹配：

```text
/submissions/detail/{submission_id}/check/
```

现已同时支持两种路径。

## 最终架构

提交采集保持唯一同步热路径：

```text
力扣 submit / check
  → inject.js 组装 payload
  → window.postMessage
  → content.js 单次 chrome.runtime.sendMessage
  → background.js 单次 POST /submit
  → SQLite commit
```

`background.js` 中，提交消息唯一的业务副作用是调用 `/submit`：

```text
content message → postSubmission(payload) → save_submission() → commit
```

badge、通知和 `lastEvent` 仅在入库响应后更新，且不能影响入库结果。

## 陪练边界

陪练与采集已经拆开：

```text
提交 → 只入库 + 成功通知
用户点击陪练页 → 按 submission_id 从 SQLite 读取上下文
用户发送第一条消息 → LangGraph / LLM 生成回复
```

因此：

- `/submit` 不调用 LangGraph、Ollama 或 coach engage；
- 陪练依赖异常不应影响采集；
- 可在未来独立加入低优先级的异步摘要 / 消息队列，但不能加入采集热路径。

## 验证方式

### 查看最近入库记录

```bash
sqlite3 ~/.local/share/leetcode-tracker/leetcode.db \
  "SELECT submission_id, problem_id, status, submitted_at
   FROM submissions ORDER BY id DESC LIMIT 10;"
```

### 验证桥接服务

```bash
curl http://127.0.0.1:8763/health
```

### 采集回归测试

```bash
node scripts/selftest_capture.mjs
```

该测试模拟：

1. 力扣提交请求；
2. 真实格式的 `/v2/check/` 判题响应；
3. `inject.js` 发出 payload；
4. 向本机 `/submit` 写入 SQLite。

## 后续约束

1. 修改扩展采集链路时，必须先运行 `node scripts/selftest_capture.mjs`。
2. 不得在 content script 中直接请求本机 bridge；由 background 的 host permission 负责访问 `127.0.0.1`。
3. 不得在采集路径中调用 Coach、LangGraph、Ollama 或其他 LLM。
4. 不得为采集增加第二条并行投递路径；需要重试时应在 background 层单点实现。
5. 页面 Console 的 `emit submission` 只代表抓取成功；是否入库应以 `/submit` 响应或 SQLite 查询为准。
