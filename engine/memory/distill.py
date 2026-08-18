"""画像蒸馏（B3，ADR-0020：周期用 LLM 从事件树压缩画像摘要 -> 人工审批 -> F 桶）。

- 输入：事件树（active 事件卡 + 最近日记录），明文、带溯源（B2 回合级 trace_event_id）
- 后端链：role=distill 配置优先 -> role=extract 免费链 -> 压缩器免费链 -> 主模型兜底
  （runtime 装配注入 backends；蒸馏绝不静默失败，全部失败记 decision_log）
- 产出：profiles/drafts/PROFILE.draft-<ts>.md（待人工审批）
- 防抖：蒸馏结果与当前画像几乎相同且人格未变 -> 不产草稿（决策日志）
- 去重：与最近草稿摘要相同且人格相同 -> 不重复产草稿（幂等）
- 降级：通道不可用 / 解析失败 -> 决策日志 + 保持旧画像
- 预算：摘要 <=200 tok（超限截断，标注截断）
- 频率：默认每周一次（cooldown 7 天）+ idle 门槛（无对话活动才跑）+ 手动"立即蒸馏"
"""

from __future__ import annotations

import difflib
import threading
import time
from collections.abc import Callable

from core.backend import Backend
from memory.extract import extract_json_object
from memory.profile import (
    AXIS_DEFS,
    PROFILE_SUMMARY_BUDGET_TOKENS,
    Dimension,
    Profile,
    ProfileStore,
)
from memory.store import MemoryStore

DISTILL_PROMPT = (
    "你是画像蒸馏器。从用户的事件记录中提炼一张画像摘要与人格多边形，只输出 JSON：\n"
    '{"summary": "不超过 200 token 的第三人称画像摘要（身份 / 目标 / 价值观 / 偏好 / 工作习惯）", '
    '"mbti": "四字母 MBTI（证据不足留空字符串）", '
    '"dimensions": [{"key": "ei", "value": 0.0-1.0}]（8 轴：ei sn tf jp task risk style form；'
    '证据不足给空数组）", '
    '"source_refs": ["来源文件路径"]}\n'
    "要求：\n"
    "- 只写稳定的身份、目标、偏好与工作习惯，不写一次性事件细节\n"
    "- 不模仿用户说话口吻，不复制对话风格样本（防冒名；ADR-0020 注入边界）\n"
    "- 人格只从事件树中可观察的稳定行为推断；证据不足时 mbti/dimensions 留空（保留现有画像人格）\n"
    "- 摘要自包含、可独立理解\n"
    "- 只输出 JSON，不要其他文字"
)

# 与当前画像的相似度阈值：高于且人格未变则视为无实质变化（防抖动）
_SIMILARITY_SKIP = 0.9

# 默认触发参数（ADR-0020，用户拍板：每周一次；idle 门槛避免抢对话）
DEFAULT_COOLDOWN_SECONDS = 7 * 24 * 3600  # 7 天
DEFAULT_IDLE_SECONDS = 30 * 60  # 30 分钟无对话活动
DEFAULT_POLL_SECONDS = 60.0


class ProfileDistillError(Exception):
    """蒸馏失败（通道不可用 / 解析失败 / 空摘要）。"""


def _resolve_persona(payload: dict, current: Profile | None) -> tuple[str, tuple[Dimension, ...]]:
    """蒸馏产出的人格；证据不足（mbti/dimensions 空）-> 保留当前人格（防幻觉）。"""
    mbti = str(payload.get("mbti", "") or "").strip().upper()
    raw_dims = payload.get("dimensions")
    dims: list[Dimension] = []
    if isinstance(raw_dims, list):
        by_key: dict[str, dict] = {}
        for item in raw_dims:
            if isinstance(item, dict) and item.get("key"):
                by_key[str(item["key"]).strip().lower()] = item
        for key, label, _left, right in AXIS_DEFS:
            item = by_key.get(key)
            if item is None:
                continue
            try:
                value = float(item.get("value", -1.0))
            except (TypeError, ValueError):
                continue
            if not (0.0 <= value <= 1.0):
                continue
            dims.append(Dimension(key=key, label=label, value=value, anchor=right))
    if not mbti and not dims:
        if current is not None:
            return current.mbti, current.dimensions
        return "", ()
    return mbti, tuple(dims)


