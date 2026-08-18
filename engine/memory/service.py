"""记忆服务（躯干六件套之一；M1.7 最小可用 = 存储 + 检索）。

V3.4 提取装配：build_extractor() 按 ExtractConfig.mode 显式开关
（off | local | cloud | main）组装提取器，纯内部管道，不依赖 DSH。
本地轨 / 云端独立模型 / 主对话模型兜底三选一；都关闭（off）则纯规则；
默认 main：local/cloud 不配置时自动复用主对话模型（DSH 注入 ctx.llm）。
"""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from core.backend import Backend

from memory.backends import (
    CloudBackend,
    CloudConfig,
    ExtractConfig,
    LocalBackend,
    LocalConfig,
    MainModelBackend,
    MainModelConfig,
    resolve_local_config,
)
from memory.extract import LLMExtractor, _EXTRACT_PROMPT_SMALL
from memory.search import MemorySearch
from memory.store import MemoryStore
from memory.strategy import (
    CloudStrategy,
    HybridStrategy,
    LocalStrategy,
    MainStrategy,
)

__all__ = ["MemoryService", "build_extractor", "load_extract_config"]


@dataclass(slots=True)
class MemoryService:
    """记忆服务门面：存储（明文 md + 索引）与检索（BM25 + RRF）。"""

    store: MemoryStore
    search: MemorySearch


def build_extractor(
    config: ExtractConfig,
    *,
    main_backend: Backend | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    local_ready: Callable[[LocalConfig], None] | None = None,
) -> LLMExtractor | None:
    """按显式开关组装提取器；off -> None（纯规则/显式记忆，零 LLM 调用）。

    - local：本地轨（任意 OpenAI 兼容端点，含 NPU 本地推理），需 base_url + model
    - cloud：云端独立模型提取，需 base_url + api_key
    - main：主对话模型兜底（默认），需注入 main_backend=ctx.llm（DSH 侧装配时传）
    - hybrid：本地优先、超长降级云端（扩展装配，非默认 mode）
    开关激活后才校验必填项——绝不静默用错误默认值。
    temperature/max_tokens：覆盖提取温度与输出预算（V3.5 wiki 双分支默认 1024，
    见 PROMPT-EVALUATION §6；如需更大输出传 max_tokens 覆盖）。
    """
    ex_kwargs: dict[str, object] = {}
    if temperature is not None:
        ex_kwargs["temperature"] = temperature
    if max_tokens is not None:
        ex_kwargs["max_tokens"] = max_tokens

    mode = config.mode
    if mode == "off":
        return None
    if mode == "local":
        resolved = resolve_local_config(config.local)
        if resolved.preset != "custom" and resolved.auto_manage:
            # 默认本地轨：提取前保证 lemonade 服务 + 模型就绪（health check + 自动拉起）
            if local_ready is not None:
                local_ready(resolved)
            else:
                from memory.lemonade import ensure_local_ready

                ensure_local_ready(model=resolved.model)
        if not resolved.base_url or not resolved.model:
            raise ValueError(
                "local 模式已激活但未配置：preset=custom 时请注入 base_url 与 model"
                "（本地 OpenAI 兼容端点，如 Ollama / LMDeploy / MindIE）"
            )
        return LLMExtractor(
            LocalBackend(resolved), strategy=LocalStrategy(resolved),
            # 本地小模型（4B 级）用精简提示词：全量提示词字段/分支过多会拉低服从度
            prompt=_EXTRACT_PROMPT_SMALL, **ex_kwargs
        )
    if mode == "cloud":
        if not config.cloud.base_url or not config.cloud.api_key:
            raise ValueError(
                "cloud 模式已激活但未配置：请注入 base_url 与 api_key"
                "（云端独立模型提取，OpenAI 兼容 API）"
            )
        return LLMExtractor(
            CloudBackend(config.cloud), strategy=CloudStrategy(config.cloud), **ex_kwargs
        )
    if mode == "main":
        if main_backend is None:
            raise ValueError("main 模式需要注入主对话模型后端（DSH 侧传 ctx.llm）")
        return LLMExtractor(
            MainModelBackend(main_backend, sanitize=config.main.sanitize),
            strategy=MainStrategy(config.main),
            **ex_kwargs,
        )
    if mode == "hybrid":
        # P1b：hybrid——本地优先、超长降级云端（fallback_backend 由 extract 按
        # RouteDecision.backend 路由）。本地轨与 local 分支同口径：preset 展开 +
        # 本地就绪 + 精简提示词；云端作为 fallback 后端。
        resolved = resolve_local_config(config.local)
        if resolved.preset != "custom" and resolved.auto_manage:
            if local_ready is not None:
                local_ready(resolved)
            else:
                from memory.lemonade import ensure_local_ready

                ensure_local_ready(model=resolved.model)
        if not resolved.base_url or not resolved.model:
            raise ValueError(
                "hybrid 模式本地轨未配置：preset=custom 时请注入 base_url 与 model"
            )
        return LLMExtractor(
            LocalBackend(resolved),
            fallback_backend=CloudBackend(config.cloud),
            strategy=HybridStrategy(resolved, config.cloud),
            prompt=_EXTRACT_PROMPT_SMALL,
            **ex_kwargs,
        )
    raise ValueError(f"无效提取模式: {mode!r}（可选: off|local|cloud|main）")


def load_extract_config(env: Mapping[str, str] | None = None) -> ExtractConfig:
    """从环境变量装配提取配置（开关激活后由外部注入，不硬编码）。

    环境变量（前缀 MEMORY_）：
      MEMORY_EXTRACT_MODE       off|local|cloud|main（缺省 main：复用主对话模型）
      MEMORY_LOCAL_BASE_URL     本地轨 OpenAI 兼容端点（local 激活后必填）
      MEMORY_LOCAL_MODEL        本地模型名（local 激活后必填）
      MEMORY_LOCAL_API_KEY      本地端点鉴权（可选，通常免鉴权）
      MEMORY_CLOUD_BASE_URL     云端独立模型端点（cloud 激活后必填）
      MEMORY_CLOUD_API_KEY      云端 API 密钥（cloud 激活后必填）
      MEMORY_CLOUD_MODEL        云端模型名（可选，缺省 deepseek-chat）

    缺失项不在这里报错：build_extractor 会在对应 mode 激活时校验必填项，
    保证"开关激活后才要求配置"的语义。mode 缺省 main：local/cloud 未配置
    时提取自动复用主对话模型（DSH 侧注入 ctx.llm，运行无感）。
    """
    env = os.environ if env is None else env
    cfg = ExtractConfig(
        mode=env.get("MEMORY_EXTRACT_MODE", "main"),
        local=LocalConfig(
            base_url=env.get("MEMORY_LOCAL_BASE_URL", ""),
            model=env.get("MEMORY_LOCAL_MODEL", ""),
            api_key=env.get("MEMORY_LOCAL_API_KEY", ""),
        ),
        cloud=CloudConfig(
            base_url=env.get("MEMORY_CLOUD_BASE_URL", "https://api.deepseek.com/v1"),
            model=env.get("MEMORY_CLOUD_MODEL", "deepseek-chat"),
            api_key=env.get("MEMORY_CLOUD_API_KEY", ""),
        ),
        main=MainModelConfig(),
    )
    return cfg
