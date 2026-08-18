"""LLM Wiki 知识库支线测试：WikiEntry 读写 / 条文切块 / 倒排检索 / 版本链 / 图件。"""

from __future__ import annotations

from memory.models import WikiEntry
from memory.tokenize import tokenize
from memory.wiki import WikiStore, WikiSearch, split_spec_sections, wiki_id


def _entry(entry_id: str = "wk-spec1", **kw) -> WikiEntry:
    base = {
        "id": entry_id,
        "kind": "spec",
        "title": "城乡规划用地分类标准",
        "content": "第1章 总则\n第1.1条 本标准的适用范围为城乡规划用地分类。\n第2章 分类\n第2.1条 用地分为居住用地、公共管理与公共服务用地。",
        "spec_id": "GB-50137-2011",
        "level": "national",
    }
    base.update(kw)
    return WikiEntry(**base)


def _concept(entry_id: str = "wk-con1", **kw) -> WikiEntry:
    base = {
        "id": entry_id,
        "kind": "concept",
        "title": "三区三线",
        "content": "三区三线是国土空间规划中的概念：农业空间、生态空间、城镇空间三区，"
                  "以及永久基本农田、生态保护红线、城镇开发边界三条控制线。",
        "tags": ("master", "terminology"),
        "entities": ("三区三线", "生态保护红线", "永久基本农田"),
    }
    base.update(kw)
    return WikiEntry(**base)


# —— 条文切块 ——


def test_split_spec_sections_structural() -> None:
    text = (
        "第1章 总则\n"
        "第1.1条 适用范围。\n"
        "第1.2条 术语定义。\n"
        "第2章 分类\n"
        "第2.1条 居住用地分类。\n"
    )
    sections = split_spec_sections(text)
    paths = [p for p, _ in sections]
    assert "第1章 总则/第1.1条 适用范围" in paths
    assert "第1章 总则/第1.2条 术语定义" in paths
    assert "第2章 分类/第2.1条 居住用地分类" in paths
    # 条文按结构切，不按 token 硬切
    assert len(sections) == 3


def test_split_spec_sections_unstructured_fallback() -> None:
    text = "没有章节结构的一段纯文本内容，没有标题。"
    sections = split_spec_sections(text)
    assert len(sections) == 1
    assert sections[0][0] == "前言"


def test_split_spec_sections_chinese_zero_article() -> None:
    """P1b：'第一百零一条' 必须被识别为条文标题（旧正则缺 零 漏配）。"""
    text = "第一条 总则\n内容A\n第一百零一条 附则\n内容B\n"
    sections = split_spec_sections(text)
    paths = [p for p, _ in sections]
    assert any("第一百零一条 附则" in p for p in paths)


def test_split_spec_sections_keeps_preamble_with_chapters() -> None:
    """P1b：有章节时头部前言不再被丢弃。"""
    text = "为规范城市防灾减灾工作，制定本标准。\n第一章 总则\n第一条 目的\n内容\n"
    sections = split_spec_sections(text)
    assert sections[0][0] == "前言"
    assert any("第一章 总则" in p for p, _ in sections)


def test_split_spec_sections_no_leading_slash() -> None:
    """P1b：无章时节/条路径不带前导斜杠（旧实现产出 '/第X节 …'）。"""
    text = "第一节 一般规定\n第一条 内容\n"
    sections = split_spec_sections(text)
    paths = [p for p, _ in sections]
    assert paths == ["第一节 一般规定/第一条 内容"]
    assert not any(p.startswith("/") for p in paths)


# —— WikiStore 读写 ——


def test_write_read_roundtrip(tmp_path) -> None:
    store = WikiStore(tmp_path / "wiki")
    entry = _concept()
    path = store.write_entry(entry)
    assert path.exists()
    got = store.read_entry(entry.id)
    assert got is not None
    assert got.title == "三区三线"
    assert got.content == entry.content
    assert got.entities == ("三区三线", "生态保护红线", "永久基本农田")
    store.close()


