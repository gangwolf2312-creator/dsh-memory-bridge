# Memory Tree System（记忆树系统）

> 从 CGAOS-V3 项目中独立提取的记忆引擎，设计目标是作为 DeepSeek Harness（DSH）私人 agent 的**长期记忆底座**。本目录是纯净、自包含、可独立运行的记忆系统：`memory/` 为引擎源码，`core/` 为其最小契约层，`tests/` 为可运行的单测。
>
> 本说明文档同时是**给 agent 的适配说明书**：任何 agent 读完本文档即可理解系统结构，并在 DSH 中以插件/工具方式完成适配。
>
> **知识库支线（LLM Wiki）**：从对话中提炼的通用知识（规范/概念/教程）不进记忆树，走独立知识库——完整设计见 [`docs/WIKI-DESIGN.md`](docs/WIKI-DESIGN.md)（双轨架构：记忆树管经历，知识库管知识）。

---

## 1. 系统定位与核心理念

这是一个**树形、事件溯源、确定性检索**的长期记忆系统，与常见的"扁平记忆文件"（如 Hermes 的 `MEMORY.md`）不同：

- **树形组织**：记忆不是一条条平铺的文本，而是 `事件卡 → 事件链 → 经验/画像` 的树。事件是叶子，链是枝，枝完结时生成"果摘要"作为导航路标。
- **明文为真源**：每张记忆卡是一个带 front matter 的 Markdown 文件，人可直接阅读、编辑、找回；`sqlite3` 只是可重建的加速索引，删了不丢数据。
- **确定性检索**：BM25 + 多路 RRF 加权，不做向量/嵌入，零外部服务、零 LLM 参与检索，延迟低、可解释。
- **生命周期完备**：记忆会老化（遗忘曲线）、会被新事实替代（版本链）、会完结萎缩（事件结束）、会被人工归档；重要安全事实豁免衰减。
- **对话永不丢**：原始对话先落盘（`runs` 表），提取是幂等状态机，失败/禁用都不删原文。

核心理念一句话：**记忆是独立可靠的数据层，不是模型自律的产物。**

---

## 2. 目录结构与模块职责

```
Memory Tree System/
├── README.md               # 本文档
├── pytest.ini              # pytest 配置（pythonpath=.）
├── memory/                 # 记忆引擎源码（24 个模块）
│   ├── __init__.py         # 公开面：MemoryStore / MemorySearch / MemoryService / detect_feedback / tokenize
│   ├── models.py           # 数据模型（MemoryCard / MemoryRun / SearchResult）
│   ├── store.py            # 存储层：明文 markdown 卡 + sqlite3 索引（核心，36KB）
│   ├── search.py           # 检索：BM25 + RRF + 树导航 + 反馈 + 相对时间（核心，20KB）
│   ├── backends.py          # 提取后端：本地轨 / 云端记忆专用 / 主对话兜底（V3.3）
│   ├── extract.py          # 写入管道：runs 状态机 → LLM 提取 → 事件卡/链/待固化
│   ├── distill.py          # 画像蒸馏：事件树 → 画像摘要 + MBTI + 8 轴人格（周频 + 人工审批）
│   ├── dsh_source.py        # DSH 会话日志字段匹配 → MemoryRun 回填（V3.2）
│   ├── decay.py            # 遗忘曲线维护（时间衰减 + 强化 + 安全豁免）
│   ├── fruit.py            # 枝完结：生成果摘要（结论摘要，树导航优先展示）
│   ├── profile.py          # 画像存储/解析（Profile / Dimension / ProfileStore）
│   ├── persona.py          # 人格库与选择（PersonaLibrary / PersonaSelector）
│   ├── rules.py            # 偏好规则台账（PreferenceLedger，同类信号 ≥3 → 提案）
│   ├── injector.py         # 记忆注入器（MemoryInjector：命中 → 上下文注入）
│   ├── sanitize.py        # 提取前脱敏：云端+本地轨敏感信息清洗（V3.5）
│   ├── strategy.py          # 提取策略：本地逐条 / 云端逐条 / 主对话兜底 / 通用攒批（V3.3）
│   ├── service.py          # 门面服务（MemoryService，组合 store+search）
│   └── tokenize.py         # 中文分词（jieba 封装，缓存）
├── core/                   # 最小契约层（从 CGAOS-V3/src/core 提取）
│   ├── backend.py          # Backend 协议：LLM 后端统一接口（complete / count_tokens）
│   ├── events.py           # Event / EventType / EventBus（可选事件挂接）
│   └── types.py            # IntentTier 等枚举
└── tests/                  # 纯单元测试（不依赖原项目，308 个用例全部通过）
```

---

## 3. 数据模型（`memory/models.py`）

### MemoryCard —— 一张记忆卡

