"""后端契约（继承 V2 core/backend.py 口径，M1 精简为 complete 主路径）。

kernel 只依赖本层协议与类型，不 import 任何业务模块；
providers/ 实现本协议，由装配层注入 kernel。零依赖（标准库）。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

__all__ = [
    "Backend",
    "BackendCapabilities",
    "BackendResult",
    "BackendToolCall",
    "ToolExecution",
    "UsageInfo",
]


@dataclass(frozen=True, slots=True)
class UsageInfo:
    """一次推理的用量与速度（口径：模型 token）。"""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    cached_tokens: int = 0
    prefill_speed_tps: float | None = None
    output_speed_tps: float | None = None
    prefill_duration_s: float | None = None

    @property
    def total(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass(frozen=True, slots=True)
class BackendToolCall:
    """模型请求的工具调用（M1 执行；arguments 为 JSON 字符串）。"""

    id: str
    name: str
    arguments: str


@dataclass(frozen=True, slots=True)
class ToolExecution:
    """一次工具执行结果（kernel 回注给模型的消息内容）。"""

    call_id: str
    tool_name: str
    ok: bool
    output: str


@dataclass(frozen=True, slots=True)
class BackendResult:
    """一次后端调用结果。"""

    text: str = ""
    thinking: str = ""
    usage: UsageInfo = field(default_factory=UsageInfo)
    tool_calls: tuple[BackendToolCall, ...] = ()
    ttft_ms: float | None = None
    finish_reason: str | None = None


@dataclass(frozen=True, slots=True)
class BackendCapabilities:
    """能力探测结果（能力探测，零假设；M1 只做最小探测）。"""

    model: str = ""
    base_url: str = ""
    tool_calling: bool = False
    prefix_cache: bool = False
    tokenizer: str = "tiktoken-cl100k-fallback"
    measured_at: float = 0.0


@runtime_checkable
class Backend(Protocol):
    """LLM 后端统一接口（本地 NPU / DeepSeek / Kimi / OpenRouter free 都实现本协议）。"""

    model: str

    def complete(
        self,
        messages: list[dict[str, object]],
        *,
        temperature: float = 0.2,
        max_tokens: int = 512,
        tools: tuple[dict, ...] = (),
        timeout: float | None = None,
        on_delta: Callable[[str], None] | None = None,
        on_thinking: Callable[[str], None] | None = None,
    ) -> BackendResult:
        """对话接口。on_delta 提供时走真实流式（逐片回调文本，首个 token 即回调），仍返回完整结果；
        默认非流式（M1 主路径），压缩器/识图/蒸馏等后台任务不传 on_delta。"""
        ...

    def count_tokens(self, text: str) -> int:
        """token 计数（口径标注，估算）。"""
        ...
