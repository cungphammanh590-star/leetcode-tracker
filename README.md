# LeetCode Tracker

完全本地的 **leetcode.cn** 刷题追踪助手（v0.2.0）。  
在浏览器正常提交后，扩展会把记录写到你的 Mac 上；你在浏览器里就能看统计和每道题的做题情况。**数据不出本机。**

## 你需要准备什么

- macOS
- Chrome 或 Edge
- [leetcode.cn](https://leetcode.cn) 账号（照常刷题即可）

## 快速开始

从 [Releases](https://github.com/cungphammanh590-star/leetcode-tracker/releases) 下载 `LeetCode-Tracker-macOS-v0.2.0.zip`，解压后会有：

```text
LeetCode Tracker.app   ← 可选：用来启动本机服务（见下文）
extension/             ← 浏览器扩展
使用说明.txt
```

### 第一步：启动本机服务（推荐方式）

**推荐在终端里启动服务**，然后用浏览器看仪表盘：

```bash
# 一次性安装（需要 Python 3.9+）
pip install git+https://github.com/cungphammanh590-star/leetcode-tracker.git

# 每次使用前启动（终端窗口请保持打开）
leetcode-tracker serve
```

启动成功后，在浏览器打开：**http://127.0.0.1:8763/**

> **关于 App**：zip 里的 `LeetCode Tracker.app` 目前也能启动同样的本机服务。  
> **后续版本会把 App 做成「启动器」**——主要负责帮你一键拉起服务；日常查看进度仍以**浏览器仪表盘**为主，不再依赖桌面里的独立窗口。

**若暂时不想用 pip 安装**：可双击 `LeetCode Tracker.app` 代替 `serve`（若系统拦截：先运行 `xattr -cr "LeetCode Tracker.app"`，再右键 → 打开）。服务起来后，同样用浏览器访问上面的地址。

### 第二步：安装浏览器扩展

1. 打开 `chrome://extensions`（Edge 用 `edge://extensions`）
2. 开启「开发者模式」
3. 「加载已解压的扩展程序」→ 选择 zip 里的 `extension` 文件夹
4. 在 `chrome://extensions` 点「重新加载」确保是最新版本

### 第三步：开刷

1. 打开 [leetcode.cn](https://leetcode.cn) 正常做题、提交
2. 扩展图标显示 **ok** 或弹出通知，表示已写入本机
3. 查看进度（任选）：
   - 浏览器打开 http://127.0.0.1:8763/
   - 或点击扩展图标 → **打开仪表盘**

## v0.2.0 能看什么

| 页面 | 内容 |
|------|------|
| **仪表盘首页** | 今日提交、连续打卡、近 7 日、今日错题汇总、题目列表 |
| **题目详情** | 点击任意题目标题进入：终身做题画像、每日情况、每次提交记录 |
| **今日错题** | 同一道题合并显示，例如 `Compile Error ×3，Wrong Answer ×2` |

题目详情地址示例：`http://127.0.0.1:8763/problems/560`

## 数据存在哪里

| 内容 | 路径 | 说明 |
|------|------|------|
| **刷题记录** | `~/.local/share/leetcode-tracker/leetcode.db` | 主数据，请勿随意删除 |
| **配置** | `~/.config/leetcode-tracker/config.json` | 端口等，首次运行自动生成 |
| **日报（可选）** | `~/leetcode-reports/` | Markdown 快照，删了可重新生成 |
| **日志（可选）** | `~/Library/Logs/leetcode-tracker*.log` | 排错用 |

仪表盘读的是数据库里的记录，**不依赖** Markdown 日报。

## 常用操作

在**已安装** `leetcode-tracker` 的前提下，终端还可以：

| 命令 | 用途 |
|------|------|
| `leetcode-tracker serve` | 启动本机服务（**推荐**） |
| `leetcode-tracker stats` | 在终端看简要统计 |
| `leetcode-tracker report --today` | 导出今日 Markdown 日报 |
| `leetcode-tracker app` | 打开桌面窗口（非首选，后续由启动器 App 替代） |

## 常见问题

**扩展显示「离线」**

本机服务没在跑。请先执行 `leetcode-tracker serve`（或双击 App），再点扩展里的「重新检测」。

**仪表盘打不开 / 数据不更新**

1. 确认终端里 `serve` 仍在运行  
2. 刷新浏览器页面  
3. 扩展是否已「重新加载」

**今日错题没有汇总、统计是空的**

先确认 `serve` 已启动，刷新仪表盘；若刚从旧版升级，关闭再开一次服务即可（会自动从已有记录恢复汇总）。

**App 闪退**

查看 `~/Library/Logs/leetcode-tracker-app.log`。可改用终端 `leetcode-tracker serve` + 浏览器仪表盘，效果相同。

## 说明与限制

- 仅支持 **leetcode.cn**（不是 leetcode.com）
- 无云同步、无账号系统、不内置 AI
- 未公证的 App 首次需「右键 → 打开」
- 扩展与 App **无需同版本号**，只要本机服务在线即可通信
