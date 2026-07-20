# Coach / LangGraph 链路说明（v0.3.0）

本文描述陪练子系统的端到端数据流与可调位点，供后续微调 prompt、图结构与流式策略时对照。  
**采集与陪练解耦**：`/submit` 永不进入本文链路。

---

## 1. 三接口总览

```text
力扣提交
  │
  ▼
① POST /submit              ← 只写 problems / submissions / stats
  │ 成功（扩展 badge + 通知 + sendResponse）
  ▼
② POST /api/coach/prepare   ← 读库 + 模板 opening → 原子创建/复用 coach_sessions
  │ （不调用 LLM；同 submission 幂等；立即返回）
  ▼
用户打开 /coach?submission=…&problem_id=…
  │ 优先 GET /api/coach/session 取缓存模板 opening
  │ 若无则按 submission prepare；缺失时按 problem_id 找该题最新提交
  ▼
③ POST /api/coach/stream    ← 用户发消息时首次调用模型；LangGraph token 流
```

兼容保留：

| 接口 | 角色 |
|------|------|
| `POST /api/coach/engage` | 兼容入口；不得绕过无 LLM prepare 契约 |
| `POST /api/coach/chat` | 同步整段回复（CLI）；内部复用 `chat_stream` |
| `GET /api/coach/hint` | popup 模板建议，不调 LLM，不创建 session |

---

## 2. 模块与文件

| 路径 | 职责 |
|------|------|
| `coach/context.py` | `build_coach_context(submission_id)`：提交事实 + kg Markdown |
| `coach/opening.py` | `template_opening(...)`：prepare 的确定性首句 |
| `coach/prompts.py` | `COACH_SYSTEM_PROMPT` |
| `coach/sessions.py` | `coach_sessions` 表 CRUD；同 submission 原子创建/复用规范 session |
| `coach/service.py` | **核心**：无模型 `prepare`；LangGraph 路由、token stream、checkpoint、结束语与 fallback |
| `coach/hint.py` | 扩展弹窗只读建议 |
| `llm/provider.py` | `build_chat_model()` → loopback-only、不走代理、有 timeout 的 ChatOllama |
| `api/` + `server.py` | FastAPI 路由 + uvicorn 入口；prepare / stream / session / chat / hint；`/submit` 隔离 |
| `static/coach.html` | 缓存 opening 展示 + fetch SSE |
| `extension/background.js` | submit 成功后再 `prepare`；深链同时携带 submission 与 problem_id |

---

## 3. prepare 详细流程

```text
prepare(conn, submission_id=None, problem_id=None)
  │
  ├─ 解析已入库 submission
  │     ├─ 有效 submission_id → 使用该提交
  │     └─ submission 缺失且有显式 problem_id → 选择该题最新提交（稳定键打破时间平局）
  │
  ├─ build_coach_context
  │     └─ get_submission_by_id  （不存在且无法回退 → HTTP 404）
  │     └─ format_kg_context_markdown（图谱外降级）
  │     └─ 拼 markdown：本次提交 + 图谱位置/进度
  │
  ├─ template_opening(...) 生成确定性首句
  │
  ├─ 原子 create-or-get session → coach_sessions
  │     └─ 同 submission 原子复用；并发冲突读取已提交规范行
  │     thread_id := session_id
  │
  └─ 立即返回 session_id + opening + submission_id + problem_id
        └─ 不构建模型、不探测 Ollama、不调用 LangGraph 模型节点
```

**微调点：**

- 模板首句质量 → `template_opening`（`opening.py`）
- 上下文厚度 → `build_coach_context` / `kg/queries.py`（是否注入 code、错题分布等）
- prepare 幂等 → submission 唯一约束与原子 create-or-get

---

## 4. LangGraph 图结构（目标正式执行边界）

LangGraph 不只是 checkpoint 容器。第一条及后续用户消息都进入图，生产路径不得在图外直接 `model.stream` 再手工回填状态。

```text
State: MessagesState 子类
  messages:（内置 add_messages reducer）
  context_markdown: str

Graph:
  route
   ├─ end_phrase ──► deterministic_close ──► checkpoint ──► END
   └─ coach ───────► model_stream ─────────► checkpoint ──► END
                         │ error / timeout
                         └────────► deterministic_fallback ─► checkpoint ─► END
```

编译：每个 stream 使用独立 `SqliteSaver` 连接与图实例，指向同一个 `leetcode.db`；连接设置 busy timeout，主库启用 WAL，避免跨线程共享长生命周期连接。