```python
@dataclass(frozen=True, slots=True)
class MemoryCard:
    id: str                    # 卡 id（如 evt-xxx / chain-xxx）
    kind: str                  # event | chain | lesson_pending | lesson_permanent | profile
    title: str                 # 一句话标题
    content: str               # 事实描述（第三人称、可独立理解）
    source_path: str           # 相对 memory_dir 的文件路径（溯源）
    created_at: str
    run_id: str | None         # 来源对话 run（溯源）
    confidence: float          # 置信度（证据驱动计算，§9.7；不再是准入阀门）
    status: str                # active | archived
    weight: float              # 反馈回路权重（只影响排序）
    last_hit_at: str | None
    hit_count: int             # 命中次数（强化）
    miss_count: int            # 未命中次数（弱化）
    parent_id: str             # 树结构：所属事件链卡 id（chain 卡为空）
    entities: tuple[str, ...]  # 专有名词（跨卡关联/多跳）
    children: tuple[str, ...]  # 树结构：链卡的子卡 id 列表
    updated_at: str            # 最近更新
    supersedes: str            # 本卡替代的旧事实标题（版本链）
    superseded_by: str         # 被哪张新卡替代（时序裁决）
    invalid_at: str | None     # 失效时间
    ended_at: str | None       # 事件完结时间（枝/叶：事件结束即萎缩）
    trace_event_id: str        # 溯源：回合根 event_id
    source_part: str           # user | assistant | tool:<name>
    source_card_ids: str       # 果/果核引用来源卡 id（溯源链）
    summary: str               # 果摘要（枝完结时生成，检索导航优先展示）
    aliases: tuple[str, ...]   # 链卡标题别名（吸收措辞漂移，归链稳定）
    evidence: str              # 证据标签：directive|explicit|inferred|uncertain|approved
    corroborations: int        # 佐证计数（独立提及/用户确认，豁免与校准依据）
```

### MemoryRun —— 一次待提取对话（`runs` 表）

```python
@dataclass(frozen=True, slots=True)
class MemoryRun:
    run_id: str
    session_id: str
    user_text: str
    reply_text: str
    tier: str                  # L0 | L1 | L2（意图档）
    ts: str
    project_id: str | None
    trace_event_id: str        # 回合级溯源
```

### SearchResult —— 检索命中

```python
@dataclass(frozen=True, slots=True)
class SearchResult:
    card_id: str
    score: float
    source_path: str
    title: str
    snippet: str
    chain_id: str              # 所属链卡 id（树形展示）
    chain_title: str
    branch_summary: str        # 所属枝的果摘要（下钻优先展示）
    created_at: str
```

---

## 4. 存储约定（`memory/store.py`）

`MemoryStore(memory_dir: Path)` 纯参数化，目录结构：

```
<memory_dir>/
├── events/
│   ├── logs/YYYY-MM-DD.md     # 日记录（时间线）
│   ├── cards/<id>.md          # 事件卡
│   └── chains/<id>.md         # 事件链卡
├── lessons/
│   ├── pending/<id>.md        # 待固化（低置信，人工审批）
│   └── permanent/<id>.md      # 已固化
├── profiles/PROFILE.md        # 画像
├── personas/                  # 人格库
└── .index/memory.db           # sqlite3 索引（可重建，明文仍是事实源）
```

- **明文为真源**：每张卡 = front matter（`---` 包围的 `key: value`）+ 正文。`_card_to_md()` / `_parse_md()` 负责往返，损坏或缺 id 的卡安全跳过。
- **索引可重建**：`cards` / `runs` / `decision_log` / `preference_signals` 四张表；`sqlite3`（WAL + busy_timeout，跨进程多读一写）做加速，删除 `.index/` 不丢任何记忆。
- **追加安全**：`runs` 表记录原始对话，提取状态机 `staged → extracting → done | failed`，失败不删 run。
- **关键方法**（给适配 agent 的 API 清单）：
  - `add_run(...)` / `mark_run(...)`：落盘对话、推进提取状态机
  - `write_card(card, sync_index=True)` / `load_card(card_id)` / `list_active_cards()` / `archive_card(...)`
  - `active_cards_with_tokens()`：检索用（卡 + 分词缓存）
  - `chain_id(title)`：同一事件链标题 → 稳定链卡 id
  - `now_iso()`：UTC+8 ISO 时间戳

---

## 5. 检索算法（`memory/search.py`）

`MemorySearch(store, ...)`，一次 `search(query, top_k, ...)` 的组成：

1. **分词**：`tokenize()`（jieba 缓存），query 与文档同口径。
2. **BM25**：`_bm25()`，k1/b 标准参数，逐文档打分。
3. **多路 RRF**：多路召回结果按 rank 融合（`score += 1/(k+rank)`），容忍不同口径噪音。
4. **树导航（B4）**：
   - 先对齐"枝的身份"：query 命中链标题（权重 ×2）+ 果摘要 → 定位枝；
   - 命中枝下叶子加权（第一轮导航，先找枝再下钻）；
   - 同一枝最多 `max_per_chain` 张叶，防一枝霸屏；
   - 实体限定多跳：共享实体只在同枝内扩展。
