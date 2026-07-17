## ADDED Requirements

### Requirement: 从 algorithm-stone 导入知识图谱

系统 SHALL 提供命令将 algorithm-stone 格式的 `map/leetcode/*.txt` 解析并写入本地 SQLite 图谱表，包含路线图（track）、子模块（node）、题目在子模块内的顺序、行内标注（annotation）及同子模块内的顺序边。

#### Scenario: 首次导入成功

- **WHEN** 用户执行图谱导入且 map 文件合法
- **THEN** 系统 MUST 在本地数据库中建立图谱记录，且题号 MUST 使用力扣 frontend 题号（与 `problem_id` 一致）

#### Scenario: 重复导入幂等

- **WHEN** 用户对已导入图谱再次执行导入
- **THEN** 系统 MUST 以最新 map 内容替换图谱参考数据，且 MUST NOT 修改用户 `submissions` 记录

### Requirement: 图谱进度按子模块聚合

系统 SHALL 能基于图谱子模块与用户 `problem_stats` 派生数据，输出该模块内题目的完成数、总数、通过率及挣扎度摘要，供陪练与 CLI 使用。

#### Scenario: 子模块内部分完成

- **WHEN** 某子模块图谱含 8 题且用户已对其中 3 题至少一次 Accepted
- **THEN** 进度查询 MUST 报告 3/8 完成及对应通过率

#### Scenario: 用户未刷过的题计入分母

- **WHEN** 子模块内存在用户从未提交的图谱题
- **THEN** 该题 MUST 计入模块题目总数且 MUST 计为未完成

### Requirement: 单题图谱上下文

系统 SHALL 能针对指定 `problem_id` 返回该题在图谱中的位置（所属 track、子模块、序位、标注）、同子模块前序题的完成概况及子模块整体进度，供陪练注入上下文。

#### Scenario: 图谱内题目

- **WHEN** 请求的题号存在于某图谱子模块
- **THEN** 上下文 MUST 包含 track 名、子模块名、序位及前序题 AC 摘要

#### Scenario: 图谱外题目

- **WHEN** 请求的题号不在任何 algorithm-stone 图谱中
- **THEN** 系统 MUST 明确标示「图谱外」，且 MUST 仍返回基于 `problem_stats` 的单题画像摘要

### Requirement: 图谱状态 CLI

系统 SHALL 提供 `leetcode-tracker kg` 子命令族，至少包含导入、整体状态、按 track 进度、单题图谱上下文，且 MUST NOT 依赖外部网络。

#### Scenario: 查看导入状态

- **WHEN** 用户执行图谱状态命令
- **THEN** 输出 MUST 包含 track 数量、子模块数量、图谱题目数量及上次导入来源信息