def _truncate_to_tokens(
    text: str, count_tokens: Callable[[str], int], budget: int
) -> tuple[str, bool]:
    """把摘要截断到预算内（启发式字符窗口收缩）；返回 (text, truncated)。"""
    truncated = False
    while count_tokens(text) > budget and len(text) > 50:
        text = text[: int(len(text) * 0.8)]
        truncated = True
    return text.strip(), truncated


def _similar(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a.strip(), b.strip()).ratio()


class ProfileDistiller:
    """一轮画像蒸馏：收集事件树 -> LLM（后端链）-> 草稿（防抖 / 去重通过才写）。"""

    def __init__(
        self,
        store: ProfileStore,
        memory: MemoryStore,
        backends: list[Backend],
        *,
        count_tokens: Callable[[str], int],
        max_cards: int = 40,
        max_log_chars: int = 6000,
    ) -> None:
        self.store = store
        self.memory = memory
        self.backends = list(backends)
        self.count_tokens = count_tokens
        self.max_cards = max_cards
        self.max_log_chars = max_log_chars

    def collect_sources(self) -> tuple[list[str], str]:
        """事件卡 + 最近日记录 -> (蒸馏源行, trace_event_id)；trace 取首个非空回合根。"""
        lines: list[str] = []
        trace = ""
        cards = self.memory.active_cards()
        events = [c for c in cards if c.kind == "event"]
        lessons = [c for c in cards if c.kind == "lesson_permanent"]
        for card in (events + lessons)[: self.max_cards]:
            lines.append(f"[{card.source_path}] {card.title}：{card.content}")
            if not trace and card.trace_event_id:
                trace = card.trace_event_id
        # 最近 7 天日记录（从新到旧）
        dates: list[str] = []
        logs_dir = self.memory.root / "events" / "logs"
        if logs_dir.is_dir():
            dates = sorted((p.stem for p in logs_dir.glob("*.md")), reverse=True)[:7]
        log_chars = 0
        for date in dates:
            path = self.memory.daily_log_path(date)
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8").strip()
            if not text:
                continue
            if log_chars + len(text) > self.max_log_chars:
                text = text[: self.max_log_chars - log_chars]
            lines.append(f"[{date}] {text}")
            log_chars += len(text)
            if log_chars >= self.max_log_chars:
                break
        return lines, trace

    def _call_llm(self, sources: list[str]) -> dict:
        """后端链逐个调用并解析 JSON；单后端失败重试一次；全失败记决策日志并抛错。"""
        last: Exception | None = None
        last_raw = ""
        backends = self.backends or []
        for backend in backends:
            for attempt in (0, 1):
                system = DISTILL_PROMPT
                if attempt == 1:
                    system += " 只输出 JSON 对象，不要 markdown 代码块，不要任何解释。"
                messages = [
                    {"role": "system", "content": system},
                    {"role": "user", "content": "\n".join(sources)},
                ]
                try:
                    resp = backend.complete(messages, temperature=0.0, max_tokens=512)
                except Exception as exc:  # noqa: BLE001 - 端点不可用（含云端失败）
                    last = exc
                    last_raw = ""
                    continue
                try:
                    return extract_json_object(resp.text)
                except (ValueError, TypeError) as exc:
                    last = exc
                    last_raw = resp.text
                    continue
        self.memory.log_decision(
            "distill_failed",
            f"全后端失败: {last} | 原始回复: {last_raw[:200]}",
        )
        raise ProfileDistillError(f"蒸馏失败: {last}")

    def distill(self) -> Profile | None:
        """跑一轮蒸馏；返回新草稿（None = 无事件 / 防抖跳过 / 去重跳过）。"""
        sources, trace = self.collect_sources()
        if not sources:
            return None  # 无事件可蒸馏是正常状态，不记日志
        payload = self._call_llm(sources)
        summary = str(payload.get("summary", "")).strip()
        if not summary:
            self.memory.log_decision("distill_failed", "空摘要")
            raise ProfileDistillError("蒸馏产出空摘要")
        summary, truncated = _truncate_to_tokens(
            summary, self.count_tokens, PROFILE_SUMMARY_BUDGET_TOKENS
        )
        if truncated:
            summary = f"{summary}（摘要超长已截断）"
        raw_refs = payload.get("source_refs", [])
        source_refs = tuple(
            str(ref) for ref in raw_refs if isinstance(ref, str) and ref.strip()
        )
        current = self.store.load()
        mbti, dimensions = _resolve_persona(payload, current)
        draft = Profile(
            summary=summary,
            updated_at="",
            version=1,
            status="draft",
            source_refs=source_refs,
            mbti=mbti,
            dimensions=dimensions,
            trace_event_id=trace,
        )

        # 防抖：与当前 approved 画像几乎相同 且 人格未变 -> 不产草稿
        if current is not None and current.status == "approved":
            persona_same = current.mbti == draft.mbti and current.dimensions == draft.dimensions
            if persona_same and _similar(current.summary, summary) >= _SIMILARITY_SKIP:
                self.memory.log_decision(
                    "distill_skip", "蒸馏结果与当前画像几乎相同（含人格），不产草稿"
                )
                return None

        # 去重：与已有草稿摘要相同且人格相同 -> 不重复产草稿（幂等）
        for _name, existing in self.store.list_drafts():
            persona_same = existing.mbti == draft.mbti and existing.dimensions == draft.dimensions
            if persona_same and _similar(existing.summary, summary) >= _SIMILARITY_SKIP:
                self.memory.log_decision("distill_skip", "已存在相同摘要的草稿，跳过")
                return None

        path = self.store.write_draft(draft)
        self.memory.log_decision("distill_draft", f"产出画像草稿: {path.name}")
        return draft


