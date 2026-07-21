## ADDED Requirements

### Requirement: 默认本地 Ollama 提供方

系统 SHALL 支持通过 Ollama 在本机运行陪练 LLM；默认配置 MUST 指向 loopback Ollama 端点与适合 8GB 内存的量化模型名，且陪练在默认配置下 MUST NOT 向云端发送用户刷题数据。Ollama 客户端 MUST 绕过 HTTP(S) 代理并配置有限请求 timeout。

#### Scenario: 默认本地推理

- **WHEN** 用户未配置云端 API 且本机 Ollama 可用
- **THEN** Coach 请求 MUST 仅与 loopback Ollama 通信，且 MUST NOT 使用环境或系统代理

#### Scenario: 拒绝非回环 Ollama

- **WHEN** Ollama base URL 的主机不是 `127.0.0.1`、`::1`、`localhost` 或等价 loopback
- **THEN** 系统 MUST 在发出请求前拒绝该配置

#### Scenario: Ollama 请求超时

- **WHEN** Ollama 在配置的有限 timeout 内未响应或流停滞
- **THEN** 调用 MUST 被取消并由 LangGraph 进入确定性 fallback，且 MUST NOT 无限占用 stream 或 thread

#### Scenario: Ollama 不可用

- **WHEN** 用户启动陪练但 Ollama 未运行或未拉取模型
- **THEN** 系统 MUST 返回可读错误，并 MUST 提示如何安装/启动 Ollama 与推荐模型

### Requirement: Prepare 不接触模型提供方

模型提供方 SHALL 仅在用户向已有会话发送 stream 消息后由 LangGraph 使用。`POST /api/coach/prepare` MUST NOT 构建模型客户端、探测 Ollama、拉取模型或发出推理请求。

#### Scenario: Prepare 立即返回

- **WHEN** 客户端为有效已入库提交调用 `prepare`
- **THEN** 系统 MUST 仅创建或复用模板会话并立即返回；即使 Ollama 未运行也 MUST 不因模型连接而阻塞

#### Scenario: 首条用户消息

- **WHEN** 用户向 prepared session 发送第一条 stream 消息
- **THEN** LangGraph MAY 构建并调用配置的模型提供方；此前 MUST 没有模型调用

### Requirement: 可选云端 API 配置占位

系统 SHALL 在配置文件中预留云端 LLM 提供方与 API 密钥字段，供用户显式启用；MVP 默认 MUST 为关闭状态，且未配置密钥时 MUST NOT 调用云端。

#### Scenario: 未配置 API 密钥

- **WHEN** `api_key` 为空且 `provider` 为默认 `ollama`
- **THEN** 任何陪练请求 MUST NOT 访问外部大模型 API

#### Scenario: 用户显式配置 API（预留）

- **WHEN** 用户在未来版本或显式设置中将 `provider` 设为云端且提供有效 `api_key`
- **THEN** 配置读写 MUST 持久化该设置（本版本实现可仅验证配置加载，不强制实现云端调用）

### Requirement: 陪练模型配置项

配置 SHALL 包含 `llm.provider`、`llm.coach_model` 及可选的 `llm.api_provider`、`llm.api_key`；缺省键 MUST 使用内置默认值，且 MUST 通过现有 `config show|set` 或等价机制可读。

#### Scenario: 查看默认 LLM 配置

- **WHEN** 用户执行配置查看
- **THEN** 输出 MUST 包含当前 provider 与 coach_model，且 api_key MUST 以脱敏形式显示或省略
