## Context

v0.2.0 已有：`submissions` 事实表、`problem_stats` / `problem_daily_stats` 派生画像、`GET /api/problems/{id}/llm-context`、浏览器仪表盘与扩展采集链路。v0.3.0 已落地知识图谱导入、Coach 包骨架、模板 `engage` / POST `chat`、popup hint；但首句仍为模板、续聊非 SSE，且 tasks/spec 与「采集解耦」决议曾互相矛盾。

2026-07-17 采集故障证明：把陪练、端口发现、队列、重试、`engage` 叠进扩展采集热路径会导致 MV3 Service Worker 下投递不稳定。恢复方案是采集只走 `/submit`。本设计在**保留该边界**的前提下，明确「挨个调、全部解耦」的第二/第三接口：先入库，再 `prepare`（只创建/复用模板会话），用户发送 stream 消息时才首次调用模型。

外部数据源：algorithm-stone `map/leetcode/*.txt`（frontend id 与 `problem_id` 一致）。不导入 LeetCode Visualizer。

约束：macOS + leetcode.cn；Neo 8GB；陪练本地优先；Tutor 本版不做；无常驻侧栏（v0.3.1）。

## Goals / Non-Goals

**Goals:**

- 图谱导入 SQLite，与 `problem_stats` JOIN 出 track/node 进度。
- 接口解耦、顺序调用：`/submit` → `/api/coach/prepare` → SSE `/api/coach/stream`。
- `prepare` 在入库成功后只读数据库，原子创建/复用模板 opening 会话并立即返回，不加载或调用 LLM。
- 用户发送第一条 stream 消息时才首次调用模型；LangGraph 负责路由、token stream、checkpoint、结束语与模型失败 fallback。
- 采集失败与陪练失败互不影响；`/submit` 永不调用 LLM。
- CLI 与本机陪练页可用；扩展在 `/submit` 成功后再单独调 `prepare`。

**Non-Goals:**

- Tutor、深度 code review、默认云端 LLM。
- 图谱可视化、向量库、Visualizer 导入。
- 力扣页常驻侧栏。
- 独立 coach 端口（与 bridge 同进程）。
- 单一接口同时入库 + LLM。
- 恢复 content 直连 bridge、Port 长连、双队列等已回退机制。

## Decisions

### D1：图谱与用户数据同库、分表

- **决定**：`leetcode.db` 新增 `kg_tracks`、`kg_nodes`、`kg_node_problems`、`kg_edges`、`kg_meta`；importer 可重复执行（先清空 kg 表再导入）。
- **理由**：陪练需 JOIN `problem_stats`；单文件备份简单。

### D2：图谱源仅 algorithm-stone map 文本

- **决定**：bundled `leetcode_tracker/data/algorithm_stone/maps/`；`kg import` 解析文本语法，不依赖 graphviz/zhon。
- **标注**：`annotation` 存原始括号内文本。

### D3：图谱 ID 与多 track 归属

- **决定**：`kg_nodes.id` = `{track_id}::{sort_order}::{submodule_name}`；一题可多 track；同子模块重复题号去重。

### D4：进度查询复用 problem_stats

- **决定**：不新建用户事实表；`accepted_count > 0` 计完成；挣扎度取 node 内均值。

### D5：Coach context 分层

- **决定**：`build_coach_context(submission_id)` 含：本次提交、图谱位置、子模块进度；**默认不含完整 code**。

### D6：LangGraph 陪练（coach 包）

- **决定**：逻辑在 `leetcode_tracker/coach/`；checkpointer 指向同库 `leetcode.db`。
- **准备**：`prepare` 仅生成确定性模板 opening 并创建/复用会话，不编译模型、不调用 Ollama。
- **正式执行边界**：第一条及后续用户消息均进入 LangGraph；图必须负责意图/结束语路由、模型 token stream、checkpoint 写入、确定性结束语和模型失败 fallback。生产流不得在图外直接调用 `model.stream` 后再手工回填状态。
- **续聊**：SSE `stream` 在同一 `thread_id` / `session_id` 上多轮；结束语由图路由到确定性收束节点，不调用模型。

