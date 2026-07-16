# LeetCode Tracker

完全本地的 **leetcode.cn** 刷题追踪助手（v0.2.0）。  
在浏览器提交题目后，扩展自动写入本机；桌面窗口、浏览器或终端可查看进度。**数据不出本机。**

## 快速开始（macOS）

从 [Releases](https://github.com/cungphammanh590-star/leetcode-tracker/releases) 下载 `LeetCode-Tracker-macOS-v0.2.0.zip`，解压后只有：

```text
LeetCode Tracker.app   ← 双击打开（本机服务 + 桌面仪表盘）
extension/             ← 浏览器「加载已解压的扩展程序」
使用说明.txt
```

1. 双击 **LeetCode Tracker.app**（若被系统拦截：右键 → 打开）
2. Chrome / Edge → `chrome://extensions` → 开启「开发者模式」→ 加载 `extension/` 文件夹
3. 打开 [leetcode.cn](https://leetcode.cn) 正常刷题提交；扩展图标 **ok** 表示已写入本机
4. 点击扩展图标 → **打开仪表盘**，或访问 http://127.0.0.1:8763/

## 数据存在哪里

| 内容 | 路径 | 是否必需 | 说明 |
|------|------|----------|------|
| **刷题记录（主数据）** | `~/.local/share/leetcode-tracker/leetcode.db` | 是 | 提交事实表 + 题目汇总表 |
| **配置** | `~/.config/leetcode-tracker/config.json` | 否 | 端口、日报目录、自启等 |
| **Markdown 日报** | `~/leetcode-reports/YYYY-MM-DD.md` | 否 | 可选快照，可重新生成 |
| **服务日志** | `~/Library/Logs/leetcode-tracker.*.log` | 否 | 自启排错用 |

### v0.2.0 新增：题目汇总表

在 SQLite 内除原始 `submissions` 外，新增两张**派生表**（详见 [docs/DATA_MODEL.md](docs/DATA_MODEL.md)）：

| 表 | 作用 |
|----|------|
| `problem_stats` | 每题终身画像（尝试次数、错误分布、AC 间隔、挣扎指数等） |
| `problem_daily_stats` | 每题每日快照（今日错题汇总、状态变化） |

仪表盘「今日错题」按**题目 + 错误类型次数**汇总，数据来自 `problem_daily_stats`。

从 v0.1 升级后，首次打开仪表盘会自动从已有提交重建汇总；也可手动执行 `leetcode-tracker rebuild-stats`。

## 常用命令

| 命令 | 说明 |
|------|------|
| `leetcode-tracker app` | 打开桌面仪表盘 |
| `leetcode-tracker stats` | 终端查看统计 |
| `leetcode-tracker rebuild-stats` | 从 submissions 重建汇总表 |
| `leetcode-tracker llm-context 560` | 输出单题 LLM 分析上下文（Markdown） |
| `leetcode-tracker report --today` | 生成今日 Markdown 日报 |
| `leetcode-tracker report clean --today` | 删除今日日报 |
| `leetcode-tracker logs clean` | 清空自启服务日志 |

HTTP API（本机桥接）：

| 端点 | 说明 |
|------|------|
| `GET /api/stats` | 仪表盘统计 |
| `GET /problems/{id}` | 单题详情页（浏览器） |
| `GET /api/problems/{id}/stats` | 单题终身 + 每日 + 提交记录 JSON |
| `GET /api/problems/{id}/llm-context` | LLM 用 Markdown 上下文 |

## 说明与限制

- 仅保证 **macOS** + **leetcode.cn**
- 无云同步、无内置大模型 API（`llm-context` 输出文本供你自行粘贴到 LLM）
- 扩展 popup 可一键打开浏览器仪表盘
- **关窗（X）**：后台保活桥接；**Cmd+Q**：停止桥接

## 常见问题

**今日错题没有汇总 / 升级后统计为空**

```bash
leetcode-tracker rebuild-stats
```

然后重启 App 或刷新 http://127.0.0.1:8763/

**扩展离线**

查看 `~/Library/Logs/leetcode-tracker-app.log`，或终端运行 `leetcode-tracker serve`。
