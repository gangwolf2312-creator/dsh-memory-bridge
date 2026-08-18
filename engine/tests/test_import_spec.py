"""scripts/import_spec.py 单元测试（分类判定 + 幂等导入 + 条文级检索端到端）。

覆盖：front matter 解析 / spec_id 提取（含全角斜杠、下划线、行业前缀）/
层级判定 / 幂等覆盖 / 检索带条号 / 读整章。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.import_spec import (
    _ENTITY_STOP,
    _SPEC_ID_RE,
    build_entry,
    extract_entities,
    extract_spec_id,
    guess_level,
    parse_front_matter,
)

from memory.wiki import WikiSearch, WikiStore


# ---------- front matter ----------

def test_parse_front_matter_basic() -> None:
    text = """---
title: 城市抗震防灾规划标准GB50413-2007
date: 2007
doc_type: 标准规范
tags:
  - 防灾减灾
  - 强制性国标
---
正文第一行
第二行"""
    fields, body = parse_front_matter(text)
    assert fields["title"] == "城市抗震防灾规划标准GB50413-2007"
    assert fields["doc_type"] == "标准规范"
    assert fields["tags"] == ["防灾减灾", "强制性国标"]
    assert body == "正文第一行\n第二行"


def test_parse_front_matter_no_fence() -> None:
    text = "没有 front matter 的纯正文"
    fields, body = parse_front_matter(text)
    assert fields == {}
    assert body == text


# ---------- spec_id 提取 ----------

@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("城市抗震防灾规划标准GB50413-2007", "GB50413-2007"),
        ("测绘基本术语GBT 14911-2008 （节选）", "GB/T14911-2008"),
        ("GB/T 50137-2011 城市用地分类", "GB/T50137-2011"),
        ("GB／T51051-2014 水资源规划规范", "GB/T51051-2014"),
        ("GB_T28921-2012", "GB/T28921-2012"),
        ("建设项目交通影响评价技术标准 CJJT 141-2010", "CJJT141-2010"),
        ("第三次全国国土调查技术规程 TDT 1055-2019", "TDT1055-2019"),
        ("公路工程技术标准JTGB01-2014（节选）", "JTGB01-2014"),
        ("大遗址保护规划规范 WWZ 0072—2015", "WWZ0072—2015"),
        ("国家公园总体规划技术规范 LYT 3188-2020", "LYT3188-2020"),
        # P2：斜杠后缀形式（JGJ/T、CJJ/T、TB/T、GB/Z、DBxx/T）
        ("城市居住区规划设计标准 JGJ/T 100-2018", "JGJ/T100-2018"),
        ("城市道路绿化规划与设计规范 CJJ/T 75-97", "CJJ/T75-97"),
        ("铁路用地分类 TB/T 1012-2009", "TB/T1012-2009"),
        ("城市规划基础资料搜集规范 GB/Z 50112-2009", "GB/Z50112-2009"),
        ("湖北省城镇规划管理技术规定 DB42/T 500-2008", "DB42"),
        ("城市绿线管理办法（2002）", ""),
        ("划拨用地目录（2001）", ""),
    ],
)
def test_extract_spec_id(title: str, expected: str) -> None:
    assert extract_spec_id(title) == expected


# ---------- 层级判定 ----------

@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("城市抗震防灾规划标准GB50413-2007", "national"),
        ("四川省中华人民共和国文物保护法实施办法", "province"),
        ("北京市城市规划条例", "province"),
        ("杭州市城市绿线管理办法", "city"),
        ("临安县土地管理规定", "county"),
        # P2：乡镇层级（此前归 national）
        ("余杭镇土地利用总体规划", "township"),
        ("石桥乡宅基地管理办法", "township"),
        ("城市紫线管理办法（2003）", "national"),
    ],
)
def test_guess_level(title: str, expected: str) -> None:
    assert guess_level(title) == expected


# ---------- 实体提取 ----------

def test_extract_entities_drops_function_words() -> None:
    ents = extract_entities("城市抗震防灾规划标准GB50413-2007")
    assert "标准" not in ents
    assert "规划" not in ents
    assert any("抗震" in e or "防灾" in e for e in ents)


def test_entity_stopwords_keep_core_terms() -> None:
    """守护：停用词表不得吞掉核心领域术语（防将来过度扩充压垮概念条目实体）。"""
    core = ("三区三线", "耕地保有量", "生态保护红线", "国土空间用途管制", "永久基本农田", "双评价")
    for term in core:
        assert term not in _ENTITY_STOP, f"核心术语 {term} 被误加进停用词表"
    # 核心术语在标题里必须能被提取为实体
    assert "耕地保有量" in extract_entities("耕地保有量指标 2026")
    assert "三区三线" in extract_entities("三区三线划定技术指南")


# ---------- 端到端：幂等 + 检索 ----------

_SAMPLE = """---
title: 城市用地分类标准GB 50137-2011
doc_type: 标准规范
field: 用地
tags:
  - 用地分类
---
第一章 总则
第一条 为统一城市用地分类，制定本标准。
第二条 本标准适用于城市总体规划编制。
第二章 用地分类
第三条 城市建设用地分为居住用地、公共管理与公共服务用地、商业服务业设施用地等。
第四条 地块用途按主导功能划分。
"""


def _sample_entry() -> object:
    fields, body = parse_front_matter(_SAMPLE)
    return build_entry(
        Path("2000-01-01 城市用地分类标准GB 50137-2011.md"),
        str(fields["title"]), str(fields.get("doc_type", "")),
        str(fields.get("field", "")), list(fields.get("tags") or []), body,
    )


def test_import_idempotent_and_searchable(tmp_path: Path) -> None:
    store = WikiStore(tmp_path / "wiki")
    e1 = _sample_entry()
    p1 = store.write_entry(e1)
    assert p1.exists()
    # 幂等：同标题重导入 → 同一 id，明文文件不重复
    e2 = _sample_entry()
    p2 = store.write_entry(e2)
    assert p2 == p1
    assert len(list((tmp_path / "wiki" / "specs").glob("*.md"))) == 1

    # 条文级检索：带条号命中
    hits = WikiSearch(store).search("居住用地", top_k=3)
    assert hits, "应命中用地分类条文"
    top = hits[0]
    assert "第三条" in top.section_path or "用地分类" in top.section_path
    assert top.spec_id == "GB50137-2011"

    # 读整章
    text = store.section_text(top.entry_id, top.section_path)
    assert text and "居住用地" in text


def test_entry_has_expected_fields() -> None:
    e = _sample_entry()
    assert e.kind == "spec"
    assert e.status == "active"
    assert e.confidence == 1.0
    assert e.evidence == "explicit"
    assert e.source_part == "tool:import_spec"
    assert e.id == "wk-" + __import__("hashlib").sha1(
        f"spec|城市用地分类标准GB 50137-2011".encode()
    ).hexdigest()[:12]
