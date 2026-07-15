## Why

MVP 已验证「国站采集 → 本地入库 → CLI/日报」可行，但日常仍缺：服务常忘开、无可视桌面入口、配置写死、日报信息偏薄。0.1.1（mvp-1.01）要把本机体验补齐到「能天天挂着刷 + 桌面一眼看到进度」，并为下版本对接大模型留好 Markdown/统计素材，同时仍保持数据不出本机。

## What Changes

- 新增轻量 **app-config**（JSON）：监听端口、报告目录、报告时间、是否开机自启；**不提供**数据库路径配置。
- 新增 macOS **launchd 自启** `leetcode-tracker serve`（可关；关闭则手动启动）；CLI 安装/卸载自启。
- 新增 **本机仪表盘**（由桥接提供只读页面/API），展示进度与今日/近期数据。
- 新增 **pywebview 桌面壳**：包装本机仪表盘为桌面窗口（非完整商店级 `.app` 签名分发）。
- 加固 **leetcode.cn** 采集；扩展改为正式提示（badge/popup/**系统通知**），**不提供**调试开关。
- 增强日报：今日错题列表、近 7 日对比；Markdown 结构保持稳定，便于下版本喂给大模型。
- 包版本升至 **0.1.1**。

**Non-goals（本 change / 本版本不做）**

- 对接任何大模型 API、云总结（**下个版本**）。
- 数据库路径配置或迁移 MySQL。
- Windows/Linux 一等支持；支持站点除 leetcode.cn 以外的域名。
- 云同步、账号系统、调试开关。
- 完整 macOS 公证/DMG 商店分发（本版以 pywebview 本地窗口为主）。

## Capabilities

### New Capabilities

- `app-config`: 本机 JSON 配置的读写与默认值；覆盖端口、报告目录、报告时间、autostart；库路径不可配。
- `local-dashboard`: 本机只读仪表盘（HTTP），展示统计与列表，数据来自 SQLite。
- `desktop-shell`: pywebview 桌面窗口加载仪表盘；提供 launchd 安装/卸载以使 serve（及桌面入口约定）可开机自启。

### Modified Capabilities

- `submission-capture`: 采集体验加固；投递成功/失败使用系统通知等正式反馈（无调试开关）。
- `progress-stats`: 补充今日错题与近 7 日对比等查询，供日报与仪表盘复用。
- `daily-report`: 日报内容增加错题与近 7 日对比；落盘目录可走配置；仍不要求 `serve` 内定时器自动出 Markdown（仪表盘为实时读库）。

## Impact

- **依赖**：引入 `pywebview`（及 macOS 所需的最小原生依赖说明）；配置文件默认 `~/.config/leetcode-tracker/config.json`。
- **CLI**：可能新增 `config` / `autostart install|uninstall` / `app`（或等价）子命令；`serve` 可同时提供仪表盘路由。
- **扩展**：通知权限；去除面向用户的调试面板开关。
- **后续**：下一版本可基于稳定日报/导出对接 LLM；桌面壳可再演进为更完整的托盘应用。
