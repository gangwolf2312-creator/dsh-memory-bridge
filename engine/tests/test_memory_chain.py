"""P0 记忆树契约：事件链聚合 / 多跳检索 / 时序检索（DESIGN §4.1 + 落地清单 §16）。"""

from __future__ import annotations

import time

from memory.models import MemoryCard
from memory.search import MemorySearch
from memory.store import MemoryStore, chain_id


def _card(
    cid: str,
    title: str,
    content: str,
    *,
    kind: str = "event",
    chain_title: str = "",
    entities: tuple[str, ...] = (),
    created_at: str = "2026-08-01T10:00:00",
) -> MemoryCard:
    parent_id = chain_id(chain_title) if chain_title else ""
    return MemoryCard(
        id=cid, kind=kind, title=title, content=content,
        source_path=f"events/cards/{cid}.md",
        created_at=created_at, parent_id=parent_id, entities=entities,
    )


def _seed(store: MemoryStore, cards: list[MemoryCard]) -> None:
    for c in cards:
        store.write_card(c)


def test_chain_aggregation_via_register(tmp_path) -> None:
    """跨 run 同主题 → 同一链卡，children 累积；子卡 parent_id 指向同一链。"""
    store = MemoryStore(tmp_path / "memory")
    a = _card(
        "evt-a-1", "联系搬家公司", "联系了搬家公司，约周六上门",
        chain_title="搬家", entities=("搬家公司",),
    )
    b = _card("evt-b-1", "宽带迁移", "宽带迁移预约完成", chain_title="搬家", entities=("宽带",))
    store.write_card(a)
    store.register_chain_card("搬家", a)
    store.write_card(b)
    store.register_chain_card("搬家", b)
    chains = [c for c in store.all_cards() if c.kind == "chain"]
    assert len(chains) == 1
    chain = chains[0]
    assert chain.title == "搬家"
    assert set(chain.children) == {"evt-a-1", "evt-b-1"}
    assert store.read_card("evt-a-1").parent_id == chain.id
    assert store.read_card("evt-b-1").parent_id == chain.id
    # 明文可找回：链卡正文按时间序列出子卡
    assert "evt-a-1" in chain.content and "evt-b-1" in chain.content
    store.close()


def test_chain_id_deterministic_same_title() -> None:
    assert chain_id("搬家") == chain_id("搬家")
    assert chain_id("搬家") != chain_id("装修")


def test_multi_hop_chain_sibling_expansion(tmp_path) -> None:
    """B4（ADR-0021）枝级路标：查询命中枝「搬家」→ 枝下叶获得加成（先找枝再下钻）。

    旧 P0 语义里「无词面重合的兄弟卡」只有 expand=True 才出现；B4 后枝级路标是
    第一轮导航信号（始终生效），expand 控制的是更深的多跳扩展（沿链兄弟/散叶实体）。
    """
    store = MemoryStore(tmp_path / "memory")
    _seed(store, [
        _card(
            "evt-a-1", "搬家公司", "搬家需要联系搬家公司并预约周六上门",
            chain_title="搬家", entities=("搬家公司",), created_at="2026-08-01T10:00:00",
        ),
        _card(
            "evt-b-1", "宽带迁移", "宽带迁移预约完成，师傅周日来装",
            chain_title="搬家", entities=("宽带",), created_at="2026-08-02T10:00:00",
        ),
        _card("evt-c-1", "咖啡习惯", "每天早上一杯美式不加糖", created_at="2026-08-03T10:00:00"),
    ])
    store.register_chain_card("搬家", store.read_card("evt-a-1"))  # 注册链卡（真实提取链路会做）
    search = MemorySearch(store)
    results = search.search("搬家联系了哪家公司", top_k=3)
    ids = [r.card_id for r in results]
    assert "evt-a-1" in ids
    assert "evt-b-1" in ids  # 枝级路标：同枝叶被带出（即使无词面重合）
    assert all(r.chain_title == "搬家" for r in results if r.chain_id)
    b_with = next(r for r in results if r.card_id == "evt-b-1")
    assert b_with.score > 0.0  # 枝级路标给非零分
    store.close()