def test_write_idempotent_same_id(tmp_path) -> None:
    store = WikiStore(tmp_path / "wiki")
    store.write_entry(_concept())
    store.write_entry(_concept(content="更新后的内容"))
    entries = store.all_entries()
    assert len(entries) == 1
    assert entries[0].content == "更新后的内容"
    store.close()


def test_plain_md_is_source_of_truth(tmp_path) -> None:
    """明文真源：删掉索引目录，重读条目不丢。"""
    import shutil

    store = WikiStore(tmp_path / "wiki")
    entry = _concept()
    store.write_entry(entry)
    store.close()
    # 删除索引（模拟损坏/重建）
    shutil.rmtree(tmp_path / "wiki" / ".index")
    store2 = WikiStore(tmp_path / "wiki")  # 重建索引
    got = store2.read_entry(entry.id)
    assert got is not None and got.title == "三区三线"
    store2.close()


# —— 条文倒排 ——


def test_spec_reindexes_sections(tmp_path) -> None:
    store = WikiStore(tmp_path / "wiki")
    store.write_entry(_entry())
    assert store.section_count("wk-spec1") == 2  # 第1章下1.1条 + 第2章下2.1条 = 2 条文
    text = store.section_text("wk-spec1", "第1章 总则/第1.1条 本标准的适用范围为城乡规划用地分类")
    assert text is not None and "适用范围" in text
    store.close()


def test_fts_index_built(tmp_path) -> None:
    store = WikiStore(tmp_path / "wiki")
    store.write_entry(_entry())
    rows = store._exec(
        "SELECT COUNT(*) FROM wiki_fts WHERE entry_id = ?", ["wk-spec1"]
    ).fetchone()
    assert int(rows[0]) > 0  # 条文入 FTS5 索引
    store.close()


# —— WikiSearch 检索 ——


def test_search_hits_section_via_inverted_index(tmp_path) -> None:
    store = WikiStore(tmp_path / "wiki")
    store.write_entry(_entry())
    store.write_entry(_concept())
    search = WikiSearch(store)
    # "居住用地"只出现在第2.1条 → 验证条文级溯源精确命中
    results = search.search("居住用地")
    assert len(results) >= 1
    top = results[0]
    assert top.entry_id == "wk-spec1"
    assert "第2.1条" in top.section_path  # 条文级溯源
    assert top.spec_id == "GB-50137-2011"
    # 通用词"用地分类"两条文都含 → 至少命中 spec，且是条文级
    results2 = search.search("用地分类")
    assert len(results2) >= 1
    assert all("条" in r.section_path for r in results2)  # 命中都是条文
    store.close()


def test_search_concept_matches_plain_entry(tmp_path) -> None:
    store = WikiStore(tmp_path / "wiki")
    store.write_entry(_concept())
    search = WikiSearch(store)
    results = search.search("什么是生态保护红线")
    assert len(results) >= 1
    assert results[0].entry_id == "wk-con1"
    store.close()


def test_search_level_filter(tmp_path) -> None:
    store = WikiStore(tmp_path / "wiki")
    store.write_entry(_entry())  # national
    store.write_entry(_concept(id="wk-prov", level="province", title="省级概念"))
    search = WikiSearch(store)
    results = search.search("用地 概念", level="province")
    assert all(r.level == "province" for r in results)
    store.close()


def test_search_empty_query_returns_none(tmp_path) -> None:
    store = WikiStore(tmp_path / "wiki")
    search = WikiSearch(store)
    assert search.search("") == []
    store.close()


# —— 版本链 + 图件 ——


def test_supersede_entry_keeps_history(tmp_path) -> None:
    store = WikiStore(tmp_path / "wiki")
    store.write_entry(_entry(entry_id="wk-old"))
    store.write_entry(_entry(entry_id="wk-new", title="新版标准"))
    assert store.supersede_entry("wk-old", "wk-new") is True
    old = store.read_entry("wk-old")
    assert old is not None
    assert old.superseded_by == "wk-new"
    assert old.invalid_at is not None  # 保留审计，不删
    assert store.read_entry("wk-new") is not None
    store.close()


