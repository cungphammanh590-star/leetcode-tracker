## Context

主规格已有 `submission-capture` / `progress-stats` / `daily-report`（归档自 mvp-implementation）。0.1.1 在仅 leetcode.cn + macOS 前提下补齐配置、自启、仪表盘与 pywebview 桌面壳；大模型对接明确延后。

## Goals / Non-Goals

**Goals:**

- 用户可选开机自启本机服务，少漏采。
- 用 pywebview 在桌面打开本地仪表盘。
- 可配置端口/报告目录/报告时间/autostart。
- 日报与统计增强到「错题 + 近 7 日」；Markdown 便于日后给 LLM。
- 扩展正式通知，无调试开关。

**Non-Goals:**

- LLM API；库路径配置；跨平台；公证分发；调试开关。

## Decisions

### D1：配置文件

- **决定**：`~/.config/leetcode-tracker/config.json`；缺省键用内置默认；库路径不进配置。
- **键**：`host`（默认 127.0.0.1）、`port`（8763）、`report_dir`、`report_time`（如 `23:00`，供文档/未来定时）、`autostart`（bool）。

### D2：自启

- **决定**：macOS LaunchAgent 调用已安装的 `leetcode-tracker serve` 绝对路径；CLI：`autostart install` / `uninstall`；`autostart` 配置为 true 时安装流程写入并 load，false 时卸载或保持不装。
- **理由**：与系统调度解耦于「进程内 timer」；用户可关。

### D3：仪表盘与桥接同端口

- **决定**：`serve` 同时提供 `/` 仪表盘静态页与只读 JSON API（如 `/api/stats`）；扩展继续 `POST /submit`。
- **理由**：单一进程，pywebview 只需打开 `http://127.0.0.1:{port}/`。

### D4：桌面壳

- **决定**：`leetcode-tracker app`（名可微调）启动时确保桥接可用（已起则复用，未起则拉起或同进程托管），再用 pywebview 打开仪表盘 URL。
- **理由**：满足「桌面展示」；不做公证 DMG。

### D5：提交后刷新

- **决定**：仪表盘前端短轮询或提交成功后扩展不强制重写 Markdown；可选：入库后触达 SSE/简单版本号接口供 UI 刷新。1.01 用短轮询即可。
- **理由**：实时看数靠 DB；Markdown 仍以 CLI `report` 为主快照。

### D6：依赖

- **决定**：`pywebview` 记入 `pyproject.toml` optional 或主依赖；README 说明 macOS 权限。

### D7：版本

- **决定**：包版本 `0.1.1`。

## Risks / Trade-offs

- [pywebview / WebKit 权限] → README 说明首次授权；失败时仍可用浏览器打开仪表盘 URL。
- [自启路径随 conda/venv 变化] → install 时写入当前 `sys.executable`/`leetcode-tracker` 绝对路径；换环境需重装 autostart。
- [扩展通知打扰] → 仅终态成功/失败各一次；无调试噪声。

## Migration Plan

- 无 DB schema 破坏性变更（若有仅 ADD）。
- 首次读配置写入默认文件可选。
- 归档后主规格更新对应 capability。

## Open Questions

- （无）桌面壳用 pywebview、LLM 下版本，已裁定。
