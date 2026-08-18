"""中文分词器契约测试（DESIGN §4.2：中文分词先行，禁空格分词）。"""

from __future__ import annotations

from memory.tokenize import tokenize


def test_ascii_words_split_and_lowercase() -> None:
    toks = tokenize("BM25 Search Engine")
    assert "bm25" in toks
    assert "search" in toks
    assert "engine" in toks


def test_chinese_sentence_segmented_by_words() -> None:
    text = "我今天下午去公园散步顺便买了一杯咖啡"
    toks = tokenize(text)
    assert "今天" in toks
    assert "公园" in toks
    assert "散步" in toks
    assert "咖啡" in toks
    # 禁止空格分词：整句不会被切成英文单词
    assert "我今天下午去公园散步顺便买了一杯咖啡" not in toks


def test_mixed_chinese_ascii() -> None:
    toks = tokenize("CGAOS 记忆系统 128GB")
    assert "cgaos" in toks
    assert "记忆" in toks
    assert "128gb" in toks


def test_punctuation_stripped() -> None:
    toks = tokenize("你好，世界！Hello, world.")
    assert "你好" in toks
    assert "hello" in toks
