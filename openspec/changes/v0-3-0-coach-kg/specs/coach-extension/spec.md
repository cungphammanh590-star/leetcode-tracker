## ADDED Requirements

### Requirement: 提交成功后异步触发陪练

当扩展成功将提交写入本机桥接后，扩展 SHALL 异步调用陪练 engage 接口，且 MUST NOT 阻塞或延迟 `/submit` 的成功响应。

#### Scenario: 提交入库后 engage

- **WHEN** 扩展收到 `/submit` 成功且 `created` 为 true 或 false（已存在也算成功入库）
- **THEN** 扩展 MUST 在后台请求陪练 engage，并携带 `submission_id`

#### Scenario: 桥接离线时不影响采集

- **WHEN** `/submit` 成功但后续 engage 请求失败
- **THEN** 扩展 MUST NOT 将已成功的采集标记为失败，且 MUST NOT 弹出采集失败类通知

### Requirement: 通知提供陪练入口

扩展在提交记录成功的系统通知中 SHALL 提供打开本机陪练页的入口或等价深链说明。

#### Scenario: 通知含陪练文案

- **WHEN** 提交已成功记录且 engage 返回有效 session 或开场信息
- **THEN** 用户 MUST 能从通知或通知触发的操作中打开本机陪练页并关联该次提交

### Requirement: 本机陪练 Web 页

桥接服务 SHALL 提供本机陪练页面与 JSON API，支持基于 `submission_id` 发起会话、发送用户消息并展示陪练回复。

#### Scenario: 从深链打开陪练页

- **WHEN** 用户打开 `http://127.0.0.1:{port}/coach?submission={id}` 且服务与图谱可用
- **THEN** 页面 MUST 展示该次提交相关的陪练开场，并 MUST 允许用户输入后续消息

#### Scenario: 服务不可用

- **WHEN** 陪练页请求时 LLM 或图谱未就绪
- **THEN** 页面 MUST 显示明确的本机配置提示（如安装 Ollama 或执行 kg import），且 MUST NOT 静默空白

### Requirement: Engage 与 Chat API

桥接服务 SHALL 提供 `POST /api/coach/engage` 与 `POST /api/coach/chat`，分别用于提交后创建会话与多轮对话；响应 MUST 为 JSON 且仅监听本机回环地址。

#### Scenario: Engage 创建会话

- **WHEN** 客户端 POST 合法 `submission_id` 至 engage
- **THEN** 服务 MUST 返回 `session_id`、首条 `opening` 文案及关联 `problem_id`

#### Scenario: Chat 续轮

- **WHEN** 客户端 POST 合法 `session_id` 与用户 `message`
- **THEN** 服务 MUST 返回陪练 `reply` 文本
