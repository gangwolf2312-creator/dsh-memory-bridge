# dsh-memory-bridge

Memory Tree 桥接插件 —— 为 DeepSeek Harness 接上「记忆树系统」：自动写入（提取）+ 自动读取（注入）+ 检索/落盘记忆、管理记忆树、驱动本地/云端记忆提取，并配套高图形化设置页 UI。

## 架构

```
DeepSeek Harness (host 插件进程)
├── lib/index.js          host 入口：拉起 sidecar、注册 /dsh-memory/* 路由、注册 3 个 agent 工具、
│                         自动提取钩子（turn/end）、自动注入钩子（user/message → system prompt context）
├── python/memory_bridge_server.py   sidecar：JSON-RPC over HTTP，承载记忆树引擎 + 衰减治理 + lemonade
├── engine/               记忆树引擎源码（core/ + memory/，依赖声明式安装，见下）
└── client/client.js      设置页 UI（6 个 tab：总览 / 事件图谱 / 知识图谱 / 时间线 / 待审 / 审计）
```

- **记忆引擎**：随插件携带 `engine/`（明文 markdown 真源 + SQLite 检索索引 + BM25/RRF 确定性检索，零外部服务依赖）。
- **Sidecar 生命周期**：由 host 随插件启停自动托管；首次调用时按配置拉起本地 lemonade 并加载记忆专用模型。
- **引擎路径解析**（无需硬编码）：自动探测 `engine/`（本包内）→ 或同级 `Memory Tree System/`（开发布局）→ 或 `DSH_MEMORY_BRIDGE_ENGINE_ROOT` 环境变量 / 插件配置 `engineRoot`。

## 安装（官方路径）

要求：DSH 0.1.0-rc.7+、Python 3.10+（本插件无 Node 原生依赖）。

```bat
:: 1) 从 GitHub 安装（替换 <owner> 为仓库所属用户）
dsh plugin --profile web add github:<owner>/dsh-memory-bridge

:: 2) 安装 Python 依赖（jieba 分词，声明式；清华镜像，失败自动回退阿里云）
pwsh <你的插件目录>/engine/install-deps.ps1
:: 等价于：pip install -r <插件目录>/engine/requirements.txt
```

重启 harness 后生效。卸载：

```bat
dsh plugin --profile web remove dsh-memory-bridge
```

> **依赖策略**：Python 依赖（jieba）走声明式安装，不随仓库内嵌、也不在安装时静默 pip install（安全 + 可控）。sidecar 对缺失依赖有容错：返回可操作的安装指引（`pip install -r engine/requirements.txt`），不会拖垮整个 harness。

## 配置（设置页 → 插件 tab）

| 项 | 说明 |
|---|---|
| 模式 mode | `off` 关闭 / `local` 本地 lemonade / `cloud` 云端记忆 API / `main` 主对话模型兜底 / `hybrid` 本地优先+云端兜底 |
| local.preset | 本地模型预设（默认 `qwen3-it-4b-flm`），或 `custom` 自填 baseUrl/model/apiKey |
| local.autoManage | 开启后：health check 自动拉起 lemonade 并加载对应模型 |
| cloud.* | 云端记忆 API（baseUrl / model / apiKey / apiKeyEnv / batchSize / maxCallsPerMinute） |
| sanitize | 提取前脱敏（手机号/邮箱/身份证/密钥），云端默认开启 |

- **API key 支持 `apiKeyEnv`**：配置 `apiKeyEnv` 指定环境变量名后，优先读环境变量，回退明文 `apiKey`（渐进迁移：设了环境变量即可删除明文 key）。
- API key 在配置回读时一律脱敏显示（`masked_config`）。
- 配置先校验后落盘（`configSet` 校验失败不写入），写入持单锁，无死锁。
- 仓库只提供 `config.example.json` 模板（无密钥）；首次运行无 `config.json` 时自动使用内置默认配置。

## UI（设置页 → 记忆）

| Tab | 内容 |
|---|---|
| 总览 | 统计 / 状态 / 审计摘要 / 最近活动 |
| 事件图谱 | 力导向图 + 记忆树导航联动（点树聚焦图、点图按图过滤树）、孤立节点/实体关联开关、方向箭头流动线 |
| 知识图谱 | wiki 条目力导向图（上位/版本关系）+ 搜索 + 条目列表 |
| 时间线 | 事件流按日期分组（今天/昨天/N 天前），时间倒序 |
| 待审 | 提取队列 / pending 经验审批 |
| 审计 | 注入/提取统计 + 「立即维护」按钮（手动衰减+治理）+ 决策日志 |

## Agent 工具

| 工具 | 用途 |
|---|---|
| `memory_search` | BM25+RRF 确定性检索记忆卡，零 LLM、零网络；返回链上下文与反馈信号提示 |
| `memory_add_run` | 显式把一轮对话写入记忆 run 队列（之后由 rules/LLM 提取决定是否成卡） |
| `memory_review` | 查看待提取 run 队列 / 指定 run 状态，用于审计 |

## HTTP API（浏览器代理，host 转发到 sidecar）

- `GET  /dsh-memory/overview` `health` `search?q=` `browse?kind=` `card?id=` `review?runId=` `wiki?q=` `config` `lemonade-status` `audit` `graph`
- `POST /dsh-memory/card-action` `add-run` `config` `lemonade-ensure` `extract` `inject` `recordUsage` `maintenance`

## 安全

- **同源校验**：POST（写操作）严格校验 Origin（浏览器同源 POST 必带）；GET（只读）宽松校验——带 Origin 的必须匹配（防跨站读取），无 Origin 放行（同源 GET fetch 与地址栏访问正常）。
- 云端提取前默认脱敏；`apiKey` 永不回显明文，支持 `apiKeyEnv` 环境变量。
- Sidecar 仅监听 127.0.0.1 随机端口，不暴露公网；RPC body 上限 1MB；hook 调试日志 1MB 轮转。

## 开发与测试

```bat
REM 独立启动 sidecar（脱离 harness 联调；--root 指向引擎目录）
python -u <插件目录>\python\memory_bridge_server.py --root <引擎目录> --config <插件目录>\config.example.json
```

启动后读 stdout 的 `DMB_PORT <port>`，然后：

```powershell
Invoke-RestMethod "http://127.0.0.1:<port>/rpc" -Method Post -Body @{method="overview";params=@{}} | ConvertTo-Json
```

一键冒烟测试（双场景：bundled engine 缺 jieba → 验证可操作指引；本地引擎 → 全功能）：

```bat
python smoke_sidecar.py
```

记忆引擎测试（独立于 harness，需要 `pip install pytest`）：

```bat
python -m pytest <引擎目录>\tests -q
```

启动器 `D:\dsh\DSH.bat`（纯 ASCII，任何终端无乱码）：单窗口后台启动 / 停止 / 状态 / 重启（含端口释放等待、日志轮转、启动检测）。
