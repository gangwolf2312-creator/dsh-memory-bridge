"""拉式溯源记忆注入（ADR-0013 D1/D3/D4）：分档检索 + 超时空注入 + 溯源格式化。

- 分档：L0 零注入 / L1 ≤1 条 / L2 ≤3 条（对齐 V2 口径 + memory_max_items=3）
- 超时：检索 50ms 超时 → 空注入（宁缺勿滥，不拖慢 TTFT）
- 溯源：每条命中带 [长期记忆·来源/链/日期] 标记，供 assembler M 桶渲染
- 本模块只做"检索 + 格式化"，不依赖 context（注入组装在 kernel 层 provider）

v0.5 根本修复（检索质量）：注入相关度改为**数据驱动分级门槛**，废除人工词表
（v0.4 的 _INJECT_STOPWORDS 属正则补丁，实测仍漏：query"要不要采用左侧边栏的
折叠逻辑…"靠单词"采用/逻辑"误注入无关卡）：
- query 核心词：jieba.posseg 词性提取（名词/动词/形容词/方位/时间/习语等实词，
  滤代词/助词/连词/副词/数词/量词；英文词 ≥4 字符），不再依赖人工停用词表
- 卡库词频 df：从 cards.tokens 列统计（词级，进程内缓存 60s）
- 事件卡（流水）：≥2 个核心词重叠，或单核心词重叠且 df≤3（idf≥4.5 的稀有词）
  ——实测单"采用"(df10)/"逻辑"(df15)/"整体"均不过；"偏好"(df19) 也低于
  稀有阈值，说明单重叠词（无论稀有度）不足以证明事件卡相关
- 事实卡（lesson/pending/偏好画像）：≥1 个核心词重叠即注入——它们是"关于
  用户的事实"，弱相关即可（"我的偏好"→ 偏好卡）
"""

from __future__ import annotations

import contextlib
import math
import time
from collections import Counter

from core.types import IntentTier
from jieba import posseg
from memory.audit import detect_inject_usage
from memory.models import SearchResult
from memory.search import MemorySearch
from memory.store import now_iso
from memory.tokenize import tokenize_words

__all__ = ["MemoryInjector"]

_LIMITS = {IntentTier.L0: 0, IntentTier.L1: 1, IntentTier.L2: 3}

# 事件卡单核心词重叠的稀有度门槛：df ≤ 3（idf ≥ 4.5 @ N≈357）。
# 数据校准（2026-08-19，N=357）：采用 df10/idf3.53、逻辑 df15/idf3.14、
# 整体 df≈10、显示 df24 全部低于门槛；数据库 df1/边栏 df2/聚团 df2 等
# 稀有词单重叠仍可注入（强信号）。
_SINGLE_WORD_MAX_DF = 3

# 卡库词频缓存：tokens 列统计（词级），进程内 60s 过期（注入热路径零额外 IO）
_DF_CACHE: dict = {"at": 0.0, "df": None}


def _query_core_words(query: str) -> dict[str, str]:
    """query 核心词（词 → 词性首字母）：jieba 词性提取实词（数据驱动，无人工词表）。

    保留：名词(n)/动词(v)/形容词(a)/方位(f)/时间(t)/习语(l/i)/简称(j)；
    过滤：代词(r)/助词(u)/连词(c)/副词(d)/介词(p)/数词(m)/量词(q)/标点(x)；
    英文词 ≥4 字符（ui/api/id 等泛缩写不计）；单字不计。
    词性用于单词通道（v0.6：仅名词/形容词单重叠可注入——动词"迁移/解决"
    语义绑定弱，实测"数据库迁移"因"迁移"单词误注入 apiKey 迁移卡）。
    """
    out: dict[str, str] = {}
    for w, flag in posseg.cut(query or ""):
        if len(w) < 2:
            continue
        if w.isascii():
            if len(w) >= 4:
                out.setdefault(w.lower(), "eng")
            continue
        f0 = flag[:1]
        if f0 in ("n", "v", "a", "f", "t", "l", "i", "j"):
            out.setdefault(w, f0)
    return out


