## MODIFIED Requirements

### Requirement: 投递失败时对用户可见

当扩展无法将捕获结果写入本机桥接（服务未启动、网络错误或被拒绝）时，扩展 MUST 向用户给出可感知提示，且 MUST NOT 静默丢弃失败而不作任何提示。正式版 MUST 使用 badge/popup 与系统通知中至少一种明确反馈；MUST NOT 提供面向用户的「调试开关」或调试面板。

#### Scenario: 服务未启动时提示

- **WHEN** 扩展已捕获提交但本机桥接不可达
- **THEN** 用户 MUST 能看到提示其启动本地服务或检查连接的信息（含系统通知或等价醒目反馈）

#### Scenario: 投递成功可感知

- **WHEN** 提交成功写入本机桥接
- **THEN** 用户 MUST 能通过 badge 和/或系统通知感知成功（无调试开关）

## ADDED Requirements

### Requirement: 国站采集合规范围

扩展与桥接采集范围 MUST 面向 `leetcode.cn`。产品文档与用户可见文案 MUST 仅声明支持 leetcode.cn，不得将其他站点列为已支持能力。

#### Scenario: 文案仅声明 cn

- **WHEN** 用户阅读 README 或扩展说明中的支持站点
- **THEN** 文案 MUST 写明仅支持 leetcode.cn
