"""V3.5 分流改造测试（PROGRESS-HANDOFF §4 / WIKI-DESIGN §13）：一次提取 → cards + wiki 双输出。

覆盖验收项：
  #2  知识类内容（"什么是三区三线"）→ wiki 条目，不产记忆卡，可检索；
  #7  同一概念措辞漂移（"三区三线"/"三条控制线"）→ 别名吸收合并到同一条目；
  #8  一次提取同时产出 cards + wiki，不额外调用；
  兼 旧 fake 裸卡列表兼容、批量双分支、低置信知识 → pending + promote、supersedes 版本链。
"""

from __future__ import annotations

import json

from core.backend import BackendResult
from memory.backends import CloudConfig
from memory.extract import ExtractionResult, LLMExtractor, MemoryWritePipeline
from memory.models import MemoryCard, MemoryRun, WikiEntry
from memory.search import MemorySearch
from memory.store import MemoryStore
from memory.strategy import CloudStrategy
from memory.wiki import WikiSearch, WikiStore


def _run(user: str = "", reply: str = "", run_id: str = "run-w1") -> MemoryRun:
    return MemoryRun(
        run_id=run_id, session_id="s1", user_text=user, reply_text=reply, tier="L1"
    )


def _cloud_cfg(**kw) -> CloudConfig:
    base = {"base_url": "https://api.deepseek.com/v1", "api_key": "test-key"}
    base.update(kw)
    return CloudConfig(**base)


def _card(cid: str, title: str, content: str, **kw) -> MemoryCard:
    return MemoryCard(
        id=cid, kind="event", title=title, content=content,
        source_path=f"events/cards/{cid}.md", created_at="2026-08-01T10:00:00",
        parent_id="", run_id="", source_part="assistant", confidence=0.9,
        evidence="explicit", corroborations=0, **kw,
    )


def _concept_raw(**kw) -> dict:
    base = {
        "kind": "concept",
        "title": "三区三线",
        "content": "三区三线是国土空间规划中的概念：农业空间、生态空间、城镇空间三区，"
                   "以及永久基本农田、生态保护红线、城镇开发边界三条控制线。",
        "tags": ["master", "terminology"],
        "entities": ["三区三线", "生态保护红线", "永久基本农田"],
        "aliases": ["三条控制线"],
        "evidence": "explicit",
        "source_part": "user",
    }
    base.update(kw)
    return base


def _card_raw(**kw) -> dict:
    base = {
        "title": "喜欢喝茶", "content": "用户喜欢喝茶", "evidence": "explicit",
        "chain": "生活习惯", "entities": [], "supersedes": "", "ended": False,
        "source_part": "user",
    }
    base.update(kw)
    return base


class _FakeDualBackend:
    """固定返回 {cards, wiki} 双分支 JSON 的假后端（模拟 LLM 分流输出）。"""

    def __init__(self, payload: dict):
        self.payload = payload
        self.calls = 0

    def complete(self, messages, *, temperature=0.0, max_tokens=512, timeout=None):
        self.calls += 1
        return BackendResult(text=json.dumps(self.payload, ensure_ascii=False))


class _FakeDualExtractor:
    """固定返回一份 ExtractionResult 的假提取器（管道测试用）。"""

    def __init__(self, result: ExtractionResult):
        self.result = result

    def extract(self, run: MemoryRun):
        return self.result


class _SeqExtractor:
    """按调用顺序返回多份 ExtractionResult（别名吸收跨 run 测试用）。"""

    def __init__(self, results: list[ExtractionResult]):
        self._results = list(results)
        self.i = 0

    def extract(self, run: MemoryRun):
        r = self._results[min(self.i, len(self._results) - 1)]
        self.i += 1
        return r


def _pipe(
    store: MemoryStore,
    wiki: WikiStore,
    extractor,
    run: MemoryRun,
) -> None:
    pipe = MemoryWritePipeline(
        store, extractor=extractor, enabled=True, worker=False, wiki_store=wiki
    )
    store.insert_run(run)
    pipe.process_staged(1)
    pipe.close()


# —— 验收 #8：一次提取双输出，不额外调用 ——