| 步骤 | 如何碰图 |
|------|----------|
| prepare | 不执行模型图；仅持久化模板 session/context |
| SSE / CLI 用户消息 | 图内路由；模型节点按 token stream；完整步骤由 checkpointer 持久化 |
| 结束语 | 图内确定性收束节点，不调用模型 |
| 模型失败 | 图内确定性 fallback，不把异常传播为采集失败 |

**并发约束：**

- 同一 `thread_id` 同时只允许一个 stream；重叠请求在模型调用/checkpoint 变更前返回冲突。
- 锁/租约必须在成功、失败和取消路径释放；不同 thread 的资源上限可另行演进。

---

## 5. SSE stream 详细流程

传输层：FastAPI `StreamingResponse`（`text/event-stream`）；工作线程内建 SQLite 连接；客户端断开时停止推送。

```text
POST /api/coach/stream  { session_id, message }
  │
  ├─ 获取 thread 独占；已有生成 → 明确冲突
  │
  ├─ LangGraph route
  │     ├─ 结束语（结束/够了/…）→ 确定性收束（不调 LLM）
  │     └─ 普通消息 → model stream（首条消息才首次调用模型）
  │
  ├─ 图内每个模型增量 → SSE event: token  { text }
  │     └─ 模型错误/timeout → deterministic fallback
  │
  ├─ 完整图步骤写 checkpoint
  │
  └─ SSE event: done；释放 thread 独占
```

浏览器：`coach.html` 用 `fetch` + `ReadableStream` 解析 `event:/data:` 块（非 EventSource，因需 POST body）。

CLI：`coach chat` 调同步 `chat()`（内部聚合 `chat_stream`），**不走 HTTP SSE**。

客户端断开时，传输层必须取消正在运行的图/模型任务并释放 thread 独占；不得继续后台生成，也不得把部分 token 作为完整 AIMessage checkpoint。取消前已完整提交的 checkpoint 保留。

---

## 6. 上下文 Markdown 形状（注入模型）

大致结构：

```markdown
## 本次提交
- 题目：{id}. {title}（{difficulty}）
- 状态 / 语言 / 用时 / 今日第 N 次

## 图谱上下文
- track / 子模块 / 序位 / annotation
- 前序题 AC 摘要
- 或「图谱外」+ problem_stats 画像
```

默认**不含完整代码**（防泄题 + 控 token）。若要微调「能否引用用户代码片段」，改 `context.py`，并同步收紧 `COACH_SYSTEM_PROMPT`。

---

## 7. 配置与依赖

| 项 | 默认 |
|----|------|
| `llm.provider` | `ollama` |
| `llm.coach_model` | `qwen2.5:7b-instruct-q4_K_M` |
| Ollama 地址 | 仅 loopback（`127.0.0.1` / `::1` / `localhost`） |
| 代理 | 显式禁用 HTTP(S) 环境/系统代理 |
| timeout | 有限值；超时取消并走图内 fallback |
| extra | `pip install 'leetcode-tracker[coach]'` |
| 图谱 | `leetcode-tracker kg import` |

`prepare` 不依赖 Ollama 是否在线；`stream` 的模型调用若不可用或超时，由 LangGraph 给出确定性 fallback。图谱未导入时仍按接口约定明确提示或降级。

---

## 8. 失败与降级矩阵

| 场景 | 行为 |
|------|------|
| 提交未入库就 prepare | 404，不调 LLM |
| 仅提供 problem_id | 回退该题最新已入库 submission；无提交则明确错误 |
| 重复/并发 prepare | 原子复用同一 session_id 与模板 opening |
| Ollama 挂了或 timeout | prepare 仍立即返回；stream 由图输出确定性 fallback |
| 同 thread 并发 stream | 在模型调用/checkpoint 前明确拒绝 |
| SSE 断连 | 取消图/模型、释放 thread；不保存伪完整回复 |
| checkpoint 写入失败 | 图按失败策略终止，不声称该轮已持久化 |
| prepare 扩展侧失败 | 只 `console.warn`，badge 不变 |

---

## 9. 微调检查清单

1. **改人设 / 防泄题** → `coach/prompts.py`
2. **改模板首句** → `coach/opening.py`
3. **改模型失败/结束语文案** → LangGraph 确定性节点
4. **改注入事实** → `coach/context.py`、`kg/queries.py`
5. **改多轮结构** → `_graph_for_turn()` 节点与边；token stream 必须保持图内
6. **改触发时机** → 扩展 `background.js`（务必保持「先 submit 成功，再 prepare」）
7. **回归采集** → `node scripts/selftest_capture.mjs`

---

## 10. 相关文档

- 接口与表：`docs/DATA_MODEL.md`
- 采集事故与热路径约束：`docs/SUBMISSION_CAPTURE_INCIDENT.md`
- OpenSpec：`openspec/changes/v0-3-0-coach-kg/`
