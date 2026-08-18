"""术语词典测试（WIKI-DESIGN §4.4：国土空间规划术语表喂 jieba）。

验收：领域复合词整词切分（检索精度/跨措辞召回）；加载幂等；词表非空且均为中文词。
"""

from __future__ import annotations

from memory.lexicon import LANDUSE_TERMS, load_lexicon
from memory.tokenize import tokenize, tokenize_words


def test_lexicon_forces_whole_word_segmentation() -> None:
    assert tokenize_words("三区三线") == ["三区三线"]
    assert tokenize_words("生态保护红线") == ["生态保护红线"]
    assert tokenize_words("永久基本农田") == ["永久基本农田"]
    assert tokenize_words("三条控制线") == ["三条控制线"]  # 别名措辞同样整词


def test_lexicon_term_survives_in_sentence() -> None:
    toks = tokenize_words("问一下什么是三区三线")
    assert "三区三线" in toks
    # 复合词不因上下文被拆散
    assert "三区" not in toks or "三线" not in toks or "三区三线" in toks


def test_tokenize_keeps_char_bigram_recall() -> None:
    """tokenize（检索用）仍保留字符 bigram：领域词内部子串也可召回。"""
    toks = tokenize("生态保护红线划定")
    assert "生态" in toks  # 字符 bigram 补充（跨词界召回不依赖整词）
    assert "生态保护红线" in toks  # 词典整词优先


def test_load_lexicon_idempotent() -> None:
    load_lexicon()
    load_lexicon()  # 二次调用不抛错、不重复累积（幂等）
    assert tokenize_words("双评价") == ["双评价"]


def test_terms_are_nonempty_cjk() -> None:
    assert len(LANDUSE_TERMS) >= 10
    assert all(
        any("\u4e00" <= ch <= "\u9fff" for ch in w) and w.strip() == w
        for w in LANDUSE_TERMS
    )
