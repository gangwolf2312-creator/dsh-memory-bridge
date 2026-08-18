"""规则提炼（ADR-0013 D5②，V2 preferences.py 移植，零 LLM）。

触发词 → 偏好信号 → 聚合 ≥3 同类 → lesson_pending 提案 → 面板审批固化（promote_lesson）。
纯规则提取（本地，不抢 TTFT，不调用任何模型）。
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

import jieba

from memory.models import MemoryCard
from memory.store import MemoryStore, now_iso

__all__ = [
    "PreferenceSignal",
    "PreferenceLedger",
    "extract_direct_memory",
    "extract_signal",
]

# 触发词 → 类别（P1 纠正 / 满意度）
_TRIGGERS: tuple[tuple[str, str], ...] = (
    ("其实", "纠正"),
    ("更喜欢", "偏好"),
    ("我喜欢", "偏好"),
    ("我偏好", "偏好"),
    ("习惯用", "习惯"),
    ("习惯", "习惯"),
    ("别用", "拒绝"),
    ("不要", "拒绝"),
    ("不用", "拒绝"),
    ("不错，就用", "满意"),
    ("靠谱，就用", "满意"),
)

_PUNCT_RE = re.compile(r"[，。！？；、,.!?;:：\n]")
_ASCII_RE = re.compile(r"[a-zA-Z0-9]+")

# 直接记忆指令（"记住：X" → 立即沉淀事件卡，零 LLM；U3.12 D5② 增强）
_DIRECT_TRIGGERS = ("记住", "记下", "记牢", "别忘了", "别忘")
# 教训指令切句：只按句末标点（保留逗号，经验卡文本更完整可用）
_LESSON_SPLIT_RE = re.compile(r"[。！？；!?;\n]")

# 行为进化：教训/经验指令（"记住教训：X" → 立即沉淀永久经验卡，零 LLM；M3.4 行为进化）
# 只收明确指令式触发词，避免裸"经验/教训"误触普通叙述。
_LESSON_TRIGGERS = ("记住教训", "记下教训", "记牢教训", "踩坑", "避坑", "经验教训")

_STOP = {
    "我", "你", "他", "她", "它", "我们", "你们", "他们",
    "的", "了", "是", "在", "要", "就", "也", "更", "最",
    "很", "都", "会", "想", "说", "觉得", "认为", "喜欢",
    "偏好", "用", "这个", "那个", "一下", "一点", "一些",
}


@dataclass(frozen=True, slots=True)
class PreferenceSignal:
    """一条偏好信号（入账单元）。"""

    topic: str  # 聚合键（触发词后的首个实义 token）
    category: str  # 纠正 | 偏好 | 习惯 | 拒绝 | 满意
    statement: str  # 规范化陈述（跨会话可读）


def _first_topic(clause: str) -> str | None:
    """取触发词后的首个实义 token 作为聚合键（jieba 词，跳过停用词）。"""
    for token in jieba.cut(clause, cut_all=False):
        tok = token.strip().lower()
        if not tok or tok in _STOP:
            continue
        if _ASCII_RE.fullmatch(tok) or any("\u4e00" <= ch <= "\u9fff" for ch in tok):
            return tok
    match = _ASCII_RE.search(clause)
    return match.group(0).lower() if match else None


def extract_direct_memory(user_text: str) -> str | None:
    """直接记忆指令：'记住：X' → X（触发词后的首个句子片段）。

    注意：全角冒号是常见前缀分隔符，不能当句子分隔符（否则 '记住：X' 会取到空串）；
    先剥离句首的冒号/逗号，再按句末标点切第一个分句。
    与偏好信号不同：这是用户明确要求"记下来"，直接沉淀为事件卡（不攒信号）。
    """
    for trigger in _DIRECT_TRIGGERS:
        idx = user_text.find(trigger)
        if idx == -1:
            continue
        remainder = user_text[idx + len(trigger):].strip().lstrip(":：，,、")
        if remainder.startswith("教训"):
            continue  # "记住教训：X" 属教训指令（② 先处理），不误当普通记忆
        clause = _PUNCT_RE.split(remainder)[0].strip()
        if clause:
            return clause
    return None


def extract_direct_lesson(user_text: str) -> str | None:
    """教训/经验指令：'记住教训：X' / '踩坑：X' → X（首个句子片段）。

    与 extract_direct_memory 同构；优先级在 recorder 中先于"记住"检查，
    否则"记住教训：X"会被"记住"误当普通记忆。
    """
    for trigger in _LESSON_TRIGGERS:
        idx = user_text.find(trigger)
        if idx == -1:
            continue
        remainder = user_text[idx + len(trigger):].strip().lstrip(":：，,、")
        clause = _LESSON_SPLIT_RE.split(remainder)[0].strip()
        if clause:
            return clause
    return None


def extract_signal(user_text: str) -> PreferenceSignal | None:
    """规则提取偏好信号；无触发词 / 无实义主题 → None。"""
    for trigger, category in _TRIGGERS:
        idx = user_text.find(trigger)
        if idx == -1:
            continue
        clause = _PUNCT_RE.split(user_text[idx + len(trigger):])[0].strip()
        if not clause:
            continue
        topic = _first_topic(clause)
        if not topic:
            continue
        return PreferenceSignal(
            topic=topic, category=category, statement=f"{trigger}{clause}"
        )
    return None


def _proposal_id(topic: str) -> str:
    digest = hashlib.sha1(f"pref|{topic}".encode()).hexdigest()[:12]
    return f"pref-{digest}"


class PreferenceLedger:
    """偏好信号入账 + 聚合提案（信号表在 memory.db，提案落 lessons/pending）。"""

    def __init__(
        self, store: MemoryStore, *, min_signals: int = 3, source_path: str = ""
    ) -> None:
        self.store = store
        self.min_signals = min_signals
        self.source_path = source_path

    def record(
        self, user_text: str, *, source_path: str | None = None
    ) -> PreferenceSignal | None:
        """提取并记录一条信号；返回信号（无触发词返回 None）。"""
        signal = extract_signal(user_text)
        if signal is None:
            return None
        self.store.record_signal(
            signal.topic,
            signal.category,
            signal.statement,
            source_path=source_path or self.source_path,
        )
        return signal

    def propose(self) -> list[MemoryCard]:
        """聚合 ≥min_signals 的同类信号 → lesson_pending 提案卡（幂等：同主题只提一次）。"""
        proposed: list[MemoryCard] = []
        for group in self.store.signal_groups(self.min_signals):
            topic, count = group["topic"], group["count"]
            card_id = _proposal_id(topic)
            if self.store.read_card(card_id) is not None:
                continue  # 已提过（pending 或已固化），不重复提案
            statements = self.store.signal_statements(topic)
            card = MemoryCard(
                id=card_id,
                kind="lesson_pending",
                title=f"偏好：{topic}（{count} 条信号）",
                content="\n".join(
                    f"- [{category}] {statement}" for statement, category in statements
                ),
                source_path=f"lessons/pending/{card_id}.md",
                created_at=now_iso(),
                confidence=0.8,
                status="active",
            )
            self.store.write_card(card)
            proposed.append(card)
        return proposed
