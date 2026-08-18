"""拉式溯源记忆注入（ADR-0013 D1/D3/D4）：分档检索 + 超时空注入 + 溯源格式化。

- 分档：L0 零注入 / L1 ≤1 条 / L2 ≤3 条（对齐 V2 口径 + memory_max_items=3）
- 超时：检索 50ms 超时 → 空注入（宁缺勿滥，不拖慢 TTFT）
- 溯源：每条命中带 [长期记忆·来源/链/日期] 标记，供 assembler M 桶渲染
- 本模块只做"检索 + 格式化"，不依赖 context（注入组装在 kernel 层 provider）
"""

from __future__ import annotations

import contextlib
import time

from core.types import IntentTier
from memory.audit import detect_inject_usage
from memory.models import SearchResult
from memory.search import MemorySearch
from memory.store import now_iso
from memory.tokenize import tokenize_words

__all__ = ["MemoryInjector"]

_LIMITS = {IntentTier.L0: 0, IntentTier.L1: 1, IntentTier.L2: 3}

# v0.4 抢救修复（注入噪音）：通用/修饰/虚词——query 与卡仅这些词面重叠不算相关。
# 实测噪音案例：query"整体UI，特别是浏览器UI在深色模式下居然是白色"仅因"整体
# 平移"命中图谱卡（重叠词元 {体,是,整体,居,整} 全为通用词/单字）而注入无关卡。
# 词表克制收录高频虚词/修饰词；单字由 len>1 过滤，不进表。
_INJECT_STOPWORDS = frozenset({
    "整体", "全部", "所有", "任何", "一切", "这个", "那个", "这些", "那些",
    "这种", "那种", "这样", "那样", "一些", "一个", "一种", "一下", "有点",
    "怎么", "什么", "为什么", "如何", "怎样", "哪个", "哪些", "多少", "几",
    "特别", "非常", "比较", "很", "挺", "都", "也", "就", "还", "再", "又",
    "和", "与", "或", "的", "了", "在", "是", "有", "没", "不", "把", "被",
    "让", "使", "用", "对", "从", "到", "向", "为", "给", "等", "以及",
    "因为", "所以", "但是", "然而", "如果", "那么", "然后", "居然", "到底",
    "究竟", "起来", "出来", "过来", "下去", "应该", "可以", "可能", "需要",
    "觉得", "认为", "问题", "情况", "方式", "方法", "东西", "时候", "地方",
    "部分", "方面", "关于", "针对", "通过", "进行", "作为", "由于", "根据",
    "按照", "例如", "比如",
})


def _inject_overlap(query: str, text: str) -> int:
    """注入相关度的实质词面重叠数：纯 jieba 词级，滤单字、通用词与短英文泛缩写。

    返回重叠词数；0 = 无实质词面相关 → 不注入。v0.4 抢救修复：弱词面重叠
    （仅通用词/单字命中）不再构成注入依据（实测"整体"误注入图谱卡；
    "ui" 泛缩写误注入"UI 总览"卡）。规则：
    - 中文词 ≥2 字；英文词 ≥4 字符（ui/api/id 等短缩写是泛词，不计）
    - 停用词表（_INJECT_STOPWORDS）过滤高频虚词/修饰词
    """
    def _words(text: str) -> set[str]:
        return {
            w for w in tokenize_words(text or "")
            if len(w) > 1
            and w not in _INJECT_STOPWORDS
            and not (w.isascii() and len(w) < 4)
        }
    return len(_words(query) & _words(text))


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
        pool_k = max(limit, limit * 3)
        results = self.search.search(
            query, top_k=pool_k, expand=False,
            project_id=project_id, project_by_run=project_by_run,
        )
        elapsed_ms = (time.perf_counter() - started) * 1000
        if elapsed_ms > self.timeout_ms:
            return []  # A6：超时 → 空注入（宁缺勿滥）
        # v0.4 抢救修复（注入噪音）：实质词面重叠门槛——search 的 BM25 词面匹配
        # 会把仅"通用词/单字"重叠的无关卡带进来（实测"整体UI…深色模式白色"因
        # "整体平移"命中图谱卡）。逐张取全文做词级重叠校验，无实质重叠 → 不注入。
        gated: list[SearchResult] = []
        for r in results:
            card = self.search.store.read_card(r.card_id)
            if card is None:
                continue
            if _inject_overlap(query, f"{card.title} {card.content}") <= 0:
                continue
            gated.append(r)
        results = gated
        # 抢救修复（v0.3，8 场景审计场景 1/3）：事实卡优先于事件流水——
        # lesson_permanent/pending 与偏好卡是"该记住的结论"，event 是"发生过
        # 的事"。search 多列 RRF 会把零使用史的事实卡挤出池子（实测 pref 卡
        # BM25 第 1 仍不在 top-9），故先做事实卡补充检索（词面重叠打分），
        # 再与检索池合并去重：事实卡在前、事件补位，截断到 limit。
        facts = self._fact_lookup(query, limit)
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

    def _fact_lookup(self, query: str, limit: int) -> list[SearchResult]:
        """事实卡补充检索：active 的 lesson_permanent/pending 卡直查 + 实质词面重叠打分。

        抢救修复（v0.3）：search 的多列 RRF（反馈/短语/枝路标）会把零使用史
        的事实卡挤出 top-N（实测：偏好卡 BM25 第 1 却不在 top-9，注入被事件
        流水占满）。这里对 active 事实卡做确定性词面重叠打分，重叠 >0 即参与
        注入排序——事实卡是"该记住的结论"，注入应优先于流水事件。

        v0.4：重叠口径收紧为**实质词级**（_inject_overlap：纯 jieba 词、滤单字
        与通用词）——与 search 结果的门槛同口径，防止单字/通用词把无关事实卡
        拉进注入（如"整体"命中含"整体平移"的卡）。
        """
        try:
            cards = self.search.store.all_cards()
            chain_titles = self.search.store.chain_title_map()
        except Exception:
            return []
        scored: list[tuple[int, SearchResult]] = []
        for c in cards:
            if getattr(c, "kind", "") not in ("lesson_permanent", "lesson_pending"):
                continue
            if getattr(c, "status", "active") not in ("active", ""):
                continue
            if getattr(c, "invalid_at", None):
                continue
            overlap = _inject_overlap(query, f"{c.title} {c.content}")
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
