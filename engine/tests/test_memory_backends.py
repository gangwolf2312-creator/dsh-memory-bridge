"""提取后端 + 显式开关 + 脱敏测试（V3.4 内部管道）。

覆盖：ExtractConfig 开关校验（off|local|cloud|main）、默认 main、激活后
配置校验、build_extractor 装配、本地 complete、云端发送前脱敏、限流与
成本记账、主对话模型兜底委托、策略路由与批量攒批。
"""

from __future__ import annotations

import json
from unittest import mock

import pytest
from core.backend import BackendResult, UsageInfo
from memory.backends import (
    _OpenAICompatBackend,
    BackendError,
    CloudBackend,
    CloudConfig,
    EXTRACT_MODES,
    ExtractConfig,
    LocalBackend,
    LocalConfig,
    MainModelBackend,
    MainModelConfig,
    RateLimitedError,
    RetryableBackendError,
)
from memory.extract import LLMExtractor
from memory.models import MemoryRun
from memory.service import build_extractor, load_extract_config
from memory.strategy import (
    CloudStrategy,
    HybridStrategy,
    LocalStrategy,
    MainStrategy,
)


def _run(user: str = "", reply: str = "", run_id: str = "run-t1") -> MemoryRun:
    return MemoryRun(
        run_id=run_id, session_id="s1", user_text=user, reply_text=reply, tier="L1"
    )


def _local_cfg(**kw) -> LocalConfig:
    """已激活的本地轨配置（不硬编码供应商，测试显式注入）。"""
    base = {"preset": "custom", "base_url": "http://127.0.0.1:13305/api/v1", "model": "memreader-4b-thinking"}
    base.update(kw)
    return LocalConfig(**base)


def _cloud_cfg(**kw) -> CloudConfig:
    """已激活的云端配置。"""
    base = {"base_url": "https://api.deepseek.com/v1", "api_key": "test-key"}
    base.update(kw)
    return CloudConfig(**base)


def _ok_response(text: str, prompt: int = 100, completion: int = 50) -> dict:
    return {
        "choices": [{"message": {"content": text}, "finish_reason": "stop"}],
        "usage": {
            "prompt_tokens": prompt,
            "completion_tokens": completion,
            "prompt_tokens_details": {"cached_tokens": 0},
        },
    }


def _fake_urlopen(payload: dict):
    body = json.dumps(payload).encode("utf-8")

    class FakeResp:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return body

    return mock.patch("urllib.request.urlopen", return_value=FakeResp())


# —— 显式开关 ——


def test_extract_config_mode_validation() -> None:
    for mode in ("off", "local", "cloud", "main"):
        assert ExtractConfig(mode=mode).mode == mode
    with pytest.raises(ValueError):
        ExtractConfig(mode="banana")


def test_extract_config_default_mode_is_main() -> None:
    """默认 main：local/cloud 不配置时提取自动复用主对话模型。"""
    assert ExtractConfig().mode == "main"
    assert ExtractConfig().main.max_turn_chars > 0


def test_build_extractor_off_returns_none() -> None:
    assert build_extractor(ExtractConfig(mode="off")) is None


def test_build_extractor_local_wires_strategy() -> None:
    ex = build_extractor(ExtractConfig(mode="local", local=_local_cfg()))
    assert isinstance(ex, LLMExtractor)
    assert ex.batch_size == 1
    assert ex.strategy.name == "local"


def test_build_extractor_local_requires_config() -> None:
    with pytest.raises(ValueError, match="local 模式已激活但未配置"):
        build_extractor(
            ExtractConfig(mode="local", local=LocalConfig(preset="custom"))
        )


def test_resolve_local_config_default_preset_expands_recipe() -> None:
    """默认预设（qwen3-it-4b-flm）自动展开 base_url/model/thinking 关闭。"""
    from memory.backends import LOCAL_PRESETS, resolve_local_config

    cfg = resolve_local_config(LocalConfig())
    recipe = LOCAL_PRESETS["qwen3-it-4b-flm"]
    assert cfg.base_url == recipe["base_url"]
    assert cfg.model == recipe["model"]
    assert cfg.extra_body == {"chat_template_kwargs": {"enable_thinking": False}}
    assert cfg.preset == "qwen3-it-4b-flm"


def test_resolve_local_config_explicit_values_win() -> None:
    """preset 默认但显式填了 base_url/model → 尊重显式值。"""
    from memory.backends import resolve_local_config

    cfg = resolve_local_config(
        LocalConfig(base_url="http://127.0.0.1:8000/v1", model="my-local")
    )
    assert cfg.base_url == "http://127.0.0.1:8000/v1"
    assert cfg.model == "my-local"