def test_extract_dual_branch_single_call() -> None:
    backend = _FakeDualBackend(
        {"cards": [_card_raw()], "wiki": [_concept_raw()]}
    )
    ex = LLMExtractor(backend, strategy=CloudStrategy(_cloud_cfg()))
    result = ex.extract(_run(user="什么是三区三线", reply="三区三线是……"))

    assert isinstance(result, ExtractionResult)
    assert backend.calls == 1  # 一次调用同时产出 cards + wiki
    assert len(result.cards) == 1
    assert result.cards[0][0].content == "用户喜欢喝茶"
    assert len(result.wiki_entries) == 1
    w = result.wiki_entries[0]
    assert w.kind == "concept"
    assert w.title == "三区三线"
    assert w.status == "active"
    assert w.aliases == ("三条控制线",)
    assert w.entities == ("三区三线", "生态保护红线", "永久基本农田")
    assert w.confidence == 0.95  # explicit + source_part=user


def test_extract_missing_wiki_branch_compat() -> None:
    """旧模型只回 cards（无 wiki 键）→ wiki 分支空，不报错。"""
    ex = LLMExtractor(
        _FakeDualBackend({"cards": [_card_raw()]}),
        strategy=CloudStrategy(_cloud_cfg()),
    )
    result = ex.extract(_run())
    assert isinstance(result, ExtractionResult)
    assert len(result.cards) == 1
    assert result.wiki_entries == []


def test_extract_array_empty_tolerated() -> None:
    """模型'无可提取'输出裸 []（v3.5 实测形态）→ 视为空提取，不炸。"""
    class _ArrayBackend:
        def complete(self, messages, *, temperature=0.0, max_tokens=512, timeout=None):
            return BackendResult(text="[]")

    ex = LLMExtractor(_ArrayBackend(), strategy=CloudStrategy(_cloud_cfg()))
    result = ex.extract(_run())
    assert isinstance(result, ExtractionResult)
    assert result.cards == []
    assert result.wiki_entries == []


def test_extract_batch_dual_branch() -> None:
    payload = {
        "results": [
            {
                "idx": 0,
                "cards": [_card_raw(content="用户喜欢喝茶")],
                "wiki": [_concept_raw()],
            },
            {"idx": 1, "cards": [], "wiki": []},
        ]
    }
    ex = LLMExtractor(
        _FakeDualBackend(payload), strategy=CloudStrategy(_cloud_cfg(batch_size=2))
    )
    out = ex.extract_batch([_run(run_id="run-b1"), _run(run_id="run-b2")])

    assert len(out) == 2
    assert out[0].cards[0][0].content == "用户喜欢喝茶"
    assert out[0].wiki_entries[0].title == "三区三线"
    assert out[1].cards == []
    assert out[1].wiki_entries == []


# —— 验收 #8 端到端：管道双写记忆库 + 知识库 ——


def test_pipeline_writes_both_stores(tmp_path) -> None:
    store = MemoryStore(tmp_path / "memory")
    wiki = WikiStore(tmp_path / "wiki")
    result = ExtractionResult(
        cards=[(_card("evt-run-1", "喜欢喝茶", "用户喜欢喝茶"), "生活习惯")],
        wiki_entries=[
            WikiEntry(
                id="wk-con1", kind="concept", title="三区三线",
                content="三区三线是国土空间规划中的概念：农业空间、生态空间、城镇空间三区，"
                        "以及永久基本农田、生态保护红线、城镇开发边界三条控制线。",
                tags=("master",), entities=("三区三线", "生态保护红线", "永久基本农田"),
                aliases=("三条控制线",),
            )
        ],
    )
    _pipe(
        store, wiki, _FakeDualExtractor(result),
        _run(user="什么是三区三线", reply="三区三线是……", run_id="run-1"),
    )

    assert store.read_card("evt-run-1").content == "用户喜欢喝茶"  # 记忆库：卡已写
    assert len(wiki.all_entries()) == 1  # 知识库：条目
    hits = WikiSearch(wiki).search("三区三线")
    assert hits and hits[0].title == "三区三线"
    wiki.close()


# —— 验收 #2：知识类内容走知识库，不产记忆卡 ——


