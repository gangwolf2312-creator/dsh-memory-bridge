"""规则提炼补测（P2：rules.py 此前零直接测试）。

覆盖：直接记忆指令（记住：X）、教训指令（记住教训：X）、偏好信号提取
（触发词 → 类别 + 主题）、PreferenceLedger 入账聚合提案（≥min_signals →
lesson_pending 提案卡，幂等不重复提案）。
"""

from __future__ import annotations

from memory.models import MemoryCard
from memory.rules import (
    PreferenceLedger,
    extract_direct_lesson,
    extract_direct_memory,
    extract_signal,
)
from memory.store import MemoryStore


# —— 直接记忆 / 教训指令 ——


def test_extract_direct_memory_fullwidth_colon() -> None:
    assert extract_direct_memory("记住：端口是 8080") == "端口是 8080"


def test_extract_direct_memory_no_colon() -> None:
    assert extract_direct_memory("记住 下午三点开会") == "下午三点开会"


def test_extract_direct_memory_first_clause_only() -> None:
    # 只取首个分句（句末标点切）
    assert extract_direct_memory("记住：周六爬山。周日休息") == "周六爬山"


def test_extract_direct_memory_no_trigger() -> None:
    assert extract_direct_memory("我周末去爬山了") is None


def test_extract_direct_memory_lesson_delegated() -> None:
    # "记住教训：X" 归教训指令，不当普通记忆
    assert extract_direct_memory("记住教训：先备份再迁移") is None


def test_extract_direct_lesson_triggers() -> None:
    assert extract_direct_lesson("记住教训：先备份再迁移") == "先备份再迁移"
    assert extract_direct_lesson("踩坑：路径有空格要引号") == "路径有空格要引号"
    assert extract_direct_lesson("今天天气不错") is None


# —— 偏好信号提取 ——


def test_extract_signal_preference() -> None:
    sig = extract_signal("我更喜欢简洁的回答")
    assert sig is not None
    assert sig.category == "偏好"
    assert sig.topic == "简洁"  # 触发词后首个实义 token
    assert "更喜欢简洁的回答" in sig.statement


def test_extract_signal_rejection() -> None:
    sig = extract_signal("别用那种花哨的模板")
    assert sig is not None
    assert sig.category == "拒绝"


def test_extract_signal_no_trigger() -> None:
    assert extract_signal("今天天气不错") is None


def test_extract_signal_empty_clause() -> None:
    assert extract_signal("我喜欢。") is None  # 触发词后无实义内容


# —— PreferenceLedger：入账 + 聚合提案 ——


def _store(tmp_path) -> MemoryStore:
    return MemoryStore(tmp_path / "memory")


def test_ledger_record_and_aggregate_proposal(tmp_path) -> None:
    store = _store(tmp_path)
    ledger = PreferenceLedger(store, min_signals=3)
    # 同一主题 3 条信号（不同句子 → 都入账）
    for text in ("我更喜欢简洁的回答", "我偏好简洁的界面", "我喜欢简洁的排版"):
        assert ledger.record(text) is not None
    assert len(store.signal_statements("简洁")) == 3
    proposed = ledger.propose()
    assert len(proposed) == 1
    card = proposed[0]
    assert card.kind == "lesson_pending"
    assert card.title.startswith("偏好：简洁")
    assert "3 条信号" in card.title
    # 落盘明文可读
    assert store.read_card(card.id) is not None
    store.close()


def test_ledger_propose_idempotent(tmp_path) -> None:
    store = _store(tmp_path)
    ledger = PreferenceLedger(store, min_signals=3)
    for text in ("我更喜欢简洁的回答", "我偏好简洁的界面", "我喜欢简洁的排版"):
        ledger.record(text)
    ledger.propose()
    # 再次 propose 不重复提案（幂等）
    assert ledger.propose() == []
    store.close()


def test_ledger_below_threshold_no_proposal(tmp_path) -> None:
    store = _store(tmp_path)
    ledger = PreferenceLedger(store, min_signals=3)
    ledger.record("我更喜欢简洁的回答")
    ledger.record("我偏好简洁的界面")
    assert ledger.propose() == []  # 只 2 条 < 3
    store.close()


def test_ledger_record_no_trigger_returns_none(tmp_path) -> None:
    store = _store(tmp_path)
    ledger = PreferenceLedger(store)
    assert ledger.record("今天天气不错") is None
    store.close()


def test_proposed_card_contains_statements(tmp_path) -> None:
    store = _store(tmp_path)
    ledger = PreferenceLedger(store, min_signals=2)
    ledger.record("我更喜欢简洁的回答")
    ledger.record("我偏好简洁的界面")
    card: MemoryCard = ledger.propose()[0]
    assert "简洁的回答" in card.content
    assert "简洁的界面" in card.content
    store.close()
