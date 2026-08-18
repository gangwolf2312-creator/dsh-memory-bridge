"""DSH 会话日志字段匹配：session.jsonl(.zstd) 事件流 -> MemoryRun。

DSH 负责写日志与挂插件钩子；本模块只做字段匹配与内部管道（零 LLM、
零网络、标准库，zstd 解压走可选依赖 zstandard）。

字段匹配契约（实测 DSH 事件结构）：

| DSH 事件字段                                    | MemoryRun 字段    |
|-------------------------------------------------|-------------------|
| header（type=session, id）                      | session_id        |
| turn/start / turn/end（data.turn）              | run_id 组成（会话+回合哈希）|
| user/message（data.content[].text 拼接）        | user_text         |
| assistant/message（data.message.content 中      | reply_text        |
|   type=="text" 拼接）                           |                   |
| assistant/message.usage（provider 上报 token）  | 成本审计（decision_log）|
| user/message（data.id，回合首个）               | trace_event_id    |
| tool/call（data.callId -> data.name）           | 工具名关联（callId 查表）|
| tool/result（message.content 内 tool-result 块  | reply_text（`[tool:name]` 前缀，| 
|   中 type==text 拼接，isError 标记）            |   截断 + 回合总预算）          |

幂等：run_id = sha1(session_id|turn) 前缀，store.insert_run 的
INSERT OR IGNORE 天然去重 —— 日志可重放、可重跑提取。
"""

from __future__ import annotations

import contextlib
import hashlib
import json
from pathlib import Path
from typing import Any, Iterator

from memory.models import MemoryRun
from memory.store import MemoryStore

__all__ = [
    "iter_events",
    "parse_session_runs",
    "backfill_runs",
    "open_session_log",
]


def open_session_log(path: str | Path):
    """按文件后缀返回文本行迭代器（.zstd 需可选依赖 zstandard）。

    Returns:
        上下文管理器，yield 逐行 str。
    """
    p = Path(path)
    if p.suffix == ".zstd":
        try:
            import zstandard  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover - 依赖可选
            raise RuntimeError(
                "读取 .zstd 会话日志需要可选依赖 zstandard：pip install zstandard"
            ) from exc

        class _ZstdLines:
            def __init__(self) -> None:
                self._fh: Any = None
                self._reader: Any = None
                self._lines: list[str] = []

            def __enter__(self):
                self._fh = p.open("rb")
                self._reader = zstandard.ZstdDecompressor().stream_reader(self._fh)
                data = self._reader.read()
                self._lines = data.decode("utf-8", "replace").splitlines()
                return self

            def __exit__(self, *exc: Any) -> None:
                try:
                    self._reader.close()  # type: ignore[union-attr]
                except Exception:
                    pass
                self._fh.close()  # type: ignore[union-attr]
                return False

            def __iter__(self) -> Iterator[str]:
                return iter(self._lines)

            def __next__(self) -> str:
                raise StopIteration  # 迭代由 __iter__ 的 iter() 驱动

        return _ZstdLines()

    class _PlainLines:
        def __init__(self) -> None:
            self._fh: Any = None

        def __enter__(self):
            self._fh = p.open("r", encoding="utf-8")
            return self

        def __exit__(self, *exc: Any) -> None:
            self._fh.close()
            return False

        def __iter__(self) -> Iterator[str]:
            return self

        def __next__(self) -> str:
            line = self._fh.readline()
            if not line:
                raise StopIteration
            return line.rstrip("\n")

    return _PlainLines()


def iter_events(path: str | Path) -> Iterator[dict[str, Any]]:
    """逐行 yield 事件 dict（跳过空行与无法解析的行）。"""
    with open_session_log(path) as lines:
        for line in lines:
            if not line.strip():
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def _content_text(content: Any) -> str:
    """拼接 content 数组中的 type==text 文本（DSH 消息 content 块）。"""
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            text = str(block.get("text") or "")
            if text:
                parts.append(text)
    return "\n".join(parts)


