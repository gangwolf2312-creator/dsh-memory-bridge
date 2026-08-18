# -*- coding: utf-8 -*-
"""memory/lemonade.py 状态机单测：health / 拉起服务 / 加载模型 / 超时 / 并发。"""
import subprocess
import threading
from unittest import mock

import pytest

from memory.lemonade import (
    DEFAULT_PRESET_MODEL,
    LemonadeError,
    LemonadeManager,
    LemonadeStatus,
    _parse_status,
    ensure_local_ready,
    set_runner,
)

UP_STATUS = """Server is running on port 13305

Property            Value
--------------------------------------------------
Version             11.6.0
WebSocket Port      9000
Max Models/Type     2

Model                         Type      Device    Recipe        Checkpoint
----------------------------------------------------------------------------------------------------
Muse-Glimmer-30B-GGUF         llm       gpu       llamacpp      unsloth/Muse-Glimmer-30B-GGUF:UD-Q4_K_XL
"""

UP_WITH_PRESET = UP_STATUS + DEFAULT_PRESET_MODEL + "              llm       npu       flm          qwen3-it-4b-FLM\n"


class _FakeProc:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _subcommand(cmd):
    """提取 lemonade 子命令（cmd = [lemonade, --host, h, --port, p, <sub>, ...]）。"""
    for token in cmd[5:]:
        if not token.startswith("-"):
            return token
    return ""


def _status_proc(state):
    if not state["server_up"]:
        return _FakeProc(1, "", "Failed to connect to server")
    return _FakeProc(0, UP_WITH_PRESET if state["loaded"] else UP_STATUS, "")


def _runner_from_state(state):
    """根据可变状态构建 fake runner：state 持有 server_up / loaded 开关。"""

    def fake(cmd, timeout=60.0):
        sub = _subcommand(cmd)
        if sub == "status":
            return _status_proc(state)
        if sub == "load":
            state["loaded"] = True
            return _FakeProc(0, "", "")
        if sub == "list":
            return _FakeProc(0, DEFAULT_PRESET_MODEL, "")
        return _FakeProc(0, "", "")

    return fake


def test_parse_status_server_up_model_loaded() -> None:
    st = _parse_status(0, UP_WITH_PRESET, "", model=DEFAULT_PRESET_MODEL)
    assert st.server_up
    assert st.model_loaded
    assert "Muse-Glimmer-30B-GGUF" in st.loaded_models
    assert st.version == "11.6.0"


def test_parse_status_server_up_model_not_loaded() -> None:
    st = _parse_status(0, UP_STATUS, "", model=DEFAULT_PRESET_MODEL)
    assert st.server_up
    assert not st.model_loaded


def test_parse_status_server_down() -> None:
    st = _parse_status(1, "", "connection refused", model=DEFAULT_PRESET_MODEL)
    assert not st.server_up
    assert not st.model_loaded


def test_ensure_ready_already_ready_no_extra_calls() -> None:
    state = {"server_up": True, "loaded": True}
    calls = []

    def fake(cmd, timeout=60.0):
        calls.append(_subcommand(cmd))
        return _runner_from_state(state)(cmd)

    mgr = LemonadeManager(runner=fake)
    st = mgr.ensure_ready()
    assert st.model_loaded
    assert calls == ["status"]


