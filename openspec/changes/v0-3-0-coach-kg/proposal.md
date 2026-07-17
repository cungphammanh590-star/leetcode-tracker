## Why

v0.2.0 已具备单题画像（`problem_stats`）、LLM 上下文导出与浏览器仪表盘，但仍是「记录与展示」——用户提交后得不到基于个人历史的陪练反馈，也缺少结构化的算法学习路径来判断薄弱点。v0.3.0 在保持数据不出本机的前提下，引入 **algorithm-stone 知识图谱** 与 **Coach 陪练系统**（LangGraph + 本地 Ollama 优先），让每次提交后能进行苏格拉底式短对话，并为后续 Tutor 讲题系统预留清晰边界。

## What Changes

- 新增 **知识图谱层**：从 [algorithm-stone](https://github.com/acm-clan/algorithm-stone) 的 `map/leetcode/*.txt` 导入路线图、子模块、题目顺序边与行内标注，存入 SQLite 只读参考表（与用户 `submissions` 事实表分离逻辑）。
- 新增 **图谱进度查询**：按 track / 子模块聚合用户 AC 率、挣扎度、前序题完成情况，供陪练判断「做得怎么样」。
- 新增 **Coach 陪练系统**（独立模块，非 Tutor）：LangGraph 工作流、苏格拉底 prompt（禁止泄题/完整解法）、提交级 context builder（本次提交 + 图谱位置 + 子模块进度）。
- 新增 **LLM 提供方抽象**：默认 Ollama 本地（Neo 8GB 友好，7B Q4）；config 预留可选 API，MVP 默认不启用云端。
- 新增 **CLI**：`leetcode-tracker kg import|status|progress|context`、`leetcode-tracker coach follow|debrief|chat`。
- 新增 **桥接 API**：`POST /api/coach/engage`、`POST /api/coach/chat`、陪练页 `GET /coach`；提交成功后扩展异步触发 engage。
- 扩展 **提交后交互（MVP）**：系统通知含陪练入口；点击打开本机 `http://127.0.0.1:8763/coach?submission=...` 短对话页（力扣页侧栏留 v0.3.1）。
- 包版本升至 **0.3.0**。

**Non-goals（本 change / v0.3.0 不做）**

- **Tutor 讲题系统**（算法讲解、伪代码、深度 code review）——独立系统，留 v0.4+。
- 导入 LeetCode Visualizer 或力扣官方 tag 图谱（扩展已写 `problems.tags`；图谱源仅 algorithm-stone）。
- 图谱可视化 UI、向量检索、embedding。
- 力扣页面常驻侧栏（v0.3.1）。
- Windows/Linux；leetcode.com；云同步；默认启用云端 LLM API。
- 修改 `submissions` 写入语义或去重规则。

## Capabilities

### New Capabilities

- `knowledge-graph`：algorithm-stone 导入、SQLite 图谱表、track/node 进度与 `kg context` 查询。
- `coach-core`：LangGraph 陪练图、CLI、会话存储、提交级 context、防泄题约束。
- `coach-extension`：提交后 `engage` API、通知深链、本机陪练页短对话。
- `llm-provider`：Ollama 本地接入与 config（`coach_model`、可选 API provider 占位）。

### Modified Capabilities

- `submission-capture`：提交成功且 bridge 在线时，扩展 SHALL 异步请求陪练 engage（不阻塞 `/submit`）；通知文案增加陪练入口。
- `progress-stats`：图谱进度查询 SHALL 复用 `problem_stats` / `problem_daily_stats` 派生数据（不新增用户事实表）。

## Impact

- **依赖**：`langgraph`、`langchain-ollama`（或等价）、可选 `langchain-openai` 占位；不引入 graphviz / PyTorch。
- **数据**：`leetcode.db` 新增 `kg_*` 表；bundled 或 `vendor/algorithm-stone` 地图文件；importer CLI。
- **服务**：`server.py` 增加 coach 相关路由与静态陪练页；Coach 逻辑独立包 `leetcode_tracker/coach/`。
- **配置**：`config.json` 扩展 `llm.coach_model`、`llm.provider`（默认 `ollama`）、可选 `llm.api_key`（默认空/off）。
- **隐私**：陪练默认 100% 本机推理；API 仅用户显式配置后可用。
- **硬件**：目标 Neo 8GB；单会话 7B Q4，图谱判断以 SQL 聚合为主、LLM 负责自然语言陪聊。
