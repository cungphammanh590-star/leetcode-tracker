## 1. 版本与依赖

- [x] 1.1 将包版本升为 `0.3.0`，更新 README 口径为陪练 + 知识图谱
- [x] 1.2 添加 `[coach]` optional extra：`langgraph`、`langchain-core`、`langchain-ollama`、`langgraph-checkpoint-sqlite`
- [x] 1.3 扩展嵌套 `config.json` → `llm.{provider,coach_model,api_provider,api_key}`；`config set llm.*` 点路径读写，api_key 脱敏

## 2. 知识图谱持久化

- [x] 2.1 在 `db.py` 增加 `kg_tracks`、`kg_nodes`、`kg_node_problems`、`kg_edges`、`kg_meta` schema
- [x] 2.2 bundled `leetcode_tracker/data/algorithm_stone/maps/`（复制上游 map 并附 LICENSE/版本说明）
- [x] 2.3 实现 `kg/import.py`：解析 algorithm-stone 文本语法（不依赖 zhon/graphviz）
- [x] 2.4 实现 `kg/queries.py`：track 列表、node 进度、单题 `kg context`（含图谱外降级）
- [x] 2.5 CLI：`leetcode-tracker kg import|status|progress|context`

## 3. LLM 提供方

- [x] 3.1 实现 `llm/provider.py`：Ollama 默认、配置加载、不可用时的明确错误
- [x] 3.2 预留 API provider 配置加载（MVP 可不实现实际 HTTP 调用，但 MUST 默认不启用）

## 4. Coach 核心

- [x] 4.1 实现 `coach/context.py`：`build_coach_context(submission_id)`（提交 + 图谱 + 子模块进度，默认不含完整 code）
- [x] 4.2 实现 `coach/prompts.py`：防泄题 system prompt 与 moment 分类提示
- [x] 4.3 实现 `coach/graph.py`：LangGraph + SqliteSaver（checkpoint 存 `leetcode.db`）；engage 模板开场，chat 才调 LLM
- [x] 4.4 CLI：`leetcode-tracker coach follow|debrief|chat`
- [ ] 4.5 手验：Neo 8GB + Ollama 7B Q4 完成一轮 WA 陪练

## 5. 桥接 API 与陪练页

- [x] 5.1 `POST /api/coach/engage`、`POST /api/coach/chat`；扩展 `/health` 返回 `port`、`kg_imported`、`coach_available`
- [x] 5.2 静态页 `static/coach.html` + 路由 `GET /coach`（query: submission / session）
- [x] 5.3 陪练页：开场展示、消息输入、错误态（Ollama/kg 未就绪）
- [ ] 5.4 手验：浏览器深链 `?submission=` 多轮对话

## 6. 扩展集成

- [x] 6.1 仅 `created: true` 时异步 `POST /api/coach/engage`；扩展启动时从 `/health` 缓存 port
- [x] 6.2 `onClicked` + `tabs` 权限：通知点击打开 `/coach?submission=...`
- [x] 6.3 engage 失败时保持采集成功态，不弹采集失败通知
- [ ] 6.4 手验：leetcode.cn 提交 → 通知 → 陪练页

## 7. 文档与验收

- [x] 7.1 更新 README：kg import、Ollama 安装、coach 用法、Neo 8GB 建议
- [x] 7.2 更新 `docs/DATA_MODEL.md`：kg 表与 coach_sessions 说明
- [x] 7.3 明确 Non-goals：无 Tutor、无 Visualizer 导入、无侧栏（v0.3.1）
- [ ] 7.4 端到端验收：采集 → kg 进度 → 提交后陪练 → 今日 debrief CLI
