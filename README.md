# LeetCode Tracker

完全本地的 **leetcode.cn** 刷题追踪助手（v0.1.1）。  
在浏览器提交题目后，扩展自动写入本机；桌面窗口或终端可查看进度。**数据不出本机。**

## 快速开始（macOS）

从 [Releases](https://github.com/cungphammanh590-star/leetcode-tracker/releases) 下载 `LeetCode-Tracker-macOS-v0.1.1.zip`，解压后只有：

```text
LeetCode Tracker.app   ← 双击打开（本机服务 + 桌面仪表盘）
extension/             ← 浏览器「加载已解压的扩展程序」
使用说明.txt
```

1. 双击 **LeetCode Tracker.app**（若被系统拦截：右键 → 打开）
2. Chrome / Edge → `chrome://extensions` → 开启「开发者模式」→ 加载 `extension/` 文件夹
3. 打开 [leetcode.cn](https://leetcode.cn) 正常刷题提交；桌面窗口会显示进度

扩展图标出现 **ok** 或系统通知，表示已写入本机。

## 数据存在哪里

| 内容 | 路径 | 是否必需 | 说明 |
|------|------|----------|------|
| **刷题记录（主数据）** | `~/.local/share/leetcode-tracker/leetcode.db` | 是 | 所有提交、代码、统计的真实来源 |
| **配置** | `~/.config/leetcode-tracker/config.json` | 否 | 端口、日报目录、自启等；首次运行自动生成 |
| **Markdown 日报** | `~/leetcode-reports/YYYY-MM-DD.md` | 否 | 从数据库导出的**快照**，可随时重新生成 |
| **服务日志** | `~/Library/Logs/leetcode-tracker.out.log`<br>`~/Library/Logs/leetcode-tracker.err.log` | 否 | 仅在使用「开机自启」时产生，用于排错 |

### 仪表盘读什么？

桌面仪表盘和浏览器里的 `http://127.0.0.1:8763/` **直接读 SQLite 数据库**（通过 `/api/stats`），**不读取** Markdown 日报。

Markdown 日报是可选导出：方便你自己存档，或日后交给大模型分析（本版本不含 AI 功能）。删了日报**不影响**仪表盘和刷题记录；需要时用命令重新生成即可。

## 常用命令

在终端执行（发行包用户需自行安装 Python 包，或仅在开发环境使用；普通用户主要靠 `.app` + 扩展）：

| 命令 | 说明 |
|------|------|
| `leetcode-tracker app` | 打开桌面仪表盘（桥接未运行时会自动拉起） |
| `leetcode-tracker stats` | 终端查看统计 |
| `leetcode-tracker report --today` | 从数据库生成今日 Markdown 日报 |
| `leetcode-tracker report clean --today` | 删除今日日报文件 |
| `leetcode-tracker report clean --all` | 删除日报目录下全部 `.md` 文件 |
| `leetcode-tracker logs clean` | 清空自启服务日志（不影响刷题数据） |
| `leetcode-tracker config show` | 查看配置 |
| `leetcode-tracker autostart install` | macOS 登录时自动启动本机服务 |
| `leetcode-tracker autostart uninstall` | 取消开机自启 |

配置项（`config set <键> <值>`）：`host`、`port`、`report_dir`、`report_time`、`autostart`。数据库路径**不可配置**。

## 清理与维护

- **刷题数据库**：不建议删除；这是唯一的主数据源。
- **Markdown 日报**：可安全删除，用 `report clean` 或手动删 `~/leetcode-reports/` 里的文件；需要时 `report --today` 会按当前数据库重新生成。
- **服务日志**：可安全删除，用 `logs clean` 或手动删上述两个 `.log` 文件；不影响刷题记录，自启服务会继续追加新日志。
- **换 Python 环境后**：若用过 `autostart install`，请重新执行一次以更新路径。

## 说明与限制

- 仅保证 **macOS** + **leetcode.cn**
- 无云同步、无账号系统、不对接大模型 API
- `.app` 未做 Apple 公证时，首次打开需「右键 → 打开」
- 自启只负责后台桥接服务；桌面窗口仍需打开 `.app` 或使用 `app` 命令
