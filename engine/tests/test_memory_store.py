"""memory 存储契约测试（明文 markdown + 索引，幂等写；runs 表 = 原始对话落盘）。"""

from __future__ import annotations

from memory.models import MemoryCard, MemoryRun
from memory.store import MemoryStore


def _card(card_id: str = "evt-store-0001", **kw) -> MemoryCard:
    base = {
        "id": card_id,
        "kind": "event",
        "title": "公园散步",
        "content": "昨天傍晚在公园散步半小时",
        "source_path": f"events/cards/{card_id}.md",
        "created_at": "2026-08-02T20:00:00",
    }
    base.update(kw)
    return MemoryCard(**base)


def test_write_read_roundtrip(tmp_path) -> None:
    store = MemoryStore(tmp_path / "memory")
    card = _card()
    path = store.write_card(card)
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---")
    assert "公园散步" in text
    got = store.read_card(card.id)
    assert got is not None
    assert got.title == card.title
    assert got.content == card.content
    assert got.source_path == card.source_path
    store.close()


def test_write_idempotent_same_id(tmp_path) -> None:
    store = MemoryStore(tmp_path / "memory")
    store.write_card(_card())
    store.write_card(_card(content="更新后的内容"))
    assert len(store.all_cards()) == 1
    assert store.read_card("evt-store-0001").content == "更新后的内容"
    store.close()


def test_daily_log_append(tmp_path) -> None:
    store = MemoryStore(tmp_path / "memory")
    p1 = store.append_daily_log("2026-08-02", "第一条")
    p2 = store.append_daily_log("2026-08-02", "第二条")
    assert p1 == p2
    text = p2.read_text(encoding="utf-8")
    assert "第一条" in text and "第二条" in text
    store.close()


def test_runs_staging_roundtrip_preserves_raw_conversation(tmp_path) -> None:
    store = MemoryStore(tmp_path / "memory")
    run = MemoryRun(
        run_id="run-store-0001",
        session_id="default",
        user_text="我周末去爬山了",
        reply_text="好的，记下了",
        tier="L1",
        ts="2026-08-02T21:00:00",
    )
    store.insert_run(run)
    got = store.next_staged_run()
    assert got is not None
    assert got.user_text == "我周末去爬山了"
    assert got.reply_text == "好的，记下了"
    # B4：next_staged_run 认领式取单——取出即 extracting（防重复提取）
    assert store.run_status("run-store-0001") == "extracting"
    store.mark_run("run-store-0001", "done")
    assert store.run_status("run-store-0001") == "done"
    assert store.staged_count() == 0
    store.close()


def test_runs_project_attribution(tmp_path) -> None:
    """B5：run 落库携带项目归属，run_project_map / runs_count 可用。"""
    store = MemoryStore(tmp_path / "memory")
    store.insert_run(
        MemoryRun(
            run_id="run-proj-0001", session_id="sess-a", user_text="a",
            reply_text="b", tier="L1", project_id="proj-a",
        )
    )
    store.insert_run(
        MemoryRun(
            run_id="run-proj-0002", session_id="sess-b", user_text="c",
            reply_text="d", tier="L1", project_id="proj-b",
        )
    )
    store.insert_run(
        MemoryRun(
            run_id="run-proj-0003", session_id="sess-c", user_text="e",
            reply_text="f", tier="L1",
        )
    )
    mapping = store.run_project_map()
    assert mapping == {"run-proj-0001": "proj-a", "run-proj-0002": "proj-b"}
    assert store.runs_count() == 3
    store.close()


def test_insert_same_run_twice_ignored(tmp_path) -> None:
    store = MemoryStore(tmp_path / "memory")
    run = MemoryRun(
        run_id="run-store-0002", session_id="s", user_text="a", reply_text="b", tier="L0"
    )
    store.insert_run(run)
    store.insert_run(run)
    store.mark_run("run-store-0002", "done")
    assert store.run_status("run-store-0002") == "done"
    store.close()