def _tool_result_text(content: Any) -> str:
    """解析 tool/result 的 content：type==tool-result 块内 type==text 文本拼接。"""
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for block in content:
        if not isinstance(block, dict) or block.get("type") != "tool-result":
            continue
        inner = block.get("content")
        if not isinstance(inner, list):
            continue
        for item in inner:
            if isinstance(item, dict) and item.get("type") == "text":
                text = str(item.get("text") or "")
                if text:
                    parts.append(text)
    return "\n".join(parts)


def _tool_result_is_error(content: Any) -> bool:
    """tool-result 块是否标记 isError（失败输出带标记，供提取器区分）。"""
    if not isinstance(content, list):
        return False
    return any(
        isinstance(b, dict) and b.get("type") == "tool-result" and bool(b.get("isError"))
        for b in content
    )


def _ts_to_iso(ms: int) -> str:
    import datetime as _dt

    return _dt.datetime.fromtimestamp(ms / 1000).isoformat(timespec="seconds")


def parse_session_runs(
    path: str | Path,
    *,
    session_id: str | None = None,
    project_id: str | None = None,
    max_turns: int | None = None,
    tier: str = "L1",
    max_tool_chars: int = 800,
    max_tool_total: int = 2000,
) -> list[MemoryRun]:
    """解析 DSH 会话日志为 MemoryRun 列表（按 turn 重组，回合边界对齐）。

    规则：
    - session_id 缺省时取日志 header 的 id；两者都没有 -> 用文件名兜底。
    - 一个回合产出一条 run；user_text 与 reply_text 都为空 -> 跳过。
    - run_id 由 会话id+回合号 哈希生成（跨重放稳定，幂等）。
    - 成本审计：回合内 assistant/message 的 usage 汇总记入 decision_log
      由 backfill_runs 落账（本函数只解析，不落盘）。
    - 工具结果：tool/result 经 callId 关联 tool/call 的工具名，以 `[tool:name]`
      前缀并入 reply_text（提取器可见 shell/文件输出）；max_tool_chars 单条截断、
      max_tool_total 回合总预算（消解能力），失败输出带 (error) 标记。
    """
    resolved_session = session_id or ""
    runs: list[MemoryRun] = []
    buffer: dict[str, Any] | None = None
    turn_costs: dict[int, dict[str, int]] = {}
    header_seen = False

    for ev in iter_events(path):
        etype = ev.get("type", "")
        if etype == "session":
            if not resolved_session and ev.get("id"):
                resolved_session = str(ev["id"])
            header_seen = True
            continue
        if etype == "turn/start":
            turn = int((ev.get("data") or {}).get("turn", 0))
            buffer = {
                "turn": turn,
                "user_parts": [],
                "flow_parts": [],
                "tool_names": {},
                "tool_total": 0,
                "trace_id": "",
                "ts_ms": int(ev.get("time") or 0),
            }
            continue
        if etype == "user/message":
            if buffer is None:
                continue
            text = _content_text((ev.get("data") or {}).get("content"))
            if text and not buffer["user_parts"]:
                buffer["user_parts"].append(text)
            if not buffer["trace_id"] and (ev.get("data") or {}).get("id"):
                buffer["trace_id"] = str(ev["data"]["id"])
            continue
        if etype == "assistant/message":
            data = ev.get("data") or {}
            text = _content_text((data.get("message") or {}).get("content"))
            if buffer is None or data.get("turn") != buffer["turn"]:
                # 无 turn/start 开头的日志：按 data.turn 惰性建缓冲
                if buffer is None or (data.get("turn") or 0) != (buffer.get("turn") or 0):
                    turn = int(data.get("turn") or 0)
                    buffer = {
                        "turn": turn,
                        "user_parts": [],
                        "flow_parts": [],
                        "tool_names": {},
                        "tool_total": 0,
                        "trace_id": "",
                        "ts_ms": int(ev.get("time") or 0),
                    }
            if text:
                buffer["flow_parts"].append(text)
            usage = ev.get("usage") or {}
            if isinstance(usage, dict):
                key = buffer["turn"]
                acc = turn_costs.setdefault(key, {"inputTokens": 0, "outputTokens": 0})
                acc["inputTokens"] += int(usage.get("inputTokens", 0))
                acc["outputTokens"] += int(usage.get("outputTokens", 0))
            continue
        if etype == "turn/end":
            if buffer is not None:
                run = _make_run(
                    buffer,
                    session_id=resolved_session or Path(path).name,
                    project_id=project_id,
                    tier=tier,
                )
                if run is not None:
                    runs.append(run)
            buffer = None
            if max_turns is not None and len(runs) >= max_turns:
                break
        if etype == "tool/call":
            # 记录 callId -> 工具名（tool/result 靠 callId 关联归属）
            if buffer is not None:
                tdata = ev.get("data") or {}
                call_id = str(tdata.get("callId") or "")
                tname = str(tdata.get("name") or "")
                if call_id and tname:
                    buffer["tool_names"][call_id] = tname
            continue
        if etype == "tool/result":
            if buffer is None:
                continue
            rdata = ev.get("data") or {}
            msg = rdata.get("message") or {}
            text = _tool_result_text(msg.get("content"))
            if not text:
                continue
            call_id = str((msg.get("source") or {}).get("callId") or "")
            tname = buffer["tool_names"].get(call_id, "tool")
            if _tool_result_is_error(msg.get("content")):
                tname = f"{tname}(error)"
            part = f"[tool:{tname}] {text[:max_tool_chars]}"
            # 回合内工具结果总预算（消解能力：防止 shell/文件输出撑爆上下文）
            remaining = max_tool_total - int(buffer["tool_total"])
            if remaining <= 0:
                continue
            if len(part) > remaining:
                part = part[:remaining]
            buffer["flow_parts"].append(part)
            buffer["tool_total"] = int(buffer["tool_total"]) + len(part)
            continue
        # 其余事件（step/*、chunk 等）不参与字段匹配

    # 日志末尾没有 turn/end：flush 最后未闭合回合
    if buffer is not None and (max_turns is None or len(runs) < max_turns):
        run = _make_run(
            buffer,
            session_id=resolved_session or Path(path).name,
            project_id=project_id,
            tier=tier,
        )
        if run is not None:
            runs.append(run)

    return runs


