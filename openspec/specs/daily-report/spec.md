# daily-report Specification

## Purpose
TBD - created by archiving change mvp-implementation. Update Purpose after archive.
## Requirements
### Requirement: 通过 CLI 生成今日日报

系统 SHALL 提供命令 `leetcode-tracker report --today`，读取本地数据库中「本地日历日今天」的提交与累计统计，生成一份 Markdown 日报。系统 MUST NOT 在桥接 `serve` 进程内自动定时生成日报，也 MUST NOT 在 `serve` 启动时自动补跑日报。

#### Scenario: 手动生成今日报告

- **WHEN** 用户执行今日日报生成命令且数据库可访问
- **THEN** 系统 MUST 在默认报告目录写入（或覆盖）当日 Markdown 文件

#### Scenario: serve 不自动出报告

- **WHEN** 用户仅启动桥接服务并经过默认示例中的报告时刻
- **THEN** 系统 MUST NOT 仅因此自动创建日报文件（除非用户另行执行报告命令或系统定时任务调用该命令）

### Requirement: 日报内容完备

今日日报 MUST 至少包含：今日提交次数、今日通过次数与今日通过率、累计提交与累计通过率、连续打卡天数、今日题目列表（题目、难度、状态、关键耗时信息若有）。

#### Scenario: 有今日提交时的内容

- **WHEN** 今日存在若干提交后生成日报
- **THEN** 报告文件 MUST 含概览指标表（或等价结构）以及今日题目列表

#### Scenario: 今日无提交仍可生成

- **WHEN** 今日尚无提交但用户执行生成命令
- **THEN** 系统 MUST 仍生成当日报告文件，并将今日计数类指标记为 0，题目列表可为空

### Requirement: 默认落盘路径与命名

在无用户配置子系统的前提下，日报 MUST 写入默认目录 `~/leetcode-reports`，文件名 MUST 为 `YYYY-MM-DD.md`（与本地日历日对应）。目录不存在时系统 MUST 创建该目录。

#### Scenario: 首次生成创建目录与文件

- **WHEN** 默认报告目录尚不存在且用户生成今日日报
- **THEN** 系统 MUST 创建该目录并写入形如 `~/leetcode-reports/2026-07-14.md` 的当日文件

#### Scenario: 同日重复生成覆盖

- **WHEN** 用户在同一日历日再次执行生成命令
- **THEN** 系统 MUST 更新同一路径下的当日文件，而非另建无关文件名

### Requirement: 文档提供可选定时示例

项目文档 SHALL 提供在 macOS 上使用 cron 或 launchd、于示例时间（如 23:00）调用日报 CLI 的可选示例；产品 MUST NOT 要求安装程序自动注册系统定时任务才算验收通过。

#### Scenario: 文档可指引手工定时

- **WHEN** 用户阅读安装或使用文档中的定时章节
- **THEN** 文档 MUST 给出可复制的示例命令或配置片段，指向默认报告生成方式

