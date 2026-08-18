"""置信度校准契约（README §9.7）：证据驱动准入，模型自评降级为排序特征。"""

from __future__ import annotations

from memory.confidence import auto_commit, base_score, compute_confidence
from memory.extract import MemoryWritePipeline
from memory.models import MemoryCard, MemoryRun
from memory.search import MemorySearch
from memory.store import MemoryStore


def _card(
    cid: str,
    title: str,
    content: str,
    *,
    kind: str = "event",
    parent_id: str = "",
    run_id: str | None = None,
    source_part: str = "assistant",
    confidence: float = 0.0,
    evidence: str = "",
    corroborations: int = 0,
    created_at: str = "2026-08-01T10:00:00",
) -> MemoryCard:
    return MemoryCard(
        id=cid, kind=kind, title=title, content=content,
        source_path=f"events/cards/{cid}.md",
        created_at=created_at, parent_id=parent_id, run_id=run_id,
        source_part=source_part, confidence=confidence,
        evidence=evidence, corroborations=corroborations,
    )


class _FakeExtractor:
    """固定返回证据标签的假提取器（管道测试用）。

    与真实 LLMExtractor 对齐：给卡打上 run.run_id（佐证按 run 去重的前提）。
    """

    def __init__(self, cards: list[tuple[MemoryCard, str]]) -> None:
        self.cards = cards

    def extract(self, run: MemoryRun) -> list[tuple[MemoryCard, str]]:
        from dataclasses import replace

        return [(replace(card, run_id=run.run_id), chain) for card, chain in self.cards]


import itertools

_run_seq = itertools.count(1)


def _run_pipe(
    store: MemoryStore,
    cards: list[tuple[MemoryCard, str]],
    user_text: str,
    *,
    run_id: str | None = None,
) -> None:
    pipe = MemoryWritePipeline(store, extractor=_FakeExtractor(cards), enabled=True, worker=False)
    run = MemoryRun(
        run_id=run_id or f"run-conf-{next(_run_seq)}",
        session_id="s", user_text=user_text,
        reply_text="好的", tier="L1",
    )
    store.insert_run(run)
    pipe.process_staged(1)
    pipe.close()


def test_evidence_base_scores() -> None:
    assert base_score("directive") == 0.95
    assert base_score("explicit") == 0.90
    assert base_score("inferred") == 0.60
    assert base_score("uncertain") == 0.35
    assert base_score("") == 0.35


def test_auto_commit_gate() -> None:
    assert auto_commit("explicit") is True
    assert auto_commit("directive") is True
    assert auto_commit("uncertain") is False
    assert auto_commit("inferred") is False
    assert auto_commit("inferred", corroborated=True) is True
    assert auto_commit("inferred", source_part="tool:search") is True
    assert auto_commit("uncertain", directive_hit=True) is True


def test_compute_confidence_modifiers() -> None:
    assert compute_confidence("explicit", source_part="user") == 0.95
    assert compute_confidence("explicit", source_part="assistant") == 0.85
    assert compute_confidence("inferred", corroborated=True, source_part="assistant") == 0.65
    assert compute_confidence("uncertain", directive_hit=True) >= 0.90
    assert compute_confidence("approved") == 1.0


def test_pipeline_evidence_routes_kind(tmp_path) -> None:
    """证据门：explicit → event；uncertain → pending。"""
    store = MemoryStore(tmp_path / "memory")
    _run_pipe(store, [
        (_card("evt-1", "明说", "用户说周六搬家", evidence="explicit", source_part="user"), "搬家"),
        (_card("evt-2", "不确定", "可能是下月", evidence="uncertain"), "搬家"),
    ], "周六搬家")
    assert store.read_card("evt-1").kind == "event"
    assert store.read_card("evt-2").kind == "lesson_pending"
    assert store.read_card("evt-1").confidence == 0.95
    store.close()


def test_pipeline_inferred_requires_corroboration(tmp_path) -> None:
    """inferred 无佐证 → pending；有佐证（同断言另一 run）→ event。"""
    store = MemoryStore(tmp_path / "memory")
    _run_pipe(store, [
        (_card("evt-new", "端口", "部署端口是 8080", evidence="inferred"), ""),
    ], "端口多少")
    assert store.read_card("evt-new").kind == "lesson_pending"
    store.close()

    store2 = MemoryStore(tmp_path / "memory2")
    store2.write_card(_card("evt-old", "端口", "部署端口是 8080", run_id="run-a"))
    _run_pipe(store2, [
        (_card("evt-new", "端口", "部署端口是 8080", evidence="inferred"), ""),
    ], "端口多少")
    card = store2.read_card("evt-new")
    assert card.kind == "event"
    assert card.confidence >= 0.60
    store2.close()


