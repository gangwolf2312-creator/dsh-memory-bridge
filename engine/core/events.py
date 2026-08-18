"""V3 契约层：事件（SSE 事件流的前后端唯一实时契约）。

事件必带 session_id（多对话并行的聚合键）；seq 由事件总线分配。
"""

from __future__ import annotations

import enum
import threading
import time
from dataclasses import dataclass, field
from typing import Any


class EventType(enum.StrEnum):
    # 会话生命周期
    SESSION_CREATED = "session_created"
    SESSION_STARTED = "session_started"
    SESSION_PAUSED = "session_paused"
    SESSION_RESUMED = "session_resumed"
    SESSION_ERROR = "session_error"
    SESSION_DONE = "session_done"
    SESSION_DELETED = "session_deleted"
    SESSION_UPDATED = "session_updated"
    SESSION_ARCHIVED = "session_archived"
    # 对话轮次
    TURN_START = "turn_start"
    TURN_PHASE = "turn_phase"
    TURN_END = "turn_end"
    TURN_CONTINUATION = "turn_continuation"  # A1：输出续写（finish_reason=length 自动补写，事件树可溯）
    TURN_INTERRUPTED = "turn_interrupted"  # A2：运行中中断（cancel 请求已生效，事件树可溯）
    CHECKPOINT = "checkpoint"  # A4：步骤完成检查点（ghost commit sha，事件树可溯）
    MESSAGE = "message"  # U3.6：显式消息节点（actor user/agent/sub/a2a），事件树记录器塑形
    # 计划
    PLAN_UPDATE = "plan_update"
    PLAN_CONTINUE = "plan_continue"  # B12：计划未完成强制续推（事件树可溯）
    # 工具/能力
    CAPABILITY_CALL = "capability_call"
    CAPABILITY_RESULT = "capability_result"
    TOOL_FUSE = "tool_fuse"  # E13：工具连续失败熔断提示
    CAPABILITY_TOGGLED = "capability_toggled"
    # 审批
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_RESOLVED = "approval_resolved"
    # 模式与模型
    MODE_SWITCHED = "mode_switched"
    MODEL_SELECTED = "model_selected"
    APPROVAL_SWITCHED = "approval_switched"  # E12：会话审批档切换
    # 额度（M2 落地）
    QUOTA_UPDATE = "quota_update"
    # 本地模型占用（弹窗协议占位，M2 段 2）
    LOCAL_BUSY = "local_busy"
    # 上下文构成/压缩（U3.11：F/D/H 计量 + 驱逐/compact 通知）
    CONTEXT_UPDATE = "context_update"
    # 记忆（U3.12：本轮注入的长期记忆命中，UI 展示用）
    MEMORY_INJECTED = "memory_injected"
    # 记忆（B1：LLM 自动提取结果，事件树可溯到 turn）
    MEMORY_EXTRACT = "memory_extract"
    # 守门员（ADR-0017 F2.0：工具执行 middleware 检查点事件）
    GUARDRAIL_BLOCK = "guardrail_block"
    GUARDRAIL_REWRITE = "guardrail_rewrite"
    GUARDRAIL_WARN = "guardrail_warn"
    GUARDRAIL_ERROR = "guardrail_error"
    GUARDRAIL_DISABLED = "guardrail_disabled"
    # 流式输出（真实逐字：complete 带 on_delta → 逐片推给前端）
    ASSISTANT_DELTA = "assistant_delta"
    THINKING_DELTA = "thinking_delta"  # 思考输出（reasoning_content 逐字推给前端 UI）
    # A5：doom-loop 检测 / 完成度检查（循环工程自愈，事件树可溯）
    DOOM_LOOP = "doom_loop"
    COMPLETION_CHECK = "completion_check"


@dataclass(frozen=True, slots=True)
class Event:
    """事件信封：seq 由事件总线分配，ts 默认当前时间。"""

    session_id: str
    type: EventType
    payload: dict[str, Any] = field(default_factory=dict)
    seq: int = 0
    ts: float = field(default_factory=time.time)

    def with_seq(self, seq: int) -> Event:
        return Event(
            session_id=self.session_id,
            type=self.type,
            payload=self.payload,
            seq=seq,
            ts=self.ts,
        )


class EventBus:
    """进程内事件总线：多订阅者，顺序分配 seq。

    M0 仅提供同步广播；M2 会话调度器接入后按 session_id 聚合。
    """

    def __init__(self) -> None:
        self._seq = 0
        self._subscribers: list[callable] = []
        self._lock = threading.Lock()

    def subscribe(self, handler: callable) -> None:
        with self._lock:
            self._subscribers.append(handler)

    def unsubscribe(self, handler: callable) -> None:
        """移除订阅者（SSE 连接断开/服务关停时回收，防泄漏）。"""
        with self._lock:
            if handler in self._subscribers:
                self._subscribers.remove(handler)

    def publish(self, event: Event) -> Event:
        with self._lock:
            self._seq += 1
            stamped = event.with_seq(self._seq)
            handlers = list(self._subscribers)
        # P2：单订阅者异常隔离——一个处理器的故障不拖垮其余订阅者 / 发布方（SSE 链路）
        for handler in handlers:
            try:
                handler(stamped)
            except Exception:  # noqa: BLE001 - 订阅者错误与总线解耦
                continue
        return stamped
