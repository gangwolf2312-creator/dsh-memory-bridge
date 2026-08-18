"""遗忘批处理 + 果摘要补测（P2：decay.py / fruit.py 此前零直接测试）。

- decay：days_between、DecayMaintenance.run_once（完结判定 / 子卡枯萎 /
  幂等 / summarizer 钩子）
- fruit：FruitSummarizer（幂等跳过 / 后端链解析 / 截断 / 全失败抛错）
"""

from __future__ import annotations

import pytest
from core.backend import BackendResult
from memory.decay import DecayMaintenance, days_between
from memory.fruit import FruitSummarizer, FruitSummaryError
from memory.models import MemoryCard
from memory.store import MemoryStore


# —— decay ——


def test_days_between() -> None:
    assert days_between("2026-07-01T10:00:00", "2026-08-01T10:00:00") == 31
    assert days_between("2026-08-01", "2026-08-01") == 0
    assert days_between("2026-08-02", "2026-08-01") == 0  # 反序取 0
    assert days_between("垃圾串", "2026-08-01") == 0  # 解析失败取 0
    assert days_between(None, "2026-08-01") == 0


def _store(tmp_path) -> MemoryStore:
    return MemoryStore(tmp_path / "memory")


def _chain(cid: str, **kw) -> MemoryCard:
    base = {
        "id": cid,
        "kind": "chain",
        "title": "搬家事件",
        "content": "事件链",
        "source_path": f"events/cards/{cid}.md",
        "created_at": "2026-06-01T10:00:00",
    }
    base.update(kw)
    return MemoryCard(**base)


def _kid(cid: str, chain_id: str, created_at: str, **kw) -> MemoryCard:
    base = {
        "id": cid,
        "kind": "event",
        "title": f"子事件 {cid}",
        "content": "内容",
        "source_path": f"events/cards/{cid}.md",
        "parent_id": chain_id,
        "created_at": created_at,
    }
    base.update(kw)
    return MemoryCard(**base)


def test_run_once_ends_idle_branch_and_wilts_leaves(tmp_path) -> None:
    store = _store(tmp_path)
    store.write_card(_chain("ch-1"))
    store.write_card(_kid("evt-k1", "ch-1", "2026-06-01T10:00:00"))
    store.write_card(_kid("evt-k2", "ch-1", "2026-06-02T10:00:00"))
    maint = DecayMaintenance(store, branch_idle_days=30)
    report = maint.run_once(now="2026-08-15T10:00:00")  # 最后子卡已 74 天
    assert report["ended"] == 1
    assert report["wilted"] == 2
    chain = store.read_card("ch-1")
    assert chain.ended_at is not None
    k1 = store.read_card("evt-k1")
    assert k1.status == "wilted"
    assert k1.ended_at == chain.ended_at
    assert k1.weight == pytest.approx(0.3)  # 默认 wilt_factor
    store.close()


def test_run_once_recent_branch_untouched(tmp_path) -> None:
    store = _store(tmp_path)
    store.write_card(_chain("ch-2"))
    store.write_card(_kid("evt-r1", "ch-2", "2026-08-10T10:00:00"))
    maint = DecayMaintenance(store, branch_idle_days=30)
    report = maint.run_once(now="2026-08-15T10:00:00")  # 5 天 < 30
    assert report == {"ended": 0, "wilted": 0, "summarized": 0}
    assert store.read_card("ch-2").ended_at is None
    store.close()


def test_run_once_idempotent(tmp_path) -> None:
    store = _store(tmp_path)
    store.write_card(_chain("ch-3"))
    store.write_card(_kid("evt-i1", "ch-3", "2026-06-01T10:00:00"))
    maint = DecayMaintenance(store, branch_idle_days=30)
    maint.run_once(now="2026-08-15T10:00:00")
    second = maint.run_once(now="2026-08-15T10:00:00")  # 已完结不再处理
    assert second["ended"] == 0 and second["wilted"] == 0
    store.close()


def test_run_once_calls_summarizer_for_ended_branch(tmp_path) -> None:
    store = _store(tmp_path)
    store.write_card(_chain("ch-4"))
    store.write_card(_kid("evt-s1", "ch-4", "2026-06-01T10:00:00"))
    calls: list[str] = []
    maint = DecayMaintenance(
        store, branch_idle_days=30,
        summarizer=lambda cid: calls.append(cid) or True,
    )
    report = maint.run_once(now="2026-08-15T10:00:00")
    assert report["summarized"] == 1
    assert calls == ["ch-4"]
    store.close()


