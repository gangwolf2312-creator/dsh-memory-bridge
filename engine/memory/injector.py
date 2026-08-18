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

__all__ = ["MemoryInjector"]

_LIMITS = {IntentTier.L0: 0, IntentTier.L1: 1, IntentTier.L2: 3}


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
        results = self.search.search(
            query, top_k=limit, project_id=project_id, project_by_run=project_by_run
        )
        elapsed_ms = (time.perf_counter() - started) * 1000
        if elapsed_ms > self.timeout_ms:
            return []  # A6：超时 → 空注入（宁缺勿滥）
        # §9.7 实证：记录"注入了什么"（inject_hit），供 detect_inject_usage 归因
        with contextlib.suppress(Exception):
            self.search.store.log_decision(
                "inject_hit",
                f"query={query[:60]!r} cards={[r.card_id for r in results]}",
            )
        return results

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