def test_legacy_column_order_migration(tmp_path) -> None:
    """P0 回归：旧库（tokens 列在新增列之前）ALTER 后物理列序与 CREATE TABLE 不同，
    SELECT 显式列名保证 parent_id/entities/children 读回正确（此前 zip 错位读到分词串）。"""
    import sqlite3

    db = tmp_path / "memory" / ".index" / "memory.db"
    db.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db))
    con.execute(
        "CREATE TABLE cards ("
        " id VARCHAR PRIMARY KEY, kind VARCHAR, title VARCHAR, content TEXT,"
        " source_path VARCHAR, created_at VARCHAR, run_id VARCHAR,"
        " confidence DOUBLE, status VARCHAR, weight DOUBLE,"
        " last_hit_at VARCHAR, hit_count INTEGER, miss_count INTEGER,"
        " tokens TEXT)"
    )
    con.execute(
        "INSERT INTO cards VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        ["evt-old-1", "event", "旧卡", "旧内容", "events/cards/evt-old-1.md",
         "2026-08-01T10:00:00", "run-old", 1.0, "active", 1.0,
         None, 0, 0, "旧 内容 分词"],
    )
    con.commit()
    con.close()

    store = MemoryStore(tmp_path / "memory")  # 触发 ALTER 补列
    store.write_card(_card(
        "evt-new-1", kind="event", title="新卡",
        content="新内容", parent_id="chn-legacy-abc",
        entities=("实体甲", "实体乙"), children=(),
    ))
    got = store.read_card("evt-new-1")
    assert got is not None
    assert got.parent_id == "chn-legacy-abc"
    assert got.entities == ("实体甲", "实体乙")

    all_cards = store.all_cards()
    m = {c.id: c for c in all_cards}
    # 新卡树字段读回正确
    assert m["evt-new-1"].parent_id == "chn-legacy-abc"
    assert m["evt-new-1"].entities == ("实体甲", "实体乙")
    # 旧行迁移后读回：parent_id 应为空而不是 tokens 分词串（此前 zip 错位 bug）
    assert m["evt-old-1"].parent_id == "", f"旧行 parent_id 错位: {m['evt-old-1'].parent_id!r}"
    assert m["evt-old-1"].content == "旧内容"
    store.close()


# —— P2：树/端 API 补测（wilted/superseded/promote_lesson 此前零测试调用）——


def test_wilted_cards_lists_ended_branch_leaves(tmp_path) -> None:
    store = MemoryStore(tmp_path / "memory")
    store.write_card(_card("chn-w1", kind="chain", title="搬家", content="链"))
    store.write_card(_card(
        "evt-w1", kind="event", title="搬家第一步", content="打包",
        parent_id="chn-w1", created_at="2026-06-01T10:00:00",
    ))
    store.mark_ended("chn-w1", at="2026-08-15T10:00:00")
    wilted = store.wilted_cards()
    assert [c.id for c in wilted] == ["evt-w1"]
    assert wilted[0].status == "wilted"
    store.close()


def test_superseded_cards_lists_version_chain(tmp_path) -> None:
    store = MemoryStore(tmp_path / "memory")
    store.write_card(_card("evt-old", title="旧事实", content="内容"))
    store.write_card(_card(
        "evt-new", title="新事实", content="内容", supersedes="旧事实",
    ))
    store.supersede_card("evt-old", "evt-new")
    superseded = store.superseded_cards()
    assert [c.id for c in superseded] == ["evt-old"]
    assert superseded[0].status == "superseded"
    assert superseded[0].superseded_by == "evt-new"
    store.close()


def test_promote_lesson_pending_to_permanent(tmp_path) -> None:
    store = MemoryStore(tmp_path / "memory")
    store.write_card(_card(
        "les-p1", kind="lesson_pending", title="教训：先备份",
        content="迁移前先备份", source_path="lessons/pending/les-p1.md",
    ))
    promoted = store.promote_lesson("les-p1")
    assert promoted is not None
    assert promoted.kind == "lesson_permanent"
    assert promoted.confidence == 1.0
    assert promoted.evidence == "approved"
    assert promoted.source_path == "lessons/permanent/les-p1.md"
    got = store.read_card("les-p1")
    assert got.kind == "lesson_permanent"  # 固化后重读为新 kind
    store.close()


def test_promote_lesson_wrong_kind_returns_none(tmp_path) -> None:
    store = MemoryStore(tmp_path / "memory")
    store.write_card(_card("evt-e1", kind="event", title="普通事件", content="内容"))
    assert store.promote_lesson("evt-e1") is None
    assert store.promote_lesson("不存在的卡") is None
    store.close()