def _make_run(
    buffer: dict[str, Any],
    *,
    session_id: str,
    project_id: str | None,
    tier: str,
) -> MemoryRun | None:
    user_text = "\n".join(p for p in buffer["user_parts"] if p)
    reply_text = "\n".join(p for p in buffer.get("flow_parts", []) if p)
    if not user_text and not reply_text:
        return None
    turn = int(buffer["turn"])
    digest = hashlib.sha1(f"{session_id}|{turn}".encode("utf-8")).hexdigest()[:12]
    return MemoryRun(
        run_id=f"run-{digest}",
        session_id=session_id,
        user_text=user_text,
        reply_text=reply_text,
        tier=tier,
        ts=_ts_to_iso(int(buffer["ts_ms"] or 0)),
        project_id=project_id,
        trace_event_id=buffer.get("trace_id", ""),
    )


def backfill_runs(
    store: MemoryStore,
    path: str | Path,
    *,
    session_id: str | None = None,
    project_id: str | None = None,
    max_turns: int | None = None,
    tier: str = "L1",
) -> int:
    """把 DSH 会话日志回填进 runs 表（原始层由 DSH 承包，这里只读不复制）。

    返回本次插入的 run 数量（INSERT OR IGNORE 幂等，重复回填不计）。
    """
    runs = parse_session_runs(
        path,
        session_id=session_id,
        project_id=project_id,
        max_turns=max_turns,
        tier=tier,
    )
    inserted = 0
    for run in runs:
        if store.run_status(run.run_id) is not None:
            continue  # 幂等：已存在则跳过
        store.insert_run(run)
        inserted += 1
    with contextlib.suppress(Exception):
        store.log_decision(
            "dsh_backfill",
            f"{Path(path).name}: {len(runs)} 回合，新增 {inserted} 条 run（tier={tier}）",
        )
    return inserted
