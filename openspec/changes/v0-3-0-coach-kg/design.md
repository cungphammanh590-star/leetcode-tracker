## Context

v0.2.0 已有：`submissions` 事实表、`problem_stats` / `problem_daily_stats` 派生画像、`GET /api/problems/{id}/llm-context`、浏览器仪表盘与扩展采集链路。尚无知识图谱与陪练能力。

外部数据源调研结论：

- **algorithm-stone**（主选）：`map/leetcode/*.txt` 含 14 条路线图、103 子模块、~902 题、~1027 条顺序边；题号为 frontend id，与 tracker `problem_id` 一致；含 `key=` / `star=` 行内标注。
- **LeetCode Visualizer**：仅为扁平 `problem → tags[]` 进度图，非图谱，且 ID 为内部 question_id，**不导入**。

约束：macOS + leetcode.cn；Neo 8GB；陪练本地优先；Tutor 讲题系统本版不做；扩展 MVP 为「通知 + 打开本机陪练页」，非力扣侧栏。

## Goals / Non-Goals

**Goals:**

- 将 algorithm-stone 学习路径导入 SQLite，与用户刷题记录 JOIN 出 track/node 级进度。
- Coach 陪练：提交后短对话、苏格拉底式、结合图谱位置判断薄弱点。
- LangGraph + Ollama 7B Q4 默认可用；config 预留 API。
- CLI 与 `8763` 桥接 API 先行；扩展异步 engage。

**Non-Goals:**

- Tutor 讲题、深度 code review、默认云端 LLM。
- 图谱可视化、向量库、LeetCode Visualizer 导入。
- 力扣页常驻侧栏（v0.3.1）。
- 独立 coach 端口（MVP 与 bridge 同进程）。

## Decisions

### D1：图谱与用户数据同库、分表

- **决定**：在现有 `leetcode.db` 新增 `kg_tracks`、`kg_nodes`、`kg_node_problems`、`kg_edges`；图谱为只读参考层，importer 可重复执行（先清空 kg 表再导入）。
- **理由**：陪练需 JOIN `problem_stats`；单文件备份简单。
- **备选**：独立 `kg.db` — 增加连接与事务复杂度，MVP 不采用。

### D2：图谱源仅 algorithm-stone map 文本

- **决定**：bundled 路径 `leetcode_tracker/data/algorithm_stone/maps/`（从上游 map 复制并注明 LICENSE/版本）；`leetcode-tracker kg import` 解析 `[根]`、`[-子模块]`、题号、`(key=...)` 语法，不依赖 graphviz/zhon。
- **理由**：map 文件是 source of truth；SVG 为生成物。
- **标注**：`annotation` 存原始括号内文本（如 `前缀和`、`star=5`）。

### D3：图谱 ID 与多 track 归属

- **决定**：`kg_nodes.id` = `{track_id}::{sort_order}::{submodule_name}`（同名子模块可共存）；一题可出现在多 track，`kg_node_problems` 用 `(node_id, problem_id)` 主键；同子模块内重复题号导入时去重。
- **理由**：与 algorithm-stone 拓扑一致；陪练可说明「这题在 DP 路线的子数组模块」。

### D4：进度查询复用 problem_stats

- **决定**：`kg progress` 不新建用户事实表；按 node 聚合：`COUNT` 图谱题数、`SUM(has_ac)` 来自 `problem_stats.accepted_count > 0`、挣扎度取 node 内 `struggle_score` 均值。
- **理由**：避免双写；与 v0.2.0 画像一致。

### D5：Coach context 分层

- **决定**：`build_coach_context(submission_id)` 输出 Markdown 块：
  1. 本次提交（status、今日第几次、语言、runtime）
  2. 图谱位置（track、node、序位、annotation、前序题 AC 情况）
  3. 子模块进度（AC 数/总数、node 挣扎均值）
  - **默认不含完整 code**；用户显式要求看代码时，Coach 仍只引导思考，不跨进 Tutor。
- **理由**：8GB 上控制 token；陪练 ≠ 讲题。

### D6：LangGraph 陪练图（coach 包）

- **决定**：`leetcode_tracker/coach/` 独立包；图节点：
  - `load_context`（tool）
  - `classify_moment`（AC / WA / TLE / CE / 多错后 AC）
  - `coach_reply`（LLM，system 硬约束防泄题）
  - 条件边：用户继续 → `coach_reply`；用户结束 → `summarize`
- **Checkpointer**：与主库同文件 `leetcode.db` 内陪练 checkpoint 表（LangGraph SqliteSaver 指向同库路径）；不单独维护 `coach_sessions.db`。
- **备选**：单 prompt 链 — 难控多轮与状态，不采用。

### D7：LLM 提供方

- **决定**：`leetcode_tracker/llm/provider.py` 抽象；默认 `provider=ollama`，`coach_model=qwen2.5:7b-instruct-q4_K_M`；`api_provider` 与 `api_key` 配置项存在但默认空，MVP 代码路径不调用。
- **理由**：本地优先；Neo 8GB 可跑 7B Q4；图谱判断不依赖 LLM。

