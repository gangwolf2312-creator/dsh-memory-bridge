"""注入利用审计（§9.7 实证地基）：规则判定"注入是否被模型真正利用"，零 LLM。

信号（有噪音但够用）：
- 输出包含注入卡的强数字 token（如 8080）→ used
- 输出命中注入卡 ≥2 个内容词元（jieba，长度≥2）→ used
- 否则 → unused

audit_summary：从 decision_log 聚合 inject_hit / inject_used / extract_skip / extract_cost，
两周窗口出一份"记忆健康"指标——这是 §9.7 经验校准的数据来源。
"""

from __future__ import annotations

import datetime as _dt
import re

from memory.models import SearchResult
from memory.store import MemoryStore
from memory.tokenize import tokenize

__all__ = ["detect_inject_usage", "audit_summary"]

_NUM_RE = re.compile(r"^[0-9]+$")

# 去噪停用词（长度>=2 但无信息量的词元，不参与"强词元"判定）
_STOP = {
    "这个", "那个", "一下", "一点", "一些", "一个", "什么", "怎么",
    "还是", "可以", "应该", "觉得", "认为", "知道", "我们", "你们",
    "他们", "没有", "不是", "就是", "已经", "现在", "然后", "因为",
}


def detect_inject_usage(
    search_results: list[SearchResult], reply_text: str,
    *, min_strong: int = 2,
) -> dict[str, bool]:
    """每个注入命中卡 → 模型输出是否真的用到了它（{card_id: bool}）。

    去噪信号（§9.7 治理闭环地基）：
    - 强词元（jieba 长度>=2，非停用词）命中 >= min_strong → used
    - 数字命中升级：数字 + 至少 1 个强词元同时命中 → used；
      纯数字需 >= 2 个不同数字（弱信号加倍）→ used；单个数字 → unused
    - 否则 → unused
    """
    out: dict[str, bool] = {}
    reply = reply_text or ""
    for res in search_results:
        tokens = set(tokenize(f"{res.title} {res.snippet}"))
        digits = [t for t in tokens if _NUM_RE.fullmatch(t)]
        strong = [
            t for t in tokens
            if len(t) >= 2 and t not in _STOP and not _NUM_RE.fullmatch(t)
        ]
        strong_hits = sum(1 for t in strong if t in reply)
        if strong_hits >= min_strong:
            out[res.card_id] = True
            continue
        digit_hits = [d for d in digits if d in reply]
        if digit_hits:
            # 数字是弱信号：需 词元共同命中 或 多个不同数字（防 "8080 恰好出现"）
            out[res.card_id] = strong_hits >= 1 or len(set(digit_hits)) >= 2
            continue
        out[res.card_id] = False
    return out


def audit_summary(store: MemoryStore, *, days: int = 14) -> dict[str, float | int]:
    """从 decision_log 聚合注入/提取审计指标（默认两周窗口）。"""
    cutoff = (
        _dt.datetime.now().astimezone() - _dt.timedelta(days=days)
    ).isoformat(timespec="seconds")
    stats: dict[str, float | int] = {
        "inject_hits": 0, "inject_used": 0, "inject_unused": 0,
        "extract_skips": 0, "extract_runs": 0,
    }
    for entry in store.decision_log():
        if entry["ts"] < cutoff:
            continue
        topic = entry["topic"]
        if topic == "inject_hit":
            stats["inject_hits"] += 1
        elif topic == "inject_used":
            # 详情格式 "{card_id}: used|unused"——先判 unused，避免 "unused" 含 "used" 误判
            if ": unused" in entry["detail"]:
                stats["inject_unused"] += 1
            elif ": used" in entry["detail"]:
                stats["inject_used"] += 1
        elif topic == "extract_skip":
            stats["extract_skips"] += 1
        elif topic == "extract_cost":
            stats["extract_runs"] += 1
    denom = stats["inject_used"] + stats["inject_unused"]
    if denom:
        stats["inject_used_rate"] = round(stats["inject_used"] / denom, 3)
    total_runs = stats["extract_runs"] + stats["extract_skips"]
    if total_runs:
        stats["skip_rate"] = round(stats["extract_skips"] / total_runs, 3)
    return stats
