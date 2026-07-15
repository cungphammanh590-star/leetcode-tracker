# leetcode-tracker

完全本地的力扣刷题追踪助手（macOS MVP）。

浏览器扩展在 [leetcode.cn](https://leetcode.cn) 捕获提交 → 本机桥接写入 SQLite → CLI 查统计 / 生成 Markdown 日报。数据不出本机。

## 快速开始（约 5 步）

1. **安装 CLI**（建议用项目虚拟环境）

```bash
cd leetcode-tracker
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

2. **启动桥接服务**（保持该终端运行）

```bash
leetcode-tracker serve
```

默认监听 `http://127.0.0.1:8763`。数据库文件：`~/.local/share/leetcode-tracker/leetcode.db`。

3. **加载浏览器扩展（Chrome / Edge）**

- 打开 `chrome://extensions`（或 Edge 对应页面）
- 开启「开发者模式」
- 「加载已解压的扩展程序」→ 选择本仓库的 `extension/` 目录

4. **在 leetcode.cn 正常刷题提交**

标题栏扩展图标会出现简短 badge（`ok` / `dup` / `!`）。若为 `!`，请确认步骤 2 的服务已启动。

5. **查看统计 / 生成今日日报**

```bash
leetcode-tracker stats
leetcode-tracker report --today
```

日报默认写入：`~/leetcode-reports/YYYY-MM-DD.md`。

## 可选：每天自动出日报（需自行配置）

产品**不会**自动注册定时任务，也**不会**在 `serve` 里到点生成报告。若需要，可用 macOS `cron` 或 `launchd` 自行调用 CLI。

示例（每天 23:00，路径按你的安装位置修改）：

```cron
0 23 * * * /Users/你的用户名/Projects/leetcode-tracker/.venv/bin/leetcode-tracker report --today
```

## CLI

| 命令 | 说明 |
|------|------|
| `leetcode-tracker serve` | 启动本机桥接 |
| `leetcode-tracker stats` | 打印累计 / 今日 / 连续打卡等 |
| `leetcode-tracker report --today` | 生成或覆盖今日 Markdown 日报 |

## 范围与限制（MVP）

- 仅保证 **macOS** + **leetcode.cn**
- 去重键为力扣 `submission_id`（缺失则拒绝入库）
- 保存完整提交源码到本地库
- 无云同步、无 Web UI、无正式配置子系统（目录/端口写死）
- 扩展对力扣改版敏感；若抓不到字段，请开 issue 或对照 Network 面板排查

## 开发说明

规格与任务见 `openspec/changes/mvp-implementation/`。
