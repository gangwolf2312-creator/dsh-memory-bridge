"""core 契约层补测（P2：types + events 此前零直接测试）。

- core.types：基础枚举 + RiskLevel.from_severity 兼容映射
- core.events：Event 信封 / with_seq / EventBus 订阅发布 / seq 递增 /
  单订阅者异常隔离（P2 修复）
"""

from __future__ import annotations

import pytest
from core.events import Event, EventBus, EventType
from core.types import (
    ApprovalMode,
    CapabilityKind,
    IntentTier,
    ReasoningEffort,
    RiskLevel,
    SandboxMode,
    SessionStatus,
    TurnOutcomeKind,
    TurnPhase,
)


# —— core.types ——


def test_intent_tier_values() -> None:
    assert IntentTier.L0 == "L0"
    assert IntentTier.L1 == "L1"
    assert IntentTier.L2 == "L2"
    assert list(IntentTier) == [IntentTier.L0, IntentTier.L1, IntentTier.L2]


def test_capability_kind_enum() -> None:
    assert CapabilityKind.BASE_TOOL.value == "base_tool"
    assert CapabilityKind.SKILL.value == "skill"
    assert CapabilityKind.MCP.value == "mcp"
    assert CapabilityKind.CLI.value == "cli"
    assert CapabilityKind.WORKFLOW.value == "workflow"


def test_risk_level_from_severity_mapping() -> None:
    # read_only → READ（无论 severity 值）
    assert RiskLevel.from_severity("high", read_only=True) is RiskLevel.READ
    assert RiskLevel.from_severity("medium", read_only=True) is RiskLevel.READ
    # 写操作按 severity 字符串映射
    assert RiskLevel.from_severity("high", read_only=False) is RiskLevel.HIGH
    assert RiskLevel.from_severity("medium", read_only=False) is RiskLevel.MEDIUM
    assert RiskLevel.from_severity("low", read_only=False) is RiskLevel.LOW
    assert RiskLevel.from_severity("unknown", read_only=False) is RiskLevel.LOW
    # 兼容带 .value 的对象（如旧枚举）
    class _Sev:
        value = "high"

    assert RiskLevel.from_severity(_Sev(), read_only=False) is RiskLevel.HIGH


def test_remaining_enums_roundtrip() -> None:
    assert ApprovalMode.SMART == "smart"
    assert SandboxMode.WORKSPACE == "workspace"
    assert ReasoningEffort.HIGH == "high"
    assert SessionStatus.WAITING_APPROVAL == "waiting_approval"
    assert TurnPhase.DECIDE == "decide"
    assert TurnOutcomeKind.INTERRUPTED == "interrupted"
    # 枚举可反向解析（契约层被装配方依赖）
    assert IntentTier("L2") is IntentTier.L2
    assert RiskLevel("catastrophic") is RiskLevel.CATASTROPHIC


# —— core.events ——


def test_event_envelope_with_seq_preserves_fields() -> None:
    ev = Event(
        session_id="s1",
        type=EventType.TURN_START,
        payload={"n": 1},
        ts=123.0,
    )
    stamped = ev.with_seq(7)
    assert stamped.seq == 7
    assert stamped.session_id == "s1"
    assert stamped.type is EventType.TURN_START
    assert stamped.payload == {"n": 1}
    assert stamped.ts == 123.0
    # 原事件不被修改（frozen + with_seq 返回新对象）
    assert ev.seq == 0


def test_bus_assigns_increasing_seq() -> None:
    bus = EventBus()
    seen: list[int] = []
    bus.subscribe(lambda ev: seen.append(ev.seq))
    bus.publish(Event("s1", EventType.TURN_START))
    bus.publish(Event("s1", EventType.TURN_END))
    assert seen == [1, 2]


def test_bus_multiple_subscribers_all_receive() -> None:
    bus = EventBus()
    got: list[EventType] = []
    bus.subscribe(lambda ev: got.append(ev.type))
    bus.subscribe(lambda ev: got.append(ev.type))
    bus.publish(Event("s1", EventType.MEMORY_EXTRACT))
    assert got == [EventType.MEMORY_EXTRACT, EventType.MEMORY_EXTRACT]


def test_bus_unsubscribe_stops_delivery() -> None:
    bus = EventBus()
    got: list[int] = []

    def h(ev):
        got.append(ev.seq)

    bus.subscribe(h)
    bus.publish(Event("s1", EventType.MESSAGE))
    bus.unsubscribe(h)
    bus.publish(Event("s1", EventType.MESSAGE))
    assert got == [1]  # 只收到第一条


def test_bus_publish_returns_stamped_event() -> None:
    bus = EventBus()
    stamped = bus.publish(Event("s1", EventType.PLAN_UPDATE))
    assert stamped.seq == 1
    assert stamped.type is EventType.PLAN_UPDATE


def test_bus_handler_exception_is_isolated() -> None:
    """P2：单订阅者抛异常不拖垮其余订阅者与发布方。"""
    bus = EventBus()
    got: list[int] = []

    def bad(ev):
        raise RuntimeError("订阅者故障")

    def good(ev):
        got.append(ev.seq)

    bus.subscribe(bad)
    bus.subscribe(good)
    stamped = bus.publish(Event("s1", EventType.TURN_END))  # 不抛异常
    assert stamped.seq == 1
    assert got == [1]