5. **遗忘曲线（A8/B2）**：`decay.py` 维护，时间衰减 + 命中强化；安全/关键事实（`_EXEMPT_KEYWORDS`：过敏/账号/密码/截止日期…）豁免衰减，防重要记忆被 top-k 挤出。
6. **反馈权重**：`detect_feedback(user_text)` 识别"不对/错了/纠正"（down）与"有用/记住了/很好"（up），调整卡 `weight`，只影响排序。
7. **相对时间（B4.6）**：query 含"昨天/上周/最近 N 天"等 → 自动注入 `since/until` 窗口，零 LLM。
8. **溯源**：命中带 `source_path` / `chain_id` / `branch_summary`，可下钻查看原文。

---

## 6. 写入管道（`memory/extract.py`）

```
runs（原始对话落盘）
  → LLM 提取（LLMExtractor.extract，走 core.Backend 协议）
  → 事件卡（confidence ≥ 0.5）或 lesson_pending（< 0.5 待人工审批）
  → 同主题归入同一事件链（chain_id 稳定）
  → 幂等：状态机 staged → extracting → done|failed，重复处理由 store 保证
  → 每次提取成功发 MEMORY_EXTRACT 事件（EventBus 可选）
```

提取提示词要求（`_EXTRACT_PROMPT`）：
- 只提取**稳定事实**（偏好/计划/经历/身份），寒暄/临时问答不提取；
- 与已有记忆冲突时填 `supersedes`（时序裁决：新覆盖旧）；
- 事件结束填 `ended: true`（枝/叶完结萎缩）；
- `source_part` 标注来源（user / assistant / tool:<name>）；
- 专有名词进 `entities` 做跨卡关联。

`LLMExtractor` 需要注入一个 `core.Backend` 实现（见 §9 适配）。

---

## 7. 蒸馏与画像（`memory/distill.py` / `profile.py` / `persona.py`）

- **画像蒸馏（B3）**：周期（默认每周一次 + idle 门槛）用 LLM 从事件树压缩出画像摘要 + MBTI + 8 轴人格多边形（ei/sn/tf/jp/task/risk/style/form），产出 `profiles/drafts/PROFILE.draft-<ts>.md` 待人工审批。
- **防抖/去重/降级**：与当前画像相似度 >0.9 不产草稿；与最近草稿相同不重复产；通道失败记 `decision_log` 并保留旧画像。
- **人格库**：`PersonaLibrary` / `PersonaSelector` 管理多套人格，按 `IntentTier` 选择注入。

---

## 8. 依赖清单与快速运行

| 依赖 | 用途 | 说明 |
|---|---|---|
| Python ≥ 3.11 | 运行时 | 使用 `StrEnum`、`dataclass(slots=True)` |
| `sqlite3`（标准库） | 索引加速 | 内置，无需安装；WAL + busy_timeout 支持跨进程 |
| `jieba` | 中文分词 | `pip install jieba` |
| `pytest`（可选） | 单测 | `pip install pytest` |

验证命令（本机已验证：308 passed，含 P2 补测的 9 个零测试模块）：

```sh
cd "D:\dsh\plugins\Memory Tree System"
python -m pytest tests -q
```

最小使用示例：

```python
from pathlib import Path
from memory.store import MemoryStore
from memory.search import MemorySearch

store = MemoryStore(Path("runtime"))          # 任意目录，自动建骨架
search = MemorySearch(store)
hits = search.search("部署端口是多少", top_k=5)
for h in hits:
    print(h.title, h.score, h.source_path)
```

---

## 9. 在 DeepSeek Harness 中适配（给 agent 的作业说明）

本系统与 DSH 是**两个独立世界**，适配 = 搭一座桥。目标：让 DSH 的 agent 拥有本系统的"记忆树"能力。核心需要完成四件事（范围收敛与注入哲学见 §9.5/§9.6）：

### 9.1 LLM 后端适配（唯一硬依赖）
`extract.py` / `fruit.py` 需要 `core.Backend` 协议（`complete(messages, ...) -> BackendResult`）。V3.4 已内置提取后端（`memory/backends.py`）：`LocalBackend`（本地轨，任意 OpenAI 兼容端点，含 NPU 推理）/ `CloudBackend`（云端独立模型提取）/ `MainModelBackend`（主对话模型兜底，DSH 注入 `ctx.llm`）；`ExtractConfig.mode` 显式开关（`off|local|cloud|main`，**默认 main**），`build_extractor()` 一键装配（见 §9.8）。DSH 侧若想走自身模型路由，也可绕过后端类，直接用 `ctx.llm.stream(GenerateOptions)`（`packages/llm/llm/src`，`AsyncIterable<StreamChunk>`），仅复用 `_extract_json_object()` 与 `LLMExtractor._cards_from_raw()`（纯函数）。用户画像蒸馏（`distill.py`，适配重点，见 §9.5/§9.6）建议直接调 DSH `ctx.llm`（模型路由自带回退链）。

