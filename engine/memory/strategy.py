"""提取策略：本地 / 云端 / 主对话兜底 的路由与容量约束。

纯内部管道组件：决定一个 run 走哪个后端、输入规模上限、是否攒批。
不涉及任何 DSH 插件接口（插件适配由 DSH 侧负责）。

- LocalStrategy   本地轨：逐条、上下文给足；超长截断
- CloudStrategy   云端：攒批摊薄调用次数；超容量跳过（省一次调用）
- MainStrategy    主对话模型兜底：逐条，主模型上下文大给足预算
- HybridStrategy  本地优先（扩展）：超长降级云端
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from memory.backends import CloudConfig, LocalConfig, MainModelConfig
from memory.models import MemoryRun

__all__ = [
    "CloudStrategy",
    "ExtractStrategy",
    "HybridStrategy",
    "LocalStrategy",
    "MainStrategy",
    "RouteDecision",
]


@dataclass(frozen=True, slots=True)
class RouteDecision:
    """一个 run 的提取路由决定。"""

    backend: str  # "local" | "cloud" | "main" | "skip"
    reason: str
    truncate_chars: int  # 输入规模上限（模型消解能力约束）


def _turn_len(run: MemoryRun) -> int:
    return len(run.user_text or "") + len(run.reply_text or "")


class ExtractStrategy(Protocol):
    """提取策略协议：路由决定 + 批量规模（内部管道契约）。"""

    name: str

    def decide(self, run: MemoryRun) -> RouteDecision:
        ...

    def batch_size(self) -> int:
        ...


class LocalStrategy:
    """本地零边际成本：逐条实时，上下文给足；超长截断不降级。"""

    name = "local"

    def __init__(self, cfg: LocalConfig) -> None:
        self.cfg = cfg

    def decide(self, run: MemoryRun) -> RouteDecision:
        cap = self.cfg.max_turn_chars
        if _turn_len(run) > cap:
            return RouteDecision("local", "truncated_over_capacity", cap)
        return RouteDecision("local", "always", cap)

    def batch_size(self) -> int:
        return 1


class CloudStrategy:
    """云端成本敏感：攒批摊薄调用次数；超容量跳过（省一次调用）。"""

    name = "cloud"

    def __init__(self, cfg: CloudConfig) -> None:
        self.cfg = cfg

    def decide(self, run: MemoryRun) -> RouteDecision:
        cap = self.cfg.max_turn_chars
        if _turn_len(run) > cap:
            return RouteDecision("skip", "over_capacity", cap)
        return RouteDecision("cloud", "batchable", cap)

    def batch_size(self) -> int:
        return self.cfg.batch_size


class MainStrategy:
    """主对话模型兜底：逐条，主模型上下文大给足预算。"""

    name = "main"

    def __init__(self, cfg: MainModelConfig) -> None:
        self.cfg = cfg

    def decide(self, run: MemoryRun) -> RouteDecision:
        cap = self.cfg.max_turn_chars
        if _turn_len(run) > cap:
            return RouteDecision("main", "truncated_over_capacity", cap)
        return RouteDecision("main", "always", cap)

    def batch_size(self) -> int:
        return 1


class HybridStrategy:
    """本地优先：本地容量内逐条；超长降级云端（单条，不攒批）。"""

    name = "hybrid"

    def __init__(self, local_cfg: LocalConfig, cloud_cfg: CloudConfig) -> None:
        self.local_cfg = local_cfg
        self.cloud_cfg = cloud_cfg

    def decide(self, run: MemoryRun) -> RouteDecision:
        local_cap = self.local_cfg.max_turn_chars
        if _turn_len(run) > local_cap:
            return RouteDecision(
                "cloud", "too_long_for_local", self.cloud_cfg.max_turn_chars
            )
        return RouteDecision("local", "always", local_cap)

    def batch_size(self) -> int:
        return 1
