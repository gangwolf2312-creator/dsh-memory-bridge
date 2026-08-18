"""NPU 慢速适配测试：优先级取单 / 积压水位 / 空闲轮询 / 超时自适应（V3.5）。"""

from __future__ import annotations

from memory.guard import extract_priority
from memory.models import MemoryRun
from memory.store import MemoryStore


def _store(tmp_path) -> MemoryStore:
    return MemoryStore(tmp_path / "memory")


def _run(run_id: str, user: str = "测试消息", priority: int = 0) -> MemoryRun:
    return MemoryRun(
        run_id=run_id, session_id="s", user_text=user, reply_text="回复",
        tier="L1", priority=priority,
    )


# —— 优先级判定（guard.extract_priority）——


def test_priority_directive_high() -> None:
    assert extract_priority("记住：部署端口是 8080", "好的") == 1
    assert extract_priority("记一下，我下月搬家", "记下") == 1
    assert extract_priority("记住教训：别周五部署", "ok") == 1


def test_priority_strong_signal_high() -> None:
    assert extract_priority("项目 A 的服务器配置好了", "ok") == 1
    assert extract_priority("部署端口是 8080", "ok") == 1
    assert extract_priority("账号密码都改好了", "ok") == 1


def test_priority_weak_or_none_low() -> None:
    assert extract_priority("今天天气不错", "是啊") == 0
    assert extract_priority("谢谢", "不客气") == 0
    assert extract_priority("帮我查一下目录", "好的") == 0


# —— 优先级取单（store.next_staged_run）——


def test_next_staged_prioritizes_high(tmp_path) -> None:
    store = _store(tmp_path)
    store.insert_run(_run("low-1", priority=0, user="先入队的普通"))
    store.insert_run(_run("high-1", priority=1, user="后入队的高优先"))
    store.insert_run(_run("low-2", priority=0))
    first = store.next_staged_run()
    assert first is not None
    assert first.run_id == "high-1"  # 高优先先取，即使后入队
    store.close()


def test_next_staged_same_priority_fifo(tmp_path) -> None:
    store = _store(tmp_path)
    store.insert_run(_run("a", priority=0))
    store.insert_run(_run("b", priority=0))
    first = store.next_staged_run()
    assert first.run_id == "a"  # 同级按时间序
    store.mark_run("a", "done")  # 取出后标记处理，才能取到下一个
    assert store.next_staged_run().run_id == "b"
    store.close()


def test_next_staged_claims_atomic(tmp_path) -> None:
    """B4 回归：next_staged_run 认领式取单——连续两次取到不同 run，无需手动 mark。"""
    store = _store(tmp_path)
    store.insert_run(_run("a"))
    store.insert_run(_run("b"))
    first = store.next_staged_run()
    assert first.run_id == "a"
    assert store.run_status("a") == "extracting"  # 取出即认领
    second = store.next_staged_run()
    assert second.run_id == "b"  # a 已被认领，不会重复返回
    assert store.next_staged_run() is None
    store.close()


def test_next_staged_retries_failed_run(tmp_path) -> None:
    """B4：failed 的 run 可被再次认领（重试语义不被认领破坏）。"""
    store = _store(tmp_path)
    store.insert_run(_run("retry-1"))
    store.mark_run("retry-1", "failed", "boom")
    got = store.next_staged_run()
    assert got is not None and got.run_id == "retry-1"
    assert store.run_status("retry-1") == "extracting"
    store.close()


# —— 积压水位（store.staged_backlog + pipeline 高水位）——


def test_staged_backlog_counts_pending(tmp_path) -> None:
    store = _store(tmp_path)
    assert store.staged_backlog() == 0
    store.insert_run(_run("a"))
    store.insert_run(_run("b"))
    assert store.staged_backlog() == 2
    store.mark_run("a", "done")
    assert store.staged_backlog() == 1
    store.close()


def test_pipeline_enqueue_respects_backlog_high_water(tmp_path) -> None:
    from memory.extract import MemoryWritePipeline

    store = _store(tmp_path)
    # P1b：水位判定只在"可消化"（enabled + 有提取器）时生效
    pipe = MemoryWritePipeline(
        store, enabled=True, extractor=object(), backlog_high_water=2
    )
    # 前两条入队
    pipe.enqueue(user_text="记住：端口 8080", reply_text="ok", session_id="s", tier="L1")
    pipe.enqueue(user_text="记住：账号 admin", reply_text="ok", session_id="s", tier="L1")
    assert store.staged_backlog() == 2
    # 第三条超水位：不入队（积压保护）
    before = store.staged_backlog()
    pipe.enqueue(user_text="记住：密码 123", reply_text="ok", session_id="s", tier="L1")
    assert store.staged_backlog() == before  # 不再增长
    pipe.close()
    store.close()


def test_pipeline_disabled_backlog_never_poisons_high_water(tmp_path) -> None:
    """P1b：禁用态（无提取器）不参与水位判定——禁用期堆满后恢复不被误拦（A5）。"""
    from memory.extract import MemoryWritePipeline

    store = _store(tmp_path)
    pipe = MemoryWritePipeline(store, enabled=True, extractor=None, backlog_high_water=2)
    pipe.enqueue(user_text="记住：端口 8080", reply_text="ok", session_id="s", tier="L1")
    pipe.enqueue(user_text="记住：账号 admin", reply_text="ok", session_id="s", tier="L1")
    assert store.staged_backlog() == 2  # 已满水位
    # 禁用态下第三条仍入队（对话不丢，恢复后一起消化）
    pipe.enqueue(user_text="记住：密码 123", reply_text="ok", session_id="s", tier="L1")
    assert store.staged_backlog() == 3
    pipe.close()
    store.close()


