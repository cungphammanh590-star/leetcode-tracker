## 已完成基线（Phase A — 勿回退）

> 以下能力已落地；后续改造不得把 LLM/队列重新叠进 `/submit` 热路径。

- [x] 1.1 包版本 `0.3.0`，README 陪练 + 知识图谱口径
- [x] 1.2 `[coach]` extra：`langgraph`、`langchain-core`、`langchain-ollama`、`langgraph-checkpoint-sqlite`
- [x] 1.3 嵌套 `llm.*` 配置与脱敏
- [x] 2.1–2.5 kg schema、bundled maps、import/queries、CLI `kg *`
- [x] 3.1–3.2 Ollama provider + API 配置占位
- [x] 4.1–4.2 context builder、防泄题 prompts
- [x] 4.3 LangGraph + SqliteSaver（当前为简化图；engage 模板 / chat POST）
- [x] 4.4 CLI `coach follow|debrief|chat`
- [x] 5.1 现有 `POST /api/coach/engage`、`POST /api/coach/chat`；`/health` 含 `port`/`kg_imported`/`coach_available`
- [x] 5.2–5.3 `GET /coach` + `coach.html`（模板开场 + POST 续聊）
- [x] 5.5 `GET /api/coach/hint` + 扩展 popup 题目建议（只读、不调 LLM）
- [x] 6.0 采集热路径仅 `/submit`（事故复盘后基线）；`/health` 缓存 port
- [x] 7.1–7.3 README、`DATA_MODEL.md`、Non-goals 文档

## 8. 接口清洗与 prepare（Phase B — 已落地旧基线，待第 13 组修订）

- [x] 8.1 新增旧版 `POST /api/coach/prepare`：校验 `submission_id` 已入库 → `build_coach_context` → LangGraph/LLM 生成 `opening` → 写入 `coach_sessions`；失败可降级模板；**不写 submissions**（第 13 组将移除 prepare 内模型调用）
- [x] 8.2 明确与 `/submit` 契约隔离：prepare 不出现在 submit 响应必填字段；单元/手工验证「无提交则 prepare 失败」
- [x] 8.3 迁移策略：`engage` 可暂映射到 prepare（或保留模板降级入口），文档与代码注释统一「三接口」口径
- [x] 8.4 更新 `docs/DATA_MODEL.md` / README：prepare 字段、`session_id`、与 chat/stream 关系

## 9. SSE 对话通道

- [x] 9.1 实现 SSE `/api/coach/stream`（输入：`session_id` + `message`；输出：流式 reply；结束语收束）
- [x] 9.2 若标准库 HTTP 不便承载：按 design D14 引入仅服务 stream 的轻量传输，**不得改动 `/submit`**（本版用标准库 SSE chunked 写出即可）
- [x] 9.3 `coach.html`：优先展示已缓存 opening；消息走 SSE；保留未就绪 banner
- [x] 9.4 CLI `coach chat` 可继续用同步调用，或可选对接 stream（二选一，文档写清）

## 10. 扩展：挨个调、全部解耦

- [x] 10.1 `background.js`：`/submit` 成功处理（badge/通知/`sendResponse`）完成后再 **单独** `POST /api/coach/prepare`；禁止并入 submit body
- [x] 10.2 prepare 失败只打日志，不改 badge、不弹「投递失败」
- [x] 10.3 通知 `onClicked` 和/或 popup：打开 `/coach?submission=...`（端口来自 health 缓存）
- [x] 10.4 跑 `node scripts/selftest_capture.mjs`；确认采集热路径无 LLM/Port 双队列回归

## 11. 手验与验收

- [x] 11.1 历史旧契约验证：Neo 8GB + Ollama 7B Q4 的 prepare LLM 首句与 SSE token 流曾用本机 curl/API 验证；**不代表第 13 组新契约已通过**
- [x] 11.2 Ollama 关闭：采集仍成功；prepare 降级或可读错误；陪练页不空白
- [x] 11.3 深链 `?submission=` 与 popup「打开陪练」（需本机浏览器点一次）
- [x] 11.4 端到端：采集 → kg progress → prepare → SSE 陪练 → `coach debrief`（需 leetcode.cn 实提一次）
- [x] 11.5 对照 `docs/SUBMISSION_CAPTURE_INCIDENT.md` 约束清单做一次回归勾选

## 12. 链路文档

- [x] 12.1 撰写 `docs/COACH_LANGGRAPH.md`（端到端链路与微调点）

## 13. Prepare / LangGraph 契约修复

> 本组是对第 8–10 组旧实现边界的修订。

- [x] 13.1 将 `POST /api/coach/prepare` 改为纯数据库/模板路径：接受已入库 `submission_id`，或接受显式 `problem_id` 并稳定选择该题最新已入库提交；不得构造或调用 LLM
- [x] 13.2 为同 submission prepare 增加数据库级唯一性或等价事务保护；并发冲突读取并复用规范会话，重复调用返回同一 `session_id` 与模板 opening
- [x] 13.3 将第一条及后续用户消息统一交给 LangGraph；图正式负责路由、token stream、checkpoint、确定性结束语与模型失败确定性 fallback，移除生产路径中图外 `model.stream`
- [x] 13.4 对同一 `thread_id` 的重叠 stream 在模型调用和 checkpoint 变更前明确拒绝；不得排队或交错 token
- [x] 13.5 SSE 客户端断连时传播取消，停止 LangGraph/模型生成并释放 thread 占用；取消不得写入伪造的完整 AI 回复
- [x] 13.6 Ollama 客户端仅允许 loopback base URL，显式绕过 HTTP(S) 代理并配置有限 timeout；超时走图内确定性 fallback
- [x] 13.7 扩展通知与 popup 深链同时携带 `submission` 和 `problem_id`；页面 prepare 可用 submission，缺失时用 problem_id 回退
- [x] 13.8 更新单元/集成验证：prepare 零模型调用、problem_id 最新提交回退、并发 prepare 幂等、同 thread 并发拒绝、模型失败 fallback、SSE 断连取消、Ollama 不走代理/超时
- [x] 13.9 运行自动化回归：`pytest -q` 13 passed；`node scripts/selftest_capture.mjs` PASS；Chrome 陪练页自动化深链/收束 PASS。真实人工浏览器验收仍由 11.2–11.4 单独完成
