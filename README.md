# dsh-memory-bridge

Memory Tree 桥接插件 —— 为 DeepSeek Harness 接上「记忆树系统」：自动写入（提取）+ 自动读取（注入）+ 检索/落盘记忆、管理记忆树、驱动本地/云端记忆提取，并配套高图形化设置页 UI。

## 架构

```
DeepSeek Harness (host 插件进程)
├── lib/index.js          host 入口：拉起 sidecar、注册 /dsh-memory/* 路由、注册 3 个 agent 工具、
│                         自动提取钩子（turn/end）、自动注入钩子（user/message → system prompt context）
├── python/memory_bridge_server.py   sidecar：JSON-RPC over HTTP，承载记忆树引擎 + 衰减治理 + lemonade
└── client/client.js      设置页 UI（6 个 tab：总览 / 事件图谱 / 知识图谱 / 时间线 / 待审 / 审计）
```

- **记忆引擎**：复用 `D:\dsh\plugins\Memory Tree System`（明文 markdown 真源 + SQLite 检索索引 + BM25/RRF 确定性检索，零外部服务依赖）。
- **Sidecar 生命周期**：由 host 随插件启停自动托管；首次调用时按配置拉起本地 lemonade 并加载记忆专用模型。

## 自动记忆流水线（写入端 + 读取端）

| 环节 | 触发 | 行为 |
|---|---|---|
| **提取** | 每轮对话 `turn/end` | 增量扫描本轮 user+assistant 文本 → 入 run 队列 → 云端/本地提取 → 事件卡/经验/知识分流落库（含门卫、归链、冲突裁决、失败退避） |
| **注入** | 每条 `user/message` | 检索相关记忆（L2 ≤3 条 / L1 ≤1 条 / 寒暄 L0 不注入，档位自动判定，50ms 超时宁缺勿滥）→ 缓存 → system prompt 渲染时以带溯源文本注入上下文（`[长期记忆 · 来源 …]`） |
| **审计闭环** | `turn/end` 后 | 判定注入记忆是否被模型回复利用（`inject_used`）→ 命中滚动/未命中降权淡出 |
| **衰减治理** | 启动对账 + 每次提取后 + 手动 | 30 天闲置枝完结枯萎（排除检索、数据保留）；全局利用率低自动收缩注入条数；低使用率卡降权 |

## 安装（官方路径）

```bat
dsh plugin --profile web add link:D:/dsh/plugins/dsh-memory-bridge
```

重启 harness 后生效。卸载：

```bat
dsh plugin --profile web remove dsh-memory-bridge
```

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
REM 独立启动 sidecar（脱离 harness 联调）
D:\Python312\python.exe -u D:\dsh\plugins\dsh-memory-bridge\python\memory_bridge_server.py --root "D:\dsh\plugins\Memory Tree System" --config D:\dsh\plugins\dsh-memory-bridge\config.json
```

启动后读 stdout 的 `DMB_PORT <port>`，然后：

```powershell
Invoke-RestMethod "http://127.0.0.1:<port>/rpc" -Method Post -Body @{method="overview";params=@{}} | ConvertTo-Json
```

记忆引擎测试（独立于 harness）：

```bat
D:\Python312\python.exe -m pytest "D:\dsh\plugins\Memory Tree System\tests" -q
```

启动器 `D:\dsh\DSH.bat`（纯 ASCII，任何终端无乱码）：单窗口后台启动 / 停止 / 状态 / 重启（含端口释放等待与启动检测）。
