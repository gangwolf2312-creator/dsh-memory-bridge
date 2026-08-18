"""Lemonade 本地轨自动拉起（健康检查 + 服务拉起 + 模型加载）。

mode=local 且 preset 为默认本地轨时，提取前保证 Lemonade 推理服务与目标
模型就绪，否则提取会直接打到连接失败：

    health -> lemonade status
      ├─ 服务未运行 → 拉起 LemonadeServer.exe（detached）→ 轮询 ≤90s
      └─ 服务在     → 检查目标模型是否已加载
                      ├─ 已加载 → 就绪（零开销直接过）
                      └─ 未加载 → lemonade load <model> → 轮询 ≤120s
  就绪 → 装配 LocalBackend 开始提取

幂等：ensure_ready 串行化（锁），并发调用只跑一次完整状态机，后续调用
快速重查即跳过。CLI 调用层可注入（runner），单测用 fake 覆盖全部状态机
分支；事件经 on_event 回调进 decision_log（topic="lemonade"）。

不硬编码路径：服务可执行文件按 环境变量 LEMONADE_SERVER_EXE >
lemonade.exe 同目录 LemonadeServer.exe 解析；端口走 13305（LEMONADE_PORT
环境变量可覆盖）。
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

__all__ = [
    "DEFAULT_LEMONADE_HOST",
    "DEFAULT_LEMONADE_PORT",
    "DEFAULT_PRESET_MODEL",
    "DEFAULT_SERVER_START_TIMEOUT_S",
    "DEFAULT_LOAD_TIMEOUT_S",
    "LemonadeError",
    "LemonadeManager",
    "LemonadeStatus",
    "ensure_local_ready",
]

DEFAULT_LEMONADE_HOST = "127.0.0.1"
DEFAULT_LEMONADE_PORT = 13305
DEFAULT_PRESET_MODEL = "qwen3-it-4b-FLM"

DEFAULT_SERVER_START_TIMEOUT_S = 90.0
DEFAULT_LOAD_TIMEOUT_S = 120.0
_POLL_STEP_S = 2.0

_STATUS_OK_RE = re.compile(r"Server is running")
_MODEL_HEADER_RE = re.compile(r"^Model\s+Type\s+Device\s+Recipe\s+Checkpoint")
_SEPARATOR_RE = re.compile(r"^[-]+\s*$")
_VERSION_RE = re.compile(r"^Version\s+(\S+)", re.MULTILINE)

_runner_override: Callable[[list[str]], subprocess.CompletedProcess] | None = None
_runner_lock = threading.Lock()


@dataclass(frozen=True, slots=True)
class LemonadeStatus:
    """一次 `lemonade status` 的解析结果。"""

    server_up: bool
    model_loaded: bool = False
    loaded_models: tuple[str, ...] = ()
    version: str = ""
    raw: str = ""


class LemonadeError(RuntimeError):
    """lemonade 健康检查/拉起失败（服务起不来 / 模型未下载 / 加载超时）。"""


def set_runner(runner: Callable[[list[str]], subprocess.CompletedProcess] | None) -> None:
    """测试注入：替换全局 runner（None 恢复默认 subprocess.run）。"""
    global _runner_override
    with _runner_lock:
        _runner_override = runner


def _default_runner(cmd: list[str], timeout: float = 60.0) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        encoding="utf-8",
        errors="replace",
    )


def _server_exe() -> str | None:
    """解析 LemonadeServer 可执行文件路径（不硬编码用户目录）。"""
    env = os.environ.get("LEMONADE_SERVER_EXE")
    if env and Path(env).is_file():
        return env
    cli = shutil.which("lemonade") or shutil.which("lemonade.exe")
    if cli:
        candidate = Path(cli).with_name("LemonadeServer.exe")
        if candidate.is_file():
            return str(candidate)
    return None


def _parse_status(returncode: int, stdout: str, stderr: str, *, model: str = "") -> LemonadeStatus:
    """解析 `lemonade status` 输出。

    服务在：exit 0 且 stdout 含 "Server is running"；加载模型列取自
    "Model Type Device Recipe Checkpoint" 表头下方的行首 token。
    """
    text = stdout if returncode == 0 else (stdout + "\n" + stderr)
    server_up = returncode == 0 and bool(_STATUS_OK_RE.search(stdout or ""))
    version = ""
    loaded: list[str] = []
    if server_up:
        m = _VERSION_RE.search(stdout or "")
        if m:
            version = m.group(1)
        in_table = False
        for line in (stdout or "").splitlines():
            if _MODEL_HEADER_RE.search(line):
                in_table = True
                continue
            if in_table:
                if _SEPARATOR_RE.search(line):
                    continue
                stripped = line.strip()
                if not stripped:
                    continue
                loaded.append(stripped.split()[0])
    return LemonadeStatus(
        server_up=server_up,
        model_loaded=model in loaded if model else False,
        loaded_models=tuple(loaded),
        version=version,
        raw=text,
    )


class LemonadeManager:
    """Lemonade 健康检查与自动拉起状态机。

    Args:
        runner: CLI 调用器（默认 subprocess.run；单测注入 fake）。
        on_event: 事件回调(topic, detail)，接线到 decision_log。
        host / port: 服务地址（默认 127.0.0.1:13305）。
    """

    def __init__(
        self,
        *,
        runner: Callable[[list[str], float], subprocess.CompletedProcess] | None = None,
        on_event: Callable[[str, str], None] | None = None,
        host: str = "",
        port: int = 0,
    ) -> None:
        self._runner = runner or _default_runner
        self._on_event = on_event or (lambda topic, detail: None)
        self._host = host or os.environ.get("LEMONADE_HOST", DEFAULT_LEMONADE_HOST)
        try:
            self._port = int(os.environ.get("LEMONADE_PORT", DEFAULT_LEMONADE_PORT))
        except ValueError:
            self._port = DEFAULT_LEMONADE_PORT
        if port:
            self._port = port
        self._ensure_lock = threading.Lock()

    def _cli(self, *args: str) -> subprocess.CompletedProcess:
        cmd = ["lemonade", "--host", self._host, "--port", str(self._port), *args]
        return self._runner(cmd)

    def _notify(self, topic: str, detail: str) -> None:
        try:
            self._on_event(topic, detail)
        except Exception:
            pass

    def status(self, *, model: str = "") -> LemonadeStatus:
        """健康检查：`lemonade status`（服务在 + 模型加载状态）。"""
        try:
            proc = self._cli("status")
        except Exception:
            return LemonadeStatus(server_up=False, model_loaded=False, loaded_models=(), raw="")
        return _parse_status(proc.returncode, proc.stdout or "", proc.stderr or "", model=model)

    def ensure_ready(
        self,
        model: str = DEFAULT_PRESET_MODEL,
        *,
        start_server: bool = True,
        load_model: bool = True,
        pin: bool = False,
        server_timeout_s: float = DEFAULT_SERVER_START_TIMEOUT_S,
        load_timeout_s: float = DEFAULT_LOAD_TIMEOUT_S,
    ) -> LemonadeStatus:
        """保证目标模型就绪：服务在 → 模型已加载 → 返回；否则逐级拉起。

        串行化（锁）：并发调用只跑一次完整状态机，其余等待后快速重查跳过。
        Raises:
            LemonadeError: 服务起不来 / 模型未下载 / 加载或轮询超时。
        """
        with self._ensure_lock:
            st = self.status(model=model)
            if st.server_up and (not load_model or st.model_loaded):
                return st
            if not st.server_up:
                if not start_server:
                    raise LemonadeError(
                        "lemonade 服务未运行（127.0.0.1:%d），且 start_server=False" % self._port
                    )
                self._notify("lemonade_start", "spawn LemonadeServer（%s:%s）" % (self._host, self._port))
                self._start_server()
                st = self._poll_server(model=model, timeout_s=server_timeout_s)
            if load_model and not st.model_loaded:
                self._notify("lemonade_load", "load %s（pin=%s）" % (model, pin))
                self._load_model(model, pin=pin)
                st = self._poll_model_loaded(model=model, timeout_s=load_timeout_s)
            return st

    def _start_server(self) -> None:
        exe = _server_exe()
        if exe is None:
            raise LemonadeError(
                "找不到 LemonadeServer.exe：请确保 lemonade 已安装或在 PATH，"
                "或设置 LEMONADE_SERVER_EXE 指向服务可执行文件"
            )
        kwargs: dict[str, object] = {
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
            "close_fds": True,
        }
        if sys.platform == "win32":
            kwargs["creationflags"] = (
                subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
            )
            kwargs["shell"] = False
        try:
            subprocess.Popen([exe], **kwargs)
        except Exception as exc:  # pragma: no cover - 系统级启动失败
            raise LemonadeError("LemonadeServer 启动失败: %s" % exc) from exc

    def _load_model(self, model: str, *, pin: bool) -> None:
        args = ["load", model] + (["--pinned"] if pin else [])
        proc = self._cli(*args)
        if proc.returncode != 0:
            hint = self._download_hint(model)
            raise LemonadeError(
                "lemonade load %s 失败（exit=%d）：%s%s"
                % (model, proc.returncode, (proc.stderr or proc.stdout or "").strip(), hint)
            )

    def _download_hint(self, model: str) -> str:
        """模型未下载时给出 lemonade pull 提示（尽力而为，失败不阻断）。"""
        try:
            proc = self._cli("list", "--downloaded")
        except Exception:
            return ""
        text = (proc.stdout or "") + (proc.stderr or "")
        if model.lower() in text.lower():
            return ""
        return "；模型未在本地下载清单中，可尝试 `lemonade pull %s`" % model

    def _poll_server(self, *, model: str, timeout_s: float) -> LemonadeStatus:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            st = self.status(model=model)
            if st.server_up:
                return st
            time.sleep(min(_POLL_STEP_S, max(0.05, deadline - time.monotonic())))
        self._notify("lemonade_timeout", "服务启动超时 %.0fs" % timeout_s)
        raise LemonadeError("lemonade 服务启动超时（%.0fs），请手动启动或查看 LEMONADE_SERVER_EXE" % timeout_s)

    def _poll_model_loaded(self, *, model: str, timeout_s: float) -> LemonadeStatus:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            st = self.status(model=model)
            if st.model_loaded:
                self._notify("local_backend_ready", "模型 %s 已就绪" % model)
                return st
            time.sleep(min(_POLL_STEP_S, max(0.05, deadline - time.monotonic())))
        self._notify("lemonade_timeout", "模型加载超时 %.0fs" % timeout_s)
        raise LemonadeError("lemonade 加载 %s 超时（%.0fs）" % (model, timeout_s))


def ensure_local_ready(
    *,
    model: str = DEFAULT_PRESET_MODEL,
    on_event: Callable[[str, str], None] | None = None,
) -> LemonadeStatus:
    """模块级便捷入口：默认 runner（可被 set_runner 注入）拉起目标模型。"""
    runner = _default_runner
    with _runner_lock:
        if _runner_override is not None:
            runner = _runner_override
    return LemonadeManager(runner=runner, on_event=on_event).ensure_ready(model=model)
