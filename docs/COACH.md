# Coach 链路说明（经典链 + 智能阶段图）

采集与陪练解耦：`/submit` 永不进入本文链路。

## 分流

| 开关 | 实现 | 说明 |
|------|------|------|
| `learning.smart_coach=true` + 云端 API Key | **Smart LangGraph**（`smart_agent/`） | 首轮意图 → phase → 拒答/空闲提议/Agent |
| 关闭智能教练 | **Classic LangChain 链**（`classic_chain.py`） | 规则意图 + ChatModel 流式；Ollama / API 钩子差异 |
| action ∈ 旁路三键 | `side_skills` | 今日总结/复习/推荐；不进对话历史 |

旧 LocalGraph / ApiGraph / `smart_coach_history` 已移除。

## 智能教练阶段

`lobby` | `today_brief` | `prep` | `in_problem` | `wrap`

- 首轮强制 `classify_intent`；之后仅 lobby/空闲或换话题再分类
- **空闲提议**：闲聊或一题结束无优化意向 → 有未通过则续刷（含 leetcode.cn 链接），否则新荐；确认后才 `bind_problem`
- **B 档离题**：边界 + 一句现状 + 单一 CTA
- **C 档要答案**：默认思路；明确要代码原文才给 ≤10 行级片段；禁整题完整可运行解

### 工具（只读 / 绑题）

`get_session_binding` · `bind_problem` · `get_current_code` · `get_error_summary` · `get_last_advice` · `get_latest_submission` · `list_unpassed_problems` · `get_user_profile_summary` · `get_topic_mastery` · `get_problem_mastery` · `suggest_next_problems`

选题候选来自规则引擎；模型不得编造列表外题号。禁止注入历史 AC 源码。

### Checkpoint

Smart：`SqliteSaver`，`thread_id=smart:{session_id}`。  
Classic：`classic_coach_history` 表轻量持久化。

## 经典链

意图 / action → `recommend|review|daily_review|optimize|answer_egress|diagnose|deep_analysis|coach_reply`  
防泄题护栏与显式出口与原先一致；C 档政策（禁整题）共用。

## LangSmith（开发用）

默认关闭。需要观测时：

```bash
export LANGSMITH_TRACING=true
export LANGSMITH_API_KEY=...
export LANGSMITH_PROJECT=leetcode-tracker-coach  # 可选
```

**维护台不提供** LangSmith 配置。开启会把对话/代码片段发往 LangSmith，仅建议本地开发使用。

## 入口

- `POST /api/coach/prepare` · `POST /api/coach/stream`
- 代码：`coach/service.py` → `smart_agent.stream` / `classic_chain`

相关：`docs/DATA_MODEL.md`。
