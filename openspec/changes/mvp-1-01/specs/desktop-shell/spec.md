## ADDED Requirements

### Requirement: pywebview 桌面窗口

系统 SHALL 提供 CLI 入口启动 pywebview 桌面窗口，加载本机仪表盘 URL。窗口 MUST 展示与浏览器打开仪表盘等价的核心进度信息。

#### Scenario: 启动桌面壳

- **WHEN** 用户执行桌面壳启动命令且本机桥接可访问（或由该命令确保服务可用）
- **THEN** 系统 MUST 打开桌面窗口并加载本机仪表盘

#### Scenario: 桥接未启动时的行为

- **WHEN** 用户启动桌面壳但桥接尚未监听
- **THEN** 系统 MUST 尝试拉起桥接或给出明确失败提示（不得静默空白无说明）

### Requirement: macOS 开机自启 serve

系统 SHALL 支持通过 launchd（LaunchAgent）在用户登录后自动启动 `leetcode-tracker serve`。系统 MUST 提供安装与卸载自启的 CLI。当配置 `autostart=false` 或用户卸载后，系统 MUST NOT 依赖自启才能手动运行。

#### Scenario: 安装自启

- **WHEN** 用户执行自启安装且当前 `leetcode-tracker` 可用
- **THEN** 系统 MUST 写入 LaunchAgent 并指向当前可执行文件的绝对路径（或等价可靠启动方式）

#### Scenario: 卸载自启

- **WHEN** 用户执行自启卸载
- **THEN** 登录后 MUST 不再自动启动该 LaunchAgent 服务

#### Scenario: 关闭自启仍可手动用

- **WHEN** 自启已关闭或未安装
- **THEN** 用户仍 MUST 能通过 CLI 手动 `serve` / 启动桌面壳