def test_knowledge_goes_wiki_not_memory(tmp_path) -> None:
    store = MemoryStore(tmp_path / "memory")
    wiki = WikiStore(tmp_path / "wiki")
    result = ExtractionResult(
        cards=[],
        wiki_entries=[
            WikiEntry(
                id="wk-con1", kind="concept", title="三区三线",
                content="三区三线是国土空间规划中的概念。",
                entities=("三区三线", "生态保护红线", "永久基本农田"),
                aliases=("三条控制线",),
            )
        ],
    )
    _pipe(
        store, wiki, _FakeDualExtractor(result),
        _run(user="什么是三区三线", reply="三区三线是……", run_id="run-2"),
    )

    assert store.all_cards() == []  # 知识不污染记忆树
    assert len(wiki.all_entries()) == 1
    hits = WikiSearch(wiki).search("什么是三区三线")
    assert hits and hits[0].title == "三区三线"
    # 记忆检索查不到该知识（不产卡自然查不到）
    assert MemorySearch(store).search("三区三线") == []
    wiki.close()


# —— 验收 #7：同一概念措辞漂移 → 别名吸收合并同一条目 ——


def test_aliases_merge_same_concept(tmp_path) -> None:
    store = MemoryStore(tmp_path / "memory")
    wiki = WikiStore(tmp_path / "wiki")
    first = WikiEntry(
        id="wk-a", kind="concept", title="三区三线",
        content="三区三线是国土空间规划中的概念：农业空间、生态空间、城镇空间三区。",
        entities=("三区三线", "生态保护红线", "永久基本农田"),
    )
    second = WikiEntry(
        id="wk-b", kind="concept", title="三条控制线",  # 措辞漂移标题
        content="三条控制线指永久基本农田、生态保护红线、城镇开发边界。",
        entities=("生态保护红线", "永久基本农田"),
    )
    ex = _SeqExtractor(
        [
            ExtractionResult(cards=[], wiki_entries=[first]),
            ExtractionResult(cards=[], wiki_entries=[second]),
        ]
    )
    pipe = MemoryWritePipeline(
        store, extractor=ex, enabled=True, worker=False, wiki_store=wiki
    )
    store.insert_run(_run(user="什么是三区三线", run_id="run-a"))
    pipe.process_staged(1)
    store.insert_run(_run(user="三条控制线是什么", run_id="run-b"))
    pipe.process_staged(1)
    pipe.close()

    entries = wiki.all_entries()
    assert len(entries) == 1  # 合并：仍是同一 canonical
    merged = entries[0]
    assert merged.title == "三区三线"  # 首写标题保留
    assert "三条控制线" in merged.aliases  # 漂移措辞 → 别名吸收
    assert "生态保护红线" in merged.entities  # 实体取并集
    # 别名可检索（FTS body 含标题+别名）
    hits = WikiSearch(wiki).search("三条控制线")
    assert hits and hits[0].title == "三区三线"
    wiki.close()


def test_spec_requires_exact_title_no_fuzzy_merge(tmp_path) -> None:
    """spec 只精确匹配：标题不同 → 不合并（规范名必须唯一）。"""
    store = MemoryStore(tmp_path / "memory")
    wiki = WikiStore(tmp_path / "wiki")
    first = WikiEntry(
        id="wk-s1", kind="spec", title="城乡规划用地分类标准",
        content="第1章 总则\n第1.1条 适用范围。", spec_id="GB-50137-2011",
        level="national",
    )
    second = WikiEntry(
        id="wk-s2", kind="spec", title="城市用地分类与规划建设用地标准",
        content="第1章 总则\n第1.1条 适用范围。", spec_id="GB-50137-2011",
        level="national",
    )
    ex = _SeqExtractor(
        [
            ExtractionResult(cards=[], wiki_entries=[first]),
            ExtractionResult(cards=[], wiki_entries=[second]),
        ]
    )
    pipe = MemoryWritePipeline(
        store, extractor=ex, enabled=True, worker=False, wiki_store=wiki
    )
    store.insert_run(_run(run_id="run-s1"))
    pipe.process_staged(1)
    store.insert_run(_run(run_id="run-s2"))
    pipe.process_staged(1)
    pipe.close()

    assert len(wiki.all_entries()) == 2  # 标题不同 → 两条独立规范
    wiki.close()


# —— 低置信知识 → pending（待审），promote 后进检索 ——


