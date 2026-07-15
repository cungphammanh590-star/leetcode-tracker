# leetcode-tracker

完全本地的 **leetcode.cn** 刷题追踪助手（v0.1.1）。

浏览器扩展捕获提交 → 本机桥接写入 SQLite → CLI / 日报 / **桌面仪表盘（pywebview）**。数据不出本机。

## 安装

```bash
cd leetcode-tracker
pip install -e .
# 桌面窗口可选依赖
pip install -e '.[app]'
```

## 常用命令

| 命令 | 说明 |
|------|------|
| `leetcode-tracker serve` | 启动桥接 + 仪表盘（默认 `http://127.0.0.1:8763/`） |
| `leetcode-tracker app` | pywebview 桌面窗口打开仪表盘（必要时自动拉起服务） |
| `leetcode-tracker stats` | 终端统计（含错题与近 7 日） |
| `leetcode-tracker report --today` | 生成今日 Markdown 日报 |
| `leetcode-tracker config show` | 查看配置 |
| `leetcode-tracker config set port 8763` | 修改配置项 |
| `leetcode-tracker autostart install` | macOS 登录自启 `serve` |
| `leetcode-tracker autostart uninstall` | 取消自启 |

配置文件：`~/.config/leetcode-tracker/config.json`  
（`host` / `port` / `report_dir` / `report_time` / `autostart`；**库路径不可配**）

数据库：`~/.local/share/leetcode-tracker/leetcode.db`  
日报默认：`~/leetcode-reports/YYYY-MM-DD.md`

## 快速使用

1. `pip install -e '.[app]'`
2. `leetcode-tracker app`（或 `serve` + 浏览器打开仪表盘）
3. Chrome 开发者模式加载 `extension/`
4. 在 **leetcode.cn** 题目页提交
5. 需要时：`leetcode-tracker report --today`；可选 `autostart install`

## 说明与限制

- 仅保证 **macOS** + **leetcode.cn**
- 自启只负责 `serve`；桌面窗口需自行打开 `app` 或浏览器
- 换 conda/venv 后请重新 `autostart install`
- **本版本不对接大模型 API**（日报 Markdown 可留给下版本总结）
- 无云同步、无账号系统

## 规格

见 `openspec/changes/mvp-1-01/` 与 `openspec/specs/`。
