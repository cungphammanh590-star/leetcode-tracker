## Why

v0.2.0 已具备单题画像、LLM 上下文导出与浏览器仪表盘，但仍是「记录与展示」——用户提交后得不到基于个人历史的陪练反馈，也缺少结构化的算法学习路径来判断薄弱点。v0.3.0 在保持数据不出本机的前提下，引入 **algorithm-stone 知识图谱** 与 **Coach 陪练系统**（LangGraph + 本地 Ollama 优先），让每次提交入库后能经**独立接口**立即准备模板开场，并在用户发送第一条消息时才启动模型与 **SSE** token 流。采集与陪练必须全部解耦：曾把陪练叠进扩展采集热路径导致投递不稳定并大规模回退（见 `docs/SUBMISSION_CAPTURE_INCIDENT.md`）。

## What Changes

- 新增 **知识图谱层**：从 [algorithm-stone](https://github.com/acm-clan/algorithm-stone) 的 `map/leetcode/*.txt` 导入路线图、子模块、题目顺序边与行内标注，存入 SQLite 只读参考表（与用户 `submissions` 事实表分离）。
- 新增 **图谱进度查询**：按 track / 子模块聚合用户 AC 率、挣扎度、前序题完成情况，供陪练判断「做得怎么样」。
- 新增 **Coach 陪练系统**（独立模块，非 Tutor）：LangGraph、防泄题 prompt、提交级 context builder、会话缓存。
- 新增 **LLM 提供方抽象**：默认 Ollama 本地（Neo 8GB 友好，7B Q4）；config 预留可选 API，MVP 默认不启用云端。
- 新增 **解耦 HTTP 接口（挨个调用，互不合并）**：
  1. `POST /submit` —— 只入库，只回采集结果；**禁止**调用 LLM / LangGraph / SSE。
  2. `POST /api/coach/prepare` —— **仅在 `/submit` 成功之后**由扩展或 CLI/页按需调用；只读已入库 submission，或按显式 `problem_id` 回退到该题最新提交，原子创建/复用模板 opening 会话并立即返回；**禁止调用 LLM**。
  3. `POST` **SSE** `/api/coach/stream` —— 用户发送消息时首次调用模型；LangGraph 正式负责路由、token stream、checkpoint、结束语及模型失败的确定性 fallback。
- 新增 **CLI**：`leetcode-tracker kg import|status|progress|context`、`leetcode-tracker coach follow|debrief|chat`。
- 扩展 **提交后交互**：采集热路径只做 `/submit` + badge/通知；`/submit` 成功回包处理完毕后，**另一次**请求 `prepare`（失败静默，不影响采集成功态）；通知/popup 深链同时携带 `submission` 与 `problem_id`，用户打开本机陪练页后发送消息才触发模型。
- 包版本 **0.3.0**。

**Non-goals（本 change / v0.3.0 不做）**

- **Tutor 讲题系统**（算法讲解、伪代码、深度 code review）——独立系统，留 v0.4+。
- 导入 LeetCode Visualizer 或力扣官方 tag 图谱（扩展已写 `problems.tags`；图谱源仅 algorithm-stone）。
- 图谱可视化 UI、向量检索、embedding。
- 力扣页面常驻侧栏（v0.3.1）。
- Windows/Linux；leetcode.com；云同步；默认启用云端 LLM API。
- 修改 `submissions` 写入语义或去重规则。
- 将陪练、队列、Port 长连、content 直连 bridge 重新叠进采集热路径。
- 在单一接口（如 `/submit`）内同时完成入库与 LLM。

## Capabilities

### New Capabilities

- `knowledge-graph`：algorithm-stone 导入、SQLite 图谱表、track/node 进度与 `kg context` 查询。
- `coach-core`：LangGraph 陪练、CLI、会话存储、提交级 context、防泄题、模板 opening 与 SSE 首次/后续模型调用逻辑。
- `coach-extension`：提交成功后的独立 `prepare`、陪练页、SSE 对话、通知/popup 深链。
- `llm-provider`：Ollama 本地接入与 config（`coach_model`、可选 API provider 占位）。

### Modified Capabilities

- `submission-capture`：采集热路径 SHALL 仅调用 `/submit`；成功后再**单独**调用陪练 `prepare`；`prepare` 失败 MUST NOT 视为采集失败。
- `progress-stats`：图谱进度查询 SHALL 复用 `problem_stats` / `problem_daily_stats` 派生数据（不新增用户事实表）。

## Impact

- **依赖**：`langgraph`、`langchain-ollama`（或等价）、`langgraph-checkpoint-sqlite`；不引入 graphviz / PyTorch。
- **数据**：`leetcode.db` 新增 `kg_*`、`coach_sessions`；bundled algorithm-stone maps；importer CLI。
- **服务**：`server.py` 保持 `/submit` 极简；另增无 LLM 的 `prepare` 与 SSE `stream`；同 submission prepare 幂等，同 thread 并发请求拒绝，SSE 断连取消正在进行的生成；Coach 逻辑在 `leetcode_tracker/coach/`。
- **配置**：嵌套 `llm` 对象；API 默认 off。
- **隐私**：陪练默认 100% 本机推理；Ollama 仅允许 loopback，显式绕过系统代理并配置请求 timeout。
- **硬件**：目标 Neo 8GB；图谱判断以 SQL 为主，LLM 仅在用户发送消息后负责自然语言陪聊。
- **回归**：修改扩展采集链路时必须跑 `node scripts/selftest_capture.mjs`。