def test_resolve_local_config_custom_passthrough() -> None:
    from memory.backends import resolve_local_config

    cfg = resolve_local_config(
        LocalConfig(preset="custom", base_url="http://x/v1", model="m")
    )
    assert cfg.base_url == "http://x/v1"
    assert cfg.model == "m"


def test_build_extractor_local_default_preset_invokes_ready_hook() -> None:
    """默认预设 + auto_manage：提取前调用 local_ready（lemonade 拉起钩子）。"""
    calls: list[LocalConfig] = []

    ex = build_extractor(
        ExtractConfig(mode="local"),
        local_ready=lambda cfg: calls.append(cfg),
    )
    assert isinstance(ex, LLMExtractor)
    assert len(calls) == 1
    assert calls[0].model == "qwen3-it-4b-FLM"


def test_build_extractor_local_custom_skips_auto_manage() -> None:
    """preset=custom：即使 auto_manage=True 也不触发 lemonade 管理。"""
    calls: list[LocalConfig] = []

    build_extractor(
        ExtractConfig(mode="local", local=_local_cfg()),
        local_ready=lambda cfg: calls.append(cfg),
    )
    assert calls == []


def test_build_extractor_cloud_wires_strategy() -> None:
    ex = build_extractor(ExtractConfig(mode="cloud", cloud=_cloud_cfg()))
    assert isinstance(ex, LLMExtractor)
    assert ex.strategy.name == "cloud"


def test_build_extractor_cloud_requires_config() -> None:
    with pytest.raises(ValueError, match="cloud 模式已激活但未配置"):
        build_extractor(ExtractConfig(mode="cloud"))


def test_build_extractor_main_requires_backend() -> None:
    with pytest.raises(ValueError, match="main 模式需要注入主对话模型后端"):
        build_extractor(ExtractConfig(mode="main"))


def test_build_extractor_main_wires_fallback() -> None:
    ex = build_extractor(
        ExtractConfig(mode="main"), main_backend=_FakeBackend()
    )
    assert isinstance(ex, LLMExtractor)
    assert ex.strategy.name == "main"