def _card_df(store) -> tuple[Counter, int]:
    """卡库词级文档频率（tokens 列统计，缓存 60s）；返回 (df, n_docs)。"""
    now = time.monotonic()
    cached = _DF_CACHE["df"]
    if cached is not None and now - _DF_CACHE["at"] < 60.0:
        return cached, _DF_CACHE["n"]
    df: Counter = Counter()
    n = 0
    try:
        rows = store._exec("SELECT tokens FROM cards WHERE status = 'active'").fetchall()
        for (tokens,) in rows:
            n += 1
            seen: set[str] = set()
            for w in (tokens or "").split():
                if len(w) > 1:
                    seen.add(w)
            for w in seen:
                df[w] += 1
    except Exception:
        pass
    _DF_CACHE["df"] = df
    _DF_CACHE["n"] = n
    _DF_CACHE["at"] = now
    return df, n


def _idf(n_docs: int, df: int) -> float:
    """标准 idf（BM25 口径）：df=0 视为 0（库中无此词 → 无证据）。"""
    if df <= 0:
        return 0.0
    return math.log(1 + (n_docs - df + 0.5) / (df + 0.5))


def _card_tokens(store, card_id: str) -> set[str]:
    """卡的词级 token 集（tokens 列；空则回退在线分词）。"""
    try:
        toks = store.card_tokens(card_id)
        if toks:
            return {w for w in toks if len(w) > 1}
    except Exception:
        pass
    card = store.read_card(card_id)
    if card is None:
        return set()
    return {w for w in tokenize_words(f"{card.title} {card.content}") if len(w) > 1}


def _card_seq(store, card_id: str) -> list[str]:
    """卡的有序词级 token 序列（短语匹配用；tokens 列保序）。"""
    try:
        toks = store.card_tokens(card_id)
        if toks:
            return [w for w in toks if len(w) > 1]
    except Exception:
        pass
    card = store.read_card(card_id)
    if card is None:
        return []
    return [w for w in tokenize_words(f"{card.title} {card.content}") if len(w) > 1]


def _phrase_hit(query_core: dict[str, str], seq: list[str]) -> bool:
    """短语通道（v0.6）：query 中相邻的核心词对在卡序列中也相邻出现。

    数据驱动依据：项目专名（记忆/插件）在单项目库里 df 极高，Σ idf 多词
    通道会误拦"记忆插件"这类精确主题短语；而"问题/解决"这类泛词在 query
    与卡中均不相邻（"问题没解决"vs"不解决…的问题"）→ 不触发。短语相邻
    是精确的主题信号。
    """
    core_words = list(query_core.keys())
    if len(core_words) < 2:
        return False
    pairs = set(zip(core_words, core_words[1:]))
    if not pairs:
        return False
    for i in range(len(seq) - 1):
        if (seq[i], seq[i + 1]) in pairs:
            return True
    return False


# 事件卡相关度门槛（v0.6 校准，2026-08-19，N=185）：
# - 单词重叠：idf ≥ 4.2（≈ df ≤ 2）——单稀有词强信号（数据库/边栏/聚团）；
#   "解决"(df3/idf3.97) 等次稀有动词不过
# - 多词重叠：Σ idf ≥ 6.0——v0.5 只数词数、无 idf 下限，实测排障 query
#   "问题(df30/idf1.81)+解决(df3/idf3.97)=5.78" 误注入无关卡；相关案例
#   "显示+模块+切换=7.97" 过；"图谱+聚团+修复"≈8+ 过；"记忆+插件+注入+
#   机制"≈7.7 过（4 词低频和够）；"注入+机制=4.64" 拦（宁缺勿滥）
_MULTI_WORD_MIN_SCORE = 6.0
_SINGLE_WORD_MIN_IDF = 4.2


def _event_gate(
    query_core: dict[str, str],
    card_tokens: set[str],
    card_seq: list[str],
    chain_title: str,
    df: Counter,
    n_docs: int,
) -> float:
    """事件卡注入门槛（v0.6）：idf 加权 + 词性 + 短语三通道。

    返回加权分（>0 才注入）：
    - 多词（≥2 重叠核心词）：Σ idf ≥ _MULTI_WORD_MIN_SCORE
    - 单词：名词/形容词且 idf ≥ _SINGLE_WORD_MIN_IDF（稀有词强信号；
      动词单重叠语义绑定弱——实测"数据库迁移"因"迁移"单词误注入 apiKey 卡）
    - 短语：query 相邻核心词对在卡序列或链标题中相邻出现 → 直接放行
      （精确主题信号，救"记忆插件"类高频项目专名）
    实测依据（N=185）：排障 query"问题+解决=5.78"误注入无关卡（v0.5 多词
    通道无下限）；相关"显示+模块+切换=7.97"、"图谱+聚团+修复≈8+" 过。
    """
    overlap = [w for w in query_core if w in card_tokens]
    if not overlap:
        return 0.0
    score = sum(_idf(n_docs, df.get(w, 0)) for w in overlap)
    if len(overlap) >= 2:
        if score >= _MULTI_WORD_MIN_SCORE:
            return score
        # 多词未达分 → 仍可走短语通道
    else:
        w = overlap[0]
        if query_core.get(w, "") in ("n", "a") and score >= _SINGLE_WORD_MIN_IDF:
            return score
    if _phrase_hit(query_core, card_seq):
        return max(score, 0.01)
    if chain_title and _phrase_hit(query_core, [w for w in tokenize_words(chain_title) if len(w) > 1]):
        return max(score, 0.01)
    return 0.0


