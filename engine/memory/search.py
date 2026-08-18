"""检索（DESIGN §4.2：BM25 + 多路 RRF + 溯源；A7 归档 / A8 反馈 / B2 遗忘 / B4 树导航）。

B4（ADR-0021）：
- 枝级路标：query 先对齐「枝的身份」（链标题×2 + 果摘要）→ 命中枝下叶加权（第一轮导航，先找枝再下钻）
- 树导航下钻：命中枝优先展示果摘要；同一枝最多 max_per_chain 张叶（防一枝霸屏）
- 实体限定多跳：共享实体只在同枝内扩展（不跨树）；无归属散叶保留实体跳转
- 关键事实豁免：高置信/安全类碎片卡不参与时间衰减（防重要记忆被 top-k 挤出）
- 命中历史加固：被反复捞起的碎片卡衰减变慢（遗忘曲线 + 强化次数）
- 相对时间：query 含「昨天/上周/最近N天」等 → 自动注入 since/until（零 LLM）
"""

from __future__ import annotations

import datetime as _dt
import math
import re

from memory.models import MemoryCard, SearchResult
from memory.store import MemoryStore, now_iso
from memory.tokenize import tokenize, tokenize_words

_DOWN_PATTERNS = (
    "不对", "错了", "不是", "重新", "其实", "更正", "纠正",
    "瞎说", "乱说", "记错", "搞错", "别乱",
)
_UP_PATTERNS = ("有用", "记住了", "没错", "很好", "靠谱", "说得对", "记得对", "对对")

# B4.4：安全/关键事实豁免关键词（命中即不参与时间衰减）
_EXEMPT_KEYWORDS = (
    "过敏", "账号", "密码", "证件", "身份证", "紧急联系", "药物", "医嘱",
    "重要截止", "截止日期", "手术", "住院",
)

# B4.6：相对时间词 → 时间窗口类型（长词在前，避免「最近3天」被「最近」误配）
_RELATIVE_TIME_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(?:最近|近)(\d{1,3})\s*个?月"), "nmonths"),
    (re.compile(r"(?:最近|近)(\d{1,3})\s*周"), "nweeks"),
    (re.compile(r"(?:最近|近)(\d{1,3})\s*天"), "ndays"),
    (re.compile(r"今天|今日"), "today"),
    (re.compile(r"昨天"), "yesterday"),
    (re.compile(r"前天"), "day_before_yesterday"),
    (re.compile(r"上上周"), "two_weeks_ago"),
    (re.compile(r"上周|上星期"), "last_week"),
    (re.compile(r"本周|这周|这星期"), "this_week"),
    (re.compile(r"上个月|上月"), "last_month"),
    (re.compile(r"这个月|本月"), "this_month"),
    (re.compile(r"去年"), "last_year"),
    (re.compile(r"今年"), "this_year"),
)


def detect_feedback(user_text: str) -> str | None:
    """识别检索侧反馈信号（A8）：纠正 → down；确认有用 → up。"""
    for pattern in _DOWN_PATTERNS:
        if pattern in user_text:
            return "down"
    for pattern in _UP_PATTERNS:
        if pattern in user_text:
            return "up"
    return None


def _month_range(year: int, month: int) -> tuple[_dt.date, _dt.date]:
    """某年某月的 (首日, 末日)。"""
    first = _dt.date(year, month, 1)
    nxt = _dt.date(year + 1, 1, 1) if month == 12 else _dt.date(year, month + 1, 1)
    return first, nxt - _dt.timedelta(days=1)


def _add_months(d: _dt.date, months: int) -> _dt.date:
    """日期加减自然月（月末对齐：1/31 减 1 月 → 1/31 或 1/28）。"""
    idx = d.month - 1 + months
    year = d.year + idx // 12
    month = idx % 12 + 1
    day = min(d.day, _month_range(year, month)[1].day)
    return d.replace(year=year, month=month, day=day)


