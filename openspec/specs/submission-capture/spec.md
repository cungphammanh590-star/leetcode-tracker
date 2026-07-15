# submission-capture Specification

## Purpose
TBD - created by archiving change mvp-implementation. Update Purpose after archive.
## Requirements
### Requirement: 扩展可在 leetcode.cn 捕获提交终态

系统 SHALL 提供可在 Chrome/Edge（Manifest V3）加载的浏览器扩展；当用户在 leetcode.cn 完成一次代码提交并产生最终判题结果时，扩展 MUST 捕获该次提交的标识、题目信息、判题状态及相关运行指标，并准备投递至本机桥接服务。

#### Scenario: 成功捕获 Accepted 提交

- **WHEN** 用户在 leetcode.cn 提交代码且判题结果为 Accepted
- **THEN** 扩展 MUST 获得非空的 `submission_id`、题目标识与 Accepted 状态，并具备向本机桥接投递的完整载荷（含源代码）

#### Scenario: 捕获非通过结果

- **WHEN** 用户提交后判题结果为 Wrong Answer、TLE 或其他非 Accepted 终态
- **THEN** 扩展仍 MUST 捕获该次提交的 `submission_id` 与终态并进入投递流程

### Requirement: 本机桥接接收并持久化提交

系统 SHALL 在本机回环地址提供 HTTP 桥接服务；服务 MUST 将合法投递写入本地 SQLite，并持久化完整提交源代码以及题目元数据（若不存在则创建，若存在则保持可更新的幂等写入）。

#### Scenario: 合法投递写入成功

- **WHEN** 桥接服务已运行且收到包含有效 `submission_id`、题目信息、状态与完整代码的投递
- **THEN** 系统 MUST 在本地数据库中新增对应提交记录，并且题目录入可用，并返回成功响应

#### Scenario: 健康检查可用

- **WHEN** 客户端请求桥接健康检查接口
- **THEN** 系统 MUST 返回表示服务可用的响应，并反映数据库可访问

### Requirement: 以 submission_id 强去重

系统 MUST 将力扣 `submission_id` 作为提交记录的唯一键。缺少 `submission_id` 的投递 MUST 被拒绝且不得写入。相同 `submission_id` 的重复投递 MUST 不产生第二条提交记录。

#### Scenario: 缺少 submission_id 时拒绝

- **WHEN** 投递载荷缺少 `submission_id` 或该字段为空
- **THEN** 桥接服务 MUST 拒绝该请求，数据库提交条数 MUST 不增加

#### Scenario: 重复投递不双写

- **WHEN** 相同 `submission_id` 的合法载荷被投递第二次
- **THEN** 系统 MUST 不创建重复提交行（可返回表示已存在或成功但无新增的响应）

### Requirement: 投递失败时对用户可见

当扩展无法将捕获结果写入本机桥接（服务未启动、网络错误或被拒绝）时，扩展 MUST 向用户给出可感知提示，且 MUST NOT 静默丢弃失败而不作任何提示。

#### Scenario: 服务未启动时提示

- **WHEN** 扩展已捕获提交但本机桥接不可达
- **THEN** 用户 MUST 能看到提示其启动本地服务或检查连接的信息

