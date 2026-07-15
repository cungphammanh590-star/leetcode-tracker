## 1. 配置与版本

- [ ] 1.1 将包版本升为 `0.1.1`，更新 README 口径为仅 leetcode.cn
- [ ] 1.2 实现 `config.json` 读写与默认值（port/report_dir/report_time/autostart；无 db 路径配置）
- [ ] 1.3 实现 `leetcode-tracker config show|set`（或等价）并让 `serve`/`report` 读取配置

## 2. 统计增强

- [ ] 2.1 实现今日错题列表查询
- [ ] 2.2 实现近 7 日提交/通过序列查询
- [ ] 2.3 `stats` 输出纳入上述摘要（或子命令展示）

## 3. 日报增强

- [ ] 3.1 更新 Markdown 模板：错题区块 + 近 7 日对比
- [ ] 3.2 `report --today` 使用配置中的 `report_dir`

## 4. 仪表盘 API 与页面

- [ ] 4.1 在桥接服务增加只读统计 API
- [ ] 4.2 实现本机仪表盘静态页（轮询刷新），由 `serve` 提供 `/`
- [ ] 4.3 手验：入库后页面短时间内反映新数据

## 5. 桌面壳与自启

- [ ] 5.1 加入 `pywebview` 依赖；实现 `leetcode-tracker app`（名可微调）打开仪表盘
- [ ] 5.2 桌面壳在桥接未启动时拉起或明确报错
- [ ] 5.3 实现 launchd `autostart install|uninstall`，写入当前绝对路径
- [ ] 5.4 `autostart=true/false` 与安装状态行为对齐并文档化

## 6. 扩展正式反馈

- [ ] 6.1 增加系统通知（成功/失败）；保留 badge/popup
- [ ] 6.2 移除面向用户的调试开关/调试区块
- [ ] 6.3 文案仅声明 leetcode.cn

## 7. 文档与验收

- [ ] 7.1 更新 README：配置、自启、桌面壳、仪表盘、0.1.1
- [ ] 7.2 明确 Non-goals：无 LLM API、无库路径配置
- [ ] 7.3 对照 specs 做一次 macOS 手验清单
