# progress-stats Specification

## Purpose
TBD - created by archiving change mvp-implementation. Update Purpose after archive.
## Requirements
### Requirement: 累计与通过率统计

系统 SHALL 基于本地提交记录提供累计提交次数、Accepted 次数及累计通过率（Accepted / 总提交，分母为 0 时通过率定义为 0）。

#### Scenario: 有提交时输出累计指标

- **WHEN** 数据库中存在多条提交且至少一条为 Accepted
- **THEN** 经由 `leetcode-tracker stats` MUST 能得到正确的累计提交数、Accepted 数与通过率

#### Scenario: 无提交时为零

- **WHEN** 数据库中尚无任何提交
- **THEN** 累计提交数与 Accepted 数 MUST 为 0，通过率 MUST 为 0

### Requirement: 按难度统计通过题数

系统 SHALL 按 Easy / Medium / Hard 分别统计「至少有一次 Accepted」的题目数量（按题目去重，而非提交次数）。

#### Scenario: 同题多次 Accepted 只计一次

- **WHEN** 同一道 Medium 题有多次 Accepted 提交
- **THEN** Medium 难度通过题数对该题 MUST 仅计 1

### Requirement: 连续打卡天数

系统 SHALL 按本地时区的日历日计算连续打卡天数：连续有至少一个提交记录的日期串；若「今天」尚无提交，则连续区间 MUST 截至昨天；若昨天也无提交且今天无提交，则连续天数 MUST 为 0。

#### Scenario: 含今天的连续区间

- **WHEN** 今天与过去两天均有提交
- **THEN** 连续打卡天数 MUST 为 3

#### Scenario: 今天未打卡但昨天以前连续

- **WHEN** 今天尚无提交，且昨天与前天有提交、大前天无提交
- **THEN** 连续打卡天数 MUST 为 2

#### Scenario: 中断后归零

- **WHEN** 今天与昨天均无提交
- **THEN** 连续打卡天数 MUST 为 0

### Requirement: 今日提交与最近列表

系统 SHALL 提供「今日提交次数」（本地日历日）以及按时间倒序的最近提交列表（默认至少 20 条，不足则全部返回）。

#### Scenario: 今日计数

- **WHEN** 本地日历日当天已入库 5 条提交
- **THEN** 今日提交数 MUST 为 5

#### Scenario: 最近列表倒序

- **WHEN** 库中存在超过 20 条提交
- **THEN** 最近列表 MUST 按提交时间倒序返回 20 条

### Requirement: 通过 CLI 查看统计

系统 SHALL 提供命令 `leetcode-tracker stats`，将上述统计以可读形式输出到标准输出。

#### Scenario: 手动查看概览

- **WHEN** 用户在本机执行 `leetcode-tracker stats`
- **THEN** 输出 MUST 包含累计与今日相关指标中的关键数值，且不依赖网络

