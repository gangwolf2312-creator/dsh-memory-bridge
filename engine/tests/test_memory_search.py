"""A1：中文长句检索命中（DESIGN §4.6：≥20 字 top-3 命中目标卡）。"""

from __future__ import annotations

import pytest
from memory.models import MemoryCard, MemoryRun
from memory.search import MemorySearch
from memory.store import MemoryStore

CORPUS = [
    ("evt-c-0001", "周末爬山",
     "上周末我和同事去爬了香山，天气很好，爬到山顶花了两个小时，回来腿酸了两天。"),
    ("evt-c-0002", "搬家计划",
     "下个月要搬到浦东，需要提前联系搬家公司，还要处理旧家具和宽带迁移。"),
    ("evt-c-0003", "新电脑",
     "买了一台新的台式机，内存 128GB，用来跑本地大模型，显卡是 NVIDIA 4070。"),
    ("evt-c-0004", "体检预约",
     "这周五预约了体检，早上八点，需要空腹，前一天晚上不要吃太油腻的东西。"),
    ("evt-c-0005", "读书笔记",
     "最近在读《人类简史》，对农业革命那一章印象很深，作者的观点很有意思。"),
    ("evt-c-0006", "旅游规划", "计划国庆去成都旅游，想去宽窄巷子和熊猫基地，还要吃火锅和串串香。"),
]


def _store(tmp_path) -> MemoryStore:
    store = MemoryStore(tmp_path / "memory")
    for cid, title, content in CORPUS:
        store.write_card(
            MemoryCard(
                id=cid, kind="event", title=title, content=content,
                source_path=f"events/cards/{cid}.md",
            )
        )
    return store


def test_a1_chinese_long_query_hits_target_in_top3(tmp_path) -> None:
    store = _store(tmp_path)
    search = MemorySearch(store)
    query = "我记得上周末好像跟同事一起去爬过香山，那天天气特别好，回来之后腿酸了"
    assert len(query) >= 20
    results = search.search(query, top_k=3)
    ids = [r.card_id for r in results]
    assert "evt-c-0001" in ids, f"长句未命中目标卡: {ids}"
    store.close()


def test_a1_short_query_also_hits(tmp_path) -> None:
    store = _store(tmp_path)
    search = MemorySearch(store)
    results = search.search("新电脑的内存多大", top_k=3)
    assert "evt-c-0003" in [r.card_id for r in results]
    store.close()


def test_b5_project_weighted_recall(tmp_path) -> None:
    """B5：同项目记忆加权优先、跨项目降权（噪音过滤），无项目上下文时行为不变。"""
    store = MemoryStore(tmp_path / "memory")
    for cid, proj in (("evt-p1", "proj-a"), ("evt-p2", "proj-b")):
        store.write_card(
            MemoryCard(
                id=cid, kind="event", title="项目构建",
                content="这个项目用 pnpm 构建，构建命令是 pnpm build。",
                source_path=f"events/cards/{cid}.md", run_id=f"run-{cid}",
            )
        )
        store.insert_run(
            MemoryRun(
                run_id=f"run-{cid}", session_id="sess-x", user_text="t",
                reply_text="r", tier="L1", project_id=proj,
            )
        )
    search = MemorySearch(store)
    query = "这个项目怎么构建，用 pnpm 的命令是什么"
    plain = [r.card_id for r in search.search(query, top_k=3)]
    assert {"evt-p1", "evt-p2"} <= set(plain)  # 无上下文：两卡都在
    weighted = [r.card_id for r in search.search(
        query, top_k=3, project_id="proj-a", project_by_run=store.run_project_map()
    )]
    assert weighted[0] == "evt-p1", f"同项目记忆未优先: {weighted}"
    assert "evt-p2" in weighted  # 跨项目只是降权，不删除
    store.close()


def test_project_factors_applied_once_not_twice(tmp_path) -> None:
    """P2：project_factors 只应用一次（旧实现非 expand 路径乘两次）。

    两张内容完全相同的卡（BM25/短语/反馈各列同值，只有项目因子不同）：
    加权后分数比 = 因子比 × 基础比；若双次应用，因子会平方（2.0/0.3 → 44.4）。
    """
    store = MemoryStore(tmp_path / "memory")
    for cid, proj, rid in (
        ("evt-fa", "proj-a", "run-fa"),
        ("evt-fb", "proj-b", "run-fb"),
    ):
        store.write_card(
            MemoryCard(
                id=cid, kind="event", title="构建配置",
                content="这个项目的构建命令是 pnpm build，用于前端工程。",
                source_path=f"events/cards/{cid}.md", run_id=rid,
            )
        )
        store.insert_run(
            MemoryRun(
                run_id=rid, session_id="s", user_text="t", reply_text="r",
                tier="L1", project_id=proj,
            )
        )
    search = MemorySearch(store)
    query = "这个项目的构建命令是什么"
    plain = {r.card_id: r.score for r in search.search(query, top_k=3)}
    weighted = {r.card_id: r.score for r in search.search(
        query, top_k=3, project_id="proj-a", project_by_run=store.run_project_map()
    )}
    base_ratio = plain["evt-fa"] / plain["evt-fb"]
    weighted_ratio = weighted["evt-fa"] / weighted["evt-fb"]
    applied = weighted_ratio / base_ratio
    assert applied == pytest.approx(2.0 / 0.3, rel=0.05), (
        f"project_factors 应用了 {applied:.2f} 倍因子比（应为单次 6.67，"
        f"双次会 ≈44.4）"
    )
    store.close()