def test_low_confidence_wiki_pending_and_promote(tmp_path) -> None:
    store = MemoryStore(tmp_path / "memory")
    wiki = WikiStore(tmp_path / "wiki")
    result = ExtractionResult(
        cards=[],
        wiki_entries=[
            WikiEntry(
                id="wk-p1", kind="concept", title="模糊概念",
                content="不确定的解释。", status="pending", confidence=0.6,
            )
        ],
    )
    _pipe(
        store, wiki, _FakeDualExtractor(result),
        _run(user="概念A", reply="可能是……", run_id="run-p1"),
    )

    # pending：明文落待审目录，不进检索
    assert (wiki.root / "pending" / "wk-p1.md").exists()
    assert (wiki.root / "concepts" / "wk-p1.md").exists() is False
    assert WikiSearch(wiki).search("模糊概念") == []
    got = wiki.read_entry("wk-p1")
    assert got is not None and got.status == "pending"

    # 审核通过 → active：移入正式目录、可检索
    promoted = wiki.promote_entry("wk-p1")
    assert promoted is not None and promoted.status == "active"
    assert promoted.confidence == 1.0
    assert not (wiki.root / "pending" / "wk-p1.md").exists()
    assert (wiki.root / "concepts" / "wk-p1.md").exists()
    hits = WikiSearch(wiki).search("模糊概念")
    assert hits and hits[0].title == "模糊概念"
    wiki.close()


def test_llm_inferred_wiki_goes_pending() -> None:
    """LLM 给 inferred/uncertain 证据 → _wiki_from_raw 直接判 pending。"""
    backend = _FakeDualBackend(
        {
            "cards": [],
            "wiki": [
                {
                    "kind": "concept", "title": "猜测概念", "content": "推断的解释",
                    "tags": [], "entities": [], "aliases": [], "evidence": "inferred",
                }
            ],
        }
    )
    ex = LLMExtractor(backend, strategy=CloudStrategy(_cloud_cfg()))
    result = ex.extract(_run())
    assert len(result.wiki_entries) == 1
    assert result.wiki_entries[0].status == "pending"
    assert result.wiki_entries[0].confidence < 0.9


# —— supersedes 版本链：标题 → 旧条目失效 ——


def test_supersedes_chain_via_title(tmp_path) -> None:
    store = MemoryStore(tmp_path / "memory")
    wiki = WikiStore(tmp_path / "wiki")
    old = WikiEntry(
        id="wk-old", kind="spec", title="城乡规划用地分类标准（旧版）",
        content="第1章 总则\n第1.1条 旧标准适用范围。", spec_id="GB-50137-2011",
        level="national",
    )
    wiki.write_entry(old)
    new = WikiEntry(
        id="wk-new", kind="spec", title="城乡规划用地分类标准",
        content="第1章 总则\n第1.1条 新标准适用范围。", spec_id="GB-50137-2011",
        level="national", supersedes="城乡规划用地分类标准（旧版）",
    )
    _pipe(
        store, wiki, _FakeDualExtractor(ExtractionResult(cards=[], wiki_entries=[new])),
        _run(run_id="run-s3"),
    )

    old_after = wiki.read_entry("wk-old")
    assert old_after is not None
    assert old_after.superseded_by == "wk-new"
    assert old_after.invalid_at is not None
    # 检索只出有效版本
    hits = WikiSearch(wiki).search("城乡规划用地分类标准")
    assert hits and hits[0].title == "城乡规划用地分类标准"
    wiki.close()


# —— 旧 fake 兼容：裸卡列表照常走管道（wiki 关闭/开启皆可） ——


def test_legacy_extractor_plain_list_ok(tmp_path) -> None:
    store = MemoryStore(tmp_path / "memory")
    wiki = WikiStore(tmp_path / "wiki")

    class _Legacy:
        def extract(self, run: MemoryRun):
            return [(_card("evt-l1", "t", "c"), "")]

    _pipe(store, wiki, _Legacy(), _run(user="u", reply="r", run_id="run-l1"))
    assert len(store.all_cards()) == 1
    assert wiki.all_entries() == []  # 裸卡列表无 wiki 分支
    wiki.close()


# —— 提示词含 wiki 分支（分流规则的唯一事实来源） ——


def test_prompts_contain_wiki_branch() -> None:
    from memory import extract as ex_mod

    assert '"wiki"' in ex_mod._EXTRACT_PROMPT
    assert "知识类内容" in ex_mod._EXTRACT_PROMPT
    assert '"wiki"' in ex_mod._BATCH_EXTRACT_PROMPT
    assert "kind=spec|concept|tutorial" in ex_mod._BATCH_EXTRACT_PROMPT
