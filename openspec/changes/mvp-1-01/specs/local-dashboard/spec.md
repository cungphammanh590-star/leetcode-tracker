## ADDED Requirements

### Requirement: 本机只读仪表盘

系统 SHALL 通过本机桥接 HTTP 服务提供仪表盘页面（默认站点根路径），展示刷题进度（至少含：今日/累计提交与通过、连续打卡、最近提交列表）。仪表盘 MUST 仅监听回环地址使用的同一服务，MUST NOT 将数据上传到外部网络。

#### Scenario: 浏览器或桌面壳打开仪表盘

- **WHEN** 桥接已运行且用户打开 `http://{host}:{port}/`
- **THEN** 页面 MUST 展示当前库中的关键统计信息

#### Scenario: 数据随入库更新可见

- **WHEN** 新提交成功写入 SQLite 后仪表盘在短时间内刷新（轮询或等价机制）
- **THEN** 用户 MUST 能看到反映新提交的统计或列表变化

### Requirement: 仪表盘只读 API

系统 SHALL 提供供仪表盘使用的本机只读 JSON API（例如统计概览），且 MUST NOT 经由仪表盘 API 提供任意文件写或远程代理能力。

#### Scenario: 统计 API 可用

- **WHEN** 客户端请求统计 API
- **THEN** 响应 MUST 包含可供页面渲染的概览字段，且仅来自本地库
