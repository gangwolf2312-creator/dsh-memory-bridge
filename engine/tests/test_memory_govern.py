"""注入治理闭环测试（§9.7 补全）：去噪判定 + 审计回流 + 健康指标驱动治理。"""

from __future__ import annotations

from memory.audit import detect_inject_usage
from memory.govern import (
    GovernanceReport,
    apply_usage_feedback,
    card_usage,
    govern_injection,
)
from memory.models import MemoryCard
from memory.search import MemorySearch
from memory.store import MemoryStore


def _card(card_id: str = "evt-gov-0001", **kw) -> MemoryCard:
    base = {
        "id": card_id,
        "kind": "event",
        "title": "部署端口",
        "content": "部署端口是 8080，用 nginx 反代",
        "source_path": f"events/cards/{card_id}.md",
        "created_at": "2026-08-02T20:00:00",
    }
    base.update(kw)
    return MemoryCard(**base)


def _results(store, query: str = "部署端口"):
    return MemorySearch(store).search(query)


# —— 去噪判定 ——


def test_detect_noisy_single_digit_is_unused(tmp_path) -> None:
    """纯数字命中（弱信号）：单个数字恰好出现 -> unused（去噪）。"""
    store = MemoryStore(tmp_path / "memory")
    store.write_card(_card("evt-1", title="端口", content="部署端口是 8080，用 nginx 反代"))
    results = _results(store)
    out = detect_inject_usage(results, "8080 是什么端口来着")
    # 数字 8080 命中但无强词元命中（"端口"在注入卡 title 里，但回复里"端口"来自用户问题——
    # 注意这里强词元可能命中"端口"，构造一个不含词元的纯数字回复）
    assert results, "检索应命中"
    # "用户只提 8080，未提部署/nginx/反代" -> 单个数字 = 弱信号 -> unused
    out2 = detect_inject_usage(results, "能帮我查一下 8080")
    assert out2.get("evt-1") is False


def test_detect_digit_plus_token_is_used(tmp_path) -> None:
    """数字 + 强词元双命中 -> used（升级后的强信号）。"""
    store = MemoryStore(tmp_path / "memory")
    store.write_card(_card("evt-1", title="部署端口", content="部署端口是 8080，用 nginx 反代"))
    results = _results(store)
    out = detect_inject_usage(results, "好的，部署端口就用 8080")
    assert out.get("evt-1") is True


def test_detect_two_digits_weak_signal_used(tmp_path) -> None:
    """纯数字但 >=2 个不同数字 -> used（弱信号加倍）。"""
    store = MemoryStore(tmp_path / "memory")
    store.write_card(_card("evt-1", title="端口", content="开放端口 8080 和 9090"))
    results = _results(store)
    out = detect_inject_usage(results, "看到有 8080 和 9090")
    assert out.get("evt-1") is True


def test_detect_strong_tokens_used(tmp_path) -> None:
    """>=2 个强词元命中 -> used。"""
    store = MemoryStore(tmp_path / "memory")
    store.write_card(_card("evt-1", title="咖啡", content="每天早上一杯美式，不加糖"))
    results = _results(store)
    out = detect_inject_usage(results, "早上那杯美式不加糖挺好的")
    assert out.get("evt-1") is True


# —— 审计回流（卡级治理）——


def test_apply_usage_feedback_hits_and_misses(tmp_path) -> None:
    store = MemoryStore(tmp_path / "memory")
    store.write_card(_card("evt-1"))
    store.write_card(_card("evt-2"))
    degraded = apply_usage_feedback(
        store,
        {"evt-1": True, "evt-2": False},
        now="2026-08-10T10:00:00",
    )
    assert degraded == []  # 首次 miss 未达阈值
    idx = {c.id: c for c in store.all_cards()}
    assert idx["evt-1"].hit_count == 1 and idx["evt-1"].miss_count == 0
    assert idx["evt-2"].miss_count == 1 and idx["evt-2"].hit_count == 0
    store.close()


def test_apply_usage_feedback_degrades_after_floor(tmp_path) -> None:
    store = MemoryStore(tmp_path / "memory")
    store.write_card(_card("evt-1"))
    for _ in range(3):
        apply_usage_feedback(store, {"evt-1": False}, now="2026-08-10T10:00:00")
    idx = {c.id: c for c in store.all_cards()}
    assert idx["evt-1"].miss_count == 3
    assert idx["evt-1"].weight < 1.0  # 达阈值降权淡出
    assert idx["evt-1"].status == "active"  # 不归档：没被利用 ≠ 记忆错误
    store.close()


# —— 全局治理 ——


def test_card_usage_aggregates(tmp_path) -> None:
    store = MemoryStore(tmp_path / "memory")
    store.log_decision("inject_used", "evt-1: used")
    store.log_decision("inject_used", "evt-1: used")
    store.log_decision("inject_used", "evt-1: unused")
    store.log_decision("inject_used", "evt-2: unused")
    agg = card_usage(store, days=14)
    assert agg["evt-1"] == {"used": 2, "unused": 1}
    assert agg["evt-2"] == {"used": 0, "unused": 1}
    store.close()


def test_govern_injection_degrades_low_usage_card(tmp_path) -> None:
    store = MemoryStore(tmp_path / "memory")
    store.write_card(_card("evt-1"))
    store.write_card(_card("evt-2"))
    # evt-1 使用率 0（< card_floor=0.2），evt-2 全 used（健康）
    for i in range(5):
        store.log_decision("inject_used", "evt-1: unused")
        store.log_decision("inject_used", "evt-2: used")
    report = govern_injection(store, days=14, card_floor=0.2, min_judged=3)
    assert isinstance(report, GovernanceReport)
    degraded_ids = [cid for cid, _ in report.degraded_cards]
    assert "evt-1" in degraded_ids
    assert "evt-2" not in degraded_ids
    idx = {c.id: c for c in store.all_cards()}
    assert idx["evt-1"].weight < 1.0
    store.close()


def test_govern_injection_suggests_contraction_when_unhealthy(tmp_path) -> None:
    store = MemoryStore(tmp_path / "memory")
    # 全局使用率 1/5 = 0.2 < 0.3 -> 建议收缩 L2
    for i in range(5):
        store.log_decision("inject_used", f"evt-{i}: {'used' if i == 0 else 'unused'}")
    report = govern_injection(store, days=14, min_judged=3, l2_limit=3)
    assert report.inject_used_rate == 0.2
    assert report.suggested_limits[1] < 3  # L2 收缩
    store.close()


def test_govern_injection_healthy_no_action(tmp_path) -> None:
    store = MemoryStore(tmp_path / "memory")
    for i in range(5):
        store.log_decision("inject_used", f"evt-{i}: used")
    report = govern_injection(store, days=14, min_judged=3, l2_limit=3)
    assert report.degraded_cards == ()
    assert report.suggested_limits == (1, 3)
    store.close()