def test_run_once_summarizer_skips_branches_with_summary(tmp_path) -> None:
    store = _store(tmp_path)
    store.write_card(_chain("ch-5", summary="已有果摘要"))
    store.write_card(_kid("evt-h1", "ch-5", "2026-06-01T10:00:00"))
    calls: list[str] = []
    maint = DecayMaintenance(
        store, branch_idle_days=30,
        summarizer=lambda cid: calls.append(cid) or True,
    )
    maint.run_once(now="2026-08-15T10:00:00")
    assert calls == []  # 幂等：有 summary 不再生成
    store.close()


# —— fruit ——


class _FakeBackend:
    def __init__(self, text: str = '{"summary": "搬家完成，新家已安顿。"}'):
        self.text = text
        self.calls = 0

    def complete(self, messages, **kw):
        self.calls += 1
        return BackendResult(text=self.text)


def test_fruit_summarize_writes_chain_summary(tmp_path) -> None:
    store = _store(tmp_path)
    store.write_card(_chain("ch-f1"))
    store.write_card(_kid("evt-f1", "ch-f1", "2026-06-01T10:00:00"))
    backend = _FakeBackend()
    summarizer = FruitSummarizer(store, [backend])
    assert summarizer.summarize("ch-f1") is True
    assert backend.calls == 1
    chain = store.read_card("ch-f1")
    assert chain.summary == "搬家完成，新家已安顿。"
    store.close()


def test_fruit_summarize_idempotent_no_call(tmp_path) -> None:
    store = _store(tmp_path)
    store.write_card(_chain("ch-f2", summary="已有果"))
    store.write_card(_kid("evt-f2", "ch-f2", "2026-06-01T10:00:00"))
    backend = _FakeBackend()
    summarizer = FruitSummarizer(store, [backend])
    assert summarizer.summarize("ch-f2") is True  # 幂等跳过
    assert backend.calls == 0
    store.close()


def test_fruit_summarize_wrong_kind_or_missing(tmp_path) -> None:
    store = _store(tmp_path)
    store.write_card(_kid("evt-f3", "ch-f3", "2026-06-01T10:00:00"))
    backend = _FakeBackend()
    summarizer = FruitSummarizer(store, [backend])
    assert summarizer.summarize("evt-f3") is False  # 非链卡
    assert summarizer.summarize("ch-missing") is False  # 不存在
    assert backend.calls == 0
    store.close()


def test_fruit_summarize_empty_branch(tmp_path) -> None:
    store = _store(tmp_path)
    store.write_card(_chain("ch-f4"))
    backend = _FakeBackend()
    summarizer = FruitSummarizer(store, [backend])
    assert summarizer.summarize("ch-f4") is False  # 空枝无可总结
    assert backend.calls == 0
    store.close()


def test_fruit_truncates_over_budget(tmp_path) -> None:
    store = _store(tmp_path)
    store.write_card(_chain("ch-f5"))
    store.write_card(_kid("evt-f5", "ch-f5", "2026-06-01T10:00:00"))
    long_summary = "结" * 200
    backend = _FakeBackend(text=f'{{"summary": "{long_summary}"}}')
    summarizer = FruitSummarizer(
        store, [backend], count_tokens=lambda t: len(t), summary_budget_tokens=100
    )
    summarizer.summarize("ch-f5")
    summary = store.read_card("ch-f5").summary
    assert len(summary) <= 100 + len("（摘要超长已截断）")
    assert "已截断" in summary
    store.close()


def test_fruit_fallback_to_next_backend(tmp_path) -> None:
    store = _store(tmp_path)
    store.write_card(_chain("ch-f6"))
    store.write_card(_kid("evt-f6", "ch-f6", "2026-06-01T10:00:00"))
    bad = _FakeBackend(text="不是 JSON")
    good = _FakeBackend(text='{"summary": "链 6 的结论"}')
    summarizer = FruitSummarizer(store, [bad, good])
    assert summarizer.summarize("ch-f6") is True
    assert store.read_card("ch-f6").summary == "链 6 的结论"
    store.close()


def test_fruit_all_backends_fail_raises(tmp_path) -> None:
    store = _store(tmp_path)
    store.write_card(_chain("ch-f7"))
    store.write_card(_kid("evt-f7", "ch-f7", "2026-06-01T10:00:00"))
    bad = _FakeBackend(text="不是 JSON")
    summarizer = FruitSummarizer(store, [bad])
    with pytest.raises(FruitSummaryError):
        summarizer.summarize("ch-f7")
    assert store.read_card("ch-f7").summary == ""  # 不写坏数据
    store.close()
