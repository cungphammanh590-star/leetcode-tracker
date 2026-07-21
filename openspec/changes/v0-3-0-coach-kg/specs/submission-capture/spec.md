## ADDED Requirements

### Requirement: 采集热路径仅提交入库

扩展在将提交投递至本机桥接时，SHALL 在采集热路径上仅调用 `POST /submit`；该路径 MUST NOT 调用陪练 `prepare`、SSE、LangGraph 或任何 LLM 接口。

#### Scenario: 热路径单一副作用

- **WHEN** content script 向 background 投递一条 submission 消息
- **THEN** background MUST 以单次（或端口刷新后重试的同构）`POST /submit` 完成入库，且 MUST NOT 在同一请求中附带陪练生成逻辑

### Requirement: 入库成功后再调用 prepare

扩展在收到 `/submit` 成功响应之后，SHALL 另一次请求陪练 `prepare` 接口；prepare 仅创建或复用模板会话且 MUST NOT 调用 LLM。该步骤 MUST NOT 改变 `/submit` 的成功语义，且 `prepare` 失败 MUST NOT 视为采集失败。

#### Scenario: 成功投递后单独 prepare

- **WHEN** 扩展完成一次成功的 `/submit` 响应处理（badge/通知可已更新）
- **THEN** 扩展 MUST 再发起独立的 `prepare` 请求并携带 `submission_id` 与可用的 `problem_id`，且 MUST NOT 将 `prepare` 合并进 `/submit`

#### Scenario: Prepare 失败不影响 badge

- **WHEN** `/submit` 已成功但 `prepare` 超时或返回错误
- **THEN** 扩展 MUST 仍保持采集成功的 badge/通知状态，且 MUST NOT 覆盖为采集失败提示

### Requirement: 采集成功通知含陪练入口

扩展在提交成功记录的系统通知或 popup 中 SHALL 引导用户打开本机陪练页，深链 MUST 同时关联该次提交与题目。

#### Scenario: 通知或 popup 可打开陪练

- **WHEN** 提交已成功记录
- **THEN** 用户 MUST 能打开 `http://127.0.0.1:{port}/coach?submission={submission_id}&problem_id={problem_id}`（参数须 URL 编码，端口与配置或 `/health` 一致）