### 9.2 暴露给模型的工具（建议 5 个）
在 DSH 中以 cordis 插件（`ctx.tools` 注册，参考 `packages/extensions/tool-*`）或 MCP server 暴露：

| 工具 | 对应实现 | 说明 |
|---|---|---|
| `memory_search(query, top_k)` | `MemorySearch.search()` | 记忆召回（确定性，无 LLM） |
| `memory_add_run(user_text, reply_text, tier)` | `store.add_run()` | 对话落盘（提取可后台异步） |
| `memory_review(pending_id, approve)` | `store` 固化路径 | 人工/用户确认待固化记忆 |
| `memory_distill(reason?)` | `distill.py`（ctx.llm 路由） | 立即蒸馏：事件树 → 画像草稿；周任务由 `schedule` 插件触发（见 §9.3） |
| `memory_inject(query)` | `MemoryInjector` | 命中 → 上下文注入（DSH 用 `agent/pre-step` 或 `ctx.agents.send` 注入 user 消息） |

### 9.3 生命周期挂接点
- **回合收尾写入**：DSH 监听 `agent/turn-stopping`（与 dsh-memory-evolve 同款钩子），把本回合 user/assistant 文本写入 `runs`，并触发异步提取。
- **每会话注入**：把用户画像/项目关键记忆渲染进系统提示词（低频轨）或作为 user 消息（需控制 KV-cache 稳定性）。
- **周期蒸馏（用户画像）**：DSH `schedule` 插件注册“每周 + idle 门槛”任务 → `distill.py`（ctx.llm 路由）产草稿 → `ask_user_question` 人工审批固化（详见 §9.6）。
- **事件**：**不使用** `core.events.EventBus`（不迁移清单，见 §9.5）。DSH 用自身事件体系（`agent/turn-stopping`、`agent/pre-step`）驱动；如需 UI 展示可用 DSH 投影/通知机制。

### 9.4 目录选址与多项目隔离
- **路径契约已代码化**：`memory/paths.py` 统一解析（`resolve_memory_root()` / `resolve_wiki_root()`）——显式传入 > 环境变量 `DSH_MEMORY_ROOT` / `DSH_WIKI_ROOT` > `$DSH_HOME`（空值视为未设，对齐 DSH home-paths 规则）> 兜底 `~/.dsh`；默认落点 `<home>/memory-tree`（记忆库）与 `<home>/memory-wiki`（知识库），两库永远分离。测试见 `tests/test_memory_paths.py`。
- 多项目隔离用 `project_id` 字段（`MemoryRun.project_id`），检索按项目加权；
- 记忆文件全部 gitignore，明文可找回、可人工编辑。

### 9.5 明确不迁移清单（DSH 适配范围收敛）

以下两项经评估与 DSH 无功能交集，**适配时不迁移、不调用、不依赖**（文件保留在仓库，仅作独立运行/单测使用）：

| 模块 | 原因 |
|---|---|
| `memory/persona.py`（PersonaLibrary / PersonaSelector，**agent 人格库**） | agent 人格由 DSH `persona` 插件/系统提示词配置，不走记忆系统 |
| `core/events.py`（Event / EventBus / EventType） | DSH 有自身事件体系，重复造轮子；改用 DSH 事件（见 §9.3） |

注意：**用户画像不在不迁移清单内**——`memory/profile.py`（`profiles/PROFILE.md` 存储）+ `memory/distill.py`（蒸馏管道）是**适配重点之一**（agent 要“懂你”靠的就是这份画像），LLM 路由与注入方式见 §9.1/§9.3/§9.6。`core/types.py` 的 `IntentTier` 仍是遗留概念，DSH 适配时简化（见 §9.6）。

### 9.6 注入哲学改造方案（借鉴 dsh-memory-evolve：低频轨注入 + 高频轨按需读 + 固定提示行收尾写）

**原则**：注入轨 = 读取策略，不改存储。记忆树存储保持不变（树形卡 + 日志），只在注入层分三层；**用户画像是常驻基线的核心内容**。

**① 常驻基线（低频轨 · 推式）**——每次请求注入
- 内容：**用户画像**（`profiles/PROFILE.md` 已审批摘要，预算 ≤200 tok）+ `lesson_permanent`（高置信、全局/项目关键事实）
- 特征：低频稳定 → 常驻注入，KV-cache 友好
- **变更检测**：用画像 `updated_at` + 关键卡 `updated_at` 列表算 digest，digest 未变则跳过注入（不产生新快照）；`superseded_by` / `invalid_at` 变化即换新快照
- 预算：总量限量（建议 ≤2048 字符），超限按 画像摘要 > 关键事实 省略

