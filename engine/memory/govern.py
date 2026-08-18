"""注入治理层（§9.7 闭环补全）：健康指标 → 治理动作。

已有：detect_inject_usage（去噪判定）+ audit_summary（健康指标）。
缺失：指标不健康时系统自动做什么。本模块补齐两级治理：

- 卡级（apply_usage_feedback）：审计结果回流 —— used → update_hits（命中滚动）；
  unused → update_misses；连续未命中达阈值 → 降权淡出（不归档、不降证据：
  "没被利用" ≠ "记忆错误"，只是当前上下文用不上）
- 全局（govern_injection）：inject_used_rate 低于阈值 → 建议收缩注入量（L2 条数
  3→2→1）+ 批量降权低使用率卡；动作写 decision_log（govern_action）可审计

纯内部管道，不依赖 DSH；零 LLM。
"""

from __future__ import annotations

import contextlib
import datetime as _dt
from dataclasses import dataclass

from memory.audit import audit_summary
from memory.store import MemoryStore

__all__ = [
    "GovernanceReport",
    "apply_usage_feedback",
    "card_usage",
    "govern_injection",
]

_WEIGHT_FLOOR = 0.1  # 审计降权下限（淡出排序，不归档）


@dataclass(frozen=True, slots=True)
class GovernanceReport:
    """一次治理决策的快照（可读动作 + 建议注入量）。"""

    window_days: int
    inject_used_rate: float
    judged_cards: int  # 判定次数足够的卡数
    degraded_cards: tuple[tuple[str, float], ...]  # (card_id, new_weight)
    suggested_limits: tuple[int, int]  # (l1_limit, l2_limit) 建议值
    actions: tuple[str, ...]  # 可读摘要（写 decision_log）


def _now_iso() -> str:
    return _dt.datetime.now().astimezone().isoformat(timespec="seconds")


def _index_cards(store: MemoryStore) -> dict[str, object]:
    """索引视图（hit/miss/weight 以 sqlite 为最新；明文只回写语义字段）。"""
    return {c.id: c for c in store.all_cards()}

    return _dt.datetime.now().astimezone().isoformat(timespec="seconds")


def apply_usage_feedback(
    store: MemoryStore,
    usage: dict[str, bool],
    *,
    miss_floor: int = 3,
    now: str | None = None,
) -> list[str]:
    """审计结果回流：used → 命中滚动；unused → miss 累计，达阈值降权淡出。

    Args:
        usage: detect_inject_usage 的输出 {card_id: used?}
        miss_floor: 连续未命中多少次开始降权（默认 3，防单次偶然）
        now: 命中时间戳（默认当前）

    Returns:
        降权卡 id 列表。
    """
    hit_ids = [cid for cid, used in usage.items() if used]
    miss_ids = [cid for cid, used in usage.items() if not used]
    if hit_ids:
        store.update_hits(hit_ids, now or _now_iso())
    if miss_ids:
        store.update_misses(miss_ids)
    index = _index_cards(store)
    degraded: list[str] = []
    for cid in miss_ids:
        card = index.get(cid)
        if card is None or card.status == "archived":
            continue
        if card.miss_count >= miss_floor:
            new_weight = max(_WEIGHT_FLOOR, card.weight * 0.5)
            store.save_stats(cid, weight=new_weight)
            degraded.append(cid)
    return degraded


def card_usage(store: MemoryStore, *, days: int = 14) -> dict[str, dict[str, int]]:
    """从 decision_log 聚合每张注入卡的 used/unused 判定次数。"""
    cutoff = (
        _dt.datetime.now().astimezone() - _dt.timedelta(days=days)
    ).isoformat(timespec="seconds")
    agg: dict[str, dict[str, int]] = {}
    for entry in store.decision_log("inject_used"):
        if entry["ts"] < cutoff:
            continue
        detail = entry["detail"]
        if ": unused" in detail:
            cid = detail.split(": ", 1)[0]
            used = False
        elif ": used" in detail:
            cid = detail.split(": ", 1)[0]
            used = True
        else:
            continue
        stat = agg.setdefault(cid, {"used": 0, "unused": 0})
        stat["used" if used else "unused"] += 1
    return agg


def govern_injection(
    store: MemoryStore,
    *,
    days: int = 14,
    card_floor: float = 0.2,
    min_judged: int = 3,
    global_floor: float = 0.3,
    l2_limit: int = 3,
) -> GovernanceReport:
    """健康指标驱动治理：低使用率卡降权 + 全局低使用率收缩注入量。

    - 卡级：判定次数 >= min_judged 且使用率 < card_floor → weight ×0.5（下限淡出）
    - 全局：判定次数合计 >= min_judged 且 inject_used_rate < global_floor
      → L2 注入条数收缩（严重 <global_floor/2 收缩 2 档，一般收缩 1 档）
    - 动作写 decision_log（govern_action），可审计
    """
    summary = audit_summary(store, days=days)
    usage = card_usage(store, days=days)
    index = _index_cards(store)
    degraded: list[tuple[str, float]] = []
    judged_cards = 0
    for cid, stat in usage.items():
        total = stat["used"] + stat["unused"]
        if total < min_judged:
            continue
        judged_cards += 1
        rate = stat["used"] / total
        if rate >= card_floor:
            continue
        card = index.get(cid)
        if card is None or card.status == "archived":
            continue
        new_weight = max(_WEIGHT_FLOOR, card.weight * 0.5)
        store.save_stats(cid, weight=new_weight)
        degraded.append((cid, new_weight))

    rate = summary.get("inject_used_rate", 0.0)
    judged_total = summary.get("inject_used", 0) + summary.get("inject_unused", 0)
    suggest_l1, suggest_l2 = 1, l2_limit
    actions: list[str] = []
    if judged_total >= min_judged and rate < global_floor:
        if rate < global_floor / 2:
            suggest_l2 = max(1, l2_limit - 2)
        else:
            suggest_l2 = max(1, l2_limit - 1)
        actions.append(
            f"inject_used_rate={rate:.2f} < {global_floor:.2f}: "
            f"建议 L2 注入条数 {l2_limit}->{suggest_l2}"
        )
    for cid, w in degraded:
        actions.append(f"card {cid} 使用率过低: weight -> {w:.2f}")
    if not actions:
        actions.append("指标健康，无需治理")

    report = GovernanceReport(
        window_days=days,
        inject_used_rate=rate,
        judged_cards=judged_cards,
        degraded_cards=tuple(degraded),
        suggested_limits=(suggest_l1, suggest_l2),
        actions=tuple(actions),
    )
    with contextlib.suppress(Exception):
        store.log_decision("govern_action", " | ".join(report.actions))
    return report
