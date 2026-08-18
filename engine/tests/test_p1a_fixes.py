"""P1a 修复回归（ADAPTATION-AUDIT 高价值 P1 第一批）。

六项：distill 冷却推进 / inject_used 生产方闭环 / main 后端脱敏 /
wiki 版本链检索失效 / 链卡重建丢字段 / batch_size 双旋钮。
"""

from __future__ import annotations

import time

from core.backend import BackendResult

from memory.backends import MainModelBackend
from memory.distill import DistillWorker
from memory.extract import MemoryWritePipeline
from memory.injector import MemoryInjector
from memory.models import MemoryCard, MemoryRun, SearchResult, WikiEntry
from memory.search import MemorySearch
from memory.store import MemoryStore
from memory.wiki import WikiSearch, WikiStore


def _card(
    cid: str, title: str, content: str, *, entities=(), evidence="", corroborations=0
) -> MemoryCard:
    return MemoryCard(
        id=cid, kind="event", title=title, content=content,
        source_path=f"events/cards/{cid}.md",
        source_part="assistant", confidence=0.9, evidence=evidence,
        corroborations=corroborations, entities=tuple(entities),
    )


def _entry(entry_id: str, title: str, *, kind: str = "spec", entities=()) -> WikiEntry:
    return WikiEntry(
        id=entry_id, kind=kind, title=title, content=f"{title}全文……",
        entities=tuple(entities),
    )


# —— P1a-1：distill 冷却在"防抖/去重/无事件"后也推进 ——


def test_distill_cooldown_advances_on_skip(tmp_path) -> None:
    """旧实现：distill 返回 None 不推进冷却 → 画像稳定后每 60s 空转一次 LLM。"""
    calls = {"n": 0}

    class _FakeDistiller:
        def distill(self):
            calls["n"] += 1
            return None  # 防抖/去重跳过

    worker = DistillWorker(
        _FakeDistiller(),
        enabled=True,
        poll_seconds=0.05,
        cooldown_seconds=0.0,
        idle_seconds=0.0,
    )
    time.sleep(0.3)
    worker.shutdown()
    assert calls["n"] >= 1
    assert worker._last_distill_at > 0.0  # 旧实现恒为 0 → 无限重跑


# —— P1a-2：inject_used 生产方（审计/治理闭环不再空转） ——


def test_injector_record_usage_writes_decision_log(tmp_path) -> None:
    store = MemoryStore(tmp_path / "memory")
    injector = MemoryInjector(MemorySearch(store))
    results = [
        SearchResult(
            card_id="evt-1", score=1.0, source_path="events/cards/evt-1.md",
            title="部署端口", snippet="部署端口是 8080",
        ),
        SearchResult(
            card_id="evt-2", score=1.0, source_path="events/cards/evt-2.md",
            title="爬山记录", snippet="周末去爬山",
        ),
    ]
    usage = injector.record_usage(results, "端口用 8080")
    assert usage == {"evt-1": True, "evt-2": False}
    entries = store.decision_log("inject_used")
    details = {e["detail"] for e in entries}
    assert "evt-1: used" in details
    assert "evt-2: unused" in details
    store.close()


# —— P1a-3：main 后端提取前脱敏（唯一绕过 sanitize 的路径） ——


def test_main_backend_sanitizes_before_delegate() -> None:
    class _Capture:
        def __init__(self) -> None:
            self.sent: list[dict] | None = None
            self.model = "test-model"

        def complete(self, messages, **kwargs):
            self.sent = messages
            return BackendResult(text='{"cards": []}')

        def count_tokens(self, text: str) -> int:
            return len(text)

    delegate = _Capture()
    backend = MainModelBackend(delegate)
    backend.complete([{"role": "user", "content": "我的 API key 是 sk-aaaaaaaaaaaaaaaa"}])
    sent = delegate.sent[0]["content"]
    assert "sk-aaaaaaaaaaaaaaaa" not in sent
    assert "<API_KEY>" in sent
    assert backend.last_sanitize_hits == ["api_key"]

    # sanitize=False 显式关闭：原样透传
    raw = _Capture()
    plain = MainModelBackend(raw, sanitize=False)
    plain.complete([{"role": "user", "content": "密钥 sk-aaaaaaaaaaaaaaaa"}])
    assert "sk-aaaaaaaaaaaaaaaa" in raw.sent[0]["content"]
    assert plain.last_sanitize_hits == []


