## ADDED Requirements

### Requirement: 陪练会话基于提交与图谱上下文

Coach 系统 SHALL 以单次 `submission_id` 或「今日复盘」为入口，组装提交事实、图谱位置与子模块进度为结构化上下文，并驱动多轮陪练对话。

#### Scenario: 针对单次提交开聊

- **WHEN** 用户提供有效 `submission_id` 启动陪练
- **THEN** 系统 MUST 加载该提交的状态、题目信息及图谱上下文，并生成首条陪练回复

#### Scenario: 今日复盘

- **WHEN** 用户请求今日复盘
- **THEN** 系统 MUST 基于今日提交与错题汇总生成复盘开场，且 MUST NOT 要求用户指定 submission_id

### Requirement: 陪练禁止泄题与完整解法

Coach 系统 MUST 在陪练模式下禁止输出完整算法步骤、可 Accepted 的完整代码或可直接抄写的伪代码；回复 MUST 以提问、反思与过程引导为主。

#### Scenario: 用户索要答案

- **WHEN** 用户明确要求「告诉我答案」或「给完整代码」
- **THEN** 陪练 MUST 拒绝直接给出解法，并 MUST 改为引导用户描述思路或怀疑点

#### Scenario: Wrong Answer 后引导

- **WHEN** 本次提交为非 Accepted
- **THEN** 陪练 SHOULD 先询问用户怀疑的错误类型（边界、复杂度、实现细节等），再决定是否追问，且 MUST NOT 直接给出修正代码

### Requirement: LangGraph 多轮陪练与持久化

系统 SHALL 使用 LangGraph 管理陪练状态机，并 MUST 将对话线程持久化到本机，以便用户在同一会话中多轮续聊。

#### Scenario: 多轮续聊

- **WHEN** 用户在已有 `session_id` 下发送后续消息
- **THEN** 系统 MUST 在同一线程内继续陪练，且 MUST 保留此前对话与上下文引用

#### Scenario: 会话结束收束

- **WHEN** 用户表示结束或达到预设轮次上限
- **THEN** 系统 MUST 给出简短收束总结（学习点与下一步建议），且 MUST NOT 进入讲题模式

### Requirement: 陪练 CLI

系统 SHALL 提供 `leetcode-tracker coach` 子命令族，至少支持 `follow`（按 submission）、`debrief`（今日复盘）与交互式 `chat`，且默认使用本机配置的 LLM 提供方。

#### Scenario: CLI 离线可用性

- **WHEN** 用户在本机执行 coach 命令且 Ollama 与图谱均已就绪
- **THEN** 命令 MUST 在不访问云端 API 的情况下完成陪练对话（默认配置下）

### Requirement: 与 Tutor 讲题系统隔离

Coach 系统 MUST NOT 实现算法讲解、知识点授课或深度代码审阅能力；任何「讲题」入口 MUST 与 Coach 包与路由分离（本版本可不实现 Tutor，但 MUST NOT 在 Coach 图内混入讲题节点）。

#### Scenario: 产品边界

- **WHEN** 用户仅使用 v0.3.0 陪练功能
- **THEN** 系统 MUST 仅暴露 Coach 相关 CLI 与 API，且 MUST NOT 提供 Tutor 讲题命令或等价能力
