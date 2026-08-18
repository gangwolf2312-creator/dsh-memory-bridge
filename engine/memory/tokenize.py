"""中文分词（DESIGN §4.2：中文分词先行，禁空格分词）。

策略：jieba 词元 + 字符 bigram 补充（查询词常跨 jieba 词边界，如"今天" vs "今天下午"）。
领域术语（国土空间规划）由 memory.lexicon 内置词典喂 jieba，整词切分（见 WIKI-DESIGN §4.4）。
以模块函数形式提供，便于后续替换为纯 n-gram / 自定义分词器。
"""

from __future__ import annotations

import logging
import re

import jieba

from memory.lexicon import load_lexicon

# 静默 jieba 初始化日志（"Building prefix dict ..." 等），避免 CLI/服务被 stderr 噪声污染
jieba.setLogLevel(logging.ERROR)

# 术语词典注入（幂等）：任何 jieba.cut 之前加载，保证领域复合词整词切分
load_lexicon()

_ASCII_RE = re.compile(r"[a-zA-Z0-9]+")
_CJK = ("\u4e00", "\u9fff")


def tokenize(text: str) -> list[str]:
    """jieba 分词 + ASCII 词切分 + CJK 字符 bigram 补充。
    - ASCII 词统一小写："BM25" → "bm25"；
    - 中文按词切分；
    - 整句 CJK 字符 unigram + bigram：跨 jieba 词边界及同义词召回补充
      （如 "橘猫叫年糕" → "猫叫"，解决查询词跨词界）
    - 纯标点/空白丢弃
    """
    tokens: list[str] = []
    for token in jieba.cut(text, cut_all=False):
        token = token.strip()
        if not token:
            continue
        if _ASCII_RE.fullmatch(token):
            tokens.append(token.lower())
        elif any(_CJK[0] <= ch <= _CJK[1] for ch in token):
            tokens.append(token)
    chars = [ch for ch in text if _CJK[0] <= ch <= _CJK[1]]
    if chars:
        # 字符 unigram：同义词/词形差异召回（如 "跑步" vs "夜跑"）
        tokens.extend(chars)
        if len(chars) >= 2:
            tokens.extend("".join(chars[i : i + 2]) for i in range(len(chars) - 1))
    return tokens


def tokenize_words(text: str) -> list[str]:
    """纯 jieba 词级分词（无 unigram/bigram 补充）——供 FTS5 索引/查询用。

    与 tokenize 的差异：不生成字符 n-gram。FTS5 倒排里字符 bigram（如"卡内"）
    是噪音 token，会造成错误匹配；词级 token 才适合全文索引。
    ASCII 统一小写；纯标点丢弃。
    """
    tokens: list[str] = []
    for token in jieba.cut(text, cut_all=False):
        token = token.strip()
        if not token:
            continue
        if _ASCII_RE.fullmatch(token):
            tokens.append(token.lower())
        elif any(_CJK[0] <= ch <= _CJK[1] for ch in token):
            tokens.append(token)
    return tokens
