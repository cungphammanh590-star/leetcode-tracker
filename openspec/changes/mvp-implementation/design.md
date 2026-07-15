## Context

本项目为绿场 MVP：在 macOS 上验证「leetcode.com 提交自动入库 → 本地统计 → CLI 日报」闭环。用户是个人刷题者；数据与代码不得离开本机。提案已锁定三件套 capability（`submission-capture` / `progress-stats` / `daily-report`），配置子系统与进程内调度明确延后。

约束摘要：仅回环监听、`submission_id` 强去重、存完整 code、日报只靠 `leetcode-tracker report --today`（可选系统定时）。

## Goals / Non-Goals

**Goals:**

- 实现扩展 → 本机桥接 → SQLite 的可靠采集链路。
- 提供可手验的统计与按日落盘的 Markdown 日报。
- 安装与日常使用路径尽量短（macOS + Chrome/Edge）。
- 技术选择保持轻量，便于后续加配置/跨平台而不推倒重来。

**Non-Goals:**

- 用户可配置目录/端口/报告时间的正式子系统。
- `serve` 内定时器或启动自动补跑日报。
- leetcode.cn、Windows/Linux 一等支持。
- Web 仪表盘、云同步、AI 分析。

## Decisions

### D1：仓库与进程形态

- **决定**：单仓库；Python 包名 `leetcode_tracker`，经 `pyproject.toml` 的 console script 暴露命令 **`leetcode-tracker`**（子命令：`serve` / `stats` / `report`），安装后可直接 `leetcode-tracker serve`，无需 `python -m`；浏览器扩展为独立 `extension/` 目录，开发者模式加载。
- **理由**：CLI 观感更干净；cron/launchd 示例也可直接调用同名命令。
- **备选**：仅 `python -m leetcode_tracker` → 可用但不优雅，作为开发兜底，正式用法以 console script 为准；扩展内直接写 SQLite → 否决。

### D2：桥接服务实现

- **决定**：Python 3.9+，优先标准库 `http.server`（或同等最小 HTTP 服务）监听 `127.0.0.1:8763`；SQLite 用标准库 `sqlite3`。
- **理由**：零/少依赖、启动快、满足 NFR；仅本机回环降低暴露面。
- **备选**：Flask/FastAPI → 对 MVP 过重；否决。第三方调度库 → 本 change 不引入（无进程内调度）。

### D3：默认路径与库位置（硬编码）

| 项 | 默认值 |
|----|--------|
| 监听 | `127.0.0.1:8763` |
| 数据库 | `~/.local/share/leetcode-tracker/leetcode.db`（若目录惯例后续微调，以实现与 README 为准，但须本机单文件） |
| 报告目录 | `~/leetcode-reports` |
| 报告文件名 | `YYYY-MM-DD.md`（本地日历日） |
| 文档示例定时 | 每天 23:00 调用 `leetcode-tracker report --today` |

- **理由**：配置后置（方案 C）；先写死才能快验证。
- **备选**：首版就做 config.json → 扩大范围，否决。

### D4：采集与去重（方案 A）

- **决定**：扩展在网络层拦截提交/判题相关请求（优先 fetch/XHR 或 declarativeNetRequest/调试接口中可行的最小方案），取得 `submission_id` 与终态后再 `POST /submit`；服务端将 `submission_id` 列为 UNIQUE；缺失或冲突时拒绝写入（4xx），不降级到「题目+时间」近似去重。
- **理由**：统计可信优先于「尽量多记」。
- **备选**：近似去重 → 易脏数据，否决（已裁定）。

### D5：请求合同（桥接 API）

- **决定**：MVP 仅两个端点：
  - `POST /submit`：题目元数据 + 提交结果 + **完整 code** + **必填 submission_id**
  - `GET /health`：进程与库可用性、提交条数等探活字段
- **理由**：够用；字段级细节实现时与扩展对齐，行为以 specs 为准。
- **说明**：CORS 仅需允许浏览器扩展来源访问本机回环（按 MV3 实际约束配置）。

### D6：数据模型要点

- **决定**：至少包含 `problems`（按力扣题目 id/slug 幂等 upsert）、`submissions`（含 `submission_id` UNIQUE、完整 `code`、状态、耗时、内存、语言、时间戳）。`daily_stats` 可选：MVP 可现算，不强制预聚合表。
- **理由**：写路径简单；读路径数据量小。
- **备选**：强制每日预聚合 → 增加写入一致性，收益低，可后置。

### D7：统计与日报

- **决定**：统计逻辑单独模块，供 `stats` 与 `report` 复用；连续打卡 = 本地时区下「连续有至少一次提交的日历日」截止今天（若今天尚无提交则截止昨天，具体规则在实现与 specs 场景中保持一致）。
- **决定**：`leetcode-tracker report --today` 读取今日提交与累计指标，覆盖写入 `~/leetcode-reports/YYYY-MM-DD.md`（同日多次执行以最后一次为准）。
- **理由**：命令可重复执行，配合用户/cron；不做 serve 补跑（方案 Z）。

### D8：可选系统定时（仅文档）

- **决定**：README 提供 macOS `launchd` 或 `cron` 示例，在 23:00 调用 `leetcode-tracker report --today`；产品代码不安装、不管理定时任务。
- **理由**：调度与采集进程解耦，符合混合方案 Z。

### D9：扩展失败提示（MVP 最简）

- **决定**：投递失败时使用最简单可感知方式（优先 `console` + 扩展 badge/title，或单次 `chrome.notifications` 二选一以实现成本最低者为准）；不自研 popup UI。
- **理由**：先验证采集链路；提示体验后续 change 再打磨。

## Risks / Trade-offs

- [力扣改版导致扩展抓不到 submission_id] → 拦截网络层而非 DOM；失败时明确提示；必要时后续加备用 GraphQL 路径（本 MVP 可不实现备用）。
- [用户未启动 serve → 采集失败] → 扩展在投递失败时提示；文档强调先 `serve`。
- [23:00 机器休眠 → 无日报] → 可手跑 `report --today` 或调整 cron；不接受 serve 内补跑范围蔓延。
- [存完整 code 增大库体积] → 本地可接受；后续再加清理/归档。
- [端口 8763 占用] → 启动失败并提示；本 MVP 不提供改端口配置。

## Migration Plan

- 绿场：无历史迁移。首次 `serve` 自动建库建表。
- 回滚：停服务、移除扩展、删除库文件与报告目录即可；无外部状态。

## Open Questions

- （无阻塞项）扩展具体勾住 leetcode.com 哪几个 URL/响应字段，实现 Phase 时对照网络面板敲定，不阻断本设计归档。