def test_multi_hop_entity_jump(tmp_path) -> None:
    """跨卡共享实体跳转：查询命中 A，经共享实体「天穹」跳出 B（词面无重合）。"""
    store = MemoryStore(tmp_path / "memory")
    _seed(store, [
        _card(
            "evt-a-1", "集团AI项目", "X集团的AI项目代号天穹，目标年底上线",
            entities=("X集团", "天穹"), created_at="2026-08-01T10:00:00",
        ),
        _card(
            "evt-b-1", "天穹负责人", "天穹项目由李雷主导，团队 6 人",
            entities=("天穹", "李雷"), created_at="2026-08-02T10:00:00",
        ),
        _card(
            "evt-c-1", "跑步计划", "每周三夜跑五公里",
            entities=("跑步",), created_at="2026-08-03T10:00:00",
        ),
    ])
    search = MemorySearch(store)
    results = search.search("X集团的AI项目谁负责", top_k=3)
    ids = [r.card_id for r in results]
    assert "evt-a-1" in ids
    assert "evt-b-1" in ids  # 实体跳转命中
    b = next(r for r in results if r.card_id == "evt-b-1")
    assert b.chain_title == ""  # 未归属链 → 链字段为空（不报错）
    store.close()


def test_since_until_filter(tmp_path) -> None:
    store = MemoryStore(tmp_path / "memory")
    _seed(store, [
        _card("evt-j-1", "成都旅游", "七月去成都旅游", created_at="2026-07-10T10:00:00"),
        _card("evt-a-1", "搬家浦东", "八月搬到了浦东", created_at="2026-08-10T10:00:00"),
        _card("evt-s-1", "换电脑", "九月计划换电脑", created_at="2026-09-10T10:00:00"),
    ])
    search = MemorySearch(store)
    results = search.search("旅游 搬家 电脑", top_k=5, since="2026-08-01", until="2026-08-31")
    ids = [r.card_id for r in results]
    assert "evt-a-1" in ids
    assert "evt-j-1" not in ids
    assert "evt-s-1" not in ids
    store.close()


def test_timeline_mode_sorts_by_time(tmp_path) -> None:
    store = MemoryStore(tmp_path / "memory")
    _seed(store, [
        _card("evt-2", "八月", "八月搬到浦东", created_at="2026-08-10T10:00:00"),
        _card("evt-1", "七月", "七月去成都", created_at="2026-07-10T10:00:00"),
        _card("evt-3", "九月", "九月换电脑", created_at="2026-09-10T10:00:00"),
    ])
    search = MemorySearch(store)
    results = search.search("", top_k=5, timeline=True)
    assert [r.card_id for r in results] == ["evt-1", "evt-2", "evt-3"]
    store.close()


def test_timeline_with_query_filters_relevance(tmp_path) -> None:
    store = MemoryStore(tmp_path / "memory")
    _seed(store, [
        _card("evt-1", "七月", "七月去成都旅游", created_at="2026-07-10T10:00:00"),
        _card("evt-2", "八月", "八月搬去浦东", created_at="2026-08-10T10:00:00"),
    ])
    search = MemorySearch(store)
    results = search.search("旅游", top_k=5, timeline=True)
    assert [r.card_id for r in results] == ["evt-1"]
    store.close()


def test_chain_card_not_base_searchable(tmp_path) -> None:
    """链卡是结构不是事实：查询命中链卡标题/正文时，不直接返回链卡本身。"""
    store = MemoryStore(tmp_path / "memory")
    a = _card(
        "evt-a-1", "宽带迁移", "搬家当天约了宽带迁移",
        chain_title="搬家", created_at="2026-08-01T10:00:00",
    )
    store.write_card(a)
    store.register_chain_card("搬家", a)
    cid = chain_id("搬家")
    search = MemorySearch(store)
    results = search.search("搬家全过程", top_k=5)
    ids = [r.card_id for r in results]
    assert "evt-a-1" in ids
    assert cid not in ids  # 链卡不进基础检索
    store.close()


def test_expand_latency_budget(tmp_path) -> None:
    """多跳扩展不破坏 A6 延迟预算（宽松护栏，防索引/实体扫描退化为 O(n^2) 文件读）。"""
    store = MemoryStore(tmp_path / "memory")
    cards = []
    for i in range(100):
        chain = f"主题{i % 10}"
        cards.append(
            _card(
                f"evt-l-{i:04d}",
                f"记忆{i}",
                f"内容：第{i}条记忆，关键词甲{i % 5} 乙{i % 7}",
                chain_title=chain,
                entities=(f"实体{i % 9}",),
                created_at=f"2026-08-{(i % 28) + 1:02d}T10:00:00",
            )
        )
    _seed(store, cards)
    search = MemorySearch(store)
    times = []
    for _ in range(10):
        t0 = time.perf_counter()
        search.search("关键词甲2 乙3", top_k=5, expand=True)
        times.append((time.perf_counter() - t0) * 1000)
    times.sort()
    assert times[-1] < 300, f"多跳检索过慢: p100={times[-1]:.1f}ms"
    store.close()
# —— §9.7 链身份稳定性：确定性归链 / 别名 / 合并修复 ——


