# LeetCode Tracker

完全本地的 **leetcode.cn** 刷题追踪助手（v0.3.1）。  
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
3. 正常提交后：**先** `/submit` 入库；成功后再**另一次**调用 `/api/coach/prepare`（只创建/复用模板会话，不调用 LLM；失败不影响采集）
4. 通知点击或弹窗「打开陪练」→ 深链同时携带 `submission` 与 `problem_id`；页面先展示模板首句，用户发送消息时才首次调用模型，续聊走 **SSE**
5. **三接口解耦**：`/submit` → `prepare` → `stream`，禁止合并进同一请求

本机桥接为 **FastAPI + uvicorn**（`GET /health` 含 `"server":"fastapi"`）。若仪表盘无新提交，先确认旧的标准库进程已退出并重启 `serve`，再**重载扩展**。

若修改了桥接端口（`leetcode-tracker config set port 9000`），扩展会通过 `GET /health` 自动读取 `port` 字段；请重新加载扩展并重启 `serve`。

## v0.3.0 新能力

| 能力 | 说明 |
|------|------|
| **知识图谱** | 自 [algorithm-stone](https://github.com/acm-clan/algorithm-stone)（MIT）导入 14 条路线、子模块与学习顺序 |
| **陪练 Coach** | 入库后 `prepare` 原子复用模板会话；首条用户消息才调用模型；LangGraph 负责路由、token 流、checkpoint、结束与 fallback |
| **陪练页** | `http://127.0.0.1:8763/coach?submission=<id>&problem_id=<id>`；缺 submission 时可按 problem_id 取该题最新提交 |
| **扩展弹窗** | 题目页打开扩展 → 本题建议 +「打开陪练」 |
| **CLI** | `kg import/status/progress/context`、`coach follow/debrief/chat`（CLI 同步；浏览器 SSE） |

讲题系统（Tutor）**不在本版本**。

## 常用命令

| 命令 | 用途 |
|------|------|
| `leetcode-tracker serve` | 启动本机服务 |
| `leetcode-tracker kg import` | 导入 bundled 知识图谱 |
| `leetcode-tracker kg progress --track dp` | 查看 DP 路线子模块进度 |
| `leetcode-tracker coach follow <submission_id>` | prepare：模板首句 + session_id（不调用 LLM） |
| `leetcode-tracker coach chat <submission_id>` | 终端同步续聊（浏览器走 SSE `/api/coach/stream`） |
| `leetcode-tracker config set llm.coach_model <name>` | 更换本地模型 |

## 数据存在哪里

| 内容 | 路径 |
|------|------|
| **刷题记录 + 图谱 + 陪练会话** | `~/.local/share/leetcode-tracker/leetcode.db` |
| **配置** | `~/.config/leetcode-tracker/config.json`（含嵌套 `llm` 对象） |

## Neo 8GB 建议

- 仅追踪：无需 Ollama
- 陪练：`prepare` 不启动模型；用户发消息后续聊使用 7B Q4。Ollama 未开或超时时由 LangGraph 给出确定性 fallback，采集不受影响
- 避免同时跑多个 Ollama 模型；陪练时关闭不必要的 Chrome 标签

## 说明与限制

- 仅 **leetcode.cn**；无云同步
- 陪练依赖 `[coach]` extra；未安装时不影响采集与统计
- **采集与陪练解耦**：`/submit` 只写库；成功后再独立 `prepare`；续聊走 SSE
- **本机模型边界**：Ollama 仅允许 loopback、显式不走代理并设置 timeout；同 thread 并发 stream 被拒绝，SSE 断连会取消生成
- 图谱覆盖约 890+ 题；图谱外题目陪练降级为 `problem_stats` 画像

## 图谱数据来源

路线图文本来自 **algorithm-stone**（MIT License），bundled 于 `leetcode_tracker/data/algorithm_stone/maps/`。详见该目录内 `LICENSE` 与 `README.txt`。

## 维护文档

- [Coach / LangGraph 链路说明（微调用）](docs/COACH_LANGGRAPH.md)
- [提交采集故障复盘与链路约束](docs/SUBMISSION_CAPTURE_INCIDENT.md)
