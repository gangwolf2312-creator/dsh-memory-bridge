"""DSH 会话日志字段匹配测试（V3.2：原始层由 DSH 承包，只读不复制）。

覆盖：session.jsonl 事件流 -> MemoryRun 字段匹配（turn 边界 / user_text /
reply_text / trace_event_id / session_id），回填幂等，空回合跳过。
"""

from __future__ import annotations

import json

from memory.dsh_source import parse_session_runs, backfill_runs
from memory.store import MemoryStore


def _line(etype: str, seq: int, data: dict, time: int = 1786631286337, usage: dict | None = None) -> str:
    ev: dict = {"type": etype, "seq": seq, "time": time, "data": data}
    if usage is not None:
        ev["usage"] = usage
    return json.dumps(ev, ensure_ascii=False)


def _session_log(tmp_path, name: str = "session.jsonl") -> str:
    p = tmp_path / name
    lines = [
        '{"type":"session","version":0,"id":"session-abc","createdAt":1786631286337,'
        '"cwd":"D:x","delegationDepth":0}',
        _line("turn/start", 1, {"turn": 1}, 1786631286337),
        _line("user/message", 2, {"content": [{"type": "text", "text": "记住：部署端口 8080"}], "id": "uid-1"}, 1786631286338),
        _line("assistant/message", 3, {"turn": 1, "step": 1, "message": {"role": "assistant", "content": [{"type": "reasoning", "text": "思考"}, {"type": "text", "text": "好的，已记住"}]}}, 1786631286339, usage={"inputTokens": 100, "outputTokens": 20}),
        _line("turn/end", 4, {"turn": 1, "reason": {"kind": "completed"}}, 1786631286340),
        _line("turn/start", 5, {"turn": 2}, 1786631286341),
        _line("user/message", 6, {"content": [{"type": "text", "text": "嗯"}], "id": "uid-2"}, 1786631286342),
        _line("turn/end", 7, {"turn": 2}, 1786631286343),
    ]
    p.write_text("\n".join(lines), encoding="utf-8")
    return str(p)


def test_parse_session_runs_field_mapping(tmp_path) -> None:
    runs = parse_session_runs(_session_log(tmp_path))
    assert len(runs) == 2
    r1 = runs[0]
    assert r1.session_id == "session-abc"  # header 匹配
    assert r1.user_text == "记住：部署端口 8080"  # user/message text 拼接
    assert r1.reply_text == "好的，已记住"  # assistant/message 仅 text（跳过 reasoning）
    assert r1.trace_event_id == "uid-1"  # 回合首个 user/message id
    assert r1.run_id.startswith("run-")
    assert r1.tier == "L1"
    assert runs[1].user_text == "嗯"
    assert runs[1].reply_text == ""


def test_parse_session_runs_no_reasoning_in_reply(tmp_path) -> None:
    """assistant/message 的 reasoning 块不进入 reply_text（字段匹配边界）。"""
    p = tmp_path / "s.jsonl"
    lines = [
        '{"type":"session","version":0,"id":"s1","createdAt":1,"delegationDepth":0}',
        _line("turn/start", 1, {"turn": 1}, 2),
        _line("user/message", 2, {"content": [{"type": "text", "text": "你好"}], "id": "u1"}, 3),
        _line("assistant/message", 3, {"turn": 1, "step": 1, "message": {"role": "assistant", "content": [{"type": "reasoning", "text": "内部思考不该入库"}, {"type": "tool-call", "id": "t1", "name": "grep", "arguments": "{}"}, {"type": "text", "text": "最终答案"}]}}, 4),
        _line("turn/end", 4, {"turn": 1}, 5),
    ]
    p.write_text("\n".join(lines), encoding="utf-8")
    runs = parse_session_runs(str(p))
    assert len(runs) == 1
    assert runs[0].reply_text == "最终答案"


def test_backfill_runs_idempotent(tmp_path) -> None:
    store = MemoryStore(tmp_path / "memory")
    path = _session_log(tmp_path)
    assert backfill_runs(store, path) == 2
    assert backfill_runs(store, path) == 0  # INSERT OR IGNORE 幂等
    assert store.runs_count() == 2
    assert store.staged_count() == 2  # 回填后待提取
    store.close()


def test_parse_skips_empty_turn(tmp_path) -> None:
    p = tmp_path / "empty.jsonl"
    lines = [
        '{"type":"session","version":0,"id":"session-xyz","createdAt":1,"delegationDepth":0}',
        _line("turn/start", 1, {"turn": 1}, 2),
        _line("turn/end", 2, {"turn": 1}, 3),
        _line("turn/start", 3, {"turn": 2}, 4),
        _line("assistant/message", 4, {"turn": 2, "step": 1, "message": {"role": "assistant", "content": [{"type": "text", "text": "模型主动发起"}]}}, 5),
        _line("turn/end", 5, {"turn": 2}, 6),
    ]
    p.write_text("\n".join(lines), encoding="utf-8")
    runs = parse_session_runs(str(p))
    assert len(runs) == 1  # turn1 全空跳过；turn2 保留 reply
    assert runs[0].reply_text == "模型主动发起"
    assert runs[0].user_text == ""