**② 拉式检索（中频 · 现成）**——每轮按 query 补漏
- 内容：`event` / `chain` 树命中（`MemorySearch.search()`）
- 特征：每轮可能不同 → 放请求尾部（user 角色消息），不污染前缀缓存
- 简化：DSH 无 `IntentTier`，去掉 L0/L1/L2 分档，改为固定上限（建议 top_k=3~5）

**③ 收尾写入提示（高频 · 固定提示行）**——让模型自己写
- 快照末尾放一行**文本永不变**的提示（变量全走工具参数，不进提示文本）：
  `回合结束时调用 memory_add_run 记录本回合进展；重要/长期事实调用 memory_add_lesson 提交建议，待用户确认后固化。`
- DSH 侧挂 `agent/turn-stopping`：把模型的工具调用落 `runs` 表 + 触发异步提取（`extract.py` 管道）
- 固定文本不变 → 前缀缓存命中率不因写入而变化

**用户画像生产管道（蒸馏，适配重点）**
- **周期**：DSH `schedule` 插件承接“每周一次 + idle 门槛”的蒸馏调度；手动用 `memory_distill` 立即触发
- **LLM**：`role=distill` 后端链 → 直接走 DSH `ctx.llm` 模型路由（自带回退链，比原 `core.Backend` 协议更简单）
- **审批**：草稿 `profiles/drafts/PROFILE.draft-<ts>.md` → DSH `ask_user_question` / 命令交互人工审批 → 固化到 `PROFILE.md`（明文；下一轮 digest 变化即注入生效）
- **防抖/去重/降级**：沿用原逻辑（与当前画像相似 >0.9 不产草稿；通道失败记 `decision_log` 并保留旧画像）

**对应代码改动**：
- `memory/injector.py` 扩展：`build_static_snapshot(project_id, branch?)`（常驻基线：用户画像 + 关键事实）+ 保留 `inject_for_query(query, top_k)`（拉式，去 IntentTier）+ 导出 `WRITE_PROMPT` 常量（固定提示行）
- `memory/store.py` 新增：`low_frequency_cards(project_id?, branch?)`（筛选 profile + lesson_permanent + active + 未失效，限量排序）与 `snapshot_digest(project_id?)`
- 蒸馏入口：`distill.py` 后端链替换为 DSH `ctx.llm`；`schedule` 插件注册周任务；`ask_user_question` 承接审批
- 三个入口的 DSH 挂接：`agent/pre-step`（① + ② + ③ 注入）与 `agent/turn-stopping`（回合写入）

**验收补充**：① 连续两轮注入文本不变（digest 生效）；② 写入日志后下一轮前缀缓存仍命中（提示行未变）；③ 画像/关键事实常驻，event 只按需检索；④ 蒸馏草稿经审批固化后，下一会话注入画像文本变化（蒸馏闭环）。

### 9.7 设计闭环：模型输出只产生候选，真值由机制裁决

两处"模型自评当事实源"的缺口已在代码中闭环：

**① 链身份稳定（防悄悄分裂）**
- 归链不再直接哈希 LLM 标题：`store.resolve_chain(title, entities)` —— 精确标题/别名 → 复用；否则标题相似（Jaccard/包含度）+ 实体消歧 → 复用；否则新建
- 链卡 canonical 标题保留首见，漂移措辞进 `aliases`（明文 front matter + `decision_log` 审计）
- 存量分裂修复：`merge_chains(keep, drop)` 子卡 re-parent + drop 链卡 `superseded_by`（版本链可回滚）；`duplicate_chain_candidates()` 检测
- 边界：仅 active 链参与归链；完结/失效链不吸新事件（新章 = 新链）

**② 置信度校准（证据驱动准入）**
- LLM 只输出证据标签 `directive|explicit|inferred|uncertain`；confidence 成为可复现计算字段（base + 来源/佐证/指令修正，上限 0.95，审批 1.0）
- 准入阀门：directive/explicit → 自动固化；inferred → 需佐证（同断言 ≥2 次 run）或 tool 来源；uncertain → 一律 pending（DSH 用 `ask_user_question` 审）
- 用户反馈联动：纠正 → 证据降级 uncertain + 置信 cap 0.4；确认 → `corroborations` +1（豁免/校准依据）
- B4.4 永不衰减豁免改键：lesson_permanent / approved / explicit / directive / 佐证 ≥1，不再信裸 0.9
- 冲突仍归 B2 时序裁决（新结果覆盖旧结果），置信门不重复设闸