### D7：LLM 提供方

- **决定**：默认 `provider=ollama`，`coach_model=qwen2.5:7b-instruct-q4_K_M`；`api_*` 占位默认空，MVP 不调用云端。
- **网络边界**：Ollama base URL 必须解析为 loopback（`127.0.0.1`、`::1` 或 `localhost`）；客户端显式不读取/不使用 HTTP(S) 代理，并设置有限请求 timeout，超时进入图内确定性 fallback。

### D8：三接口解耦（采集 / 准备 / 对话）——修订基准

- **决定**：三个独立 HTTP 契约，**禁止合并**：

| 顺序 | 接口 | 职责 | 调用方 |
|------|------|------|--------|
| 1 | `POST /submit` | 只写 `problems`/`submissions`/stats | 扩展采集热路径（唯一同步副作用） |
| 2 | `POST /api/coach/prepare` | 读库 → 原子创建/复用 `session_id` + 模板 `opening`；不调用 LLM | `/submit` **成功之后**另一次调用；或 CLI/陪练页补调 |
| 3 | SSE `/api/coach/stream` | 首次及后续模型对话；LangGraph 路由并流式输出 | 陪练页 / CLI |

- **扩展时序（挨个调）**：

```text
content → background → POST /submit
       → 成功：badge + 通知 + sendResponse(ok)
       → 另一次：POST /api/coach/prepare { submission_id, problem_id }
         （不阻塞上一步成功语义；失败只打日志，不改 badge、不弹「投递失败」）
用户点陪练 → GET /coach?submission=...&problem_id=...
       → 若已有 session：展示模板 opening；否则页内再调 prepare
       → 用户发送消息后才走 SSE /api/coach/stream 并首次调用模型
```

- **明确禁止**：
  - `/submit` handler 内调用 prepare / LLM / SSE；
  - content script 直连 bridge；
  - 为采集再引入 Port 长连、双队列、storage 冲刷连环路径；
  - prepare 失败覆盖采集成功态。

- **prepare 输入与回退**：优先使用有效的已入库 `submission_id`；未提供 submission 时，允许显式 `problem_id`，并选择该题 `submitted_at` 最新（再以稳定键打破平局）的已入库提交；找不到时返回明确错误且不创建空会话。
- **幂等与原子性**：同一 submission 的并发/重复 prepare 必须由数据库唯一约束或等价事务保证只产生一个规范会话；冲突方读取并复用已提交行，返回同一 `session_id` 和 opening。
- **与旧决议差异**：此前「prepare + LLM 首句」改为「prepare 仅模板，首条 stream 消息才调用模型」；**采集热路径仍只 `/submit`**，符合事故复盘。

- **兼容**：现有 `POST /api/coach/engage`（模板）与 `POST /api/coach/chat`（整段 JSON）在迁移期可保留为降级；目标契约以 `prepare` + SSE `stream` 为准。`GET /api/coach/hint`（popup 模板建议）可保留，不替代 `prepare`。

### D9：与 Tutor 边界

- **决定**：无 `tutor/` 包、无讲题路由；Coach prompt 禁止完整解法与可 AC 代码。

### D10：多 track 题目选 node（B+C）

- **决定**：候选 node 中 AC 率最低者优先；平局取该 track 下最近 `submitted_at` 最新者。

### D11：依赖与配置

- **决定**：LangGraph 栈在 `[coach]` optional extra；嵌套 `llm` 对象；`config set llm.*` 点路径；`api_key` 脱敏。

### D12：端口与 health

- **决定**：`GET /health` 返回 `port`、`kg_imported`、`coach_available`；扩展启动时缓存 port。

### D13：版本

- **决定**：包版本 `0.3.0`。

### D14：SSE 实现落点