### D8：HTTP 与扩展集成（采集 / 陪练解耦）

- **决定**：在现有 `ThreadingHTTPServer` 增加：
  - `POST /api/coach/engage` — body: `{submission_id}`；返回 `{session_id, opening, problem_id}`（**仅陪练页/CLI 按需调用**）
  - `POST /api/coach/chat` — body: `{session_id, message}`；返回 `{reply, done?}`
  - `GET /coach` — 静态陪练页，query `submission` 或 `session`
- **扩展**：`/submit` 成功后**只** badge + 通知「提交已记录」+ 深链打开陪练页；**不**在提交热路径调用 engage / LLM。
- **开场白**：用户打开陪练页时 `engage` 读库拼上下文 + **模板**开场；用户发送首条消息后 `/api/coach/chat` 才调用 LangGraph + Ollama。
- **理由**：采集与陪练完全解耦；入库不被陪练拖慢；慢一步（打开页面 / 日后消息队列）均可接受。

### D9：与 Tutor 边界

- **决定**：无 `tutor/` 包、无讲题路由；陪练页仅文案链到未来 Tutor（disabled 或「即将推出」）。Coach system prompt 禁止算法步骤与可 AC 代码。
- **理由**：用户要求两系统分离。

### D10：多 track 题目选 node（B+C）

- **决定**：一题属多 track 时，陪练 context 只选**一个** node 展开：
  1. **主规则（B）**：在各候选 node 中选取用户 AC 率最低（`accepted_in_node / total_in_node`）者；
  2. **平局（C）**：若 AC 率相同，选取该 track 下用户**最近 `submitted_at` 最新**的 node。
- **理由**：对齐薄弱点判断，且 tie-break 贴近当前学习状态。

### D11：依赖与配置

- **决定**：LangGraph 栈放入 `pyproject.toml` 的 **`[coach]` optional extra**（`pip install leetcode-tracker[coach]`）；核心 `serve`/采集零 LLM 依赖。
- **决定**：`config.json` 使用**嵌套** `llm` 对象（`provider`、`coach_model`、`api_provider`、`api_key`）；`config set llm.provider` 支持点路径读写，`api_key` 展示脱敏。

### D12：端口与 health

- **决定**：`GET /health` 扩展返回 `port`、`kg_imported`（kg 表是否有数据）、`coach_available`（是否安装 `[coach]` 依赖）；扩展启动时拉取并缓存 `port`（替代硬编码 8763）。改端口场景以 health + README 说明为准。

### D13：版本

- **决定**：包版本 `0.3.0`。

## Risks / Trade-offs

- [algorithm-stone 仅覆盖 ~902 题] → 图谱外题目降级为 `problem_stats` + `problems.tags`；context 标明「图谱外」。
- [8GB 上 Ollama + Chrome + serve 争内存] → 文档建议关闭多余模型；engage 开场可用模板句 + 可选 LLM；单会话串行。
- [标准库 HTTP 无 SSE] → 陪练页用 POST 轮询 `/api/coach/chat`；v0.3.1 可换 Starlette 子应用。
- [Ollama 未安装] → engage 返回模板开场 + 页内提示安装；CLI `coach` 明确报错。
- [上游 map 更新] → importer 记录 `kg_meta.source_version`；README 说明如何刷新 bundled maps。

## Migration Plan

1. 升级后首次 `serve` 或 `kg import` 执行 kg schema migration（`CREATE TABLE IF NOT EXISTS`）。
2. 用户运行 `leetcode-tracker kg import`（或首次 `coach` 自动提示导入）。
3. 安装 Ollama 与模型（README 文档化）；无 Ollama 时采集与统计不受影响。
4. 扩展需重新加载以启用 engage 通知。
5. 回滚：不删用户数据；停用 coach 路由与扩展 engage 即可；kg 表可保留。

## Resolved Decisions（原 Open Questions，实施基准）

以下为用户确认、作为 v0.3.0 开发基准的决议：

| 议题 | 决议 |
|------|------|
| 多 track 选题 | **B+C**：最弱 node 优先，平局取最近活跃 track |
| 提交瞬间 engage | **否**：扩展只入库 + 通知；打开陪练页再 engage |
| 依赖安装 | **`[coach]` extra**，核心包不强制 LangGraph |
| config 结构 | **嵌套 `llm` 对象** |
| 通知打开陪练 | **`onClicked` + `tabs` 权限**（深链，不预跑 LLM） |
| engage 开场 | **模板生成**；用户 chat 后才调 LLM |
| 会话存储 | **统一 `leetcode.db`**，无独立 coach db 文件 |
| 端口同步 | **`/health` 返回 port** + 扩展缓存 + 文档 |
| bundled maps | **是**：随 pip 包发行，附 algorithm-stone MIT attribution |
| 会话保留 | MVP **不自动清理**；后续可加 30 天 TTL |
| 采集/陪练边界 | **硬拆开**：`/submit` 不写 coach；陪练只读库；可异步/队列 |
