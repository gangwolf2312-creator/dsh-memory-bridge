"""提取后端：本地模型 / 云端独立模型 / 主对话模型兜底，显式开关 + 成本控制。

适配 DSH 发现：对话原始层由 DSH 会话日志承包（免费），本模块只承担
"提取"这唯一一项额外成本。mode 显式开关（三选一 + off）：

  off    -> 不启用 LLM 提取（纯规则/显式记忆，零调用）
  local  -> 本地轨：任意 OpenAI 兼容端点（Ollama / llama.cpp / vLLM /
            LMDeploy / MindIE 等，含 NPU 推理服务），零边际成本
  cloud  -> 云端独立模型提取（DeepSeek 等 OpenAI 兼容 API），攒批 + 限流
  main   -> 主对话模型兜底：复用 DSH ctx.llm（注入 Backend，不新增网络路径）

默认 main：local/cloud 都不开启时，提取自动复用主对话模型（运行无感）。
off 是显式选择"不要任何 LLM 提取"（纯规则/显式记忆）。

不硬编码供应商：base_url / model / api_key 默认全部留空，激活后才由调用方
注入（环境变量 / DSH 插件 / 配置文件），激活校验在 build_extractor()。

实现 core.backend.Backend 协议，供 LLMExtractor 与 DSH 侧装配复用。
模型消解能力 = 输入规模上限（max_turn_chars / max_context_tokens）；
资源占用 = 本地推理的并发、超时、上下文预算（LocalConfig）。
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from core.backend import Backend, BackendResult, UsageInfo

from memory.sanitize import sanitize_messages

__all__ = [
    "EXTRACT_MODES",
    "BackendError",
    "RetryableBackendError",
    "CloudBackend",
    "CloudConfig",
    "ExtractConfig",
    "LOCAL_PRESETS",
    "LocalBackend",
    "LocalConfig",
    "resolve_local_config",
    "MainModelBackend",
    "MainModelConfig",
    "RateLimitedError",
]

EXTRACT_MODES: tuple[str, ...] = ("off", "local", "cloud", "main", "hybrid")
# 本地轨预设 recipe（preset=默认时展开；custom 由用户显式配置 base_url/model）
LOCAL_PRESETS: dict[str, dict[str, object]] = {
    "qwen3-it-4b-flm": {
        "label": "qwen3-it-4b-FLM（Lemonade 本地轨 · 默认）",
        "base_url": "http://127.0.0.1:13305/v1",
        "model": "qwen3-it-4b-FLM",
        "temperature": 0.0,
        "max_tokens": 1024,
        "extra_body": {"chat_template_kwargs": {"enable_thinking": False}},
    },
}



@dataclass(frozen=True, slots=True)
class LocalConfig:
    """本地轨配置（mode=local 激活后必须配置 base_url 与 model）。

    不硬编码供应商：地址与模型名由调用方注入（DSH 插件 / 环境变量 /
    配置文件），本模块只定义字段与资源约束。
    参考：Ollama（http://127.0.0.1:11434/v1）、LMDeploy / MindIE 的
    OpenAI 兼容端点（昇腾 NPU 本地推理）、llama.cpp server 等。
    """

    preset: str = "qwen3-it-4b-flm"  # qwen3-it-4b-flm（默认，自动展开 recipe）| custom（自填 base_url/model）
    auto_manage: bool = True  # preset 默认轨：提取前自动健康检查 + 拉起 lemonade 对应模型
    base_url: str = ""
    model: str = ""
    api_key: str = ""  # 本地端点通常无需鉴权
    timeout_s: float = 60.0
    max_context_tokens: int = 8192  # 上下文预算（资源占用上限）
    max_turn_chars: int = 4000  # 单轮输入字符上限：超限截断（消解能力）
    concurrency: int = 1  # 并发上限（CPU/显存/NPU 占用控制）
    extra_body: dict[str, Any] = field(default_factory=dict)  # 透传模型特有参数（如 thinking 开关）
    sanitize: bool = True  # 提取前脱敏（防 API key/凭证进记忆卡；本地虽不出网但记忆卡是持久化的）


@dataclass(frozen=True, slots=True)
class CloudConfig:
    """云端独立模型提取配置（成本与调用次数控制）。"""

    base_url: str = "https://api.deepseek.com/v1"
    model: str = "deepseek-chat"
    api_key: str = ""
    timeout_s: float = 120.0
    batch_size: int = 8  # 攒批：一次调用处理 N 条对话（摊薄调用次数）
    max_calls_per_minute: int = 10  # 调用次数限流（成本硬约束）
    max_turn_chars: int = 8000  # 单轮输入上限（云端消解能力更强）
    retries: int = 2
    sanitize: bool = True  # 发送前脱敏（对话/工具输出中的密钥等替换为占位符）
    extra_body: dict[str, Any] = field(default_factory=dict)  # 透传模型特有参数（如 thinking 开关）


@dataclass(frozen=True, slots=True)
class MainModelConfig:
    """主对话模型兜底（mode=main）：复用 DSH ctx.llm 提取。

    无自有网络路径：DSH 侧把主对话后端注入 build_extractor(main_backend=ctx.llm)，
    本配置只约束输入规模上限（主对话模型上下文大，给足预算）。
    """

    max_turn_chars: int = 8000
    sanitize: bool = True  # P1a：提取前脱敏（防 API key/凭证进持久化记忆卡；local/cloud 同口径）


@dataclass(frozen=True, slots=True)
class ExtractConfig:
    """提取总配置：显式开关（off | local | cloud | main）+ 各级后端参数。

    三选一 + off：
    - local：本地轨（任意 OpenAI 兼容端点，含 NPU 本地推理）
    - cloud：云端独立模型提取（OpenAI 兼容 API）
    - main：主对话模型兜底（DSH ctx.llm 注入，默认；不新增网络路径）
    - off：显式关闭 LLM 提取（纯规则/显式记忆）

    默认 main：local/cloud 不配置时自动复用主对话模型（运行无感）。
    """

    mode: str = "main"  # off | local | cloud | main
    local: LocalConfig = field(default_factory=LocalConfig)
    cloud: CloudConfig = field(default_factory=CloudConfig)
    main: MainModelConfig = field(default_factory=MainModelConfig)

    def __post_init__(self) -> None:
        if self.mode not in EXTRACT_MODES:
            raise ValueError(f"无效提取模式: {self.mode!r}（可选: {', '.join(EXTRACT_MODES)}）")


def resolve_local_config(cfg: LocalConfig) -> LocalConfig:
    """preset 展开：默认本地轨自动填充 base_url/model/thinking 关闭。

    - preset=custom 或已显式填 base_url+model → 原样返回（用户自管端点）
    - preset=默认 recipe → 用 LOCAL_PRESETS 展开（缺省值填充，显式值优先）
    展开后 base_url/model 必然非空，供 build_extractor 校验。
    """
    if cfg.preset == "custom" or (cfg.base_url and cfg.model):
        return cfg
    recipe = LOCAL_PRESETS.get(cfg.preset)
    if recipe is None:
        raise ValueError(
            f"未知本地预设: {cfg.preset!r}（可选: {', '.join(sorted(LOCAL_PRESETS))} + custom）"
        )
    return LocalConfig(
        preset=cfg.preset,
        auto_manage=cfg.auto_manage,
        base_url=cfg.base_url or str(recipe["base_url"]),
        model=cfg.model or str(recipe["model"]),
        api_key=cfg.api_key,
        timeout_s=cfg.timeout_s,
        max_context_tokens=cfg.max_context_tokens,
        max_turn_chars=cfg.max_turn_chars,
        concurrency=cfg.concurrency,
        extra_body=cfg.extra_body or dict(recipe["extra_body"]),
        sanitize=cfg.sanitize,
    )


class BackendError(Exception):
    """后端调用失败（端点不可用 / 非 2xx）。"""


class RetryableBackendError(BackendError):
    """可重试的瞬时失败（P1b：5xx/429/网络不可达——云端重试的依据）。"""


class RateLimitedError(BackendError):
    """云端调用超过限流窗口（调用次数成本约束）。"""


class _OpenAICompatBackend(Backend):
    """OpenAI 兼容 /chat/completions 后端基类（非流式主路径）。"""

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str,
        timeout_s: float,
        extra_body: dict[str, Any] | None = None,
    ) -> None:
        self.model = model
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout_s = timeout_s
        self._extra_body = dict(extra_body) if extra_body else {}

    def complete(
        self,
        messages: list[dict[str, object]],
        *,
        temperature: float = 0.2,
        max_tokens: int = 512,
        tools: tuple[dict, ...] = (),
        timeout: float | None = None,
        on_delta: Any = None,
        on_thinking: Any = None,
    ) -> BackendResult:
        """同步调用 /chat/completions；返回完整结果（后台任务非流式）。"""
        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        if tools:
            body["tools"] = list(tools)
        if self._extra_body:
            body.update(self._extra_body)
        req = urllib.request.Request(
            f"{self._base_url}/chat/completions",
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                **( {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {} ),
            },
            method="POST",
        )
        deadline = timeout if timeout is not None else self._timeout_s
        try:
            with urllib.request.urlopen(req, timeout=deadline) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            code = exc.code
            detail = exc.read().decode("utf-8", "replace")[:200]
            # P1b：5xx/429 是瞬时失败（可重试），4xx 是请求本身问题（不重试）
            if code >= 500 or code == 429:
                raise RetryableBackendError(f"后端 HTTP {code}: {detail}") from exc
            raise BackendError(f"后端 HTTP {code}: {detail}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise RetryableBackendError(f"后端不可达: {exc}") from exc
        try:
            choice = payload["choices"][0]["message"]
            usage = payload.get("usage", {})
        except (KeyError, IndexError, TypeError) as exc:
            raise BackendError(f"后端响应结构异常: {exc}") from exc
        return BackendResult(
            text=str(choice.get("content") or ""),
            thinking=str(choice.get("reasoning_content") or ""),
            usage=UsageInfo(
                prompt_tokens=int(usage.get("prompt_tokens", 0)),
                completion_tokens=int(usage.get("completion_tokens", 0)),
                cached_tokens=int(usage.get("prompt_tokens_details", {}).get("cached_tokens", 0))
                if isinstance(usage.get("prompt_tokens_details"), dict)
                else 0,
            ),
            finish_reason=str(payload.get("choices", [{}])[0].get("finish_reason") or "") or None,
        )

    def count_tokens(self, text: str) -> int:
        """中文按字符粗略估算（2 字符/1 token）；供预算与记账。"""
        return max(1, len(text) // 2)


class LocalBackend(_OpenAICompatBackend):
    """本地模型后端：零边际成本，资源占用由 LocalConfig 约束（含 NPU 推理）。

    提取前脱敏（默认开）：本地虽不出网，但对话中的 API key/凭证若进记忆卡
    会持久化在明文 md 里——比出网更糟。命中类型记 last_sanitize_hits 供审计。
    """

    def __init__(self, cfg: LocalConfig) -> None:
        super().__init__(
            base_url=cfg.base_url,
            model=cfg.model,
            api_key=cfg.api_key,
            timeout_s=cfg.timeout_s,
            extra_body=cfg.extra_body,
        )
        self.max_context_tokens = cfg.max_context_tokens
        self.max_turn_chars = cfg.max_turn_chars
        self.concurrency = cfg.concurrency
        self.sanitize = cfg.sanitize
        self.last_sanitize_hits: list[str] = []

    def complete(
        self,
        messages: list[dict[str, object]],
        *,
        temperature: float = 0.0,
        max_tokens: int = 512,
        tools: tuple[dict, ...] = (),
        timeout: float | None = None,
        on_delta: Any = None,
        on_thinking: Any = None,
    ) -> BackendResult:
        if self.sanitize:
            messages, self.last_sanitize_hits = sanitize_messages(messages)
        return super().complete(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools,
            timeout=timeout,
            on_delta=on_delta,
            on_thinking=on_thinking,
        )


class CloudBackend(_OpenAICompatBackend):
    """云端后端：调用次数限流 + 成本记账（决策日志与审计用）+ 发送前脱敏。"""

    def __init__(self, cfg: CloudConfig) -> None:
        super().__init__(
            base_url=cfg.base_url,
            model=cfg.model,
            api_key=cfg.api_key,
            timeout_s=cfg.timeout_s,
            extra_body=cfg.extra_body,
        )
        self.batch_size = cfg.batch_size
        self.max_calls_per_minute = cfg.max_calls_per_minute
        self.max_turn_chars = cfg.max_turn_chars
        self.retries = cfg.retries
        self.sanitize = cfg.sanitize
        self.last_sanitize_hits: list[str] = []  # 最近一次请求的脱敏命中类型（审计用）
        self._calls: int = 0
        self._prompt_tokens: int = 0
        self._completion_tokens: int = 0
        self._call_times: deque[float] = deque()

    def complete(
        self,
        messages: list[dict[str, object]],
        *,
        temperature: float = 0.2,
        max_tokens: int = 512,
        tools: tuple[dict, ...] = (),
        timeout: float | None = None,
        on_delta: Any = None,
        on_thinking: Any = None,
    ) -> BackendResult:
        self._check_rate_limit()
        if self.sanitize:
            messages, self.last_sanitize_hits = sanitize_messages(messages)
        # P1b：CloudConfig.retries 落地——瞬时失败（5xx/429/不可达）退避重试，
        # 4xx / 限流 / 结构错误不重试（重试无意义或会再撞限流窗口）。
        attempt = 0
        while True:
            try:
                result = super().complete(
                    messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    tools=tools,
                    timeout=timeout,
                    on_delta=on_delta,
                    on_thinking=on_thinking,
                )
                break
            except RetryableBackendError as exc:
                attempt += 1
                if attempt > self.retries:
                    raise
                time.sleep(min(1.5, 0.3 * attempt))  # 300ms → 600ms → 900ms
        self._calls += 1
        self._prompt_tokens += result.usage.prompt_tokens
        self._completion_tokens += result.usage.completion_tokens
        self._call_times.append(time.monotonic())
        return result

    def _check_rate_limit(self) -> None:
        """滑动窗口限流：窗口内调用次数 >= max_calls_per_minute -> 拒发。"""
        if self.max_calls_per_minute <= 0:
            return
        now = time.monotonic()
        while self._call_times and now - self._call_times[0] > 60.0:
            self._call_times.popleft()
        if len(self._call_times) >= self.max_calls_per_minute:
            raise RateLimitedError(
                f"云端调用限流：最近 60s 已达 {self.max_calls_per_minute} 次"
            )

    def cost_summary(self) -> dict[str, int]:
        """成本记账快照（供 decision_log / audit 聚合）。"""
        return {
            "calls": self._calls,
            "prompt_tokens": self._prompt_tokens,
            "completion_tokens": self._completion_tokens,
            "total_tokens": self._prompt_tokens + self._completion_tokens,
        }


class MainModelBackend(Backend):
    """主对话模型兜底：包装 DSH 注入的 Backend（ctx.llm / 主对话后端）。

    不新增网络路径：提取请求原样复用主对话模型通道（模型回退链、鉴权
    均由 DSH 侧配置，记忆系统只定义契约）。温度固定 0.0 保证提取确定性。

    P1a：提取前同样过脱敏（sanitize）——对话原文已在 DSH 会话层，但提取
    结果会持久化进记忆卡，密钥/凭证必须以占位符形式进卡（与 local/cloud
    同口径；此前 main 是唯一绕过脱敏的路径）。
    """

    def __init__(self, delegate: Backend, *, sanitize: bool = True) -> None:
        self._delegate = delegate
        self.sanitize = sanitize
        self.model = getattr(delegate, "model", "main-model")
        self.last_sanitize_hits: list[str] = []

    def complete(
        self,
        messages: list[dict[str, object]],
        *,
        temperature: float = 0.0,
        max_tokens: int = 512,
        tools: tuple[dict, ...] = (),
        timeout: float | None = None,
        on_delta: Any = None,
        on_thinking: Any = None,
    ) -> BackendResult:
        if self.sanitize:
            messages, self.last_sanitize_hits = sanitize_messages(messages)
        return self._delegate.complete(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools,
            timeout=timeout,
            on_delta=on_delta,
            on_thinking=on_thinking,
        )

    def count_tokens(self, text: str) -> int:
        return self._delegate.count_tokens(text)
