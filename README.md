# dsh-memory-bridge

Memory Tree 桥接插件 —— 为 DeepSeek Harness 接上「记忆树系统」：检索/落盘记忆、管理记忆树、驱动本地/云端记忆提取，并配套高图形化设置页 UI。

## 架构

```
DeepSeek Harness (host 插件进程)
├── lib/index.js          host 入口：拉起 sidecar、注册 /dsh-memory/* 路由、注册 3 个 agent 工具
├── python/memory_bridge_server.py   sidecar：JSON-RPC over HTTP，承载记忆树引擎 + lemonade 自动拉起
└── client/client.js      设置页 UI（5 个 tab：总览 / 记忆卡 / 知识库 / 待审 / 审计）
```

- **记忆引擎**：复用 `D:\dsh\plugins\Memory Tree System`（明文 markdown 真源 + SQLite 检索索引 + BM25/RRF 确定性检索，零外部服务依赖）。
- **Sidecar 生命周期**：由 host 随插件启停自动托管；首次调用时按配置拉起本地 lemonade 并加载记忆专用模型。

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
| cloud.* | 云端记忆 API（baseUrl / model / apiKey / batchSize / maxCallsPerMinute） |
| sanitize | 提取前脱敏（手机号/邮箱/身份证/密钥），云端默认开启 |

- API key 在配置回读时一律脱敏显示（`masked_config`）。
- 配置先校验后落盘（`configSet` 校验失败不写入），写入持单锁，无死锁。

## Agent 工具

| 工具 | 用途 |
|---|---|
| `memory_search` | BM25+RRF 确定性检索记忆卡，零 LLM、零网络；返回链上下文与反馈信号提示 |
| `memory_add_run` | 显式把一轮对话写入记忆 run 队列（之后由 rules/LLM 提取决定是否成卡） |
| `memory_review` | 查看待提取 run 队列 / 指定 run 状态，用于审计 |

## HTTP API（浏览器代理，host 转发到 sidecar）

- `GET  /dsh-memory/overview` `health` `search?q=` `browse?kind=` `card?id=` `review?runId=` `wiki?q=` `config` `lemonade-status` `audit`
- `POST /dsh-memory/card-action` `add-run` `config` `lemonade-ensure` `extract`（校验同源 Origin，拒绝跨站）

## 安全

- 所有 POST 路由做同源校验（Origin vs Host），跨站直接 403。
- 云端提取前默认脱敏；`apiKey` 永不回显明文。
- Sidecar 仅监听 127.0.0.1 随机端口，不暴露公网。

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
