"""A8：检索侧反馈回路（DESIGN §4.2/§4.6：降权有下限、升权有上限）。"""

from __future__ import annotations

from memory.models import MemoryCard
from memory.search import MemorySearch, detect_feedback
from memory.store import MemoryStore


def _seed(tmp_path) -> tuple[MemoryStore, MemorySearch, str]:
    store = MemoryStore(tmp_path / "memory")
    card_id = "evt-f-0001"
    store.write_card(MemoryCard(
        id=card_id, kind="event", title="体检", content="这周五早上八点体检，要空腹",
        source_path=f"events/cards/{card_id}.md",
    ))
    return store, MemorySearch(store, feedback_max_weight=2.0, feedback_floor=0.1), card_id


def test_a8_downweight_lowers_weight(tmp_path) -> None:
    store, search, card_id = _seed(tmp_path)
    before = store.read_card(card_id).weight
    search.apply_feedback([card_id], "down")
    assert store.read_card(card_id).weight < before


def test_a8_upweight_capped(tmp_path) -> None:
    store, search, card_id = _seed(tmp_path)
    for _ in range(20):
        search.apply_feedback([card_id], "up")
    assert store.read_card(card_id).weight <= 2.0


def test_a8_detect_feedback_signals() -> None:
    assert detect_feedback("不对，你记错了") == "down"
    assert detect_feedback("其实不是那样的") == "down"
    assert detect_feedback("你说的对，很有用") == "up"
    assert detect_feedback("今天天气怎么样") is None