class _FakeBackend:
    model = "main-model"

    def complete(self, messages, **kw) -> BackendResult:
        return BackendResult(text='{"cards": []}', usage=UsageInfo())

    def count_tokens(self, text: str) -> int:
        return max(1, len(text) // 2)


# —— 环境变量装配（激活后配置，不硬编码）——


def test_load_extract_config_from_env_cloud() -> None:
    env = {
        "MEMORY_EXTRACT_MODE": "cloud",
        "MEMORY_CLOUD_BASE_URL": "https://api.deepseek.com/v1",
        "MEMORY_CLOUD_API_KEY": "sk-test",
        "MEMORY_CLOUD_MODEL": "deepseek-chat",
    }
    cfg = load_extract_config(env)
    assert cfg.mode == "cloud"
    assert cfg.cloud.base_url == "https://api.deepseek.com/v1"
    assert cfg.cloud.api_key == "sk-test"
    assert cfg.cloud.model == "deepseek-chat"


def test_load_extract_config_from_env_local() -> None:
    env = {
        "MEMORY_EXTRACT_MODE": "local",
        "MEMORY_LOCAL_BASE_URL": "http://127.0.0.1:8000/v1",
        "MEMORY_LOCAL_MODEL": "qwen-4b",
    }
    cfg = load_extract_config(env)
    assert cfg.mode == "local"
    assert cfg.local.base_url == "http://127.0.0.1:8000/v1"
    assert cfg.local.model == "qwen-4b"


def test_load_extract_config_defaults_main_and_empty() -> None:
    """mode 缺省 main（复用主对话模型）；未激活的后端配置全空。"""
    cfg = load_extract_config({})
    assert cfg.mode == "main"  # 默认走主对话模型，不硬编码供应商
    assert cfg.local.base_url == ""
    assert cfg.local.model == ""
    assert cfg.cloud.base_url == "https://api.deepseek.com/v1"
    assert cfg.cloud.api_key == ""


# —— 本地后端 ——


def test_local_backend_posts_chat_completions() -> None:
    backend = LocalBackend(_local_cfg())
    with _fake_urlopen(_ok_response('{"cards": []}')) as m:
        result = backend.complete([{"role": "user", "content": "hi"}], max_tokens=64)
    req = m.call_args[0][0]
    assert req.full_url.endswith("/chat/completions")
    body = json.loads(req.data.decode("utf-8"))
    assert body["model"] == "memreader-4b-thinking"
    assert body["stream"] is False
    assert result.text == '{"cards": []}'
    assert result.usage.prompt_tokens == 100
    assert result.usage.completion_tokens == 50


# —— 本地轨脱敏（防 key 进记忆卡）——


def test_local_backend_sanitizes_sensitive_content() -> None:
    """本地轨默认脱敏：API key/凭证在提取前替换为占位符（防进记忆卡）。"""
    backend = LocalBackend(_local_cfg())
    secret = "我的 key 是 sk-abcdefghijklmnop，密码 password=123456"
    with _fake_urlopen(_ok_response("ok")) as m:
        backend.complete([{"role": "user", "content": secret}])
    req = m.call_args[0][0]
    body = json.loads(req.data.decode("utf-8"))
    sent = body["messages"][0]["content"]
    assert "sk-abcdefghijklmnop" not in sent
    assert "password=123456" not in sent
    assert "api_key" in backend.last_sanitize_hits
    assert "credential" in backend.last_sanitize_hits


def test_local_backend_sanitize_can_be_disabled() -> None:
    """显式关闭本地轨脱敏（信任本地模型/数据时）。"""
    backend = LocalBackend(_local_cfg(sanitize=False))
    secret = "sk-abcdefghijklmnop"
    with _fake_urlopen(_ok_response("ok")) as m:
        backend.complete([{"role": "user", "content": f"key {secret}"}])
    req = m.call_args[0][0]
    body = json.loads(req.data.decode("utf-8"))
    assert secret in body["messages"][0]["content"]
    assert backend.last_sanitize_hits == []


def test_local_backend_sanitize_keeps_normal_text() -> None:
    """脱敏不误伤正常中文内容。"""
    backend = LocalBackend(_local_cfg())
    text = "用户喜欢喝茶，明天去杭州，部署端口是 8080"
    with _fake_urlopen(_ok_response("ok")) as m:
        backend.complete([{"role": "user", "content": text}])
    req = m.call_args[0][0]
    body = json.loads(req.data.decode("utf-8"))
    sent = body["messages"][0]["content"]
    assert "喜欢喝茶" in sent
    assert "8080" in sent  # 端口数字不脱敏（非凭证）
    assert backend.last_sanitize_hits == []


# —— 脱敏（安全缺口堵漏）——


def test_cloud_backend_sanitizes_sensitive_content() -> None:
    backend = CloudBackend(_cloud_cfg())
    secret = "AKIAABCDEFGHIJKLMNOP password=123456"
    with _fake_urlopen(_ok_response("ok")) as m:
        backend.complete([{"role": "user", "content": secret}])
    req = m.call_args[0][0]
    body = json.loads(req.data.decode("utf-8"))
    sent = body["messages"][0]["content"]
    assert "AKIAABCDEFGHIJKLMNOP" not in sent
    assert "password=123456" not in sent
    assert "aws_key" in backend.last_sanitize_hits
    assert "credential" in backend.last_sanitize_hits


def test_cloud_backend_sanitize_can_be_disabled() -> None:
    backend = CloudBackend(_cloud_cfg(sanitize=False))
    secret = "sk-abcdefghijklmnop"
    with _fake_urlopen(_ok_response("ok")) as m:
        backend.complete([{"role": "user", "content": f"key {secret}"}])
    req = m.call_args[0][0]
    body = json.loads(req.data.decode("utf-8"))
    assert secret in body["messages"][0]["content"]  # 显式关闭脱敏
    assert backend.last_sanitize_hits == []


# —— 通用 OpenAI 兼容云端 ——


def test_cloud_backend_rate_limit() -> None:
    backend = CloudBackend(_cloud_cfg(max_calls_per_minute=2))
    with _fake_urlopen(_ok_response("ok")):
        backend.complete([{"role": "user", "content": "a"}])
        backend.complete([{"role": "user", "content": "b"}])
        with pytest.raises(RateLimitedError):
            backend.complete([{"role": "user", "content": "c"}])
    assert backend.cost_summary()["calls"] == 2


def test_cloud_backend_cost_ledger() -> None:
    backend = CloudBackend(_cloud_cfg())
    with _fake_urlopen(_ok_response("ok", prompt=120, completion=30)):
        backend.complete([{"role": "user", "content": "a"}])
        backend.complete([{"role": "user", "content": "b"}])
    summary = backend.cost_summary()
    assert summary["calls"] == 2
    assert summary["prompt_tokens"] == 240
    assert summary["completion_tokens"] == 60
    assert summary["total_tokens"] == 300


# —— 主对话模型兜底 ——


def test_main_model_backend_delegates() -> None:
    calls: list[dict] = []

    class _Delegate:
        model = "deepseek-chat"

        def complete(self, messages, **kw) -> BackendResult:
            calls.append({"messages": messages, "temperature": kw.get("temperature")})
            return BackendResult(text='{"cards": []}')

        def count_tokens(self, text: str) -> int:
            return len(text)

    backend = MainModelBackend(_Delegate())
    result = backend.complete([{"role": "user", "content": "hi"}], temperature=0.3)
    assert calls[0]["temperature"] == 0.3  # 原样转发调用方参数
    assert result.text == '{"cards": []}'
    assert backend.model == "deepseek-chat"
    assert backend.count_tokens("abc") == 3


# —— 策略路由 ——


def test_local_strategy_truncates_over_capacity() -> None:
    strat = LocalStrategy(_local_cfg(max_turn_chars=10))
    d = strat.decide(_run(user="很长的用户消息", reply="很长的回复"))
    assert d.backend == "local"
    assert d.reason == "truncated_over_capacity"


def test_main_strategy_truncates_over_capacity() -> None:
    strat = MainStrategy(MainModelConfig(max_turn_chars=10))
    d = strat.decide(_run(user="很长的用户消息", reply="很长的回复"))
    assert d.backend == "main"
    assert d.reason == "truncated_over_capacity"
    assert strat.batch_size() == 1


def test_cloud_strategy_skips_over_capacity() -> None:
    strat = CloudStrategy(_cloud_cfg(max_turn_chars=10))
    d = strat.decide(_run(user="很长的用户消息", reply="很长的回复"))
    assert d.backend == "skip"
    assert d.reason == "over_capacity"


def test_hybrid_escalates_to_cloud() -> None:
    strat = HybridStrategy(_local_cfg(max_turn_chars=10), _cloud_cfg())
    d = strat.decide(_run(user="很长的用户消息", reply="很长的回复"))
    assert d.backend == "cloud"
    assert d.reason == "too_long_for_local"


def test_cloud_strategy_batch_size() -> None:
    assert CloudStrategy(_cloud_cfg(batch_size=5)).batch_size() == 5
    assert LocalStrategy(_local_cfg()).batch_size() == 1


# —— 批量攒批提取（云端）——


def test_cloud_extract_batch_single_call() -> None:
    cfg = _cloud_cfg(batch_size=2)
    backend = CloudBackend(cfg)
    calls: list[dict] = []
    batch_text = json.dumps(
        {
            "results": [
                {
                    "idx": 0,
                    "cards": [
                        {
                            "title": "甲",
                            "content": "用户喜欢喝茶",
                            "evidence": "explicit",
                            "chain": "",
                            "entities": [],
                            "supersedes": "",
                            "ended": False,
                            "source_part": "user",
                        }
                    ],
                },
                {
                    "idx": 1,
                    "cards": [
                        {
                            "title": "乙",
                            "content": "推断迁移可能",
                            "evidence": "inferred",
                            "chain": "",
                            "entities": [],
                            "supersedes": "",
                            "ended": False,
                            "source_part": "user",
                        }
                    ],
                },
            ]
        },
        ensure_ascii=False,
    )

    def fake_urlopen(req, timeout=None):
        calls.append(json.loads(req.data.decode("utf-8")))
        body = json.dumps(_ok_response(batch_text)).encode("utf-8")

        class FakeResp:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def read(self):
                return body

        return FakeResp()

    ex = LLMExtractor(backend, strategy=CloudStrategy(cfg))
    with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
        out = ex.extract_batch([_run("u1", "r1", "run-1"), _run("u2", "r2", "run-2")])

    assert len(calls) == 1  # 攒批：一次调用
    assert calls[0]["messages"][0]["content"].startswith("你是一次性记忆提取器")
    assert len(out) == 2
    assert out[0].cards[0][0].content == "用户喜欢喝茶"
    assert out[1].cards[0][0].content == "推断迁移可能"
    assert backend.cost_summary()["calls"] == 1


def test_local_extract_batch_loops_per_run() -> None:
    backend = LocalBackend(_local_cfg())
    ex = LLMExtractor(backend, strategy=LocalStrategy(_local_cfg()))
    calls: list[str] = []
    payload = json.dumps(
        {
            "cards": [
                {
                    "title": "X",
                    "content": "内容",
                    "evidence": "explicit",
                    "chain": "",
                    "entities": [],
                    "supersedes": "",
                    "ended": False,
                    "source_part": "user",
                }
            ]
        },
        ensure_ascii=False,
    )

    def fake_urlopen(req, timeout=None):
        calls.append(req.full_url)
        body = json.dumps(_ok_response(payload)).encode("utf-8")

        class FakeResp:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def read(self):
                return body

        return FakeResp()

    with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
        out = ex.extract_batch([_run("u1", "r1", "run-1"), _run("u2", "r2", "run-2")])
    assert len(calls) == 2  # 本地逐条
    assert len(out) == 2


# —— P1b：路由消费 / retries 落地 ——


def test_extract_modes_include_hybrid() -> None:
    """P1b：hybrid 分支可达（此前 EXTRACT_MODES 无 hybrid，build_extractor 分支死代码）。"""
    assert "hybrid" in EXTRACT_MODES
    assert ExtractConfig(mode="hybrid").mode == "hybrid"


def test_route_decision_skip_consumed_no_call() -> None:
    """P1b：云端超容量 → 策略裁决 skip，一次调用都不发（省一次调用真正落地）。"""
    cfg = _cloud_cfg(max_turn_chars=10)
    backend = CloudBackend(cfg)
    ex = LLMExtractor(backend, strategy=CloudStrategy(cfg))

    def _explode(req, timeout=None):
        raise AssertionError("超容量 run 不应发出云端调用")

    with mock.patch("urllib.request.urlopen", side_effect=_explode):
        result = ex.extract(_run(user="很长的用户消息", reply="很长的回复"))
    assert result.cards == [] and result.wiki_entries == []
    assert backend.cost_summary()["calls"] == 0


def test_hybrid_routes_cloud_when_local_over_capacity() -> None:
    """P1b：hybrid 本地超长 → 降级云端（RouteDecision.backend 真正消费）。"""
    local_calls = {"n": 0}
    cloud_calls = {"n": 0}

    class _Local:
        def complete(self, messages, **kw):
            local_calls["n"] += 1
            return BackendResult(text='{"cards": []}')

        def count_tokens(self, t):
            return len(t)

    class _Cloud:
        def complete(self, messages, **kw):
            cloud_calls["n"] += 1
            return BackendResult(text='{"cards": []}')

        def count_tokens(self, t):
            return len(t)

    # 本地容量内 → 本地
    ex_ok = LLMExtractor(
        _Local(), fallback_backend=_Cloud(),
        strategy=HybridStrategy(_local_cfg(max_turn_chars=1000), _cloud_cfg()),
    )
    ex_ok.extract(_run(user="短", reply="短"))
    assert local_calls["n"] == 1 and cloud_calls["n"] == 0

    # 本地超长 → 云端
    ex_big = LLMExtractor(
        _Local(), fallback_backend=_Cloud(),
        strategy=HybridStrategy(_local_cfg(max_turn_chars=10), _cloud_cfg()),
    )
    ex_big.extract(_run(user="很长的用户消息", reply="很长的回复"))
    assert local_calls["n"] == 1 and cloud_calls["n"] == 1


def test_cloud_retries_transient_failure(monkeypatch) -> None:
    """P1b：CloudConfig.retries 落地——瞬时失败退避重试到成功。"""
    attempts = {"n": 0}

    def flaky(self, messages, **kw):
        attempts["n"] += 1
        if attempts["n"] <= 2:
            raise RetryableBackendError("flaky 5xx")
        return BackendResult(text='{"cards": []}', usage=UsageInfo(1, 1))

    monkeypatch.setattr(_OpenAICompatBackend, "complete", flaky)
    backend = CloudBackend(_cloud_cfg(retries=2))
    result = backend.complete([{"role": "user", "content": "hi"}])
    assert attempts["n"] == 3  # 2 次失败 + 1 次成功
    assert backend.cost_summary()["calls"] == 1  # 只记成功调用


def test_cloud_no_retry_on_4xx(monkeypatch) -> None:
    """P1b：4xx（请求本身问题）不重试。"""
    attempts = {"n": 0}

    def bad(self, messages, **kw):
        attempts["n"] += 1
        raise BackendError("HTTP 401")

    monkeypatch.setattr(_OpenAICompatBackend, "complete", bad)
    backend = CloudBackend(_cloud_cfg(retries=3))
    with pytest.raises(BackendError):
        backend.complete([{"role": "user", "content": "hi"}])
    assert attempts["n"] == 1