def test_parse_max_turns(tmp_path) -> None:
    runs = parse_session_runs(_session_log(tmp_path), max_turns=1)
    assert len(runs) == 1
    assert runs[0].user_text == "记住：部署端口 8080"


# —— 工具结果字段匹配（tool/call + tool/result）——


def _tool_log(tmp_path, name: str = "tools.jsonl") -> str:
    p = tmp_path / name
    lines = [
        '{"type":"session","version":0,"id":"session-tool","createdAt":1,"delegationDepth":0}',
        _line("turn/start", 1, {"turn": 1}, 2),
        _line("user/message", 2, {"content": [{"type": "text", "text": "搜一下 api key 在哪"}], "id": "u1"}, 3),
        _line("tool/call", 3, {"turn": 1, "step": 1, "callId": "call_1", "name": "grep", "arguments": "{}"}, 4),
        _line("tool/result", 4, {"turn": 1, "step": 1, "message": {"source": {"kind": "tool", "callId": "call_1"}, "content": [{"type": "tool-result", "toolCallId": "call_1", "content": [{"type": "text", "text": "Found 1 match\nline 76: apiKey: 'x-api-key'"}]}], "role": "user"}}, 5),
        _line("assistant/message", 5, {"turn": 1, "step": 2, "message": {"role": "assistant", "content": [{"type": "text", "text": "key 在 line 76"}]}}, 6),
        _line("turn/end", 6, {"turn": 1}, 7),
    ]
    p.write_text("\n".join(lines), encoding="utf-8")
    return str(p)


def test_tool_result_enters_reply(tmp_path) -> None:
    runs = parse_session_runs(_tool_log(tmp_path))
    assert len(runs) == 1
    reply = runs[0].reply_text
    assert "[tool:grep]" in reply  # callId 关联工具名
    assert "Found 1 match" in reply  # 工具输出进入 run 文本
    assert "line 76: apiKey" in reply
    assert reply.endswith("key 在 line 76")  # assistant 最终文本在后


def test_tool_result_truncation(tmp_path) -> None:
    runs = parse_session_runs(_tool_log(tmp_path), max_tool_chars=12)
    part = [line for line in runs[0].reply_text.split("\n") if line.startswith("[tool:")]
    assert part, "工具结果应存在"
    assert len(part[0]) <= 12 + len("[tool:grep] ")


def test_tool_result_error_marker(tmp_path) -> None:
    p = tmp_path / "err.jsonl"
    lines = [
        '{"type":"session","version":0,"id":"session-err","createdAt":1,"delegationDepth":0}',
        _line("turn/start", 1, {"turn": 1}, 2),
        _line("user/message", 2, {"content": [{"type": "text", "text": "跑一下"}], "id": "u1"}, 3),
        _line("tool/call", 3, {"turn": 1, "step": 1, "callId": "c1", "name": "pwsh", "arguments": "{}"}, 4),
        _line("tool/result", 4, {"turn": 1, "step": 1, "message": {"source": {"kind": "tool", "callId": "c1"}, "content": [{"type": "tool-result", "toolCallId": "c1", "content": [{"type": "text", "text": "command not found"}], "isError": True}], "role": "user"}}, 5),
        _line("turn/end", 5, {"turn": 1}, 6),
    ]
    p.write_text("\n".join(lines), encoding="utf-8")
    runs = parse_session_runs(str(p))
    assert runs[0].reply_text.startswith("[tool:pwsh(error)]")


def test_tool_result_total_budget(tmp_path) -> None:
    runs = parse_session_runs(_tool_log(tmp_path), max_tool_total=20)
    tool_lines = [line for line in runs[0].reply_text.split("\n") if line.startswith("[tool:")]
    total = sum(len(line) for line in tool_lines)
    assert total <= 20  # 回合总预算约束


def test_tool_result_unknown_call_uses_tool(tmp_path) -> None:
    """tool/result 无对应 tool/call：工具名回退 'tool'。"""
    p = tmp_path / "orphan.jsonl"
    lines = [
        '{"type":"session","version":0,"id":"session-orphan","createdAt":1,"delegationDepth":0}',
        _line("turn/start", 1, {"turn": 1}, 2),
        _line("user/message", 2, {"content": [{"type": "text", "text": "查一下"}], "id": "u1"}, 3),
        _line("tool/result", 3, {"turn": 1, "step": 1, "message": {"source": {"kind": "tool", "callId": "zzz"}, "content": [{"type": "tool-result", "toolCallId": "zzz", "content": [{"type": "text", "text": "输出"}]}], "role": "user"}}, 4),
        _line("turn/end", 4, {"turn": 1}, 5),
    ]
    p.write_text("\n".join(lines), encoding="utf-8")
    runs = parse_session_runs(str(p))
    assert runs[0].reply_text.startswith("[tool:tool] 输出")