def test_ensure_ready_starts_server_then_loads_model() -> None:
    state = {"server_up": False, "loaded": False}
    status_calls = {"n": 0}
    calls = []

    def fake(cmd, timeout=60.0):
        sub = _subcommand(cmd)
        calls.append(sub)
        if sub == "status":
            status_calls["n"] += 1
            # 首次 status（服务未起）→ refused；_start_server 之后的轮询 → 起来
            if status_calls["n"] == 1:
                return _FakeProc(1, "", "refused")
            return _status_proc(state)
        return _runner_from_state(state)(cmd)

    events: list[tuple[str, str]] = []

    def _fake_popen(*_args, **_kwargs):
        state["server_up"] = True  # 模拟 LemonadeServer 拉起成功
        return mock.MagicMock()

    with mock.patch("memory.lemonade.subprocess.Popen", side_effect=_fake_popen) as popen:
        mgr = LemonadeManager(runner=fake, on_event=lambda t, d: events.append((t, d)))
        st = mgr.ensure_ready(server_timeout_s=10, load_timeout_s=10)
    assert st.server_up and st.model_loaded
    assert popen.called
    assert any(t == "lemonade_start" for t, _ in events)
    assert any(t == "lemonade_load" for t, _ in events)
    assert any(t == "local_backend_ready" for t, _ in events)


def test_ensure_ready_load_failure_raises_with_hint() -> None:
    state = {"server_up": True, "loaded": False}

    def fake(cmd, timeout=60.0):
        sub = _subcommand(cmd)
        if sub == "status":
            return _status_proc(state)
        if sub == "load":
            return _FakeProc(1, "", "model not found")
        if sub == "list":
            return _FakeProc(0, "SomeOtherModel", "")  # 目标模型未下载
        return _FakeProc(0, "", "")

    mgr = LemonadeManager(runner=fake)
    with pytest.raises(LemonadeError, match="lemonade pull"):
        mgr.ensure_ready(load_timeout_s=0.1)


def test_ensure_ready_server_start_timeout() -> None:
    def fake(cmd, timeout=60.0):
        return _FakeProc(1, "", "refused")

    with mock.patch("memory.lemonade.subprocess.Popen"):
        mgr = LemonadeManager(runner=fake)
        with pytest.raises(LemonadeError, match="服务启动超时"):
            mgr.ensure_ready(server_timeout_s=0.1)


def test_ensure_ready_load_timeout() -> None:
    state = {"server_up": True, "loaded": False}

    def fake(cmd, timeout=60.0):
        sub = _subcommand(cmd)
        if sub == "status":
            return _status_proc(state)  # load 后 status 一直不变（loaded=False）
        if sub == "load":
            return _FakeProc(0, "", "")
        return _FakeProc(0, "", "")

    mgr = LemonadeManager(runner=fake)
    with pytest.raises(LemonadeError, match="加载 .* 超时"):
        mgr.ensure_ready(load_timeout_s=0.1)


def test_ensure_ready_start_server_false_when_down() -> None:
    def fake(cmd, timeout=60.0):
        return _FakeProc(1, "", "refused")

    mgr = LemonadeManager(runner=fake)
    with pytest.raises(LemonadeError, match="start_server=False"):
        mgr.ensure_ready(start_server=False)


def test_ensure_ready_concurrent_load_once() -> None:
    """并发 ensure_ready：串行化，load 只执行一次。"""
    state = {"server_up": True, "loaded": False}
    load_count = 0
    lock = threading.Lock()

    def fake(cmd, timeout=60.0):
        nonlocal load_count
        sub = _subcommand(cmd)
        if sub == "status":
            return _status_proc(state)
        if sub == "load":
            with lock:
                load_count += 1
            state["loaded"] = True
            return _FakeProc(0, "", "")
        return _FakeProc(0, "", "")

    mgr = LemonadeManager(runner=fake)
    results: list[LemonadeStatus] = []
    errs: list[Exception] = []

    def run():
        try:
            results.append(mgr.ensure_ready(load_timeout_s=10))
        except Exception as exc:  # noqa: BLE001
            errs.append(exc)

    threads = [threading.Thread(target=run) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errs
    assert all(r.model_loaded for r in results)
    assert load_count == 1


def test_ensure_local_ready_uses_injected_runner() -> None:
    state = {"server_up": True, "loaded": True}
    set_runner(_runner_from_state(state))
    try:
        st = ensure_local_ready()
        assert st.model_loaded
    finally:
        set_runner(None)
