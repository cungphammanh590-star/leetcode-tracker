## Why

刷题者需要零手动录入、完全本地的进度追踪，才能持续看清投入与薄弱点，同时避免把提交代码和刷题数据交给云端。MVP 要尽快验证三件事：用户愿不愿用本地工具、扩展+本地桥接能否稳住采集、CLI 生成的日报有没有用——用最小闭环证明后再加配置与跨平台。

## What Changes

- 新增 Chrome/Edge（MV3）扩展：在 leetcode.cn 捕获提交与判题结果，并向本机桥接服务投递。
- 新增本机 Python HTTP 桥接服务（默认 `127.0.0.1:8763`）：接收投递、校验、写入 SQLite（含完整代码）。
- 新增本地持久化：题目与提交记录 schema、以力扣 `submission_id` 唯一去重；缺失 id 则拒绝入库。
- 新增基础统计查询：累计提交/通过率、难度分布、连续打卡、今日提交、最近提交列表。
- 新增日报能力：`leetcode-tracker report --today` 生成 Markdown 到默认目录 `~/leetcode-reports/YYYY-MM-DD.md`；文档提供可选 cron/launchd 示例。不在 `serve` 内做定时或启动补跑。
- 新增命令行入口 `leetcode-tracker`（console script）：子命令 `serve`、`report --today`、`stats`。

**Non-goals（本 change 明确不做）**

- 用户可配置能力（报告目录/时间/端口的配置 UI 或正式 config 子系统）——默认写死，后续独立 change。
- `serve` 内调度器或启动时自动补跑日报。
- leetcode.com、Windows/Linux 安装与定时任务打磨。
- 云同步、Web 仪表盘、AI 分析、多用户账号。

## Capabilities

### New Capabilities

- `submission-capture`: 浏览器扩展捕获 leetcode.cn 提交与判题结果，经本机桥接写入 SQLite；`submission_id` 必填且唯一去重；持久化完整代码与题目元数据。
- `progress-stats`: 基于本地库计算累计与今日指标、难度分布、连续打卡天数、最近提交列表；经 `leetcode-tracker stats` 可读。
- `daily-report`: 通过 `leetcode-tracker report --today` 按日生成并落盘 Markdown 日报（默认路径与命名）；调度交由用户/cron，本系统不内置定时。

### Modified Capabilities

- （无——主规格尚未建立）

## Impact

- **新增组件**：`extension/`（MV3）、Python 桥接与 CLI、SQLite 库文件、默认报告目录下的 Markdown。
- **本机网络**：仅监听回环地址；除用户访问 leetcode.cn 外，产品自身不发起外部请求。
- **依赖边界**：Python 侧尽量标准库；若引入第三方须在 design 明示并论证。
- **后续预留**：`app-config`、跨站点/跨平台、进程内调度或 serve 补跑，均作为后续 change，不阻塞本 MVP 归档。