**③ 成本控制与实证 instrumentation**
- 提取门卫 `should_extract()`（`memory/guard.py`，零 LLM）：指令/数字/专名/时间词/长句 → 入队；寒暄 → run 照常落盘但 `status=skipped`（对话永不丢，省 LLM 调用）
- 全链路埋点进 `decision_log`：`inject_hit`（注入了什么卡）/ `inject_used`（模型输出是否用到）/ `extract_cost`（每回合输入字符量）/ `extract_skip`
- `detect_inject_usage()`（`memory/audit.py`）：规则归因——输出含注入卡强数字 token 或 ≥2 词元命中 → used；零 LLM、有噪音但够用
- `audit_summary()`：按周聚合注入命中率/使用率/跳过率/提取成本 → "注入是否被模型真正利用"的第一份实证（§9.7 经验校准的数据来源）

**④ 治理闭环（V3.3 补全：指标不健康时系统自动做什么）**
- 去噪判定：`detect_inject_usage` 升级——数字命中需"数字 + 强词元"双命中（纯数字需 ≥2 个不同数字）；强词元 = jieba 长度≥2、非停用词、非数字
- 卡级回流：`apply_usage_feedback(store, usage)`——used → `update_hits`（命中滚动清零 miss）；unused → `update_misses`；连续 ≥3 次未命中 → `weight ×0.5` 淡出排序（不归档、不降证据："没被利用" ≠ "记忆错误"）
- 全局治理：`govern_injection(store)`——`inject_used_rate < 0.3` → 建议 L2 注入条数 3→2→1（`suggested_limits`）；低使用率卡批量降权；动作写 `decision_log`（`govern_action`）可审计
- 装配建议：DSH 侧每回合 `detect_inject_usage` + `apply_usage_feedback` 回流；每周（或 idle）跑一次 `govern_injection`，把 `suggested_limits` 应用到 `MemoryInjector`（`l1_limit/l2_limit`）

新增字段（幂等迁移，旧库自动补列）：`aliases` / `evidence` / `corroborations`。
新增测试：`tests/test_memory_confidence.py`（置信门/反馈联动/豁免改键）+ `test_memory_chain.py` 归链/合并用例 + `tests/test_memory_guard.py`（门卫/审计）。

### 9.8 三级提取后端与 DSH 日志数据源（V3.3 实测落地）

**数据源层：DSH 会话日志就是免费原始层**

DSH 每次模型调用都写 `session.jsonl(.zstd)`（`DSH_SESSION_JSONL` 环境变量定位），
事件流含 `turn/start|end`、`user/message`、`assistant/message`（content 数组含
reasoning/tool-call/text）、`tool/call|result`、`assistant/chunk.usage`
（provider 上报精确 token）。记忆系统**不再自己落盘对话**：`memory/dsh_source.py`
只做字段匹配（DSH 事件 → MemoryRun），零 LLM、零网络。

字段匹配契约（实测）：
| DSH 事件字段 | MemoryRun 字段 |
|---|---|
| header.id | session_id |
| turn/start \| turn/end（data.turn） | run_id（会话+回合哈希，跨重放稳定） |
| user/message content[].text | user_text |
| assistant/message content[type=text].text | reply_text（reasoning 不进入） |
| user/message.data.id | trace_event_id |
| assistant/message.usage | 成本审计（decision_log） |
| tool/call（data.callId → data.name） | 工具名关联（callId 查表） |
| tool/result（message.content 内 tool-result 块中 type==text，isError 标记） | reply_text（`[tool:name]` 前缀，按事件时间序，截断 + 回合总预算） |

工具结果：`tool/result` 经 `callId` 关联 `tool/call` 的工具名，以 `[tool:name]` 前缀按事件时间序并入 `reply_text`（提取器可见 shell/文件输出；`isError` 标记失败），`max_tool_chars` 单条截断 + `max_tool_total` 回合总预算。实测 30 回合日志中 20 个回合含工具输出。

回填幂等：`backfill_runs()` 用 `INSERT OR IGNORE`，同一会话可重复回填/重放/重跑提取
（日志可重来，提取不是一次性消费）。实测：本地真实会话 30 回合 → 30 条 run，字段全部对齐。

**提取后端显式开关（三选一 + off：本地 / 云端独立模型 / 主对话兜底）**
- `ExtractConfig.mode ∈ off | local | cloud | main`（`memory/backends.py`；**默认 main**）
- `off`：不启用 LLM 提取（纯规则/显式记忆 `rules.py`，零调用）
- `local`：本地轨（任意 OpenAI 兼容端点：Ollama / llama.cpp / vLLM / LMDeploy / MindIE，含 NPU 本地推理），零边际成本
- `cloud`：云端独立模型提取（OpenAI 兼容 API，如 DeepSeek），攒批 + 限流 + 脱敏
- `main`：主对话模型兜底（**默认**，DSH 侧注入 `ctx.llm`，复用主对话通道，不新增网络路径）
- **本地与云端二选一；都不开则默认走 `main`（复用主对话模型提取，运行无感）；`off` 显式关闭 LLM 提取**

