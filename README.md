# LeetCode Tracker

完全本地的 **leetcode.cn** 刷题追踪助手（v0.3.0）。  
在浏览器正常提交后，扩展会把记录写到你的 Mac 上；可选 **知识图谱 + 本地陪练** 在每次提交后陪你复盘。**刷题数据不出本机**；陪练默认使用本机 Ollama（可选配置云端 API 占位，MVP 未启用）。

## 你需要准备什么

- macOS
- Chrome 或 Edge
- [leetcode.cn](https://leetcode.cn) 账号（照常刷题即可）
- **陪练（可选）**：`pip install 'leetcode-tracker[coach]'` + [Ollama](https://ollama.com/) + 量化模型（Neo 8GB 建议 `qwen2.5:7b-instruct-q4_K_M`）

## 快速开始

```bash
# 追踪（核心）
pip install git+https://github.com/cungphammanh590-star/leetcode-tracker.git

# 陪练 + 知识图谱（可选 extra）
pip install 'leetcode-tracker[coach]'

# 启动本机服务
leetcode-tracker serve

# 一次性导入学习路线图（algorithm-stone，随包附带）
leetcode-tracker kg import
```

浏览器打开：**http://127.0.0.1:8763/**

### 浏览器扩展

1. `chrome://extensions` → 开发者模式 → 加载 `extension/` 文件夹
2. 在 **leetcode.cn 题目页** 点击扩展图标 → 弹窗显示 **本题陪练建议**（只读本机库，按需）
3. 正常提交后：扩展**只负责入库**；成功会通知「提交已记录」，点击可打开陪练页
4. **陪练与采集解耦**：不会在提交瞬间调用 LLM / engage；打开陪练页时才读库组上下文，你开口后才走 LangGraph

若修改了桥接端口（`leetcode-tracker config set port 9000`），扩展会通过 `GET /health` 自动读取 `port` 字段；请重新加载扩展并重启 `serve`。

## v0.3.0 新能力

| 能力 | 说明 |
|------|------|
| **知识图谱** | 自 [algorithm-stone](https://github.com/acm-clan/algorithm-stone)（MIT）导入 14 条路线、子模块与学习顺序 |
| **陪练 Coach** | 打开陪练页时读库组上下文；对话时才调本地 LLM；**不泄题、不讲完整解法** |
| **陪练页** | `http://127.0.0.1:8763/coach?submission=<id>` 或 `?problem_id=<id>` |
| **扩展弹窗** | 题目页打开扩展 → 本题建议 +「打开陪练」 |
| **CLI** | `kg import/status/progress/context`、`coach follow/debrief/chat` |

讲题系统（Tutor）**不在本版本**。

## 常用命令

| 命令 | 用途 |
|------|------|
| `leetcode-tracker serve` | 启动本机服务 |
| `leetcode-tracker kg import` | 导入 bundled 知识图谱 |
| `leetcode-tracker kg progress --track dp` | 查看 DP 路线子模块进度 |
| `leetcode-tracker coach follow <submission_id>` | 模板开场 + session_id |
| `leetcode-tracker coach chat <submission_id>` | 终端交互陪练（首条消息后调 Ollama） |
| `leetcode-tracker config set llm.coach_model <name>` | 更换本地模型 |

## 数据存在哪里

| 内容 | 路径 |
|------|------|
| **刷题记录 + 图谱 + 陪练会话** | `~/.local/share/leetcode-tracker/leetcode.db` |
| **配置** | `~/.config/leetcode-tracker/config.json`（含嵌套 `llm` 对象） |

## Neo 8GB 建议

- 仅追踪：无需 Ollama
- 陪练：打开陪练页时模板开场（不调 LLM）；你发送第一条消息后才会调用 7B Q4
- 避免同时跑多个 Ollama 模型；陪练时关闭不必要的 Chrome 标签

## 说明与限制

- 仅 **leetcode.cn**；无云同步
- 陪练依赖 `[coach]` extra；未安装时不影响采集与统计
- **采集与陪练解耦**：`/submit` 只写库；陪练按需读库，扩展提交热路径不调用 engage/LLM
- 图谱覆盖约 890+ 题；图谱外题目陪练降级为 `problem_stats` 画像

## 图谱数据来源

路线图文本来自 **algorithm-stone**（MIT License），bundled 于 `leetcode_tracker/data/algorithm_stone/maps/`。详见该目录内 `LICENSE` 与 `README.txt`。

## 维护文档

- [提交采集故障复盘与链路约束](docs/SUBMISSION_CAPTURE_INCIDENT.md)
