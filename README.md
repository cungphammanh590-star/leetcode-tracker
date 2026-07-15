# leetcode-tracker

完全本地的 **leetcode.cn** 刷题追踪助手（v0.1.1）。

浏览器扩展捕获提交 → 本机桥接写入 SQLite → CLI / 日报 / **桌面仪表盘（pywebview）**。数据不出本机。

## 普通用户（推荐）：macOS 发行包

发行 ZIP 解压后**只有两项**：

```text
LeetCode Tracker.app   ← 双击打开（本机服务 + 桌面窗）
extension/             ← 浏览器「加载已解压的扩展」
使用说明.txt
```

**不含** `openspec`、源码、`node_modules` 等开发文件。

1. 双击 `LeetCode Tracker.app`（若被拦截：右键 → 打开）
2. Chrome/Edge → 开发者模式 → 加载 `extension/` 文件夹
3. 在 leetcode.cn 提交；桌面窗口可看进度

### 维护者如何打这个包

```bash
chmod +x scripts/package_macos.sh
./scripts/package_macos.sh
# 产物：release/LeetCode-Tracker-macOS-v0.1.1.zip
```

将该 zip 上传到 GitHub Release 即可。

## 开发者安装

```bash
cd leetcode-tracker
pip install -e .
pip install -e '.[app]'          # 桌面窗口
# pip install -e '.[packaging]'  # 打 macOS 包时需要
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

## 说明与限制

- 仅保证 **macOS** + **leetcode.cn**
- 自启只负责 `serve`；桌面窗口用 `.app` / `app` 命令或浏览器打开仪表盘
- 换 conda/venv 后请重新 `autostart install`
- **本版本不对接大模型 API**
- 无云同步、无账号系统
- `.app` 未做 Apple 公证时，首次需「右键打开」

## 规格（仅仓库开发用）

见 `openspec/`（不进入用户发行包）。