def test_figures_reference(tmp_path) -> None:
    store = WikiStore(tmp_path / "wiki")
    store.write_entry(_entry())
    store.add_figure("wk-spec1", "GB-3", "figures/GB-3-用地分类示意图.png", "用地分类示意图")
    figs = store.figures_of("wk-spec1")
    assert figs == [("GB-3", "figures/GB-3-用地分类示意图.png", "用地分类示意图")]
    store.close()


def test_delete_entry_removes_index(tmp_path) -> None:
    store = WikiStore(tmp_path / "wiki")
    store.write_entry(_entry())
    assert store.delete_entry("wk-spec1") is True
    assert store.read_entry("wk-spec1") is None
    assert store.section_count("wk-spec1") == 0
    store.close()


# —— 实体传导链（验收 #4） ——


def _chain_store(tmp_path) -> WikiStore:
    """四篇条目：耕地保有量体系（传导链）+ 一篇无关条目。"""
    store = WikiStore(tmp_path / "wiki")
    store.write_entry(_concept("wk-chain-target", title="耕地保有量指标",
                               entities=("耕地保有量", "省级约束")))
    store.write_entry(_concept("wk-chain-prov", title="省级耕地保护约束",
                               entities=("耕地保有量", "省级约束", "约束")))
    store.write_entry(_concept("wk-chain-city", title="市级耕地落实",
                               entities=("耕地保有量", "市级落实")))
    store.write_entry(_concept("wk-chain-other", title="城市绿化管理",
                               entities=("绿化",)))
    return store


def test_related_by_entities_chain_order(tmp_path) -> None:
    store = _chain_store(tmp_path)
    engine = WikiSearch(store)
    hits = engine.related_by_entities("wk-chain-target")
    # 共享 2 实体的省级条目在前，共享 1 实体的市级条目在后
    assert [h.entry_id for h in hits] == ["wk-chain-prov", "wk-chain-city"]
    assert hits[0].score == 2.0
    assert hits[1].score == 1.0
    assert "耕地保有量" in hits[0].snippet
    # 无关条目不进入传导链
    assert "wk-chain-other" not in [h.entry_id for h in hits]
    store.close()


def test_related_by_entities_min_shared_and_k(tmp_path) -> None:
    store = _chain_store(tmp_path)
    engine = WikiSearch(store)
    assert len(engine.related_by_entities("wk-chain-target", min_shared=2)) == 1
    assert len(engine.related_by_entities("wk-chain-target", top_k=1)) == 1
    assert engine.related_by_entities("wk-chain-target", min_shared=3) == []
    store.close()


def test_related_by_entities_no_entities_or_unknown(tmp_path) -> None:
    store = _chain_store(tmp_path)
    engine = WikiSearch(store)
    # 目标无实体 → 无传导链
    store.write_entry(_concept("wk-chain-none", title="无实体条目", entities=()))
    assert engine.related_by_entities("wk-chain-none") == []
    # 不存在的条目 id
    assert engine.related_by_entities("wk-no-such") == []
    store.close()


def test_related_by_entities_excludes_pending(tmp_path) -> None:
    store = _chain_store(tmp_path)
    store.write_entry(_concept("wk-chain-pend", title="待审省级约束",
                               entities=("耕地保有量", "省级约束"),
                               status="pending"))
    engine = WikiSearch(store)
    hits = engine.related_by_entities("wk-chain-target")
    assert "wk-chain-pend" not in [h.entry_id for h in hits]
    store.close()


# —— wiki_id 稳定性 ——


def test_wiki_id_deterministic() -> None:
    assert wiki_id("三区三线", "concept") == wiki_id("三区三线", "concept")
    assert wiki_id("三区三线", "concept") != wiki_id("三区三线", "spec")
    assert wiki_id("三区三线") != wiki_id("永久基本农田")


# —— tokenize 与 wiki 兼容 ——


def test_wiki_tokenize_works_with_zh() -> None:
    toks = tokenize("生态保护红线划定")
    assert "生态" in toks
    assert "保护" in toks
