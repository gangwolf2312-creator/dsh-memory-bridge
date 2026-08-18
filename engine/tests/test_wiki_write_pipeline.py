"""WikiWritePipeline 测试（WIKI-DESIGN 待办 #2：幂等写 + 版本链 + 待审路由）。

管道是写侧单一权威：提取分流产出的 wiki 条目 / 未来 wiki_add 工具 / DSH backfill
都经它落盘。覆盖：幂等合并、版本链、pending 路由、enabled 关闭、worker 队列、审计回调。
"""

from __future__ import annotations

from memory.models import MemoryRun, WikiEntry
from memory.wiki import WikiStore, WikiWritePipeline


def _entry(**kw) -> WikiEntry:
    base = {
        "id": "wk-t1",
        "kind": "concept",
        "title": "三区三线",
        "content": "三区三线是国土空间规划中的概念：农业空间、生态空间、城镇空间三区，"
                   "以及永久基本农田、生态保护红线、城镇开发边界三条控制线。",
        "entities": ("三区三线", "生态保护红线", "永久基本农田"),
    }
    base.update(kw)
    return WikiEntry(**base)


def _run(run_id: str = "run-w") -> MemoryRun:
    return MemoryRun(
        run_id=run_id, session_id="s1", user_text="什么是三区三线", reply_text="……", tier="L1"
    )


def test_submit_idempotent_merge(tmp_path) -> None:
    """同概念措辞漂移二次写 → 别名吸收合并到 canonical，不产生新条目。"""
    store = WikiStore(tmp_path / "wiki")
    pipe = WikiWritePipeline(store, enabled=True)
    first = _entry(id="wk-a", title="三区三线")
    second = _entry(id="wk-b", title="三条控制线", entities=("生态保护红线",))

    s1 = pipe.submit(_run(), [first])
    s2 = pipe.submit(_run(), [second])

    entries = store.all_entries()
    assert len(entries) == 1  # 合并：仍是同一 canonical
    assert entries[0].title == "三区三线"
    assert "三条控制线" in entries[0].aliases
    assert s1[0]["merged"] is False
    assert s2[0]["merged"] is True  # 别名吸收，未产生新条目
    store.close()


def test_submit_version_chain(tmp_path) -> None:
    """supersedes 标题 → 旧条目标 superseded_by + invalid_at，不删（版本链）。"""
    store = WikiStore(tmp_path / "wiki")
    pipe = WikiWritePipeline(store, enabled=True)
    old = _entry(
        id="wk-old", kind="spec", title="城乡规划用地分类标准（旧版）",
        content="第1章 总则\n第1.1条 旧标准。", spec_id="GB-50137-2011", level="national",
    )
    store.write_entry(old)
    new = _entry(
        id="wk-new", kind="spec", title="城乡规划用地分类标准",
        content="第1章 总则\n第1.1条 新标准。", spec_id="GB-50137-2011", level="national",
        supersedes="城乡规划用地分类标准（旧版）",
    )

    s = pipe.submit(_run(), [new])

    assert s[0]["superseded"] is True
    old_after = store.read_entry("wk-old")
    assert old_after is not None
    assert old_after.superseded_by == "wk-new"
    assert old_after.invalid_at is not None
    store.close()


def test_submit_pending_routing(tmp_path) -> None:
    """低置信 pending 条目 → 落待审目录，不进正式目录。"""
    store = WikiStore(tmp_path / "wiki")
    pipe = WikiWritePipeline(store, enabled=True)
    pipe.submit(_run(), [_entry(id="wk-p1", title="模糊概念", status="pending", confidence=0.6)])

    assert (store.root / "pending" / "wk-p1.md").exists()
    assert not (store.root / "concepts" / "wk-p1.md").exists()
    store.close()


def test_submit_spec_requires_exact_title(tmp_path) -> None:
    """spec 只精确匹配：标题不同 → 两条独立规范，不模糊合并。"""
    store = WikiStore(tmp_path / "wiki")
    pipe = WikiWritePipeline(store, enabled=True)
    a = _entry(id="wk-s1", kind="spec", title="城乡规划用地分类标准",
               spec_id="GB-50137-2011", level="national")
    b = _entry(id="wk-s2", kind="spec", title="城市用地分类与规划建设用地标准",
               spec_id="GB-50137-2011", level="national")

    pipe.submit(_run(), [a, b])

    assert len(store.all_entries()) == 2
    store.close()


def test_enabled_false_noop(tmp_path) -> None:
    """enabled=False → submit/enqueue 均不落盘。"""
    store = WikiStore(tmp_path / "wiki")
    pipe = WikiWritePipeline(store, enabled=False)
    assert pipe.submit(_run(), [_entry()]) == []
    pipe.enqueue(_run(), [_entry()])
    assert store.all_entries() == []
    store.close()


def test_worker_drains_queue(tmp_path) -> None:
    """worker 模式：enqueue 非阻塞 → close 前 flush，队列不丢。"""
    store = WikiStore(tmp_path / "wiki")
    pipe = WikiWritePipeline(store, enabled=True, worker=True, poll_seconds=0.05)
    pipe.enqueue(_run(), [_entry()])
    pipe.enqueue(_run(), [_entry(id="wk-b", title="另一条")])
    pipe.close()  # close 先 flush 再停线程

    assert len(store.all_entries()) == 2
    store.close()


def test_flush_drains_queue(tmp_path) -> None:
    """flush 同步清空队列并返回成功写条数。"""
    store = WikiStore(tmp_path / "wiki")
    pipe = WikiWritePipeline(store, enabled=True)
    pipe.enqueue(_run(), [_entry()])
    assert pipe.flush() == 1
    assert pipe.flush() == 0  # 队列已清空
    assert len(store.all_entries()) == 1
    store.close()


def test_log_callback_records_decisions(tmp_path) -> None:
    """审计回调：每次写决策记 wiki_write（MemoryWritePipeline 接记忆库 log_decision）。"""
    store = WikiStore(tmp_path / "wiki")
    logs: list[tuple[str, str]] = []
    pipe = WikiWritePipeline(store, enabled=True, log=lambda n, d: logs.append((n, d)))
    pipe.submit(_run(), [_entry()])

    names = [n for n, _ in logs]
    assert "wiki_write" in names
    assert "merged=False" in dict(logs)["wiki_write"]
    store.close()
