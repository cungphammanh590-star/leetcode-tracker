## ADDED Requirements

### Requirement: 图谱进度复用题目画像

系统 SHALL 允许图谱进度查询复用 `problem_stats` 与 `problem_daily_stats` 中的派生字段（如 AC 次数、挣扎指数、最近状态），且 MUST NOT 为图谱进度单独维护与用户提交冲突的第二套事实表。

#### Scenario: 子模块进度与 problem_stats 一致

- **WHEN** 某题在 `problem_stats` 中 `accepted_count > 0`
- **THEN** 图谱子模块进度 MUST 将该题计为已完成

#### Scenario: 仅有提交但未 AC

- **WHEN** 某题有提交记录但 `accepted_count` 为 0
- **THEN** 图谱子模块进度 MUST 将该题计为未完成，且 MAY 在陪练上下文中引用挣扎或错误分布信息
