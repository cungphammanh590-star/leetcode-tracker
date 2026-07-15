## ADDED Requirements

### Requirement: 本机配置文件可读可写

系统 SHALL 在本机维护 JSON 配置文件（默认路径 `~/.config/leetcode-tracker/config.json`）。配置 MUST 至少支持：`host`、`port`、`report_dir`、`report_time`、`autostart`。系统 MUST NOT 通过该配置暴露数据库文件路径的设置项。

#### Scenario: 缺失配置时使用默认值

- **WHEN** 配置文件不存在
- **THEN** 系统 MUST 使用内置默认值（含 `127.0.0.1`、`8763`、`~/leetcode-reports`、示例报告时间、`autostart=false`）正常运行

#### Scenario: 更新配置后桥接使用新端口

- **WHEN** 用户将 `port` 改为其他未被占用的端口并重启服务
- **THEN** 桥接 MUST 监听新端口

### Requirement: 提供配置 CLI

系统 SHALL 提供 CLI 以查看与更新上述配置项（具体子命令名在实现中确定，如 `config show` / `config set`）。

#### Scenario: 查看当前配置

- **WHEN** 用户执行查看配置命令
- **THEN** 输出 MUST 包含当前生效的 port、report_dir、report_time、autostart（库路径若展示也仅为只读信息，不可 set）