def test_resolve_chain_different_wording_same_chain(tmp_path) -> None:
    """措辞漂移：'搬家' 与 '搬家计划' 归同一链，canonical 保留首见，漂移进 aliases。"""
    from dataclasses import replace

    store = MemoryStore(tmp_path / "memory")
    a = _card("evt-a-1", "联系搬家公司", "联系了搬家公司，约周六上门", chain_title="搬家", entities=("搬家公司",))
    store.write_card(a)
    store.register_chain_card("搬家", a)
    b = replace(
        _card("evt-b-1", "宽带迁移", "宽带迁移预约完成", chain_title="搬家计划", entities=("宽带",)),
        parent_id="",
    )
    store.write_card(b)
    store.register_chain_card("搬家计划", b)
    chains = [c for c in store.all_cards() if c.kind == "chain" and c.status == "active"]
    assert len(chains) == 1
    chain = chains[0]
    assert chain.title == "搬家"
    assert "搬家计划" in chain.aliases
    assert set(chain.children) == {"evt-a-1", "evt-b-1"}
    store.close()


def test_resolve_chain_entity_disambiguation(tmp_path) -> None:
    """实体消歧：标题部分重合但实体不同的主题（买房/卖房）不误并。"""
    from dataclasses import replace

    store = MemoryStore(tmp_path / "memory")
    a = _card("evt-a-1", "看房", "看了三套房子", chain_title="买房", entities=("房子甲",))
    store.write_card(a)
    store.register_chain_card("买房", a)
    b = replace(
        _card("evt-b-1", "挂牌", "挂到中介出售", chain_title="卖房", entities=("中介",)),
        parent_id="",
    )
    store.write_card(b)
    store.register_chain_card("卖房", b)
    chains = [c for c in store.all_cards() if c.kind == "chain" and c.status == "active"]
    assert len(chains) == 2
    store.close()


def test_resolve_chain_alias_exact_match(tmp_path) -> None:
    """别名精确命中：漂移措辞再次出现仍归同一链；无关主题开新链。"""
    store = MemoryStore(tmp_path / "memory")
    a = _card("evt-a-1", "联系搬家公司", "联系了搬家公司", chain_title="搬家", entities=("搬家公司",))
    store.write_card(a)
    store.register_chain_card("搬家", a)
    assert store.resolve_chain("搬家计划", ("宽带",)) == chain_id("搬家")
    assert store.resolve_chain("搬家计划") == chain_id("搬家")  # 别名精确命中
    assert store.resolve_chain("装修", ("师傅",)) != chain_id("搬家")  # 无关 → 新链
    store.close()


def test_merge_chains_repair_split(tmp_path) -> None:
    """存量修复：分裂链合并 → 子卡 re-parent、drop 链 superseded、标题进 aliases。"""
    store = MemoryStore(tmp_path / "memory")
    a = _card("evt-a-1", "联系搬家公司", "联系了搬家公司", chain_title="搬家", entities=("搬家公司",))
    b = _card("evt-b-1", "宽带迁移", "宽带迁移预约完成", chain_title="搬家进度", entities=("宽带",))
    for c, t in ((a, "搬家"), (b, "搬家进度")):
        store.write_card(c)
        store.register_chain_card(t, c)
    chains = [c for c in store.all_cards() if c.kind == "chain" and c.status == "active"]
    assert len(chains) == 2
    keep = next(c for c in chains if c.title == "搬家")
    drop = next(c for c in chains if c.title == "搬家进度")
    assert store.merge_chains(keep.id, drop.id) == 1
    assert store.read_card("evt-b-1").parent_id == keep.id
    dropped = store.read_card(drop.id)
    assert dropped.status == "superseded" and dropped.superseded_by == keep.id
    kept = store.read_card(keep.id)
    assert "搬家进度" in kept.aliases
    assert set(kept.children) == {"evt-a-1", "evt-b-1"}
    store.close()


def test_duplicate_chain_candidates_detects_split(tmp_path) -> None:
    """分裂检测：标题相似的链对被找出（修复入口）。"""
    store = MemoryStore(tmp_path / "memory")
    for c, t in (
        (_card("evt-a-1", "联系搬家公司", "联系了搬家公司", chain_title="搬家", entities=("搬家公司",)), "搬家"),
        (_card("evt-b-1", "宽带迁移", "宽带迁移预约完成", chain_title="搬家进度", entities=("宽带",)), "搬家进度"),
    ):
        store.write_card(c)
        store.register_chain_card(t, c)
    dups = store.duplicate_chain_candidates()
    assert len(dups) >= 1
    titles = {d.title for a, b, _ in dups for d in (a, b)}
    assert titles == {"搬家", "搬家进度"}
    store.close()