def test_pipeline_directive_trigger_overrides(tmp_path) -> None:
    """'记住：X' 指令 → 即使 LLM 标 uncertain 也直达 event（确定性双保险）。"""
    store = MemoryStore(tmp_path / "memory")
    _run_pipe(store, [
        (_card("evt-1", "端口", "部署端口是 8080", evidence="uncertain"), "部署"),
    ], "记住：部署端口是 8080")
    card = store.read_card("evt-1")
    assert card.kind == "event"
    assert card.confidence >= 0.90
    store.close()


def test_feedback_down_demotes_evidence(tmp_path) -> None:
    """用户纠正 → 证据降级 uncertain + 置信 cap（取消"永不衰减"资格）。"""
    store = MemoryStore(tmp_path / "memory")
    store.write_card(_card("evt-1", "体检", "这周五早上八点体检", confidence=0.95, evidence="explicit"))
    MemorySearch(store).apply_feedback(["evt-1"], "down")
    card = store.read_card("evt-1")
    assert card.evidence == "uncertain"
    assert card.confidence <= 0.4
    store.close()


def test_feedback_up_increments_corroborations(tmp_path) -> None:
    """用户确认 → 佐证 +1（豁免/校准依据）。"""
    store = MemoryStore(tmp_path / "memory")
    store.write_card(_card("evt-1", "体检", "这周五早上八点体检", confidence=0.6, evidence="inferred"))
    MemorySearch(store).apply_feedback(["evt-1"], "up")
    assert store.read_card("evt-1").corroborations == 1
    store.close()


def test_promote_lesson_marks_approved(tmp_path) -> None:
    """人工审批固化 → lesson_permanent + approved + 1.0（权威真值）。"""
    store = MemoryStore(tmp_path / "memory")
    store.write_card(_card(
        "les-1", "偏好", "用户偏好简洁回答",
        kind="lesson_pending", evidence="uncertain", confidence=0.35,
    ))
    promoted = store.promote_lesson("les-1")
    assert promoted is not None
    assert promoted.kind == "lesson_permanent"
    assert promoted.evidence == "approved"
    assert promoted.confidence == 1.0
    store.close()


def test_b44_exemption_rekey(tmp_path) -> None:
    """B4.4 豁免改键：不再信模型裸 0.9；explicit / lesson_permanent 才豁免。"""
    store = MemoryStore(tmp_path / "memory")
    store.write_card(_card("evt-1", "体检安排", "体检安排", confidence=0.6, evidence="inferred", created_at="2026-06-01T10:00:00"))
    store.write_card(_card("evt-2", "搬家安排", "周六搬家", confidence=0.9, evidence="explicit", created_at="2026-06-01T10:00:00"))
    store.write_card(_card("les-1", "踩坑经验", "部署前先备份", kind="lesson_permanent", confidence=0.6, created_at="2026-06-01T10:00:00"))
    search = MemorySearch(store)
    assert search._recency_factor(store.read_card("evt-1")) < 1.0
    assert search._recency_factor(store.read_card("evt-2")) == 1.0
    assert search._recency_factor(store.read_card("les-1")) == 1.0
    store.close()


def test_corroboration_counts_pending_card(tmp_path) -> None:
    """佐证盲区修复：第一张 inferred → pending；第二张 inferred 再提 → pending 卡算佐证 → event。"""
    store = MemoryStore(tmp_path / "memory")
    _run_pipe(store, [
        (_card("les-1", "端口", "部署端口是 8080", evidence="inferred"), ""),
    ], "端口多少")
    assert store.read_card("les-1").kind == "lesson_pending"
    _run_pipe(store, [
        (_card("evt-2", "端口", "部署端口是 8080", evidence="inferred"), ""),
    ], "还是 8080 吗")
    assert store.read_card("evt-2").kind == "event"
    assert store.count_corroborations(store.read_card("evt-2")) >= 1
    store.close()


def test_corroboration_counts_permanent_card(tmp_path) -> None:
    """已固化的 lesson_permanent 同样是佐证源。"""
    store = MemoryStore(tmp_path / "memory")
    store.write_card(_card("les-p", "端口", "部署端口是 8080", kind="lesson_permanent", run_id="run-p"))
    assert store.count_corroborations(_card("evt-x", "端口", "部署端口是 8080")) == 1
    store.close()