**激活后配置，不硬编码供应商**
- 所有供应商地址/模型名默认留空：开关激活后由调用方注入（`build_extractor(config, main_backend=...)` 或环境变量装配 `load_extract_config(env)`）
- 激活校验：`local` 缺 `base_url/model`、`cloud` 缺 `base_url/api_key`、`main` 未注入后端 → 均报错提示，绝不静默用错误默认值
- 环境变量（`memory/service.py`）：`MEMORY_EXTRACT_MODE`（缺省 main）、`MEMORY_LOCAL_BASE_URL` / `MEMORY_LOCAL_MODEL` / `MEMORY_LOCAL_API_KEY`、`MEMORY_CLOUD_BASE_URL` / `MEMORY_CLOUD_API_KEY` / `MEMORY_CLOUD_MODEL`
- 参考组合：本地 = Ollama（`http://127.0.0.1:11434/v1`）/ LMDeploy / MindIE（昇腾 NPU）+ 本地小模型；云端 = DeepSeek（`https://api.deepseek.com/v1`）

**脱敏（安全缺口堵漏，`memory/sanitize.py`）**
- 云端后端（`CloudBackend`）发送前对 messages 内容脱敏：API Key、Bearer/Token、私有密钥块、AWS Key、身份证、手机号、邮箱、常见凭证键值 → 替换为占位符
- **本地轨（`LocalBackend`）默认也脱敏**（`sanitize=True`）：本地虽不出网，但对话中的 API key/凭证若进记忆卡会持久化在明文 md——比出网更糟。真实语料验证：含 key 回合提取后 key 未泄漏
- 命中类型记录在 `last_sanitize_hits`（审计用）：用户可感知"本次提取脱过哪些类"
- 可显式关闭（`sanitize=False`，信任本地模型/数据时）；脱敏会轻微降低提取质量，但保证凭证不入记忆

**差异化提取策略（`memory/strategy.py`）**
| 策略 | 调用模式 | 成本 | 消解能力 | 适用 |
|---|---|---|---|---|
| local | 逐条实时 | 零边际（NPU/本地推理） | max_turn_chars 截断（默认 4000） | 高频轮次（运行无感） |
| cloud | 攒批 N 条一次调用（默认 8） | 调用次数摊薄 8x | 超容量跳过（默认 8000） | 低频批量 |
| main | 逐条 | 复用主对话计费 | 主模型上下文大（默认 8000） | 默认兜底 |

**资源占用与模型消解能力（评估重点）**
- `LocalConfig`：`max_context_tokens`（上下文预算）、`concurrency`（并发上限）、`timeout_s`、`max_turn_chars`（单轮输入上限，超限截断）——NPU 本地推理通过 OpenAI 兼容端点接入，资源占用由这些参数约束
- `CloudConfig`：`max_calls_per_minute`（滑动窗口限流）、`batch_size`（攒批规模）、`retries`、`sanitize`
- `CloudBackend.cost_summary()` → `decision_log`：调用次数/输入/输出 token 精确记账（provider 上报，非估算）
- 提取成本 = 除"对话落盘"外唯一额外项；门卫 + 显式记忆（零 LLM）+ 本地轨（零边际）把成本压到最低

**模型参数建议（本地小模型 / qwen3-tk-4b-FLM + NPU 场景）**
- **温度 `temperature=0.0`**：结构化抽取要求确定性（同输入同输出，可复现可审计）；勿用高温度
- **`max_tokens=512`**：关闭 thinking 后足够（卡片 JSON 小）；若开启 thinking 需 1024+（thinking 占输出预算）
- **思考模式**：默认关闭（`extra_body={"chat_template_kwargs": {"enable_thinking": false}}`）——提取是快速结构化任务，thinking 不增值且拖慢 NPU
- **`max_turn_chars=4000`**（≈2k token，32K 上下文下远低于上限）：NPU 慢速场景输入越短推理越快；4000 字符覆盖绝大多数真实回合
- **透传机制**：`LocalConfig/CloudConfig.extra_body` 可透传任意模型特有参数（thinking 开关等），`build_extractor(cfg, temperature=..., max_tokens=...)` 覆盖温度/预算
- **验收**：`scripts/probe_extract.py` 跑真实端点出质量报告（JSON 成功率/证据枚举/链稳定性/每条耗时）；`--limit/--only/--sleep` 适配 NPU 慢速分批验证
- **测试集**：`probes/extract_cases.py` 23 条覆盖 12 组能力（指令/明确/推断/不确定/寒暄/知识/链/完结/工具/裁决/领域术语/压力）
### 9.9 DSH 侧接入建议（实测 API 精准版）