def test_pipeline_enqueue_sets_priority(tmp_path) -> None:
    from memory.extract import MemoryWritePipeline

    store = _store(tmp_path)
    pipe = MemoryWritePipeline(store, enabled=True, extractor=None)
    pipe.enqueue(user_text="记住：部署端口是 8080", reply_text="ok", session_id="s", tier="L1")
    pipe.enqueue(user_text="今天天气不错", reply_text="是啊", session_id="s", tier="L1")
    high = store.next_staged_run()
    assert high is not None and high.priority == 1  # directive 高优先
    store.mark_run(high.run_id, "done")
    low = store.next_staged_run()
    assert low is not None and low.priority == 0
    pipe.close()
    store.close()


# —— 超时自适应（MemoryWritePipeline._timeout_for）——


def test_timeout_for_scales_with_chars(tmp_path) -> None:
    from memory.extract import MemoryWritePipeline

    store = _store(tmp_path)
    pipe = MemoryWritePipeline(store, enabled=True, extractor=None, timeout_per_chars=0.02)
    short = _run("s", user="短")
    long_run = _run("l", user="长" * 5000)
    assert pipe._timeout_for(short) == 60.0  # 下限 60s
    assert pipe._timeout_for(long_run) >= 100.0  # 5000 字符 × 0.02 = 100s
    pipe.close()
    store.close()


def test_timeout_for_disabled_when_zero(tmp_path) -> None:
    from memory.extract import MemoryWritePipeline

    store = _store(tmp_path)
    pipe = MemoryWritePipeline(store, enabled=True, extractor=None, timeout_per_chars=0)
    assert pipe._timeout_for(_run("a", user="x" * 10000)) is None  # 默认关闭
    pipe.close()
    store.close()


# —— B3/B4 修复回归（ADAPTATION-AUDIT BLOCKER）——


def test_process_staged_batch_claims_distinct_runs(tmp_path) -> None:
    """B4 回归：批量取单认领去重——两条 run 各取一次，绝不 8 次重复同一条。"""
    from memory.extract import ExtractionResult, MemoryWritePipeline

    store = _store(tmp_path)
    store.insert_run(_run("a"))
    store.insert_run(_run("b"))
    seen: list[str] = []

    class _BatchFake:
        def extract(self, run) -> ExtractionResult:
            return ExtractionResult()

        def extract_batch(self, runs) -> list[ExtractionResult]:
            seen.extend(r.run_id for r in runs)
            return [ExtractionResult() for _ in runs]

    pipe = MemoryWritePipeline(
        store, extractor=_BatchFake(), enabled=True, worker=False, batch_size=8
    )
    n = pipe.process_staged()  # 无 limit：按 batch_size=8 取量
    assert n == 2
    assert len(seen) == 2  # 旧实现：8 次重复同一条
    assert sorted(seen) == ["a", "b"]
    assert store.staged_count() == 0  # 无残留 staged/extracting
    pipe.close()
    store.close()


def test_commit_phase_failure_marks_failed_not_stuck(tmp_path, monkeypatch) -> None:
    """B3 回归：提交阶段异常 → run 转 failed 可重试，不永久卡 extracting。"""
    from memory.extract import ExtractionResult, MemoryWritePipeline
    from memory.models import MemoryCard

    store = _store(tmp_path)
    store.insert_run(_run("run-b3"))

    class _Fake:
        def extract(self, run) -> ExtractionResult:
            return ExtractionResult(
                cards=[
                    (
                        MemoryCard(
                            id="evt-b3-001", kind="event", title="测试",
                            content="内容", source_part="assistant",
                            confidence=0.9, evidence="explicit",
                        ),
                        "",
                    )
                ]
            )

    pipe = MemoryWritePipeline(store, extractor=_Fake(), enabled=True, worker=False)

    def _boom(card, *, sync_index=True):
        raise OSError("simulated write failure")

    monkeypatch.setattr(store, "write_card", _boom)
    pipe.process_staged(1)
    # 旧实现：异常被 worker suppress 吞掉 → 永久 extracting；现在转 failed 可重试
    assert store.run_status("run-b3") == "failed"
    assert store.all_cards() == []
    # failed 可被再次认领（重试闭环）
    retry = store.next_staged_run()
    assert retry is not None and retry.run_id == "run-b3"
    pipe.close()
    store.close()


# —— P1b：失败退避（不秒烧 max_failures）——


def test_failed_run_backs_off_before_retry(tmp_path) -> None:
    """P1b：失败后进入退避期——期内 process_staged 不重试，失败次数不虚增。"""
    import time as _time
    from memory.extract import ExtractError, MemoryWritePipeline

    store = _store(tmp_path)
    store.insert_run(_run("run-backoff"))

    class _Fail:
        def extract(self, run):
            raise ExtractError("端点不可达")

    pipe = MemoryWritePipeline(
        store, extractor=_Fail(), enabled=True, worker=False, max_failures=3
    )
    assert pipe.process_staged(1) == 1  # 第一次失败
    assert store.run_status("run-backoff") == "failed"
    assert pipe._failures["run-backoff"] == 1
    assert pipe._retry_at["run-backoff"] > _time.monotonic()  # 退避已排期

    assert pipe.process_staged(1) == 0  # 退避期内：认领后放回，不消耗失败次数
    assert store.run_status("run-backoff") == "failed"
    assert pipe._failures["run-backoff"] == 1  # 未虚增
    pipe.close()
    store.close()
