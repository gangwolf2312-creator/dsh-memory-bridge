"""画像层 + 人格库补测（P2：profile.py / persona.py 此前零直接测试）。

- profile：Profile 渲染 / to_md ↔ parse_profile 往返、ProfileStore 保存/草稿/
  审批（version+1）/驳回（移入 rejected）
- persona：parse_persona、PersonaLibrary 排序、PersonaSelector 显式点名 >
  关键词命中 > 默认人格
"""

from __future__ import annotations

import pytest

from memory.persona import PersonaLibrary, PersonaSelector, parse_persona
from memory.profile import (
    Dimension,
    Profile,
    ProfileStore,
    parse_profile,
)

# —— profile ——


def _profile(**kw) -> Profile:
    base = {
        "summary": "用户是规划领域工程师，偏好结构化输出。",
        "updated_at": "2026-08-15T10:00:00",
        "version": 1,
        "status": "approved",
        "source_refs": ("events/cards/evt-1.md",),
        "mbti": "ISTJ",
        "dimensions": (Dimension("ei", "外向-内向", 0.8, "内向"),),
    }
    base.update(kw)
    return Profile(**base)


def test_render_f_block_summary_only() -> None:
    p = Profile(summary="  简洁摘要  ")
    assert p.render_f_block() == "简洁摘要"


def test_render_f_block_with_persona() -> None:
    p = _profile()
    block = p.render_f_block()
    assert block.startswith("用户是规划领域工程师")
    assert "人格多边形：ISTJ（ei=0.80）" in block


def test_profile_to_md_parse_roundtrip() -> None:
    p = _profile()
    parsed = parse_profile(p.to_md())
    assert parsed is not None
    assert parsed.summary == p.summary
    assert parsed.version == 1
    assert parsed.status == "approved"
    assert parsed.mbti == "ISTJ"
    assert parsed.source_refs == ("events/cards/evt-1.md",)
    assert len(parsed.dimensions) == 1
    assert parsed.dimensions[0].key == "ei"
    assert parsed.dimensions[0].value == 0.8
    assert parsed.dimensions[0].anchor == "内向"


def test_parse_profile_invalid() -> None:
    assert parse_profile("没有 front matter") is None
    assert parse_profile("---\nversion: 1\n---\n") is None  # 空摘要


def test_profile_store_save_load_approve_version_bump(tmp_path) -> None:
    store = ProfileStore(tmp_path / "memory")
    store.save(_profile(version=1), approve=True)
    loaded = store.load()
    assert loaded is not None
    assert loaded.status == "approved"
    assert loaded.version == 1
    # 再次审批：version+1
    store.save(_profile(summary="更新后的摘要"), approve=True)
    assert store.load().version == 2
    assert store.load().summary == "更新后的摘要"


def test_profile_store_draft_flow(tmp_path) -> None:
    store = ProfileStore(tmp_path / "memory")
    draft = _profile(status="draft", summary="草稿摘要")
    path = store.write_draft(draft)
    assert path.exists()
    name = path.name
    assert name.startswith("PROFILE.draft-")
    drafts = store.list_drafts()
    assert len(drafts) == 1
    assert drafts[0][1].summary == "草稿摘要"
    assert store.read_draft(name) is not None
    assert store.read_draft("不存在的草稿.md") is None


def test_profile_store_approve_draft(tmp_path) -> None:
    store = ProfileStore(tmp_path / "memory")
    path = store.write_draft(_profile(status="draft", summary="待审批摘要"))
    approved = store.approve(path.name)
    assert approved.status == "approved"
    assert store.load().status == "approved"
    assert store.load().summary == "待审批摘要"
    # 草稿保留（可找回）
    assert store.read_draft(path.name) is not None


def test_profile_store_approve_missing_draft_raises(tmp_path) -> None:
    store = ProfileStore(tmp_path / "memory")
    with pytest.raises(KeyError):
        store.approve("不存在.md")


def test_profile_store_reject_moves_draft(tmp_path) -> None:
    store = ProfileStore(tmp_path / "memory")
    path = store.write_draft(_profile(status="draft", summary="被驳回的摘要"))
    dst = store.reject(path.name)
    assert dst.exists()
    assert store.list_drafts() == []  # 草稿区不再有
    assert store.read_draft(path.name) is None


# —— persona ——


_PERSONA_MD = """---
id: concise
name: 简洁型
mbti: INTJ
when: 简洁/精炼/短回答
default: false
dimensions:
  - key: style  value: 0.2
  - key: form   value: 0.3
---
回答要简洁，直击要点，不绕弯子。
"""


def test_parse_persona_full() -> None:
    p = parse_persona(_PERSONA_MD)
    assert p is not None
    assert p.id == "concise"
    assert p.name == "简洁型"
    assert p.mbti == "INTJ"
    assert p.when == ("简洁", "精炼", "短回答")
    assert p.default is False
    assert "直击要点" in p.discipline
    assert len(p.dimensions) == 2
    assert p.dimensions[0].key == "style"
    assert p.dimensions[0].value == 0.2


def test_parse_persona_invalid() -> None:
    assert parse_persona("无 front matter") is None
    assert parse_persona("---\nname: 无 id\n---\n有正文") is None  # 缺 id
    assert parse_persona("---\nid: x\n---\n") is None  # 缺正文


def test_persona_render_d_block() -> None:
    p = parse_persona(_PERSONA_MD)
    block = p.render_d_block()
    assert block.startswith("当前人格：简洁型（INTJ）")
    assert "行为纪律：回答要简洁" in block


def _write_personas(tmp_path) -> PersonaLibrary:
    root = tmp_path / "memory"
    pdir = root / "personas"
    pdir.mkdir(parents=True)
    (pdir / "a.md").write_text(
        "---\nid: a\nname: A型\nwhen: 技术/编码\n---\n纪律 A。\n", encoding="utf-8"
    )
    (pdir / "d.md").write_text(
        "---\nid: d\nname: D型\ndefault: true\n---\n纪律 D。\n", encoding="utf-8"
    )
    (pdir / "b.md").write_text(
        "---\nid: b\nname: B型\nwhen: 技术\n---\n纪律 B。\n", encoding="utf-8"
    )
    return PersonaLibrary(root)


def test_library_list_sorting_default_first(tmp_path) -> None:
    lib = _write_personas(tmp_path)
    ids = [p.id for p in lib.list()]
    assert ids == ["d", "a", "b"]  # default 优先，其余 id 字典序
    assert lib.get("b") is not None
    assert lib.get("nope") is None
    assert lib.default().id == "d"


def test_selector_explicit_override(tmp_path) -> None:
    lib = _write_personas(tmp_path)
    sel = PersonaSelector(lib)
    # 显式点名（动词 + 名字）覆盖关键词
    picked = sel.select("请用 A型 的风格回答")
    assert picked is not None and picked.id == "a"


def test_selector_keyword_hits(tmp_path) -> None:
    lib = _write_personas(tmp_path)
    sel = PersonaSelector(lib)
    # 关键词命中：b 命中"技术"1 次，a 命中"技术/编码"2 次 → a 优先
    picked = sel.select("这段技术方案涉及编码实现")
    assert picked is not None and picked.id == "a"
    # 无命中 → 默认人格
    assert sel.select("今天天气怎么样").id == "d"


def test_selector_empty_library(tmp_path) -> None:
    lib = PersonaLibrary(tmp_path / "memory")  # 无 personas 目录
    assert PersonaSelector(lib).select("随便说点什么") is None
