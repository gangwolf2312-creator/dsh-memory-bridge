"""遗忘批处理（ADR-0019 决策 5：事件完结即萎缩 + 后台每日任务）。

- 事件完结判定：active 链卡无 ended_at，最近子卡（叶）created_at 距今 > branch_idle_days
  → 枝完结（ended_at）+ 子卡枯萎（status=wilted、weight 降、ended_at 继承）。
- 枯萎 = 排除在检索之外（遗忘的本质），数据保留可翻看、可人工修剪。
- 纯规则（零 LLM，不抢 TTFT）；显式完结（LLM ended=true）由提取管道 mark_ended 处理。
- run_once() 供测试/手动触发；worker 线程（每日一次）由应用入口启动。
"""

from __future__ import annotations

import contextlib
import datetime as _dt
import threading
from collections.abc import Callable

from memory.store import MemoryStore, now_iso

__all__ = ["DecayMaintenance", "days_between"]


def days_between(earlier: str, later: str) -> int:
    """两个 ISO 日期串的整天差（YYYY-MM-DD 前缀解析；解析失败返回 0）。"""
    try:
        a = _dt.date.fromisoformat(earlier[:10])
        b = _dt.date.fromisoformat(later[:10])
        return max(0, (b - a).days)
    except (ValueError, TypeError):
        return 0


class DecayMaintenance:
    """遗忘维护：每日判定完结枝并萎缩其叶。"""

    def __init__(
        self,
        store: MemoryStore,
        *,
        branch_idle_days: int = 30,
        wilt_factor: float = 0.3,
        interval_seconds: float = 24 * 3600,
        summarizer: Callable[[str], bool] | None = None,
    ) -> None:
        self.store = store
        self.branch_idle_days = branch_idle_days
        self.wilt_factor = wilt_factor
        self.interval_seconds = interval_seconds
        self.summarizer = summarizer  # B4：果摘要生成钩子（枝完结后调用）
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def run_once(self, now: str | None = None) -> dict:
        """执行一轮完结/萎缩判定；返回 {"ended": n, "wilted": m}。"""
        now = now or now_iso()
        ended = 0
        wilted = 0
        for chain in self.store.all_cards():
            if chain.kind != "chain" or chain.status != "active" or chain.ended_at:
                continue
            kids = self.store.children_of(chain.id)
            if not kids:
                continue
            latest = max((k.created_at or "")[:10] for k in kids)
            if days_between(latest, now) > self.branch_idle_days:
                wilted += self.store.mark_ended(chain.id, at=now)
                ended += 1
        if ended:
            self.store.log_decision("decay", f"完结 {ended} 枝，枯萎 {wilted} 叶")
        summarized = self._summarize_ended_branches()
        return {"ended": ended, "wilted": wilted, "summarized": summarized}

    def _summarize_ended_branches(self) -> int:
        """B4：对已完结但尚无果摘要的枝触发果摘要生成（幂等：有 summary 跳过）。

        每日 run_once 都会扫描 → 生成失败次日自动重试；无 summarizer（未装配）时跳过。
        """
        if self.summarizer is None:
            return 0
        summarized = 0
        for chain in self.store.all_cards():
            if chain.kind != "chain" or not chain.ended_at:
                continue
            if chain.summary.strip():
                continue
            with contextlib.suppress(Exception):
                if self.summarizer(chain.id):
                    summarized += 1
        return summarized

    def start(self) -> None:
        """启动后台 daemon 线程（每日一次；启动延迟 60s 避免与对话争抢）。"""
        if self._thread is not None:
            return

        def _loop() -> None:
            if self._stop.wait(60.0):
                return
            while not self._stop.is_set():
                with contextlib.suppress(Exception):
                    self.run_once()
                self._stop.wait(self.interval_seconds)

        self._thread = threading.Thread(target=_loop, name="memory-decay", daemon=True)
        self._thread.start()

    def close(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None
