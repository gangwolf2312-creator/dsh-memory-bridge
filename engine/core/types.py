"""V3 契约层：基础枚举与类型（零依赖）。"""

from __future__ import annotations

import enum


class IntentTier(enum.StrEnum):
    """意图注入档位（继承 V2 口径，M1 规则检测）。"""

    L0 = "L0"  # 免工具：零工具注入
    L1 = "L1"  # 轻工具：注入可用工具
    L2 = "L2"  # 重任务：注入工具 + 自动规划


class CapabilityKind(enum.StrEnum):
    """四类手脚 + 工作流预留。"""

    BASE_TOOL = "base_tool"
    SKILL = "skill"
    MCP = "mcp"
    CLI = "cli"
    WORKFLOW = "workflow"


class RiskLevel(enum.StrEnum):
    """工具/行为风险档（E12 风险矩阵唯一事实源，审批裁决基准）。

    定义在 core（零依赖）以切断 security ↔ tools 的循环导入；tools.contract 再导出。
    READ=只读零副作用；LOW=低风险写（可自动放行）；MEDIUM=中风险写（SMART 审批）；
    HIGH=高风险（恒审批，不可一键绕过）；CATASTROPHIC=灾难（恒拒，不可审批）。
    """

    READ = "read"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CATASTROPHIC = "catastrophic"

    @staticmethod
    def from_severity(severity: object, *, read_only: bool) -> RiskLevel:
        """旧 severity/read_only 二元 → 风险档（MCP 启发式等兼容入口；不依赖 tools.contract 防循环）。"""
        if read_only:
            return RiskLevel.READ
        value = getattr(severity, "value", None) or str(severity)
        if value == "high":
            return RiskLevel.HIGH
        if value == "medium":
            return RiskLevel.MEDIUM
        return RiskLevel.LOW


class ApprovalMode(enum.StrEnum):
    """审批策略四档（E12，对齐 QwenPaw ToolExecutionLevel + V2 ExecutionLevel 语义，默认 SMART）。

    STRICT 严格：所有工具调用都入审批（读也审）——陌生/高安全/审计场景。
    SMART  智能：只读与低风险写自动放行；MEDIUM 审批（可"记住"）；HIGH 恒审批；灾难/越界恒拒。
    AUTO   信任：仅守卫名单（高风险/危险命令模式）审批，其余全放行——日常高频不打扰。
    OFF    全自动：仅灾难拦截 + 路径逃逸拦截——仅限完全信任的本地沙箱会话。
    """

    STRICT = "strict"
    SMART = "smart"
    AUTO = "auto"
    OFF = "off"


class SandboxMode(enum.StrEnum):
    """沙箱策略：NONE / WORKSPACE / CONTAINER（预留）。"""

    NONE = "none"
    WORKSPACE = "workspace"
    CONTAINER = "container"


class ReasoningEffort(enum.StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class SessionStatus(enum.StrEnum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    WAITING_APPROVAL = "waiting_approval"
    ERROR = "error"
    DONE = "done"


class TurnPhase(enum.StrEnum):
    """Loop 六步（继承 V2 LoopEngine，M1 落地行为，M0 只定序）。"""

    ACT = "act"
    GATE = "gate"
    STOP = "stop"
    RUBRIC = "rubric"
    DECIDE = "decide"
    END = "end"


class TurnOutcomeKind(enum.StrEnum):
    DONE = "done"
    INTERRUPTED = "interrupted"
    ERROR = "error"
    STOPPED = "stopped"
