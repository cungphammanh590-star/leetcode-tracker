# LeetCode Tracker

完全本地的 **leetcode.cn** 刷题追踪助手（**v0.3.3**）。  
在力扣正常提交后，浏览器扩展会把记录写到你的 Mac；可选本地 AI 陪练帮你复盘。**刷题数据不出本机。**

## 你需要准备什么

- macOS
- Chrome 或 Edge
- [leetcode.cn](https://leetcode.cn) 账号（照常刷题即可）
- 可选陪练：[Ollama](https://ollama.com/) 本地模型，或在维护台填写 **DeepSeek API Key**（8GB 本机建议 `qwen2.5:7b-instruct-q4_K_M`）

## 安装

```bash
# 核心（追踪 + 仪表盘）
pip install git+https://github.com/cungphammanh590-star/leetcode-tracker.git@v0.3.3

# 可选：陪练（Ollama + DeepSeek 依赖一并安装）
pip install 'leetcode-tracker[coach]'
```

若从旧版升级且维护台报缺少 `langchain-openai`，请再执行一次上面的 `[coach]` 安装后重启 `serve`。

浏览器扩展请从本版 [Release](https://github.com/cungphammanh590-star/leetcode-tracker/releases/tag/v0.3.3) 下载 zip，解压后使用其中的 `extension/` 文件夹（或克隆本仓库后加载仓库内 `extension/`）。

## 日常使用

```bash
# 启动本机服务（唯一界面：浏览器）
leetcode-tracker serve

# 可选：导入学习路线图（陪练更准，随包附带）
leetcode-tracker kg import
```

然后：

1. 打开仪表盘：**http://127.0.0.1:8763/**
2. `chrome://extensions` → 开发者模式 → **加载已解压的扩展程序** → 选 `extension/`
3. 在 leetcode.cn 正常做题、提交；扩展角标显示 ok 即表示已记录
4. 需要陪练时：点通知或扩展弹窗里的「打开陪练」，在页面里发消息即可（未装 `[coach]` / 未开 Ollama 也不影响采集）

维护台（清日志、重建统计、导入图谱、陪练模型）：**http://127.0.0.1:8763/ops**

若改过端口：`leetcode-tracker config set port 9000`，然后重启 `serve` 并重载扩展。

## 页面一览

| 地址 | 做什么 |
|------|--------|
| `/` | 按天概览（默认今天）、当日题目/错题、近 7 日、最近提交 |
| `/ops` | 维护台 |
| `/coach` | 陪练对话 |
| `/problems/{题号}` | 单题详情 |

## 常用命令

| 命令 | 用途 |
|------|------|
| `leetcode-tracker serve` | 启动本机服务 |
| `leetcode-tracker kg import` | 导入知识图谱 |
| `leetcode-tracker kg progress --track dp` | 查看某条路线进度 |
| `leetcode-tracker coach follow <submission_id>` | 准备陪练会话（不调模型） |
| `leetcode-tracker coach chat <submission_id>` | 终端续聊 |
| `leetcode-tracker config set llm.coach_model <name>` | 更换本地模型 |
| `leetcode-tracker autostart install` | 开机自动 `serve` |

## 数据在哪

| 内容 | 路径 |
|------|------|
| 刷题记录 / 图谱 / 陪练会话 | `~/.local/share/leetcode-tracker/leetcode.db` |
| 配置 | `~/.config/leetcode-tracker/config.json` |

时间与「今日」统计均按 **中国时区（北京时间）** 切日；仪表盘可切换日期回顾历史一天。若本机仍有旧版 `~/leetcode-reports` 目录，可自行删除，产品不再读写。

## 陪练小提示（可选）

- 只追踪：不必装 Ollama / 不必填 API Key
- 本地：打开 Ollama 并拉取模型后再在陪练页发消息
- 云端：打开 **http://127.0.0.1:8763/ops** →「陪练模型」选 DeepSeek，填写 Key 后保存；可「测试连接」或「一键清除 Key」
- 模型超时/失败会有兜底回复，**不影响提交采集**
- 8GB 机器避免同时跑多个大模型；陪练时少开无必要标签页

## 说明

- 仅支持 **leetcode.cn**，无云同步
- 未安装 `[coach]` 时，采集与统计照常可用
- 图谱覆盖约 890+ 题；图谱外的题仍可陪练，只是缺少路线位置信息
- 维护台里的破坏性操作需要确认；本版不提供网页清空全部提交、也不在网页改端口

## 图谱来源

路线图来自 **algorithm-stone**（MIT），随包装在 `leetcode_tracker/data/algorithm_stone/maps/`。