# —— P1a-4：wiki 版本链——supersede 后旧规范退出检索/查找/传导链 ——


def test_wiki_superseded_excluded_from_search_and_lookup(tmp_path) -> None:
    store = WikiStore(tmp_path / "wiki")
    store.write_entry(_entry("wk-old", "城市防灾减灾规范", entities=("防灾减灾",)))
    store.write_entry(_entry("wk-new", "城市防灾减灾规范 2026 版", entities=("防灾减灾",)))
    store.write_entry(_entry("wk-fire", "城市消防专项规划", entities=("防灾减灾",)))

    search = WikiSearch(store)
    # supersede 前：旧规范可搜到
    assert any(r.entry_id == "wk-old" for r in search.search("防灾减灾"))
    assert store.find_entry_by_title("城市防灾减灾规范") is not None

    assert store.supersede_entry("wk-old", "wk-new") is True
    old = store.read_entry("wk-old")
    assert old is not None
    assert old.status == "superseded"  # P1a：状态置位
    assert old.superseded_by == "wk-new"

    # supersede 后：不再进检索 / 查找 / 传导链
    assert not any(r.entry_id == "wk-old" for r in search.search("防灾减灾"))
    assert store.find_entry_by_title("城市防灾减灾规范") is None
    related = search.related_by_entities("wk-new")
    assert not any(r.entry_id == "wk-old" for r in related)
    # 传导链仍对 active 条目生效（wk-fire 共享实体被带出；self 排除）
    assert any(r.entry_id == "wk-fire" for r in related)
    store.close()


# —— P1a-5：链卡重建保留字段 + entities 取子卡并集 ——


def test_chain_card_preserves_fields_and_unions_entities(tmp_path) -> None:
    store = MemoryStore(tmp_path / "memory")
    a = _card("evt-a-1", "搬家第一天", "搬进新家", entities=("搬家", "新家"))
    b = _card("evt-a-2", "搬家第二天", "买家具", entities=("搬家", "家具"))
    store.write_card(a)
    store.write_card(b)

    chain1 = store.register_chain_card("搬家", a)
    assert set(chain1.entities) == {"搬家", "新家"}
    # 给链卡设置证据/佐证（模拟治理回写）
    store.save_stats(chain1.id, evidence="explicit", corroborations=1)

    chain2 = store.register_chain_card("搬家", b)
    assert set(chain2.entities) == {"搬家", "新家", "家具"}  # 子卡实体并集
    assert chain2.evidence == "explicit"  # 重建不清零（旧实现丢字段）
    assert chain2.corroborations == 1
    assert len(chain2.children) == 2
    # 明文/索引一致
    got = store.read_card(chain2.id)
    assert got is not None and got.entities == chain2.entities
    assert got.evidence == "explicit"
    store.close()


# —— P1a-6：batch_size 双旋钮合一 ——


def test_pipeline_batch_size_derives_from_extractor(tmp_path) -> None:
    store = MemoryStore(tmp_path / "memory")

    class _Batched:
        batch_size = 8

    pipe = MemoryWritePipeline(store, extractor=_Batched(), enabled=True, worker=False)
    assert pipe.batch_size == 8  # 缺省：自动对齐提取器（旧实现恒 1 → 云端攒批永远走不到）

    pipe2 = MemoryWritePipeline(
        store, extractor=_Batched(), enabled=True, worker=False, batch_size=2
    )
    assert pipe2.batch_size == 2  # 显式传入仍可覆盖

    pipe3 = MemoryWritePipeline(store, extractor=None, enabled=True, worker=False)
    assert pipe3.batch_size == 1  # 无提取器 → 1
    pipe.close()
    pipe2.close()
    pipe3.close()
    store.close()
