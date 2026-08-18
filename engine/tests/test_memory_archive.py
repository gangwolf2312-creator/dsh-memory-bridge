"""A7：不做时间衰减 → 未命中降权 → 归档可找回（DESIGN §4.4/§4.6）。"""

from __future__ import annotations

from memory.models import MemoryCard
from memory.search import MemorySearch
from memory.store import MemoryStore


def test_a7_misses_archive_and_recover(tmp_path) -> None:
    store = MemoryStore(tmp_path / "memory")
    store.write_card(MemoryCard(
        id="evt-a-0001", kind="event", title="电脑配置",
        content="台式机 128GB 内存，4070 显卡，跑本地大模型",
        source_path="events/cards/evt-a-0001.md",
    ))
    store.write_card(MemoryCard(
        id="evt-a-0002", kind="event", title="体检安排",
        content="这周五早上八点体检，要空腹，前一晚别吃油腻",
        source_path="events/cards/evt-a-0002.md",
    ))
    store.write_card(MemoryCard(
        id="evt-a-0003", kind="event", title="公园散步",
        content="昨天傍晚在小区旁边的公园散步半小时，空气很好",
        source_path="events/cards/evt-a-0003.md",
    ))
    search = MemorySearch(store, archive_after_misses=2)
    hit_query = "昨天傍晚在小区旁边的公园散步半小时"  # 精确命中 0003
    for _ in range(2):
        search.search(hit_query, top_k=1)
    # 0001 连续未命中 2 次 → 降权 + 归档
    card = store.read_card("evt-a-0001")
    assert card is not None
    assert card.status == "archived"
    assert card.weight < 1.0  # 降权
    assert card.miss_count >= 2
    # 归档不进检索
    results = search.search("电脑配置 台式机 内存", top_k=5)
    assert "evt-a-0001" not in [r.card_id for r in results]
    # 明文可找回：直接读卡 + 恢复 active
    store.save_stats("evt-a-0001", status="active")
    assert store.read_card("evt-a-0001").status == "active"
    store.close()
