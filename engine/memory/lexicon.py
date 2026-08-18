"""国土空间规划术语词典（WIKI-DESIGN §4.4）：内置术语表喂 jieba。

不建外部服务：纯本地词表，tokenize 模块导入时（任何 jieba.cut 之前）幂等注入，
让领域复合词保持整词切分（如 "三区三线" → 1 个 token，而非 "三区/三线"），
提升 BM25 / FTS5 检索精度与跨措辞召回（别名 "三条控制线" 同样整词入库）。

术语词典更新周任务（schedule）只改本表即可，无需改代码。
"""

from __future__ import annotations

import jieba

__all__ = ["LANDUSE_TERMS", "load_lexicon"]

# 国土空间规划领域术语（复合词为主；喂 jieba 强制整词切分）
LANDUSE_TERMS: tuple[str, ...] = (
    # 空间格局
    "三区三线", "三条控制线", "双评价", "国土空间规划", "国土空间用途管制",
    "用途管制", "用途分区", "城镇空间", "农业空间", "生态空间",
    "生态保护红线", "永久基本农田", "城镇开发边界", "管控边界", "多规合一",
    "主体功能区",
    # 规划类型与传导
    "总体规划", "专项规划", "详细规划", "上位规划", "规划传导", "村庄规划",
    "中心城区",
    # 指标与实施
    "耕地保有量", "建设用地", "农用地", "开发强度", "国土综合整治", "生态修复",
)

# 注入词频：高于 jieba 默认词频，保证整词切分优先（词表内前缀碎片按 0 频占位）
_TERM_FREQ = 10000
_TERM_TAG = "n"

_loaded = False


def load_lexicon() -> None:
    """把术语表注入 jieba（幂等；首次调用后置位，避免重复 add_word 累积）。"""
    global _loaded
    if _loaded:
        return
    for word in LANDUSE_TERMS:
        jieba.add_word(word, freq=_TERM_FREQ, tag=_TERM_TAG)
    _loaded = True