> 本系统只做字段匹配与内部管道；以下为 DSH 侧写插件时的接法建议，不在本仓库实现。
> 所有接口均基于本地 DSH 源码 `packages/` 实测。

**① 回合收尾写入（`agent/turn-stopping`）**
- 事件真实签名：`ctx.on('agent/turn-stopping', ({ agent, turn, signal }) => ...)`
  （`packages/core/agent/src/runtime-types.ts`，payload = `{ agent, turn, signal }`）
- 接法 A（日志回填，最省）：`turn` 到达后调 `backfill_runs(store, dshSessionJsonl, max_turns=turn)`，
  路径取 `ctx.sessionPersistence.locate()` 或环境变量 `DSH_SESSION_JSONL`；同一会话幂等，多轮触发不重复
- 接法 B（实时读取，精确到回合）：`ctx.sessionQuery.readSurface(sessionId)`
  → `{ session, capturedThroughSeq, events }`，`events` 为 `user/message | assistant/message | tool/result`
  折叠序列（model-history 顺序），按 `turn/start|end` 重组后喂 `MemoryWritePipeline.enqueue()`
  （`memory/dsh_source.py` 提供同构解析，字段匹配契约见 §9.8）

**② 提取后端选择（显式开关）**
- 本仓库自带：`build_extractor(ExtractConfig(mode="local"|"cloud"|"main"), main_backend=ctx.llm)`（`memory/service.py`），
  `LLMExtractor` 已接 `core.Backend` 协议 + 策略（限流/截断/兜底）；`main` 模式（默认）注入 DSH 主对话后端，
  `local` 模式接本地 OpenAI 兼容端点（Ollama/LMDeploy/MindIE，含 NPU 推理）
- 或 DSH 侧直接用 `ctx.llm.stream(GenerateOptions)`（流式块含 text/reasoning/tool-call），
  组装完整文本后复用 `_extract_json_object()` + `LLMExtractor._cards_from_raw()`
- 画像蒸馏 `distill.py` 同理：建议走 DSH `ctx.llm` 路由，输出草稿 → `ask_user_question` 审批

**③ 记忆注入（`agent/pre-step`）**
- 低频轨：`injector.build_static_snapshot(project_id)` 渲染进系统提示词（画像 + 关键事实，`snapshot_digest` 变化才更新）
- 高频轨：`inject_for_query(query, top_k)` 按需拉取（BM25 + RRF，确定性）
- 收尾写：回合内改动经 `agent/turn-stopping` 落库，进下一轮注入（固定提示行收尾写）

**④ 成本核算闭环**
- `CloudBackend.cost_summary()` → `decision_log`（`calls/prompt_tokens/completion_tokens`，provider 上报精确值）
- 全链路埋点已就绪：`inject_hit` / `inject_used` / `extract_cost` / `extract_skip`（`memory/audit.py`）
- 周聚合：`audit_summary()` 输出注入命中率/使用率/跳过率/提取成本 → "记忆是否真的被利用"的第一份实证

**⑤ 目录选址**
- `MemoryStore(root)` 的 root 建议放在 DSH 工作区之外（如 `~/.dsh-memory/`），与 DSH 的 `sessions/` 分离：
  DSH 管原始层（日志），记忆树管提炼层（明文卡 + sqlite 索引）

### 验收标准
1. `pytest tests -q` 全绿；
2. DSH 会话里对 AI 说"记一下：部署端口是 8080"，下一会话问"部署端口是多少"能命中；
3. 说"不对/记错了"后，同一条记忆权重下降（排序后移）；
4. 记忆目录里的 markdown 卡人工可读、可编辑，删除 `.index/` 不丢数据。
5. 用户画像蒸馏产草稿 → 审批固化 → 下一会话注入画像文本变化。
6. 同一主题跨会话换措辞（"搬家"/"搬家计划"）→ 归同一链，链数不增；
7. 用户纠正后记忆证据降级（不再永不衰减）；"记住：X" 直达 event。

---

## 10. 与 dsh-memory-evolve 的关系（参考）

| 维度 | 本系统（Memory Tree） | dsh-memory-evolve |
|---|---|---|
| 记忆形态 | 树形（事件/链/经验/画像） | 扁平条目（Hermes 兼容） |
| 检索 | BM25+RRF+遗忘+反馈+树导航 | 几乎无记忆检索（全量注入+按需读） |
| 生命周期 | 版本链/失效/完结/衰减 | 仅归档 |
| 多设备同步 | 无（可补 git 三方合并） | 成熟（git 分支+身份证合并） |
| DSH 集成 | 未适配（本文档即适配起点） | 开箱即用（12 个 WebUI Tab） |

结论：记忆内核以本系统为准（检索/生命周期/树更完整）；若需要跨设备同步与 WebUI 管理，借鉴 dsh-memory-evolve 的 git 三方合并与审查确认制思路。