## 1. 项目骨架与持久化

- [ ] 1.1 确定 Python 包布局（`leetcode_tracker/`），用 `pyproject.toml` 注册 console script `leetcode-tracker`，子命令占位：`serve` / `stats` / `report`（安装后可直接 `leetcode-tracker serve`）
- [ ] 1.2 实现路径常量：数据库 `~/.local/share/leetcode-tracker/leetcode.db`、报告目录 `~/leetcode-reports`；启动前确保父目录可创建
- [ ] 1.3 编写 SQLite schema（`problems`、`submissions`，`submission_id` UNIQUE）与首次连接时自动建表
- [ ] 1.4 实现题目 upsert 与提交插入（含完整 `code`）；缺少 `submission_id` 时抛出/返回可映射为 4xx 的错误；重复 `submission_id` 不双写
- [ ] 1.5 用本地脚本或临时测试插入样例数据，验证建库、去重与完整 code 落盘

## 2. 桥接服务（HTTP）

- [ ] 2.1 用标准库实现回环 HTTP 服务，默认监听 `127.0.0.1:8763`；端口占用时失败并打印明确错误
- [ ] 2.2 实现 `GET /health`（服务可用、库可访问、提交条数等）
- [ ] 2.3 实现 `POST /submit`：校验必填字段 → 调用持久化层 → 返回成功/4xx JSON；配置扩展访问本机所需的 CORS/预检（按 MV3 实际需要）
- [ ] 2.4 打通 `leetcode-tracker serve`：启动服务并阻塞运行，直到进程退出
- [ ] 2.5 用 `curl` 手验：健康检查、合法写入、缺 id 拒绝、重复 id 不双写

## 3. 浏览器扩展（采集）

- [ ] 3.1 创建 MV3 扩展骨架（`manifest.json`、图标、后台/service worker、必要权限），可在 Chrome 开发者模式加载
- [ ] 3.2 在 leetcode.com 网络层捕获提交与判题终态，解析出非空 `submission_id`、题目元数据、状态、运行指标与完整源代码
- [ ] 3.3 终态就绪后 `POST` 到本机 `http://127.0.0.1:8763/submit`
- [ ] 3.4 桥接不可达或 4xx 时给出最简可感知提示（如 badge/`console` 或一次性 notification，不自研 UI）
- [ ] 3.5 在真实 leetcode.com 提交一题（含非 Accepted 若方便），确认 3 秒内库中可见且不重复

## 4. 统计模块与 CLI

- [ ] 4.1 实现统计模块：累计提交/Accepted/通过率、按难度去重通过数、今日提交数、最近 20 条倒序列表
- [ ] 4.2 实现连续打卡天数（本地时区日历日；今日无提交则截至昨天；断档为 0）
- [ ] 4.3 实现 `leetcode-tracker stats`，在标准输出打印上述关键指标
- [ ] 4.4 用已知样例数据（或扩展实采数据）核对 `stats` 与 spec 场景一致

## 5. 日报生成

- [ ] 5.1 实现 Markdown 日报渲染（今日概览、累计、连续天数、今日题目列表）；今日无提交仍可生成且计数为 0
- [ ] 5.2 实现 `leetcode-tracker report --today`：创建默认目录、写入/覆盖 `~/leetcode-reports/YYYY-MM-DD.md`
- [ ] 5.3 确认 `serve` 进程内无定时器、无启动补跑逻辑
- [ ] 5.4 手验：同日执行两次 `leetcode-tracker report --today` 覆盖同一文件

## 6. 文档与收尾

- [ ] 6.1 编写 macOS README：`pip install -e .`（或等价）后执行 `leetcode-tracker serve`、加载扩展、执行 `stats` / `report --today`（步骤尽量 ≤5）
- [ ] 6.2 在文档中加入可选 cron 或 launchd 示例（如每天 23:00 调用 `leetcode-tracker report --today`），并写明产品不自动注册定时任务
- [ ] 6.3 对照 acceptance：采集入库、强去重、统计与日报、无外部网络依赖（除 leetcode.com）；列出已知限制（仅 mac、仅 .com、无配置子系统）
