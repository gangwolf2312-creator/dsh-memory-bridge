"""画像蒸馏核心 + 注入器补测（P2：distill.py / injector.py 此前零直接测试）。

- distill：collect_sources（事件卡 + trace + 日记录）、distill 主路径产草稿、
  防抖（与 approved 几乎相同且人格未变跳过）、去重（同摘要草稿幂等）、
  空摘要抛错、证据不足保留当前人格
- injector：L0 零注入不触发检索、L1/L2 上限、溯源格式化（含果摘要优先）、
  检索超时 → 空注入
"""

from __future__ import annotations

import time

import pytest
from core.backend import BackendResult
from core.types import IntentTier
from memory.distill import ProfileDistillError, ProfileDistiller
from memory.injector import MemoryInjector
from memory.models import MemoryCard, SearchResult
from memory.profile import Profile, ProfileStore
from memory.store import MemoryStore


# —— distill ——


class _FakeBackend:
    def __init__(self, text: str):
        self.text = text
        self.calls = 0

    def complete(self, messages, **kw):
        self.calls += 1
        return BackendResult(text=self.text)


_GOOD_PAYLOAD = (
    '{"summary": "用户是规划领域工程师，偏好结构化输出，长期目标是知识库建设。", '
    '"mbti": "istj", '
    '"dimensions": [{"key": "ei", "value": 0.8}], '
    '"source_refs": ["events/cards/evt-1.md"]}'
)


def _memory(tmp_path) -> MemoryStore:
    store = MemoryStore(tmp_path / "memory")
    card = MemoryCard(
        id="evt-distill-1",
        kind="event",
        title="知识库选型讨论",
        content="确定走 Memory Tree System 路线",
        source_path="events/cards/evt-distill-1.md",
        trace_event_id="evt-abc-123",
        created_at="2026-08-01T10:00:00",
    )
    store.write_card(card)
    store.append_daily_log("2026-08-10", "讨论知识库设计")
    return store


def _distiller(tmp_path, memory, backend) -> ProfileDistiller:
    return ProfileDistiller(
        ProfileStore(tmp_path / "memory"),
        memory,
        [backend],
        count_tokens=lambda t: len(t),
    )


def test_collect_sources_cards_and_logs(tmp_path) -> None:
    memory = _memory(tmp_path)
    d = _distiller(tmp_path, memory, _FakeBackend(_GOOD_PAYLOAD))
    lines, trace = d.collect_sources()
    assert any("知识库选型讨论" in line for line in lines)
    assert any("2026-08-10" in line for line in lines)
    assert trace == "evt-abc-123"  # 首个非空回合根


def test_distill_writes_draft(tmp_path) -> None:
    memory = _memory(tmp_path)
    backend = _FakeBackend(_GOOD_PAYLOAD)
    d = _distiller(tmp_path, memory, backend)
    draft = d.distill()
    assert draft is not None
    assert draft.status == "draft"
    assert draft.mbti == "ISTJ"  # 大写归一
    assert draft.summary.startswith("用户是规划领域工程师")
    assert draft.trace_event_id == "evt-abc-123"
    assert len(d.store.list_drafts()) == 1
    assert backend.calls == 1


def test_distill_keeps_current_persona_when_evidence_insufficient(tmp_path) -> None:
    """证据不足（无 mbti/dimensions）→ 保留已审批画像的人格（防幻觉）。"""
    memory = _memory(tmp_path)
    ps = ProfileStore(tmp_path / "memory")
    ps.save(
        Profile(
            summary="旧摘要", status="approved", mbti="ENTP",
            dimensions=(),
        ),
        approve=True,
    )
    payload = '{"summary": "新摘要", "mbti": "", "dimensions": []}'
    d = ProfileDistiller(ps, memory, [_FakeBackend(payload)], count_tokens=lambda t: len(t))
    draft = d.distill()
    assert draft is not None
    assert draft.mbti == "ENTP"  # 保留旧人格
    assert draft.summary == "新摘要"


def test_distill_debounce_same_as_approved(tmp_path) -> None:
    """防抖：与 approved 摘要几乎相同且人格未变 → 不产草稿。"""
    memory = _memory(tmp_path)
    ps = ProfileStore(tmp_path / "memory")
    ps.save(
        Profile(summary="用户是规划领域工程师。", status="approved", mbti="ISTJ"),
        approve=True,
    )
    payload = '{"summary": "用户是规划领域工程师。", "mbti": "ISTJ", "dimensions": []}'
    d = ProfileDistiller(ps, memory, [_FakeBackend(payload)], count_tokens=lambda t: len(t))
    assert d.distill() is None
    assert ps.list_drafts() == []


