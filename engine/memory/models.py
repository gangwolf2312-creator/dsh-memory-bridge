"""记忆数据模型（DESIGN §4.1/§4.4；零依赖）。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MemoryCard:
    """一张记忆卡：事件 / 事件链 / 经验（pending|permanent）/ 画像。

    P0 记忆树：parent_id = 所属事件链卡 id（chain 卡为空）；
    entities = 卡内专有名词（跨卡关联/多跳跳转用）；
    children = 链卡的子卡 id 列表（事件卡为空；明文树结构可找回）。
    """

    id: str
    kind: str  # event | chain | lesson_pending | lesson_permanent | profile
    title: str
    content: str
    source_path: str  # 相对 memory_dir（溯源，A3）
    created_at: str = ""
    run_id: str | None = None
    confidence: float = 0.0
    status: str = "active"  # active | archived（A7）
    weight: float = 1.0  # 反馈回路权重（A8，只影响排序）
    last_hit_at: str | None = None
    hit_count: int = 0
    miss_count: int = 0
    parent_id: str = ""  # P0：所属事件链 id
    entities: tuple[str, ...] = ()  # P0：专有名词实体
    children: tuple[str, ...] = ()  # P0：链卡子卡 id（仅 chain 卡使用）
    # —— B2（ADR-0019）记忆树形态：更新/失效/完结/溯源 ——
    updated_at: str = ""  # 最近更新（演化/重写时间）
    supersedes: str = ""  # B2：本卡替代的旧事实（标题/id，提取时 LLM 标注；与 superseded_by 配对）
    superseded_by: str = ""  # 被哪张新卡替代（时序裁决版本链；空=未替代）
    invalid_at: str | None = None  # 失效时间（被覆盖/事件完结）
    ended_at: str | None = None  # 事件完结时间（枝/叶：事件结束即萎缩）
    trace_event_id: str = ""  # 溯源：回合根 event_id（痕迹层 events 表）
    source_part: str = ""  # 来源类别：user / assistant / tool:<name>
    source_card_ids: str = ""  # 果/果核引用来源卡 id（逗号分隔，溯源链）
    summary: str = ""  # B4：果摘要（枝完结时生成的结论摘要，检索树导航优先展示）
    aliases: tuple[str, ...] = ()  # 链卡标题别名（吸收 LLM 措辞漂移，归链稳定，§9.7）
    evidence: str = ""  # 证据标签：directive|explicit|inferred|uncertain|approved（置信校准，§9.7）
    corroborations: int = 0  # 佐证计数：独立提及/用户确认加固（豁免与校准依据）


@dataclass(frozen=True, slots=True)
class MemoryRun:
    """一次待提取对话（runs 表 = 原始对话落盘，提取后不删，保底不丢）。"""

    run_id: str
    session_id: str
    user_text: str
    reply_text: str
    tier: str  # L0 | L1 | L2
    ts: str = ""
    project_id: str | None = None  # 项目归属（召回按项目加权，噪音过滤）
    trace_event_id: str = ""  # B2：回合根 event_id（溯源标注，回合级）
    priority: int = 0  # 提取优先级（1=高优先，如 directive/关键事实；0=普通）


@dataclass(frozen=True, slots=True)
class SearchResult:
    """一条检索命中（带溯源路径；P0 附带所属事件链）。"""

    card_id: str
    score: float
    source_path: str
    title: str
    snippet: str
    chain_id: str = ""  # P0：所属链卡 id（多跳/树形展示）
    chain_title: str = ""  # P0：所属链卡标题
    branch_summary: str = ""  # B4：所属枝的果摘要（树导航下钻优先展示；空=无果）
    created_at: str = ""  # P0：时序检索/时间线展示


@dataclass(frozen=True, slots=True)
class WikiEntry:
    """一条知识条目（LLM Wiki 支线，独立于 MemoryCard——知识不污染记忆树）。

    kind 三分：spec（规范全文，需条文切块）/ concept（独立概念/术语，单条）/
    tutorial（教程/指南）。
    """

    id: str  # wk-<slug>（规范slug/概念slug，全局唯一）
    kind: str  # spec | concept | tutorial
    title: str  # 条目标题（规范名/概念名）
    content: str  # 条目正文（规范全文 / 概念解释 / 教程正文）
    spec_id: str = ""  # 规范编号（kind=spec 时必填，如 GB-50137-2011）
    level: str = ""  # national|province|city|county|township（层级过滤）
    admin: str = ""  # 行政单元（同级区分）
    parent_ref: str = ""  # 上位规划规范id（轻量指针）
    tags: tuple[str, ...] = ()  # 领域分类（点分标签，跨目录检索）
    aliases: tuple[str, ...] = ()  # 条目别名（吸收措辞漂移，同 resolve_chain 思路）
    entities: tuple[str, ...] = ()  # 专有名词（规划传导链的实体载体）
    source_path: str = ""  # 相对 wiki_dir 的文件路径（溯源）
    created_at: str = ""
    updated_at: str = ""
    source_run_id: str = ""  # 来源对话 run（溯源）
    source_part: str = ""  # user | assistant | tool:<name>
    evidence: str = ""  # explicit|inferred|uncertain（模型标签；inferred/uncertain → pending）
    status: str = "active"  # active=已入库（可检索）| pending=低置信待审（不进检索）
    confidence: float = 1.0  # 准入置信（默认 explicit 直通；低置信知识进 pending）
    supersedes: str = ""  # 版本链：本条目替代的旧条目标题（新规范覆盖旧版）
    superseded_by: str = ""  # 被哪条新条目替代
    invalid_at: str | None = None  # 失效时间（规范版本更新）
    figures: tuple[tuple[str, str, str], ...] = ()  # (图件编号, 相对路径, 说明)


@dataclass(frozen=True, slots=True)
class WikiSearchResult:
    """一条知识检索命中（条文级溯源：spec_id + 章/节/条号）。"""

    entry_id: str
    score: float
    source_path: str
    title: str
    snippet: str
    spec_id: str = ""  # 所属规范编号
    section_path: str = ""  # 条文溯源路径（如"第3章/第3.3条"）
    level: str = ""  # 层级（national/province/...）
    created_at: str = ""
