## ADDED Requirements

### Requirement: 陪练会话基于已入库提交与图谱上下文

Coach 系统 SHALL 以单次 `submission_id`、显式 `problem_id` 或「今日复盘」为入口，组装提交事实、图谱位置与子模块进度为结构化上下文，并驱动多轮陪练对话。使用 `problem_id` 时 MUST 回退到该题最新的已入库 submission，并以稳定规则打破时间平局。

#### Scenario: 针对单次提交开聊

- **WHEN** 用户或客户端提供有效且已入库的 `submission_id` 启动 `prepare`
- **THEN** 系统 MUST 加载该提交的状态、题目信息及图谱上下文，并返回确定性模板 opening，且 MUST NOT 调用 LLM

#### Scenario: 按题号回退到最新提交

- **WHEN** 客户端未提供 `submission_id` 但显式提供有效 `problem_id`
- **THEN** 系统 MUST 选择该题最新的已入库 submission 创建或复用会话；该题无提交时 MUST 返回明确错误

#### Scenario: 今日复盘

- **WHEN** 用户请求今日复盘
- **THEN** 系统 MUST 基于今日提交与错题汇总生成复盘开场，且 MUST NOT 要求用户指定 submission_id

### Requirement: 入库后方可 prepare

Coach `prepare` MUST 只读已存在的提交与派生数据；当指定 submission 不存在且不能按显式 `problem_id` 找到最新提交时 MUST 返回明确错误，且 MUST NOT 写入 `submissions`。

#### Scenario: 提交尚未入库

- **WHEN** 客户端对不存在的 `submission_id` 调用 `prepare`
- **THEN** 系统 MUST 失败并返回可读错误，且 MUST NOT 调用 LLM 假装成功；只有客户端同时显式提供 `problem_id` 时才可按该题最新提交回退

### Requirement: Prepare 无模型调用且原子幂等

`prepare` SHALL 在单个原子数据库边界内创建或复用模板 opening 会话并立即返回。相同 submission 的顺序或并发调用 MUST 收敛到同一个规范会话，MUST 返回同一 `session_id`，且 MUST NOT 初始化或调用任何 LLM。

#### Scenario: 重复 prepare

- **WHEN** 客户端针对同一 submission 重复调用 `prepare`
- **THEN** 系统 MUST 复用既有规范会话并返回相同 `session_id` 与模板 opening

#### Scenario: 并发 prepare

- **WHEN** 两个请求并发 prepare 同一 submission
- **THEN** 数据库唯一约束或等价事务 MUST 防止重复规范会话，冲突请求 MUST 读取并返回已提交的同一会话

### Requirement: 陪练禁止泄题与完整解法

Coach 系统 MUST 在陪练模式下禁止输出完整算法步骤、可 Accepted 的完整代码或可直接抄写的伪代码；回复 MUST 以提问、反思与过程引导为主。

#### Scenario: 用户索要答案

- **WHEN** 用户明确要求「告诉我答案」或「给完整代码」
- **THEN** 陪练 MUST 拒绝直接给出解法，并 MUST 改为引导用户描述思路或怀疑点

#### Scenario: Wrong Answer 后引导

- **WHEN** 本次提交为非 Accepted
- **THEN** 陪练 SHOULD 先询问用户怀疑的错误类型（边界、复杂度、实现细节等），再决定是否追问，且 MUST NOT 直接给出修正代码

### Requirement: LangGraph 正式管理多轮执行与持久化

系统 SHALL 使用 LangGraph 管理陪练状态与生产执行。第一条及后续用户消息的路由、token stream、checkpoint、结束语和模型失败确定性 fallback MUST 在图内完成；生产路径 MUST NOT 绕过图直接调用模型流再手工回填状态。

#### Scenario: 多轮续聊

- **WHEN** 用户在已有 `session_id` 下经 SSE 发送后续消息
- **THEN** 系统 MUST 在同一线程内继续陪练，且 MUST 保留此前对话与上下文引用

#### Scenario: 首次模型调用

- **WHEN** prepare 已返回模板 opening，但用户尚未发送 stream 消息
- **THEN** 系统 MUST NOT 调用模型；模型的首次调用 MUST 发生在首条用户消息进入 LangGraph 时

#### Scenario: 会话结束收束

- **WHEN** 用户表示结束或达到预设轮次上限
- **THEN** LangGraph MUST 路由到确定性结束节点并给出简短收束总结，MUST NOT 调用模型，且 MUST NOT 进入讲题模式

### Requirement: 模型失败确定性降级

模型仅可在用户发送 stream 消息后由 LangGraph 调用；当模型不可用、超时或流式生成失败时，图 MUST 输出确定性 fallback，并 MUST NOT 影响采集链路或破坏最后一个完整 checkpoint。

#### Scenario: Ollama 可用并收到用户消息

- **WHEN** 本机 Ollama 与模型可用且用户向已有 session 发送消息
- **THEN** LangGraph MUST 流式返回模型 token 并提交完整轮次 checkpoint

#### Scenario: Ollama 不可用

- **WHEN** Ollama 未运行、模型缺失、超时或生成失败
- **THEN** LangGraph MUST 返回确定性 fallback，且 MUST NOT 要求调用方回滚 `/submit`

### Requirement: 同线程串行与 SSE 取消

同一 `thread_id` 同时 SHALL 最多存在一个进行中的 stream。重叠请求 MUST 在模型调用和 checkpoint 变更前被明确拒绝；SSE 客户端断开 MUST 取消下游图与模型生成并释放线程占用。

#### Scenario: 同线程重叠请求

- **WHEN** 一个 thread 正在生成时收到该 thread 的第二个 stream 请求
- **THEN** 系统 MUST 明确返回冲突且 MUST NOT 排队、调用模型或写 checkpoint

#### Scenario: 客户端断开

- **WHEN** SSE 客户端在回复完成前断开
- **THEN** 系统 MUST 传播取消、停止生成并释放并发保护，且 MUST NOT 把部分 token 伪装成完整 AI 回复写入 checkpoint

### Requirement: 陪练 CLI

系统 SHALL 提供 `leetcode-tracker coach` 子命令族，至少支持 `follow`（按 submission）、`debrief`（今日复盘）与交互式 `chat`，且默认使用本机配置的 LLM 提供方。

#### Scenario: CLI 离线可用性

- **WHEN** 用户在本机执行 coach 命令且 Ollama 与图谱均已就绪
- **THEN** 命令 MUST 在不访问云端 API 的情况下完成陪练对话（默认配置下）；prepare 阶段仍 MUST 为无模型的模板会话

### Requirement: 与 Tutor 讲题系统隔离

Coach 系统 MUST NOT 实现算法讲解、知识点授课或深度代码审阅能力；任何「讲题」入口 MUST 与 Coach 包与路由分离（本版本可不实现 Tutor，但 MUST NOT 在 Coach 图内混入讲题节点）。

#### Scenario: 产品边界

- **WHEN** 用户仅使用 v0.3.0 陪练功能
- **THEN** 系统 MUST 仅暴露 Coach 相关 CLI 与 API，且 MUST NOT 提供 Tutor 讲题命令或等价能力