- **决定**：SSE 挂在 bridge 同进程；标准库 HTTP 若不便承载长流，可引入轻量 ASGI/子应用仅服务 `/api/coach/stream`，**不得**改写 `/submit` 路径。
- **备选**：短期用 chunked POST 模拟流式，但契约名与客户端仍按 stream 设计，便于替换。

### D15：会话存储

- **决定**：`coach_sessions` + LangGraph checkpoint 同库；同 submission 仅一个规范 prepare 会话；MVP 不自动清理会话。

### D16：同线程并发与断连

- **同 thread 并发**：每个 `thread_id` 同时最多一个进行中的 stream；第二个请求在任何模型调用或 checkpoint 变更前以明确的冲突响应拒绝，不排队、不交错 token。
- **断连取消**：SSE 客户端断开时，服务必须向下游传播取消，停止 LangGraph/模型生成并释放线程占用；不得继续后台生成。仅完整提交的图步骤可写 checkpoint，取消不得写入伪造的完整 AI 回复。

## Risks / Trade-offs

- [首条 stream 调 LLM 较慢] → prepare 始终立即返回模板；页面先展示模板并对用户消息逐 token 渲染。
- [每题都 prepare] → 仅做 SQL 与模板渲染，不启动模型；同 submission 幂等避免重复会话。
- [algorithm-stone 仅 ~902 题] → 图谱外降级 `problem_stats` + 标明「图谱外」。
- [8GB 争用] → README 建议单模型；同 thread 严格拒绝并发，跨 thread 资源控制可后续增加。
- [SSE + ThreadingHTTPServer] → D14 允许局部升级传输层，采集路径不动。
- [扩展再调 prepare 引发回归] → 必须：热路径零 LLM；prepare 在成功态之后；`selftest_capture.mjs` 必跑；失败静默。

## Migration Plan

1. kg schema 与 `coach_sessions` 已随 serve/import 创建。
2. 用户 `kg import` + 安装 Ollama / `[coach]` extra。
3. 将 `prepare` 收敛为无 LLM 的原子模板会话；将路由、token stream、checkpoint、结束语和模型失败 fallback 全部移入 LangGraph。
4. 扩展：`/submit` 成功后再单独 `prepare`；通知/popup 深链同时携带 `submission` 与 `problem_id`。
5. stream 增加同 thread 并发拒绝与 SSE 断连取消；Ollama 强制 loopback、绕过代理并设置 timeout。
6. 废弃把 LLM opening 归于 prepare 的文案；旧 API 可暂留但不得绕过新边界。
7. 回滚：停用 prepare/stream 即可；采集与 kg 表不受损。

## Resolved Decisions（实施基准）

| 议题 | 决议 |
|------|------|
| 多 track 选题 | **B+C**：最弱 node，平局最近活跃 |
| 接口形态 | **三接口解耦**：submit → prepare → SSE stream，禁止合并 |
| 调用顺序 | **必须先入库成功再 prepare**（无数据可读） |
| 谁调 prepare | 扩展在 `/submit` 成功后另一次调用；页/CLI 可补调 |
| prepare opening | **确定性模板，不调用 LLM**；同 submission 原子幂等 |
| 首次模型调用 | 用户发送第一条 **SSE stream** 消息时 |
| LangGraph 职责 | 路由、token stream、checkpoint、结束语、模型失败确定性 fallback |
| 续聊传输 | **SSE**；同 thread 并发拒绝，断连取消生成 |
| 采集热路径 | **仅 `/submit`**；无 Port 双队列；无 content 直连 |
| prepare 失败 | **不影响**采集成功 badge/通知 |
| prepare 回退 | 显式 `problem_id` → 该题最新已入库 submission |
| Ollama | 仅 loopback、不走代理、有 timeout |
| 深链 | 同时带 `submission` 与 `problem_id` |
| 依赖安装 | `[coach]` extra |
| config | 嵌套 `llm` |
| 会话存储 | 统一 `leetcode.db` |
| 端口 | `/health.port` + 扩展缓存 |
| bundled maps | 是，附 MIT attribution |
| Tutor | 不做 |
