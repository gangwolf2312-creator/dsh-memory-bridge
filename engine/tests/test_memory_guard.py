"""提取门卫与注入审计契约（§9.7 成本控制 + 实证 instrumentation）。"""

from __future__ import annotations

from memory.audit import audit_summary, detect_inject_usage
from memory.guard import should_extract
from memory.models import MemoryCard
from memory.search import MemorySearch
from memory.store import MemoryStore


def _card(cid: str, title: str, content: str) -> MemoryCard:
    return MemoryCard(
        id=cid, kind="event", title=title, content=content,
        source_path=f"events/cards/{cid}.md", created_at="2026-08-01T10:00:00",
    )


def test_guard_chitchat_skipped() -> None:
    assert should_extract("好的", "好的") == (False, "寒暄")
    assert should_extract("嗯嗯", "没问题")[0] is False
    assert should_extract("哈哈", "哈哈")[0] is False


def test_guard_fact_signals_kept() -> None:
    assert should_extract("记住：部署端口是 8080", "好的")[0] is True   # 指令
    assert should_extract("端口多少", "8080")[0] is True               # 专名提示
    assert should_extract("周六搬家", "好的")[0] is True               # 事实提示
    assert should_extract("下周要出差三天", "好的")[0] is True          # 时间词
    assert should_extract("我觉得这个方案整体上比较合理可以考虑推进", "好的")[0] is True  # 长句


def test_guard_empty_and_short() -> None:
    assert should_extract("", "")[0] is False
    assert should_extract("好", "")[0] is False


def test_enqueue_guard_marks_skipped(tmp_path) -> None:
    """门卫生效于 enqueue：寒暄 → run 落盘但 skipped；事实信号 → staged。"""
    from memory.extract import MemoryWritePipeline

    store = MemoryStore(tmp_path / "memory")

    class _NoopExtractor:
        def extract(self, run):
            return []

    pipe = MemoryWritePipeline(store, extractor=_NoopExtractor(), enabled=True, worker=False)
    r1 = pipe.enqueue(user_text="好的", reply_text="好的", tier="L1")
    r2 = pipe.enqueue(user_text="记住：部署端口是 8080", reply_text="好的", tier="L1")
    assert store.run_status(r1) == "skipped"
    assert store.run_status(r2) == "staged"
    assert any(e["topic"] == "extract_skip" for e in store.decision_log())
    pipe.close()


def test_detect_inject_usage(tmp_path) -> None:
    """注入利用归因：输出含注入卡强数字 token → used。"""
    store = MemoryStore(tmp_path / "memory")
    store.write_card(_card("evt-1", "端口", "部署端口是 8080，用 nginx 反代"))
    store.write_card(_card("evt-2", "咖啡", "每天早上一杯美式"))
    results = MemorySearch(store).search("部署端口")
    assert results, "检索应命中 evt-1"
    out = detect_inject_usage(results, "好的，端口就用 8080")
    assert out.get("evt-1") is True
    store.close()


def test_audit_summary_aggregates(tmp_path) -> None:
    """周报聚合：inject_hit / inject_used / extract_skip / extract_cost。"""
    store = MemoryStore(tmp_path / "memory")
    store.log_decision("inject_hit", "query='端口' cards=['evt-1']")
    store.log_decision("inject_used", "evt-1: used")
    store.log_decision("inject_used", "evt-2: unused")
    store.log_decision("extract_skip", "run-x: 寒暄")
    store.log_decision("extract_cost", "run-y: in_chars=500")
    s = audit_summary(store)
    assert s["inject_hits"] == 1
    assert s["inject_used"] == 1 and s["inject_unused"] == 1
    assert s["extract_skips"] == 1
    assert s["extract_runs"] == 1
    assert s["inject_used_rate"] == 0.5
    assert s["skip_rate"] == 0.5
    store.close()