def test_distill_dedupe_same_draft(tmp_path) -> None:
    """去重：相同摘要草稿已存在 → 幂等跳过。"""
    memory = _memory(tmp_path)
    d = _distiller(tmp_path, memory, _FakeBackend(_GOOD_PAYLOAD))
    first = d.distill()
    assert first is not None
    assert d.distill() is None  # 第二次同摘要 → 跳过
    assert len(d.store.list_drafts()) == 1


def test_distill_empty_summary_raises(tmp_path) -> None:
    memory = _memory(tmp_path)
    d = _distiller(tmp_path, memory, _FakeBackend('{"summary": ""}'))
    with pytest.raises(ProfileDistillError):
        d.distill()


def test_distill_no_sources_returns_none(tmp_path) -> None:
    """无事件可蒸馏是正常状态（不抛错、不调后端）。"""
    store = MemoryStore(tmp_path / "memory")
    backend = _FakeBackend(_GOOD_PAYLOAD)
    d = ProfileDistiller(
        ProfileStore(tmp_path / "memory"), store, [backend],
        count_tokens=lambda t: len(t),
    )
    assert d.distill() is None
    assert backend.calls == 0


# —— injector ——


def _result(cid: str, **kw) -> SearchResult:
    base = {
        "card_id": cid,
        "score": 1.0,
        "source_path": f"events/cards/{cid}.md",
        "title": "端口配置",
        "snippet": "端口 8080",
        "chain_title": "服务器部署",
        "created_at": "2026-08-10",
    }
    base.update(kw)
    return SearchResult(**base)


class _FakeStore:
    def __init__(self):
        self.logs: list[tuple[str, str]] = []

    def log_decision(self, name, detail):
        self.logs.append((name, detail))


class _FakeSearch:
    def __init__(self, results=None, delay_ms: float = 0.0):
        self.results = results or []
        self.delay_ms = delay_ms
        self.calls: list[dict] = []

    def search(self, query, *, top_k, project_id=None, project_by_run=None):
        self.calls.append(
            {"query": query, "top_k": top_k, "project_id": project_id}
        )
        if self.delay_ms:
            time.sleep(self.delay_ms / 1000)
        return self.results[:top_k]

    @property
    def store(self):
        return _FakeStore()


def test_injector_l0_zero_injection_no_search() -> None:
    search = _FakeSearch(results=[_result("c1")])
    inj = MemoryInjector(search)
    assert inj.inject_for_tier(IntentTier.L0, "随便什么") == []
    assert search.calls == []  # L0 不触发检索


def test_injector_l1_l2_limits() -> None:
    search = _FakeSearch(results=[_result(f"c{i}") for i in range(5)])
    inj = MemoryInjector(search)
    assert len(inj.inject_for_tier(IntentTier.L1, "端口")) == 1
    assert len(inj.inject_for_tier(IntentTier.L2, "端口")) == 3
    assert [c["top_k"] for c in search.calls] == [1, 3]


def test_injector_timeout_returns_empty() -> None:
    search = _FakeSearch(results=[_result("c1")], delay_ms=80)
    inj = MemoryInjector(search, timeout_ms=10)
    assert inj.inject_for_tier(IntentTier.L2, "端口") == []  # A6 超时空注入
    assert len(search.calls) == 1  # 检索确实发生（只是结果被丢弃）


def test_injector_format_result_plain() -> None:
    r = _result("c1")
    text = MemoryInjector.format_result(r)
    assert "[长期记忆 · 来源 events/cards/c1.md · 链: 服务器部署 · 2026-08-10]" in text
    assert "端口 8080" in text


def test_injector_format_result_prefers_branch_summary() -> None:
    r = _result("c1", branch_summary="部署已完成，端口 8080 生效。")
    text = MemoryInjector.format_result(r)
    assert "果: 部署已完成，端口 8080 生效。" in text
    assert "端口 8080" in text


def test_injector_accepts_string_tier() -> None:
    search = _FakeSearch(results=[_result("c1")])
    inj = MemoryInjector(search)
    assert len(inj.inject_for_tier("L1", "端口")) == 1
