## ADDED Requirements

### Requirement: 今日错题列表查询

系统 SHALL 能列出「本地日历日今天」中状态非 Accepted 的提交（今日错题），供 CLI、日报与仪表盘复用。

#### Scenario: 今日有错题

- **WHEN** 今日存在至少一条非 Accepted 提交
- **THEN** 错题列表 MUST 包含这些提交的题目标识与状态

#### Scenario: 今日无错题

- **WHEN** 今日提交均为 Accepted 或今日无提交
- **THEN** 错题列表 MUST 为空

### Requirement: 近七日对比查询

系统 SHALL 提供近 7 个本地日历日（含今天）的提交次数与通过次数（或等价汇总），以便日报与仪表盘做对比展示。

#### Scenario: 输出七日序列

- **WHEN** 请求近 7 日对比数据
- **THEN** 结果 MUST 覆盖 7 个日期的提交/通过计数（无数据日计 0）
