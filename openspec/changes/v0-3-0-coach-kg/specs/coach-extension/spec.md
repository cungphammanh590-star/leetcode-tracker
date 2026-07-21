## ADDED Requirements

### Requirement: 提交成功后单独调用 prepare

当扩展已成功完成一次 `/submit` 且收到成功响应后，扩展 SHALL **另一次**请求 `POST /api/coach/prepare`（携带 `submission_id`），且该请求 MUST NOT 并入 `/submit` 请求体或响应契约，MUST NOT 阻塞或改写 `/submit` 的成功语义。

#### Scenario: 入库成功后再 prepare

- **WHEN** 扩展收到 `/submit` 成功响应（无论 `created` 为 true 或 false）
- **THEN** 扩展 MUST 在成功态处理之后发起独立的 `prepare` 请求，且 MUST NOT 在 `/submit` 尚未成功时调用 `prepare`

#### Scenario: prepare 失败不影响采集

- **WHEN** `/submit` 已成功但 `prepare` 超时、网络错误或返回错误
- **THEN** 扩展 MUST 仍保持采集成功的 badge/通知状态，且 MUST NOT 弹出采集失败类通知

### Requirement: 通知与入口打开陪练页

扩展在提交记录成功后 SHALL 提供打开本机陪练页的入口（系统通知点击、popup 按钮或等价深链），同时关联该次 `submission_id` 与 `problem_id`。

#### Scenario: 深链打开陪练

- **WHEN** 用户通过通知或 popup 打开陪练入口
- **THEN** 系统 MUST 打开 `http://127.0.0.1:{port}/coach?submission={submission_id}&problem_id={problem_id}`（参数须 URL 编码，端口与 `/health` 或配置一致）

### Requirement: 本机陪练 Web 页

桥接服务 SHALL 提供本机陪练页面，支持展示已缓存的模板开场、经 SSE 发送用户消息并流式展示陪练回复；LLM 或图谱未就绪时 MUST 显示明确配置提示。

#### Scenario: 已有 prepare 会话

- **WHEN** 用户打开 `/coach?submission={id}` 且该提交已有成功的 `prepare` 会话
- **THEN** 页面 MUST 展示缓存的模板 `opening` 作为第一句，并 MUST NOT 因展示 opening 调用模型；用户发送消息后 MUST 经 SSE 首次调用模型

#### Scenario: 尚无 prepare 结果

- **WHEN** 用户打开陪练页但尚无可用会话（prepare 未完成或失败）
- **THEN** 页面 MUST 使用深链中的 `submission` 调用 `prepare`，或在 submission 缺失/无效时使用显式 `problem_id` 回退到该题最新提交；仍无提交时 MUST 显示明确错误且 MUST NOT 静默空白

#### Scenario: 服务不可用

- **WHEN** 陪练页请求时 LLM 依赖或图谱未就绪
- **THEN** 页面 MUST 显示明确的本机配置提示（如安装 Ollama、`pip install 'leetcode-tracker[coach]'` 或 `kg import`）

### Requirement: Prepare 与 SSE 对话 API

桥接服务 SHALL 提供与 `/submit` 分离的陪练 API：`POST /api/coach/prepare` 与 SSE `/api/coach/stream`；响应仅监听本机回环地址。

#### Scenario: Prepare 创建或复用模板会话

- **WHEN** 客户端在对应提交已入库后 POST 合法 `submission_id`，或 POST 显式 `problem_id` 至 `prepare`
- **THEN** 服务 MUST 只读 submission/派生数据，原子创建或复用模板会话，并立即返回 `session_id`、`opening`、`submission_id` 与 `problem_id`；MUST NOT 调用 LLM，MUST NOT 写入或修改 `submissions` 事实行

#### Scenario: SSE 续轮

- **WHEN** 客户端在合法 `session_id` 上经 SSE 发送用户消息
- **THEN** 服务 MUST 通过 LangGraph 流式返回陪练回复文本，并 MUST 保留同一会话线程上下文；该消息为会话首条用户消息时才可首次调用模型

#### Scenario: 同 thread 并发请求

- **WHEN** 同一 `thread_id` 已有进行中的 SSE 生成
- **THEN** 服务 MUST 在调用模型或修改 checkpoint 前拒绝新的重叠请求

#### Scenario: SSE 断连

- **WHEN** 客户端在生成完成前断开 SSE
- **THEN** 服务 MUST 取消 LangGraph 与模型生成并释放 thread 占用，且 MUST NOT 在后台继续生成

#### Scenario: Prepare 与 Submit 契约隔离

- **WHEN** 客户端调用 `/submit`
- **THEN** 响应 MUST NOT 依赖 LLM 完成，MUST NOT 包含必须等待 `prepare` 的字段