class MemoryInjector:
    """把检索命中格式化为带溯源的注入文本（A3）；超时 → 空注入（A6）。"""

    def __init__(
        self,
        search: MemorySearch,
        *,
        l1_limit: int = 1,
        l2_limit: int = 3,
        timeout_ms: int = 50,
    ) -> None:
        self.search = search
        self.l1_limit = l1_limit
        self.l2_limit = l2_limit
        self.timeout_ms = timeout_ms

    def inject_for_tier(
        self,
        tier: IntentTier,
        query: str,
        *,
        project_id: str | None = None,
        project_by_run: dict[str, str] | None = None,
    ) -> list[SearchResult]:
        """按档位检索；L0 零注入；超时返回空列表。"""
        tier = tier if isinstance(tier, IntentTier) else IntentTier(tier)
        limit = _LIMITS.get(tier, 0)
        if limit == 0 or not query.strip():
            return []  # L0 零注入，不触发检索
        limit = min(limit, self.l1_limit if tier is IntentTier.L1 else self.l2_limit)
        started = time.perf_counter()
        # 抢救修复（v0.3）：放宽候选池（limit×3）——search 的反馈/短语列会把
        # 零使用史的事实卡挤出 top-N（实测：偏好卡 BM25 第 1 却不在 top-9）；
        # 池内再做事实优先 + 截断到 limit，保证"该记住的结论"有机会注入。
        # v0.4：注入禁用多跳扩展（expand=False）——沿链兄弟/实体扩展是树导航
        # 浏览语义，注入场景会把同链无关兄弟成倍拉高（实测图谱两张卡分数翻倍）。
        # v0.5：track_hits=False 纯只读——注入查询不写 hit/miss/归档记账（A7
        # 记账是 UI 检索语义；注入的无关查询会把无关卡 miss 累积到 50 批量归档，
        # 实测 66 张卡被测试 query 误归档后已恢复）。
        pool_k = max(limit, limit * 3)
        results = self.search.search(
            query, top_k=pool_k, expand=False, track_hits=False,
            project_id=project_id, project_by_run=project_by_run,
        )
        elapsed_ms = (time.perf_counter() - started) * 1000
        if elapsed_ms > self.timeout_ms:
            return []  # A6：超时 → 空注入（宁缺勿滥）
        # v0.5 根本修复：数据驱动分级门槛（废除人工词表）——
        #   1) query 核心词 = jieba 词性提取的实词
        #   2) 事件卡（search 结果）：Σ idf 多词门槛 / 名词形容词稀有词 /
        #      相邻短语通道（v0.6）
        #   3) 事实卡（lesson/pending/偏好）：≥1 核心词重叠即注入
        # search 的排序（RRF 多列）只用于候选召回，注入排序按本评分。
        q_core = _query_core_words(query)
        if not q_core:
            return []  # query 无实义核心词（纯虚词）→ 零注入
        df, n_docs = _card_df(self.search.store)
        gated: list[tuple[float, SearchResult]] = []
        for r in results:
            toks = _card_tokens(self.search.store, r.card_id)
            if not toks:
                continue
            seq = _card_seq(self.search.store, r.card_id)
            score = _event_gate(q_core, toks, seq, r.chain_title or "", df, n_docs)
            if score > 0:
                gated.append((score, r))
        gated.sort(key=lambda item: item[0], reverse=True)
        results = [r for _, r in gated]
        # 事实卡通道（v0.3 事实优先 + v0.5 门槛：核心词重叠 ≥1）
        facts = self._fact_lookup(query, limit, q_core=q_core)
        seen: set[str] = set()
        merged: list[SearchResult] = []
        for r in [*facts, *results]:
            cid = getattr(r, "card_id", "") or ""
            if not cid or cid in seen:
                continue
            seen.add(cid)
            merged.append(r)
            if len(merged) >= limit:
                break
        results = merged
        # 抢救修复（v0.3）：事实卡命中记账——search() 的 miss/归档记账只认它自己的
        # top-N（事实卡被多列 RRF 挤出池子时每次注入都 miss+1，50 次后仍会被归档，
        # 事实卡补充检索就白做了）。被补充检索命中并注入的事实卡按检索命中记账
        # （miss 清零），否则事实卡边注入边走向归档。
        if facts:
            fact_ids = [getattr(r, "card_id", "") for r in facts]
            with contextlib.suppress(Exception):
                self.search.store.update_hits([c for c in fact_ids if c], now_iso())
        # §9.7 实证：记录"注入了什么"（inject_hit），供 detect_inject_usage 归因
        with contextlib.suppress(Exception):
            self.search.store.log_decision(
                "inject_hit",
                f"query={query[:60]!r} cards={[r.card_id for r in results]}",
            )
        return results

    def _fact_lookup(
        self, query: str, limit: int, *, q_core: dict[str, str] | None = None
    ) -> list[SearchResult]:
        """事实卡补充检索：active 的 lesson_permanent/pending 卡直查 + 核心词重叠。

        抢救修复（v0.3）：search 的多列 RRF（反馈/短语/枝路标）会把零使用史
        的事实卡挤出 top-N（实测：偏好卡 BM25 第 1 却不在 top-9，注入被事件
        流水占满）。这里对 active 事实卡做确定性词面重叠，重叠 >0 即参与注入
        排序——事实卡是"该记住的结论"，注入应优先于流水事件。

        v0.5：重叠口径 = query 核心词（词性提取实词）∩ 卡词；门槛 ≥1。
        与事件卡不同：事实卡是"关于用户的事实"，弱相关即可（"我的偏好"→
        偏好卡），不需要稀有词/多词门槛。
        """
        try:
            cards = self.search.store.all_cards()
            chain_titles = self.search.store.chain_title_map()
        except Exception:
            return []
        q_core = q_core if q_core is not None else _query_core_words(query)
        if not q_core:
            return []
        scored: list[tuple[int, SearchResult]] = []
        for c in cards:
            if getattr(c, "kind", "") not in ("lesson_permanent", "lesson_pending"):
                continue
            if getattr(c, "status", "active") not in ("active", ""):
                continue
            if getattr(c, "invalid_at", None):
                continue
            toks = _card_tokens(self.search.store, c.id)
            overlap = len(set(q_core) & toks)
            if overlap <= 0:
                continue
            scored.append(
                (
                    overlap,
                    SearchResult(
                        card_id=c.id,
                        score=float(overlap),
                        source_path=c.source_path,
                        title=c.title,
                        snippet=(c.content or "")[:120],
                        chain_id=c.parent_id or "",
                        chain_title=chain_titles.get(c.parent_id or "", ""),
                        created_at=c.created_at or "",
                    ),
                )
            )
        scored.sort(key=lambda item: item[0], reverse=True)
        return [r for _, r in scored[:limit]]

    @staticmethod
    def format_result(r: SearchResult) -> str:
        """溯源格式化：[长期记忆 · 来源 xxx · 链: yyy · 2026-08-10] 标题：snippet

        B4（ADR-0021 树导航下钻）：命中枝且带果摘要时，优先展示「果」（枝的结论），
        叶卡仍带溯源；无果摘要走原格式（不回归）。
        """
        parts = [f"来源 {r.source_path}"]
        if r.chain_title:
            parts.append(f"链: {r.chain_title}")
        if r.created_at:
            parts.append(r.created_at[:10])
        meta = " · ".join(parts)
        head = f"[长期记忆 · {meta}]"
        if r.branch_summary:
            return f"{head} 果: {r.branch_summary}（{r.title}）"
        return f"{head} {r.title}：{r.snippet}"

    def record_usage(
        self,
        search_results: list[SearchResult],
        reply_text: str,
        *,
        min_strong: int = 2,
    ) -> dict[str, bool]:
        """审计闭环生产方（P1a）：判定注入是否被模型回复真正利用，落 decision_log。

        旧实现：detect_inject_usage 存在但无人调用，inject_used 日志永远为空，
        audit_summary / govern_injection 的注入利用率指标空转（闭环断裂）。
        本方法在注入 → 回复完成后调用：每个命中卡记一条
        "{card_id}: used|unused"（audit_summary / card_usage 的解析格式）。

        Args:
            search_results: 本次实际注入的检索命中（inject_for_tier 返回值）。
            reply_text: 注入后模型的回复文本（判定利用信号）。
            min_strong: 强词元命中阈值（透传 detect_inject_usage）。

        Returns:
            {card_id: used?}（调用方可直接喂 apply_usage_feedback 回流治理）。
        """
        usage = detect_inject_usage(search_results, reply_text, min_strong=min_strong)
        for cid, used in usage.items():
            with contextlib.suppress(Exception):
                self.search.store.log_decision(
                    "inject_used", f"{cid}: {'used' if used else 'unused'}"
                )
        return usage

    def build_static_snapshot(
        self,
        *,
        profile: object | None = None,
        budget_chars: int = 2048,
        min_confidence: float = 0.7,
        query: str = "",
    ) -> tuple[str, str]:
        """常驻基线快照（低频推式注入层）：approved 画像 + 高置信永久经验。

        设计（ADR-0020）：画像 + lesson_permanent（高置信、全局/项目关键事实）
        每次请求常驻注入；用 digest 检测变更，未变则调用方复用旧文本（KV-cache 友好）。

        v0.3 抢救修复：增加**相关性闸门**——画像/经验仅在 query 命中相关语义时注入，
        避免"无相关内容也注入"引入噪音（8 场景审计：寒暄/无关主题/无匹配不再无条件注入）。

        Args:
            profile: Profile 对象（approved）或 None（未接线画像时跳过画像段）。
            budget_chars: 总量预算（超限按 画像摘要 > 关键事实 省略）。
            min_confidence: 永久经验的最低置信（低于不入基线）。
            query: 当前轮用户消息（用于相关性闸门；空串 = 不注入画像/经验）。

        Returns:
            (text, digest)：text 为注入文本（可为空串），digest 为快照指纹
            （画像 updated_at + 卡 id/updated_at 排序拼接的 sha1 前缀）。
        """
        import hashlib

        # 相关性闸门：query 需含"身份/偏好/经验"类语义词，否则跳过整段快照
        # （防止画像/经验在无关主题、寒暄、无匹配时无条件注入）
        _RELEVANCE_HINTS = (
            "我", "我的", "我们", "偏好", "喜欢", "习惯", "身份", "工作",
            "项目", "风格", "经验", "教训", "目标", "计划", "决定",
            "remember", "prefer", "habit", "experience", "lesson",
            "project", "goal", "plan", "identity", "profile",
        )
        q = (query or "").strip()
        relevant = bool(q) and any(h in q for h in _RELEVANCE_HINTS)

        lines: list[str] = []
        digest_parts: list[str] = []

        # ① 画像段（已审批）：仅在 query 相关时注入
        if relevant and profile is not None:
            summary = getattr(profile, "summary", "") or ""
            if summary.strip():
                block = summary.strip()
                mbti = getattr(profile, "mbti", "") or ""
                dims = getattr(profile, "dimensions", ()) or ()
                if mbti or dims:
                    axes = " ".join(f"{d.key}={d.value:.2f}" for d in dims)
                    block += f"\n人格多边形：{mbti or '?'}（{axes}）"
                lines.append(f"[画像] {block}")
                digest_parts.append(f"profile:{getattr(profile, 'updated_at', '')}")

        # ② 高置信永久经验（lesson_permanent，active，未失效，置信达标，且与 query 相关）
        budget_left = budget_chars
        used = 0
        for line in lines:
            used += len(line)
        with contextlib.suppress(Exception):
            cards = self.search.store.all_cards()
            for card in sorted(
                cards,
                key=lambda c: (c.updated_at or c.created_at or ""),
                reverse=True,
            ):
                if getattr(card, "kind", "") != "lesson_permanent":
                    continue
                if getattr(card, "status", "active") not in ("active", ""):
                    continue
                if getattr(card, "invalid_at", None):
                    continue
                conf = getattr(card, "confidence", 0.0) or 0.0
                if conf < min_confidence:
                    continue
                text = f"{card.title}：{card.content}"
                # 相关性闸门：经验内容需与 query 有词面重叠才注入（防无关经验噪音）
                if not relevant or not any(t in q for t in (card.title or "") + (card.content or "")):
                    continue
                if used + len(text) > budget_left:
                    continue
                lines.append(f"[经验] {text}")
                used += len(text)
                digest_parts.append(f"{card.id}:{card.updated_at or card.created_at or ''}")

        if not lines:
            return "", ""
        digest = hashlib.sha1("|".join(digest_parts).encode()).hexdigest()[:12]
        return "\n".join(lines), digest