def parse_relative_time(query: str) -> tuple[str, str] | None:
    """B4.6：从 query 解析相对时间词 → (since, until) ISO 日期；无命中返回 None。

    对齐 H-Mem「时间提示推断」的轻量规则版：零 LLM、零延迟，注入预算友好。
    """
    q = query.strip()
    if not q:
        return None
    today = _dt.date.today()
    iso = _dt.date.isoformat
    for pattern, kind in _RELATIVE_TIME_RULES:
        m = pattern.search(q)
        if m is None:
            continue
        if kind == "ndays":
            n = max(1, int(m.group(1)))
            return iso(today - _dt.timedelta(days=n - 1)), iso(today)
        if kind == "nweeks":
            n = max(1, int(m.group(1)))
            return iso(today - _dt.timedelta(weeks=n)), iso(today)
        if kind == "nmonths":
            n = max(1, int(m.group(1)))
            return iso(_add_months(today, -n)), iso(today)
        if kind == "today":
            return iso(today), iso(today)
        if kind == "yesterday":
            y = today - _dt.timedelta(days=1)
            return iso(y), iso(y)
        if kind == "day_before_yesterday":
            y = today - _dt.timedelta(days=2)
            return iso(y), iso(y)
        if kind == "two_weeks_ago":
            monday = today - _dt.timedelta(days=today.weekday() + 14)
            return iso(monday), iso(monday + _dt.timedelta(days=6))
        if kind == "last_week":
            monday = today - _dt.timedelta(days=today.weekday() + 7)
            return iso(monday), iso(monday + _dt.timedelta(days=6))
        if kind == "this_week":
            monday = today - _dt.timedelta(days=today.weekday())
            return iso(monday), iso(today)
        if kind == "last_month":
            prev_last = _month_range(today.year, today.month)[0] - _dt.timedelta(days=1)
            prev_first = prev_last.replace(day=1)
            return iso(prev_first), iso(prev_last)
        if kind == "this_month":
            return iso(today.replace(day=1)), iso(today)
        if kind == "last_year":
            return iso(_dt.date(today.year - 1, 1, 1)), iso(_dt.date(today.year - 1, 12, 31))
        if kind == "this_year":
            return iso(_dt.date(today.year, 1, 1)), iso(today)
    return None


def _bm25(
    query_tokens: list[str],
    doc_tokens: list[str],
    df: dict[str, int],
    n_docs: int,
    avgdl: float,
    *,
    k1: float = 1.5,
    b: float = 0.75,
) -> float:
    if not doc_tokens or not query_tokens:
        return 0.0
    dl = len(doc_tokens)
    tf: dict[str, int] = {}
    for token in doc_tokens:
        tf[token] = tf.get(token, 0) + 1
    score = 0.0
    for qt in set(query_tokens):
        if qt not in tf:
            continue
        idf = math.log(1 + (n_docs - df.get(qt, 0) + 0.5) / (df.get(qt, 0) + 0.5))
        score += idf * (tf[qt] * (k1 + 1)) / (tf[qt] + k1 * (1 - b + b * dl / avgdl))
    return score


