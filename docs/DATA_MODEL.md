# 数据模型规范（v0.3.0）

## 设计原则

1. **`submissions` 是唯一事实来源**：每次提交一条记录，只增不改。
2. **`problem_stats` / `problem_daily_stats` 是派生读模型**：可从 `submissions` 全量重建。
3. **`problems` 是题目维表**：`problem_stats` 冗余 `title/difficulty/topic_tags` 便于 LLM 单条读取；`upsert_problem` 后必须同步到 `problem_stats`。

## 表结构

### `problems`（题目维表）

| 字段 | 说明 |
|------|------|
| problem_id | 力扣题号（唯一） |
| title / slug / difficulty / tags | 题目元数据 |

### `submissions`（提交事实表）

| 字段 | 说明 |
|------|------|
| submission_id | 力扣提交 ID（唯一） |
| problem_id / status / submitted_at | 关联题目、判题状态、时间 |
| code / runtime_ms / memory_mb / language | 可选详情 |

`status` 与扩展写入对齐，使用全称：`Accepted`、`Wrong Answer`、`Compile Error` 等。

### `problem_stats`（终身画像）

每题一行，回答「我在这道题上是什么水平」。

| 字段 | 说明 |
|------|------|
| total_attempts / accepted_count / wrong_count | 终身计数 |
| status_breakdown | JSON，键为完整 status 名称 |
| first_attempt_at / last_attempt_at / first_accepted_at | 时间线 |
| acceptance_rate / struggle_score | 预计算比率 |
| solve_time_seconds | 首次 AC 耗时（秒） |
| **avg_attempts_to_ac** | **本次 AC 与上次 AC 之间的尝试次数**（含本次 AC；首次 AC 则为累计尝试数） |
| attempts_at_last_ac | 内部字段，上次 AC 时的 total_attempts，用于增量更新 |
| last_status / last_submitted_at | 最新快照 |
| llm_summary / common_pitfall | 预留，供后续 LLM 写入 |

### `problem_daily_stats`（每日快照）

每题每天一行，回答「今天/近期状态怎么变」。

| 字段 | 说明 |
|------|------|
| day | `YYYY-MM-DD`（本地日历日） |
| attempts / accepted_today / wrong_today | 当日计数 |
| status_breakdown | 当日 JSON 分布 |
| consecutive_days | 该题连续有提交的自然日天数 |
| is_new_today | 是否人生首次做这题 |
| is_review_today | 是否复习（此前已 AC，今天又做） |
| status_change | `first_ac` / `improved` / `declined` / `stuck` |

#### `status_change` 算法

| 值 | 条件 |
|----|------|
| `first_ac` | 当日有 AC，且 `first_accepted_at` 落在当日 |
| `improved` | 当日有 AC（非首次 AC） |
| `stuck` | 当日仅错题，且昨日也有错题 |
| `declined` | 当日仅错题，但此前已 AC |
| （空） | 其他 |

近 7 日趋势在查询时对 `problem_daily_stats` 按 `day` 聚合（方案 A），不冗余 `last_7d_*` 字段。

### 知识图谱（`kg_*`，只读参考层）

自 algorithm-stone map 导入；与用户 `submissions` 分离逻辑，可 `kg import` 重复执行。

| 表 | 说明 |
|----|------|
| `kg_tracks` | 路线图（dp、tree…） |
| `kg_nodes` | 子模块；`id` = `{track_id}::{sort_order}::{name}` |
| `kg_node_problems` | 题在子模块内顺序与 `annotation` |
| `kg_edges` | 同子模块内学习顺序边 |
| `kg_meta` | 导入时间、来源等 |

多 track 选题（陪练）：**最弱 node 优先**，平局取**最近活跃** track。

### 陪练（`coach_sessions` + LangGraph checkpoint 表）

| 表 | 说明 |
|----|------|
| `coach_sessions` | session 元数据、模板 opening、context Markdown |
| LangGraph checkpoint 表 | 与 `leetcode.db` 同文件，存多轮对话状态 |

## 写入时机

1. `save_submission` 成功插入新提交后，同事务调用 `apply_submission_stats`。
2. `upsert_problem` 后调用 `sync_problem_meta`。
3. 升级后若 `problem_stats` 为空但 `submissions` 有数据，首次读统计时自动 `rebuild-stats`。
4. 手动：`leetcode-tracker rebuild-stats --from-scratch`。

## API

| 端点 | 说明 |
|------|------|
| `GET /api/stats` | 仪表盘；`today_wrong` 来自 `problem_daily_stats` |
| `GET /api/problems/{id}/stats` | 单题终身 + 近 7 日每日快照 |
| `GET /api/problems/{id}/llm-context` | LLM 用 Markdown 上下文 |
| `GET /health` | 含 `port`、`kg_imported`、`coach_available` |
| `GET /coach` | 陪练 Web 页 |
| `GET /api/coach/hint` | 按 `problem_id` 或库内 `slug` 返回模板建议（扩展弹窗，只读） |
| `POST /api/coach/engage` | 打开陪练页时按需读库组上下文 + 模板开场（不调 LLM） |
| `POST /api/coach/chat` | 多轮陪练（调 Ollama；注入 session 内已缓存 context） |

## CLI

| 命令 | 说明 |
|------|------|
| `leetcode-tracker rebuild-stats` | 从 submissions 全量重建汇总表 |
| `leetcode-tracker llm-context 560` | 打印单题 LLM 上下文 |
| `leetcode-tracker kg import` | 导入知识图谱 |
| `leetcode-tracker kg progress --track dp` | 路线进度 |
| `leetcode-tracker coach follow <submission_id>` | 陪练开场 |
