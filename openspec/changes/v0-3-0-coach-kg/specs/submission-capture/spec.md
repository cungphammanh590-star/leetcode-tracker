## ADDED Requirements

### Requirement: 提交成功后触发陪练 engage

扩展在成功将提交投递至本机桥接后，SHALL 异步请求陪练 engage 接口；该步骤 MUST NOT 改变 `/submit` 的成功语义，且 engage 失败 MUST NOT 视为采集失败。

#### Scenario: 成功投递后后台 engage

- **WHEN** 扩展完成一次成功的 `/submit` 响应
- **THEN** 扩展 MUST 在后台向本机桥接发起陪练 engage 请求，并携带 `submission_id`

#### Scenario: Engage 失败不影响 badge

- **WHEN** `/submit` 已成功但 engage 超时或返回错误
- **THEN** 扩展 MUST 仍保持采集成功的 badge/通知状态，且 MUST NOT 覆盖为采集失败提示

### Requirement: 采集成功通知含陪练入口

扩展在提交成功记录的系统通知中 SHALL 引导用户打开本机陪练页，关联该次提交。

#### Scenario: 通知可打开陪练

- **WHEN** 提交已成功记录
- **THEN** 系统通知或用户随后可执行的操作 MUST 能打开 `http://127.0.0.1:{port}/coach?submission={submission_id}`（端口与配置一致）