class DistillWorker:
    """Idle-gated 后台蒸馏：只在对话低谷 + 冷却期后跑一轮，不抢主路径（每周一次默认）。"""

    def __init__(
        self,
        distiller: ProfileDistiller,
        *,
        enabled: bool = True,
        poll_seconds: float = DEFAULT_POLL_SECONDS,
        cooldown_seconds: float = DEFAULT_COOLDOWN_SECONDS,
        idle_seconds: float = DEFAULT_IDLE_SECONDS,
    ) -> None:
        self.distiller = distiller
        self.enabled = enabled
        self.cooldown_seconds = cooldown_seconds
        self.idle_seconds = idle_seconds
        self._last_activity_at = time.monotonic()
        self._last_distill_at = 0.0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        if enabled:
            self._thread = threading.Thread(
                target=self._worker_loop, args=(poll_seconds,), daemon=True
            )
            self._thread.start()

    def touch(self) -> None:
        """对话活动时调用：推迟下一轮蒸馏（优先保障对话）。"""
        self._last_activity_at = time.monotonic()

    def _worker_loop(self, poll_seconds: float) -> None:
        while not self._stop.is_set():
            idle_for = time.monotonic() - self._last_activity_at
            interval_ok = time.monotonic() - self._last_distill_at >= self.cooldown_seconds
            if idle_for >= self.idle_seconds and interval_ok:
                try:
                    self.distiller.distill()
                except Exception:  # noqa: BLE001 - 失败不推进冷却，下轮重试
                    pass
                else:
                    # P1a：无论产稿/防抖/去重/无事件，本轮蒸馏已执行 → 推进冷却。
                    # 旧实现只在产稿时推进：画像稳定后每 60s 空转一次 LLM（token 烧蚀）。
                    self._last_distill_at = time.monotonic()
            self._stop.wait(poll_seconds)

    def shutdown(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=3.0)