class MemorySearch:
    """检索入口：search() 会同步更新命中/未命中统计（A7）。"""

    def __init__(
        self,
        store: MemoryStore,
        *,
        archive_after_misses: int = 50,
        feedback_max_weight: float = 3.0,
        feedback_floor: float = 0.1,
        recency_half_life_days: float = 14.0,
        reinforce_eta: float = 2.0,  # B4.5：命中历史加固强度
        exempt_keywords: tuple[str, ...] | None = None,  # B4.4：关键事实豁免词表
        max_branches: int = 3,  # B4.1：枝级路标最多命中枝数
        max_per_chain: int = 2,  # B4.2：同一枝最多保留叶数（防一枝霸屏）
        branch_title_weight: float = 2.0,  # B4.1：枝标题命中权重（×2）
    ) -> None:
        self.store = store
        self.archive_after_misses = archive_after_misses
        self.feedback_max_weight = feedback_max_weight
        self.feedback_floor = feedback_floor
        self.recency_half_life_days = recency_half_life_days
        self.reinforce_eta = reinforce_eta
        self.exempt_keywords = tuple(exempt_keywords) if exempt_keywords else _EXEMPT_KEYWORDS
        self.max_branches = max_branches
        self.max_per_chain = max_per_chain
        self.branch_title_weight = branch_title_weight

    def search(
        self,
        query: str,
        top_k: int = 5,
        *,
        since: str | None = None,
        until: str | None = None,
        timeline: bool = False,
        expand: bool = True,
        project_id: str | None = None,
        project_by_run: dict[str, str] | None = None,
        track_hits: bool = True,
    ) -> list[SearchResult]:
        """检索（B4：枝级路标 + 树导航下钻 + 限定多跳；A7 命中统计照旧）。

        - since/until：显式按 created_at 日期硬过滤；未给定时，B4.6 相对时间词自动软加权（不排除）
        - timeline：时间线模式，按 created_at 升序返回（query 非空时先按相关度过滤）
        - expand：多跳扩展（沿链兄弟 + 同枝/散叶实体）；枝级路标始终生效（第一轮导航）
        - project_id + project_by_run：项目加权（同项目 ×2 / 跨项目 ×0.3 / 无归属 ×1）
        - track_hits（v0.5 根本修复）：True = 命中/未命中统计 + miss 归档记账（UI 检索/工具
          用）；False = **纯只读**（注入用——注入查询是低频无关 query，若记账会把无关卡
          miss 累积到 50 后批量归档，实测 66 张卡被测试 query 误归档）
        - 链卡是结构不是事实，不进基础检索；但作为「枝级路标」参与定位与结果标注
        """
        query_tokens = tokenize(query)
        # B4.6：相对时间提示 → 自动时序窗口（显式 since/until 优先，不覆盖）
        # 对齐 H-Mem 时序相关 T(m,Q)：时间窗口是软加权列，不做硬过滤（防误伤无日期/混合查询）
        auto_since: str | None = None
        auto_until: str | None = None
        if since is None and until is None and query.strip():
            parsed = parse_relative_time(query)
            if parsed is not None:
                auto_since, auto_until = parsed
        card_pairs = self.store.active_cards_with_tokens()
        # 链卡（枝）单列：作为枝级路标参与定位；不进基础检索（结构不是事实）
        chain_pairs = [(c, toks) for c, toks in card_pairs if c.kind == "chain"]
        card_pairs = [
            (card, toks)
            for card, toks in card_pairs
            if card.kind != "chain" and self._in_window(card, since, until)
        ]
        if not card_pairs:
            return []
        cards = [card for card, _ in card_pairs]
        doc_tokens = [toks or tokenize(card.content) for card, toks in card_pairs]
        n = len(cards)

        # BM25 分数：FTS5 全文索引（jieba 预处理 + bm25() 内置排名），按 cards 顺序对齐
        bm25 = self._fts_scores(cards, query_tokens)
        phrase = [1.0 if query.strip() and query.strip() in card.content else 0.0 for card in cards]
        # 项目加权：同项目记忆优先、跨项目降权（噪音过滤；无归属卡不惩罚）
        project_factors: list[float] | None = None
        if project_id is not None and project_by_run:
            project_factors = []
            for card in cards:
                proj = project_by_run.get(card.run_id or "")
                if proj is None:
                    project_factors.append(1.0)
                else:
                    project_factors.append(2.0 if proj == project_id else 0.3)
        # A8 反馈权重：基线归零，仅升权卡获得 RRF 加成；权重只影响排序
        feedback = [
            max(0.0, card.weight * (1 + 0.1 * math.log1p(card.hit_count)) - 1.0)
            for card in cards
        ]
        chain_titles = self.store.chain_title_map()

        # B4.1 枝级路标：query 对齐活跃枝的「身份」（标题×2 + 果摘要）→ 枝下叶加权。
        id_pos = {c.id: i for i, c in enumerate(cards)}
        # 只认枝标题/果摘要，不认子卡标题——叶子各自走 BM25 直打，避免「提到厨房就把
        # 搬家/做饭两枝都当路标」的模糊命中（事件身份 = 枝名，先找枝再下钻）。
        chain_by_id: dict[str, MemoryCard] = {
            c.id: c for c, _ in chain_pairs if c.status == "active"
        }
        branch_col = [0.0] * n
        if chain_by_id and query_tokens:
            ranked_chains: list[tuple[str, float]] = []
            qset = set(query_tokens)
            for cid, chain in chain_by_id.items():
                title_hits = len(set(tokenize(chain.title)) & qset)
                summary_hits = len(set(tokenize(chain.summary)) & qset)
                score = self.branch_title_weight * title_hits + summary_hits
                if score > 0:
                    ranked_chains.append((cid, score))
            ranked_chains.sort(key=lambda item: item[1], reverse=True)
            hit_chains = {cid for cid, _ in ranked_chains[: self.max_branches]}
            for i, card in enumerate(cards):
                if card.parent_id in hit_chains:
                    branch_col[i] = 1.0

        # B4.6：相对时间软加权列（命中自动窗口的卡 +1，其余 0；无时间词则全 0）
        if auto_since is not None or auto_until is not None:
            time_col = [
                1.0 if self._in_window(card, auto_since, auto_until) else 0.0 for card in cards
            ]
        else:
            time_col = [0.0] * n

        if timeline:
            # 时序模式：query 非空 → 相关度过滤后按时间升序；空查询 = 记忆时间线
            if query.strip():
                relevant = [i for i in range(n) if bm25[i] > 0 or phrase[i] > 0]
            else:
                relevant = list(range(n))
            ranked = sorted(relevant, key=lambda i: (cards[i].created_at or "", i))[:top_k]
            merged = [0.0] * n
        else:
            rrf = self._rrf_merge([bm25, phrase, feedback, branch_col, time_col])
            if expand and query.strip():
                # —— 多跳扩展：首跳命中 → 沿链兄弟 + 同枝/散叶实体 ——
                base_order = sorted(range(n), key=lambda i: rrf[i], reverse=True)
                hits = [i for i in base_order if rrf[i] > 0][: max(1, top_k)]
                chain_col = [0.0] * n
                entity_col = [0.0] * n
                entity_index: dict[str, list[int]] = {}
                for idx, card in enumerate(cards):
                    for ent in card.entities:
                        entity_index.setdefault(ent, []).append(idx)
                for hit_idx in hits:
                    hit = cards[hit_idx]
                    for sib in self.store.siblings(hit.id):  # 沿链：同一事件链的兄弟卡
                        pos = id_pos.get(sib.id)
                        if pos is not None:
                            chain_col[pos] = max(chain_col[pos], 1.0)
                    # B4.3 实体限定多跳：共享实体只在同枝内扩展（不跨树）；
                    # 无归属散叶（双方 parent_id 都空）保留实体跳转（V2 能力不回归）
                    for ent in hit.entities:
                        for pos in entity_index.get(ent, []):
                            if pos == hit_idx:
                                continue
                            other = cards[pos]
                            if other.parent_id == hit.parent_id:
                                entity_col[pos] = max(entity_col[pos], 1.0)
                rrf = self._rrf_merge([bm25, phrase, feedback, branch_col, chain_col, entity_col, time_col])
            merged = rrf
            # P2：project_factors 只应用一次（旧实现非 expand 路径乘两次——
            # 先乘 L290 再乘此处；expand 路径 L290 的乘法被重合并覆盖成无效代码）
            if project_factors is not None:
                merged = [v * f for v, f in zip(merged, project_factors, strict=False)]
            # B2/B4：碎片时间衰减（未归链零散事件卡；B4.4 豁免 + B4.5 命中历史加固）
            if self.recency_half_life_days > 0:
                merged = [v * self._recency_factor(cards[i]) for i, v in enumerate(merged)]
            ranked = sorted(range(n), key=lambda i: merged[i], reverse=True)

        # B4.2 树导航下钻：同一枝最多 max_per_chain 张叶（防一枝霸屏）；首条带果摘要
        ranked = self._apply_per_chain_cap(ranked, cards)
        emitted_branch: set[str] = set()
        results: list[SearchResult] = []
        for i in ranked[:top_k]:
            card = cards[i]
            chain_id = card.parent_id
            branch_summary = ""
            if chain_id and chain_id not in emitted_branch:
                chain = chain_by_id.get(chain_id)
                if chain is not None and chain.summary.strip():
                    branch_summary = chain.summary.strip()
                emitted_branch.add(chain_id)
            results.append(
                SearchResult(
                    card_id=card.id,
                    score=merged[i] if not timeline else float(n - i),
                    source_path=card.source_path,
                    title=card.title,
                    snippet=card.content[:120],
                    chain_id=chain_id,
                    chain_title=chain_titles.get(chain_id, ""),
                    branch_summary=branch_summary,
                    created_at=card.created_at,
                )
            )

        if track_hits:
            hit_ids = {r.card_id for r in results}
            now = now_iso()
            hit_list = [c.id for c in cards if c.id in hit_ids]
            archive_list = [
                c.id
                for c in cards
                if c.id not in hit_ids and c.miss_count + 1 >= self.archive_after_misses
            ]
            miss_list = [
                c.id
                for c in cards
                if c.id not in hit_ids and c.miss_count + 1 < self.archive_after_misses
            ]
            self.store.update_hits(hit_list, now)
            self.store.update_misses(miss_list)
            self.store.archive_cards(archive_list)
        return results

    def _fts_scores(self, cards: list[MemoryCard], query_tokens: list[str]) -> list[float]:
        """FTS5 BM25 分数，按 cards 顺序对齐（未命中的卡为 0）。

        FTS5 bm25() 返回负值（越小越相关），取负号转正；card_id 不在结果中的卡 0 分。
        查询用词级分词（tokenize_words）：tokenize() 的字符 bigram（如"卡内"）在
        FTS5 倒排里是噪音，会造成错误匹配。
        """
        if not query_tokens or not cards:
            return [0.0] * len(cards)
        words = [t for t in tokenize_words(" ".join(query_tokens)) if t]
        if not words:
            return [0.0] * len(cards)
        match_q = " OR ".join(f'"{t}"' for t in words)
        rows = self.store._exec(
            "SELECT card_id, bm25(card_fts) AS score FROM card_fts "
            "WHERE card_fts MATCH ? ORDER BY score",
            [match_q],
        ).fetchall()
        score_by_id = {str(r[0]): -float(r[1]) for r in rows}
        return [max(0.0, score_by_id.get(card.id, 0.0)) for card in cards]

    def _apply_per_chain_cap(self, ranked: list[int], cards: list[MemoryCard]) -> list[int]:
        """B4.2：同一枝最多保留 max_per_chain 张叶（散叶不限），其余按序补位。"""
        if self.max_per_chain <= 0:
            return ranked
        per_chain: dict[str, int] = {}
        out: list[int] = []
        for idx in ranked:
            chain = cards[idx].parent_id or ""
            if chain and per_chain.get(chain, 0) >= self.max_per_chain:
                continue
            per_chain[chain] = per_chain.get(chain, 0) + 1
            out.append(idx)
        return out

    def _recency_factor(self, card) -> float:
        """B2/B4 碎片时间衰减：未归链（parent_id 空）的零散事件卡按遗忘曲线降权。

        - B4.4 关键事实豁免：高置信（>=0.9）或命中安全关键词 → 不衰减（防重要记忆被挤出）
        - B4.5 命中历史加固：用最近命中时间（无命中史用创建时间）+ 命中次数扩展半衰期
          （反复捞起 = 有用 → 慢衰减，对应强化半衰期）
        - 树上卡不衰减（事件生命周期由完结萎缩管理）；枯萎卡已由 active_cards_with_tokens 排除
        """
        if self.recency_half_life_days <= 0 or card.parent_id or card.kind != "event":
            return 1.0
        if (
            card.kind == "lesson_permanent"
            or card.evidence in ("directive", "explicit", "approved")
            or card.corroborations >= 1
            or card.confidence >= 0.95
            or any(kw in card.title or kw in card.content for kw in self.exempt_keywords)
        ):
            return 1.0  # B4.4 关键事实豁免（§9.7 改键：不再信模型裸自评 0.9）
        anchor = (card.last_hit_at or card.created_at or "")[:10]
        try:
            days = max(0, (_dt.date.today() - _dt.date.fromisoformat(anchor)).days)
        except (ValueError, TypeError):
            return 1.0
        tau = self.recency_half_life_days * (1 + self.reinforce_eta * math.log1p(card.hit_count))
        return math.exp(-days / tau)

    @staticmethod
    def _in_window(card, since: str | None, until: str | None) -> bool:
        """按 created_at 前 10 位（YYYY-MM-DD）做闭区间日期过滤。"""
        date = (card.created_at or "")[:10]
        if since and date < since[:10]:
            return False
        return not (until and date > until[:10])

    @staticmethod
    def _rrf_merge(scores: list[list[float]], k: int = 60) -> list[float]:
        """RRF 合并：每列仅排分>0 的文档，避免全 0 列按原始顺序平序产生噪声。"""
        n = len(scores[0])
        merged = [0.0] * n
        for column in scores:
            ranked = sorted(
                (i for i, score in enumerate(column) if score > 0),
                key=lambda i: column[i],
                reverse=True,
            )
            for pos, idx in enumerate(ranked):
                merged[idx] += 1.0 / (k + pos + 1)
        return merged

    def apply_feedback(self, card_ids: list[str], direction: str) -> None:
        """A8：纠正 → 降权（有下限）；确认有用 → 升权（有上限）。权重只影响排序。"""
        for card_id in card_ids:
            card = self.store.read_card(card_id)
            if card is None:
                continue
            if direction == "down":
                weight = max(self.feedback_floor, card.weight * 0.5)
                # §9.7 联动校准：用户纠正 = 最高真值 → 证据降级（取消"永不衰减"资格）
                self.store.save_stats(
                    card_id, weight=weight,
                    evidence="uncertain",
                    confidence=min(card.confidence, 0.4),
                )
            elif direction == "up":
                weight = min(self.feedback_max_weight, card.weight * 1.25)
                # §9.7 联动校准：用户确认 → 佐证 +1（豁免/校准依据）
                self.store.save_stats(
                    card_id, weight=weight,
                    corroborations=card.corroborations + 1,
                )
            else:
                continue
