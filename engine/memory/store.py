"""记忆存储（DESIGN §4.1：明文 markdown 为事实来源 + sqlite3 索引加速）。

目录约定（全部 gitignore，明文可找回）：
  events/logs/YYYY-MM-DD.md   日记录
  events/cards/<id>.md        事件卡（提取结果）
  events/chains/<id>.md       事件链卡
  lessons/pending/<id>.md     待固化（低质量/冲突，§4.3）
  lessons/permanent/<id>.md   已固化（人工审批后）
  profiles/PROFILE.md         画像（M6 蒸馏，先占位）
  .index/memory.db            sqlite3 索引（可重建；明文仍是事实来源）

runs 表 = 原始对话落盘 + 提取状态机（staged → extracting → done|failed），
提取失败/暂存都不删 run —— 对话永不丢（A5）。
"""

from __future__ import annotations

import contextlib
import datetime as _dt
import hashlib
import re
import threading
from dataclasses import replace
from pathlib import Path
from typing import Any

import sqlite3

from memory.models import MemoryCard, MemoryRun
from memory.tokenize import tokenize, tokenize_words

_KIND_DIRS = {
    "event": "events/cards",
    "chain": "events/chains",
    "lesson_pending": "lessons/pending",
    "lesson_permanent": "lessons/permanent",
    "profile": "profiles",
}

# 只读浏览用目录表（M4 记忆管理面板；logs 不是卡片但可查看）
_BROWSE_DIRS = (
    ("log", "events/logs"),
    ("event", "events/cards"),
    ("chain", "events/chains"),
    ("lesson_pending", "lessons/pending"),
    ("lesson_permanent", "lessons/permanent"),
    ("profile", "profiles"),
)


class _Rows:
    """锁内物化结果集：兼容 sqlite3 游标读取接口（B2 配套）。

    旧 _exec 把游标放出锁外惰性读取；本类在锁内一次性取完全部行，
    调用点的 fetchall/fetchone/fetchmany/迭代语义与游标一致。
    """

    __slots__ = ("_rows", "_i")

    def __init__(self, rows: list) -> None:
        self._rows = rows
        self._i = 0

    def fetchall(self) -> list:
        rows, self._rows = self._rows, []
        self._i = len(rows)
        return rows

    def fetchone(self):
        if self._i >= len(self._rows):
            return None
        row = self._rows[self._i]
        self._i += 1
        return row

    def fetchmany(self, size: int = 1) -> list:
        out = self._rows[self._i : self._i + size]
        self._i += len(out)
        return out

    def __iter__(self):
        return iter(self._rows)

    def __len__(self) -> int:
        return len(self._rows)

_CARD_SCHEMA = """
CREATE TABLE IF NOT EXISTS cards (
    id VARCHAR PRIMARY KEY,
    kind VARCHAR, title VARCHAR, content TEXT,
    source_path VARCHAR, created_at VARCHAR, run_id VARCHAR,
    confidence DOUBLE, status VARCHAR, weight DOUBLE,
    last_hit_at VARCHAR, hit_count INTEGER, miss_count INTEGER,
    parent_id VARCHAR, entities TEXT, children TEXT,
    summary TEXT,
    updated_at VARCHAR, supersedes VARCHAR, superseded_by VARCHAR, invalid_at VARCHAR, ended_at VARCHAR,
    trace_event_id VARCHAR, source_part VARCHAR, source_card_ids VARCHAR,
    aliases TEXT, evidence VARCHAR, corroborations INTEGER,
    tokens TEXT
)
"""

# 记忆卡 FTS5 全文索引（jieba 预处理：title+content 分词空格拼接，unicode61 按空格切词）
_CARD_FTS_SCHEMA = """
CREATE VIRTUAL TABLE IF NOT EXISTS card_fts USING fts5(
    body,
    card_id UNINDEXED,
    status UNINDEXED
)
"""

_RUNS_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id VARCHAR PRIMARY KEY,
    session_id VARCHAR, user_text TEXT, reply_text TEXT,
    tier VARCHAR, ts VARCHAR, status VARCHAR, error VARCHAR,
    project_id VARCHAR, trace_event_id VARCHAR,
    priority INTEGER DEFAULT 0
)
"""

_DECISION_SCHEMA = """
CREATE TABLE IF NOT EXISTS decision_log (
    ts VARCHAR, topic VARCHAR, detail TEXT
)
"""

# M6 偏好信号（DESIGN §4.2 提炼：同类 ≥3 → 提案 → 人工审批固化）
_SIGNALS_SCHEMA = """
CREATE TABLE IF NOT EXISTS preference_signals (
    id VARCHAR PRIMARY KEY,
    ts VARCHAR, topic VARCHAR, category VARCHAR,
    statement TEXT, source_path VARCHAR
)
"""


def now_iso() -> str:
    return _dt.datetime.now().astimezone().isoformat(timespec="seconds")


def _card_to_md(card: MemoryCard) -> str:
    return "\n".join(
        [
            "---",
            f"id: {card.id}",
            f"kind: {card.kind}",
            f"title: {card.title}",
            f"source_path: {card.source_path}",
            f"created_at: {card.created_at}",
            f"run_id: {card.run_id or ''}",
            f"confidence: {card.confidence}",
            f"status: {card.status}",
            f"weight: {card.weight}",
            f"last_hit_at: {card.last_hit_at or ''}",
            f"hit_count: {card.hit_count}",
            f"miss_count: {card.miss_count}",
            f"parent_id: {card.parent_id}",
            f"entities: {', '.join(card.entities)}",
            f"children: {', '.join(card.children)}",
            f"updated_at: {card.updated_at}",
            f"supersedes: {card.supersedes}",
            f"superseded_by: {card.superseded_by}",
            f"invalid_at: {card.invalid_at or ''}",
            f"ended_at: {card.ended_at or ''}",
            f"trace_event_id: {card.trace_event_id}",
            f"source_part: {card.source_part}",
            f"source_card_ids: {card.source_card_ids}",
            f"summary: {card.summary}",
            f"aliases: {', '.join(card.aliases)}",
            f"evidence: {card.evidence}",
            f"corroborations: {card.corroborations}",
            "---",
            f"# {card.title}",
            "",
            card.content,
            "",
        ]
    )


def _parse_md(text: str) -> MemoryCard | None:
    """解析 front matter + 正文（明文可找回；缺 id 返回 None）。"""
    if not text.startswith("---"):
        return None
    _, _, rest = text.partition("---")
    head, sep, body = rest.partition("\n---\n")
    if not sep:
        return None
    fields: dict[str, str] = {}
    for line in head.splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    if "id" not in fields:
        return None
    title = fields.get("title", "")
    content = body.strip()
    if content.startswith(f"# {title}"):
        content = content[len(f"# {title}") :].strip()

    def _num(key: str, default: float) -> float:
        raw = fields.get(key)
        if raw in (None, ""):
            return default
        try:
            return float(raw)
        except ValueError:
            return default

    return MemoryCard(
        id=fields["id"],
        kind=fields.get("kind", "event"),
        title=title,
        content=content,
        source_path=fields.get("source_path", ""),
        created_at=fields.get("created_at", ""),
        run_id=fields.get("run_id") or None,
        confidence=_num("confidence", 0.0),
        status=fields.get("status", "active"),
        weight=_num("weight", 1.0),
        last_hit_at=fields.get("last_hit_at") or None,
        hit_count=int(_num("hit_count", 0)),
        miss_count=int(_num("miss_count", 0)),
        parent_id=fields.get("parent_id", ""),
        entities=tuple(x.strip() for x in fields.get("entities", "").split(",") if x.strip()),
        children=tuple(x.strip() for x in fields.get("children", "").split(",") if x.strip()),
        updated_at=fields.get("updated_at", ""),
        supersedes=fields.get("supersedes", ""),
        superseded_by=fields.get("superseded_by", ""),
        invalid_at=fields.get("invalid_at") or None,
        ended_at=fields.get("ended_at") or None,
        trace_event_id=fields.get("trace_event_id", ""),
        source_part=fields.get("source_part", ""),
        source_card_ids=fields.get("source_card_ids", ""),
        summary=fields.get("summary", ""),
        aliases=tuple(x.strip() for x in fields.get("aliases", "").split(",") if x.strip()),
        evidence=fields.get("evidence", ""),
        corroborations=int(_num("corroborations", 0)),
    )


_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,80}$")


def _literal_ids(card_ids: list[str]) -> str:
    """字面量 id 列表：内联字面量避免参数绑定开销，
    必须内联为 SQL 字面量达到 A6 预算；id 均为内部生成，白名单校验防注入。"""
    for card_id in card_ids:
        if not _SAFE_ID_RE.fullmatch(card_id):
            raise ValueError(f"unsafe card id: {card_id!r}")
    return ", ".join(f"'{card_id}'" for card_id in card_ids)


_CARD_COLUMNS = (
    "id", "kind", "title", "content", "source_path", "created_at", "run_id",
    "confidence", "status", "weight", "last_hit_at", "hit_count", "miss_count",
    "parent_id", "entities", "children",
    "summary", "updated_at", "supersedes", "superseded_by", "invalid_at", "ended_at",
    "trace_event_id", "source_part", "source_card_ids",
    "aliases", "evidence", "corroborations", "tokens",
)
_CARD_SELECT = "SELECT " + ", ".join(_CARD_COLUMNS) + " FROM cards"


def chain_id(chain_title: str) -> str:
    """事件链 id：由标题哈希确定 → 跨 run 同主题自动归同一链（P0 记忆树）。"""
    digest = hashlib.sha1(f"chain|{chain_title.strip()}".encode()).hexdigest()[:12]
    return f"chn-{digest}"


class MemoryStore:
    """明文 markdown + sqlite3 索引；全部写操作幂等（A4）。"""

    def __init__(self, memory_dir: Path) -> None:
        self.root = Path(memory_dir)
        # sqlite3 单连接非线程安全：recorder(写)/loop(检索)/HTTP(读) 多线程并发必须串行
        self._lock = threading.Lock()
        for sub in (*_KIND_DIRS.values(), "events/logs"):
            (self.root / sub).mkdir(parents=True, exist_ok=True)
        (self.root / ".index").mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(
            str(self.root / ".index" / "memory.db"), check_same_thread=False
        )
        # sqlite3：busy_timeout 必须先设（默认 0=撞锁立即失败），再切 WAL 多读一写
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._exec(_CARD_SCHEMA)
        self._exec(_CARD_FTS_SCHEMA)
        # P0 记忆树：旧库补列（sqlite3 幂等），无需清空旧记忆
        _existing_cols = {r[1] for r in self._exec("PRAGMA table_info(cards)")}
        for _col, _coltype in (
            ("parent_id", "VARCHAR"), ("entities", "TEXT"), ("children", "TEXT"),
            ("updated_at", "VARCHAR"), ("supersedes", "VARCHAR"), ("superseded_by", "VARCHAR"),
            ("invalid_at", "VARCHAR"), ("ended_at", "VARCHAR"),
            ("trace_event_id", "VARCHAR"), ("source_part", "VARCHAR"),
            ("source_card_ids", "VARCHAR"), ("summary", "TEXT"),
            ("aliases", "TEXT"), ("evidence", "VARCHAR"), ("corroborations", "INTEGER"),
        ):
            if _col not in _existing_cols:
                self._exec(f"ALTER TABLE cards ADD COLUMN {_col} {_coltype}")
        self._exec(_RUNS_SCHEMA)
        # 项目归属（B5）：旧库补列（sqlite3 幂等）
        _run_cols = {r[1] for r in self._exec("PRAGMA table_info(runs)")}
        if "project_id" not in _run_cols:
            self._exec("ALTER TABLE runs ADD COLUMN project_id VARCHAR")
        if "trace_event_id" not in _run_cols:
            self._exec("ALTER TABLE runs ADD COLUMN trace_event_id VARCHAR")
        if "priority" not in _run_cols:
            self._exec("ALTER TABLE runs ADD COLUMN priority INTEGER DEFAULT 0")
        self._exec(_DECISION_SCHEMA)
        self._exec(_SIGNALS_SCHEMA)

    # —— 卡片（明文 + 索引双写）——

    def _exec(self, sql: str, params: list | None = None) -> _Rows | None:
        """线程安全执行：execute + 读取 + 提交全部在锁内完成。

        B2 修复：旧实现锁只覆盖 execute/commit，游标惰性读取（fetchall/
        fetchone）发生在锁外——sqlite3 单连接多线程并发下，另一线程的 execute
        会使未读完的游标失效（Recursive use of cursors / 脏读），DSH 多线程
        宿主必然崩溃。现改为锁内物化全部行，返回 _Rows 兼容游标读取接口。
        写语句返回 None；调用点无 lastrowid/rowcount 依赖（已核实）。
        """
        with self._lock:
            cur = self._conn.execute(sql, params or [])
            if sql.lstrip().upper().startswith(
                ("INSERT", "UPDATE", "DELETE", "ALTER", "CREATE")
            ):
                self._conn.commit()
                return None
            return _Rows(cur.fetchall())

    def browse(self, limit: int = 20) -> list[dict]:
        """只读浏览：扫描 memory/ 下明文 markdown（排除 .index/），按类型归组。"""
        entries: list[dict] = []
        for kind, rel in _BROWSE_DIRS:
            base = self.root / rel
            if not base.is_dir():
                continue
            paths = sorted(base.glob("*.md"), reverse=True)
            for path in paths:
                try:
                    head = path.read_text(encoding="utf-8")[:120].replace("\n", " ")
                except OSError:
                    head = ""
                entries.append(
                    {
                        "kind": kind,
                        "path": str(path.relative_to(self.root)),
                        "title": path.stem,
                        "snippet": head,
                    }
                )
                if len(entries) >= limit:
                    return entries
        return entries


    def card_path(self, card: MemoryCard) -> Path:
        sub = _KIND_DIRS.get(card.kind, "events/cards")
        return self.root / sub / f"{card.id}.md"

    def write_card(self, card: MemoryCard, *, sync_index: bool = True) -> Path:
        """幂等写卡（同 id 覆盖，A4）。"""
        path = self.card_path(card)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_card_to_md(card), encoding="utf-8")
        if sync_index:
            self._upsert_index(card)
        return path

    def read_card(self, card_id: str) -> MemoryCard | None:
        """明文为事实来源：扫描各 kind 目录解析 md。"""
        for sub in _KIND_DIRS.values():
            path = self.root / sub / f"{card_id}.md"
            if path.exists():
                return _parse_md(path.read_text(encoding="utf-8"))
        return None

    def all_cards(self) -> list[MemoryCard]:
        rows = self._exec(_CARD_SELECT).fetchall()
        return [self._row_to_card(row) for row in rows]

    def active_cards(self) -> list[MemoryCard]:
        rows = self._exec(_CARD_SELECT + " WHERE status = 'active'").fetchall()
        return [self._row_to_card(row) for row in rows]

    def count_cards(self, *, kind: str | None = None, status: str | None = None) -> int:
        sql = "SELECT COUNT(*) FROM cards WHERE 1=1"
        params: list[str] = []
        if kind:
            sql += " AND kind = ?"
            params.append(kind)
        if status:
            sql += " AND status = ?"
            params.append(status)
        row = self._exec(sql, params).fetchone()
        return int(row[0])

    def card_tokens(self, card_id: str) -> list[str]:
        row = self._exec("SELECT tokens FROM cards WHERE id = ?", [card_id]).fetchone()
        return row[0].split() if row and row[0] else []

    def active_cards_with_tokens(self) -> list[tuple[MemoryCard, list[str]]]:
        """单查询取 active 卡 + 已分词 tokens（检索热路径，A6 预算内）。"""
        rows = self._exec(_CARD_SELECT + " WHERE status = 'active'").fetchall()
        out: list[tuple[MemoryCard, list[str]]] = []
        for row in rows:
            card = self._row_to_card(row)
            tokens = row[-1].split() if row[-1] else []
            out.append((card, tokens))
        return out

    def update_hits(self, card_ids: list[str], at: str) -> None:
        """命中统计：单条 UPDATE 滚动增量（合并为单语句减少提交次数）。"""
        if not card_ids:
            return
        at_literal = str(at).replace("'", "''")
        self._exec(
            f"UPDATE cards SET hit_count = hit_count + 1, miss_count = 0, "
            f"last_hit_at = '{at_literal}' WHERE id IN ({_literal_ids(card_ids)})"
        )

    def update_misses(self, card_ids: list[str]) -> None:
        if not card_ids:
            return
        self._exec(
            f"UPDATE cards SET miss_count = miss_count + 1 WHERE id IN ({_literal_ids(card_ids)})"
        )

    def archive_cards(self, card_ids: list[str]) -> None:
        """未命中达阈值 → miss+1、降权半、archived（A7；不做时间衰减）；回写明文。"""
        if not card_ids:
            return
        self._exec(
            f"UPDATE cards SET miss_count = miss_count + 1, weight = weight * 0.5, "
            f"status = 'archived' WHERE id IN ({_literal_ids(card_ids)})"
        )
        for card_id in card_ids:
            self._sync_md_from_index(card_id)


    def update_card(
        self, card_id: str, *, title: str | None = None, content: str | None = None
    ) -> MemoryCard | None:
        """Manually edit a card: rewrite plain md + index (md stays source of truth)."""
        card = self.read_card(card_id)
        if card is None:
            return None
        card = replace(
            card,
            title=title.strip() if title is not None else card.title,
            content=content if content is not None else card.content,
        )
        self.write_card(card)
        return card

    def delete_card(self, card_id: str) -> bool:
        """Manually delete a card: drop md file + index row.

        Deleting a chain card detaches its children (parent_id cleared, they
        become unattached events); deleting a child removes it from the parent
        chain's children list.
        """
        card = self.read_card(card_id)
        if card is None:
            return False
        if card.kind == "chain":
            rows = self._exec(
                "SELECT id FROM cards WHERE parent_id = ?", [card_id]
            ).fetchall()
            for (child_id,) in rows:
                child = self.read_card(str(child_id))
                if child is not None:
                    self.write_card(replace(child, parent_id="", children=()))
        if card.parent_id:
            parent = self.read_card(card.parent_id)
            if parent is not None:
                kids = tuple(k for k in parent.children if k != card_id)
                self.write_card(replace(parent, children=kids))
        path = self.card_path(card)
        with contextlib.suppress(OSError):
            path.unlink(missing_ok=True)
        self._exec("DELETE FROM cards WHERE id = ?", [card_id])
        self._exec("DELETE FROM card_fts WHERE card_id = ?", [card_id])
        return True

    def _sync_md_from_index(self, card_id: str) -> None:
        """以索引行为准回写明文卡（避免读旧 md 导致统计回退）。
        索引行刚被 UPDATE 过，内容/tokens 未变，只写 md 跳过重新索引（A6 归档热点不重写索引）。"""
        row = self._exec(_CARD_SELECT + " WHERE id = ?", [card_id]).fetchone()
        if row is not None:
            self.write_card(self._row_to_card(row), sync_index=False)

    # —— P0 记忆树：事件链挂载与子卡查询 ——

    def children_of(self, parent_id: str) -> list[MemoryCard]:
        """返回某链卡的全部 active 子卡（按时间升序）。"""
        rows = self._exec(
            _CARD_SELECT + " WHERE parent_id = ? AND status = 'active' ORDER BY created_at",
            [parent_id],
        ).fetchall()
        return [self._row_to_card(r) for r in rows]

    def all_children_of(self, parent_id: str) -> list[MemoryCard]:
        """某链卡的全部子卡（含枯萎叶，按时间升序）——果摘要生成需要读到完结枝的叶。"""
        rows = self._exec(
            _CARD_SELECT + " WHERE parent_id = ? ORDER BY created_at",
            [parent_id],
        ).fetchall()
        return [self._row_to_card(r) for r in rows]

    def siblings(self, card_id: str) -> list[MemoryCard]:
        """同一事件链下的兄弟卡（排除自身）——多跳检索沿链扩展。"""
        card = self.read_card(card_id)
        if card is None or not card.parent_id:
            return []
        rows = self._exec(
            _CARD_SELECT + " WHERE parent_id = ? AND status = 'active' AND id <> ?"
            " ORDER BY created_at",
            [card.parent_id, card_id],
        ).fetchall()
        return [self._row_to_card(r) for r in rows]

    def chain_title_map(self) -> dict[str, str]:
        """全部 active 链卡的 id → 标题（检索结果标注所属链用）。"""
        rows = self._exec(
            "SELECT id, title FROM cards WHERE kind = 'chain' AND status = 'active'"
        ).fetchall()
        return {r[0]: r[1] for r in rows}

    # —— P0 归链稳定（§9.7）：链身份确定性裁决，模型输出只产生候选 ——

    _CHAIN_ENTITY_BONUS = 0.3
    _CHAIN_MERGE_THRESHOLD = 0.65
    _CHAIN_ALIAS_MAX = 16

    @staticmethod
    def _chain_title_sim(a: str, b: str) -> float:
        """标题相似：max(Jaccard, 包含度)——子集措辞漂移（搬家 vs 搬家计划）也能命中。"""
        ta, tb = set(tokenize(a)), set(tokenize(b))
        if not ta or not tb:
            return 0.0
        inter = len(ta & tb)
        return max(inter / len(ta | tb), inter / min(len(ta), len(tb)))

    @staticmethod
    def _entity_overlap(a: set[str], b: set[str]) -> float:
        if not a or not b:
            return 0.0
        return len(a & b) / len(a | b)

    def active_chain_cards(self) -> list[MemoryCard]:
        """active 链卡（归链/合并的检索语料）。"""
        rows = self._exec(
            _CARD_SELECT + " WHERE kind = 'chain' AND status = 'active'"
        ).fetchall()
        return [self._row_to_card(r) for r in rows]

    def _find_active_chain_by_title_or_alias(self, title: str) -> MemoryCard | None:
        title = (title or "").strip()
        if not title:
            return None
        for chain in self.active_chain_cards():
            if chain.title == title or title in chain.aliases:
                return chain
        return None

    def _chain_entity_fingerprint(self, chain: MemoryCard) -> set[str]:
        """链的实体指纹 = 全部子卡实体并集（归链消歧/分裂检测用）。"""
        fp: set[str] = set()
        for cid in chain.children:
            child = self.read_card(cid)
            if child is not None:
                fp.update(child.entities)
        return fp

    def _add_chain_alias(self, chain_id: str, alias: str) -> None:
        alias = (alias or "").strip()
        if not alias:
            return
        chain = self.read_card(chain_id)
        if chain is None or chain.kind != "chain":
            return
        if alias == chain.title or alias in chain.aliases:
            return
        aliases = (chain.aliases + (alias,))[-self._CHAIN_ALIAS_MAX :]
        self.write_card(replace(chain, aliases=aliases, updated_at=now_iso()))
        self.log_decision("chain_alias", f"{chain_id}: +{alias}")

    def resolve_chain(
        self, title: str, entities: tuple[str, ...] = (), *, project_id: str | None = None
    ) -> str:
        """确定性归链（§9.7）：精确标题/别名 → 复用；否则标题相似 + 实体消歧 → 复用；否则新建。

        链身份不再由本次 LLM 标题哈希直接决定（防跨会话措辞漂移悄悄分裂）；
        canonical 标题保留首见，漂移措辞进 aliases（明文 + decision_log 审计）。
        仅 active 链参与归链；完结/失效链不吸新事件（新章 = 新链）。
        """
        title = (title or "").strip()
        if not title:
            return ""
        exact = self._find_active_chain_by_title_or_alias(title)
        if exact is not None:
            return exact.id
        ent_set = set(entities)
        chains = self.active_chain_cards()
        fps = {ch.id: self._chain_entity_fingerprint(ch) for ch in chains}
        best_id, best_score = "", 0.0
        for chain in chains:
            score = self._chain_title_sim(title, chain.title)
            if ent_set and fps[chain.id]:
                score += self._CHAIN_ENTITY_BONUS * self._entity_overlap(ent_set, fps[chain.id])
            if score > best_score:
                best_score, best_id = score, chain.id
        if best_id and best_score >= self._CHAIN_MERGE_THRESHOLD:
            self._add_chain_alias(best_id, title)
            return best_id
        return chain_id(title)

    def duplicate_chain_candidates(
        self, *, title_threshold: float = 0.55, entity_threshold: float = 0.5
    ) -> list[tuple[MemoryCard, MemoryCard, float]]:
        """检测疑似分裂链（修复存量用）：标题相似 或 子卡实体高度重叠。"""
        chains = self.active_chain_cards()
        fps = {ch.id: self._chain_entity_fingerprint(ch) for ch in chains}
        out: list[tuple[MemoryCard, MemoryCard, float]] = []
        for i, a in enumerate(chains):
            for b in chains[i + 1 :]:
                ts = self._chain_title_sim(a.title, b.title)
                eo = self._entity_overlap(fps[a.id], fps[b.id])
                if ts >= title_threshold or eo >= entity_threshold:
                    out.append((a, b, round(max(ts, eo), 3)))
        return out

    def merge_chains(self, keep_id: str, drop_id: str) -> int:
        """合并分裂链（§9.7）：drop 的子卡 re-parent 到 keep，drop 链卡 superseded
        （版本链可回滚，明文保留）。返回 re-parent 的子卡数。"""
        keep, drop = self.read_card(keep_id), self.read_card(drop_id)
        if keep is None or drop is None or keep.id == drop.id:
            return 0
        if keep.kind != "chain" or drop.kind != "chain":
            return 0
        moved = 0
        for child in self.all_children_of(drop_id):
            self.write_card(replace(child, parent_id=keep_id, updated_at=now_iso()))
            moved += 1
        children = tuple(dict.fromkeys([*keep.children, *drop.children]))
        aliases = tuple(dict.fromkeys([*keep.aliases, drop.title, *drop.aliases]))
        merged = replace(
            keep,
            children=children,
            aliases=aliases[: self._CHAIN_ALIAS_MAX],
            updated_at=now_iso(),
        )
        child_cards = [c for c in (self.read_card(cid) for cid in children) if c is not None]
        lines = [
            f"- {c.created_at} [{c.id}] {c.title}：{c.content.replace(chr(10), ' ').strip()[:80]}"
            for c in sorted(child_cards, key=lambda x: x.created_at)
        ]
        self.write_card(replace(merged, content="\n".join(lines)))
        self.supersede_card(drop_id, keep_id)
        self.log_decision("chain_merge", f"{drop_id} -> {keep_id}，迁移 {moved} 张叶")
        return moved

    def count_corroborations(self, card: MemoryCard) -> int:
        """佐证计数（§9.7）：同断言在其它 run 中出现过几次（token 级近重复，确定性零 LLM）。

        跨 kind 统计 event + lesson_pending + lesson_permanent——pending 卡也是独立提及，
        不能因为第一张 inferred 待审就漏掉它对后续卡片的佐证。
        """
        tokens = set(tokenize(card.content))
        if not tokens:
            return 0
        run_ids: set[str] = set()
        rows = self._exec(
            _CARD_SELECT + " WHERE kind IN ('event', 'lesson_pending', 'lesson_permanent')"
            " AND status = 'active' AND id <> ?",
            [card.id],
        ).fetchall()
        for row in rows:
            other = self._row_to_card(row)
            ot = set(tokenize(other.content))
            if not ot:
                continue
            if len(tokens & ot) / len(tokens | ot) >= 0.8:
                if other.run_id:
                    run_ids.add(other.run_id)
        return len(run_ids)

    def register_chain_card(self, chain_title: str, child: MemoryCard) -> MemoryCard:
        """把事件卡挂到事件链卡（P0）：链 id 由 resolve_chain 确定性裁决
        （措辞漂移归同一链，§9.7），canonical 标题保留首见；
        链卡明文保存 children 列表 + 按时间序重建正文（树结构可找回）。

        P1a：重建时保留链卡既有 entities/evidence/corroborations 不清零，
        且 entities 取全部子卡实体并集（实体检索/传导链可命中链卡）。
        """
        cid = child.parent_id or self.resolve_chain(chain_title, child.entities)
        existing = self.read_card(cid)
        children = tuple(
            dict.fromkeys([*(existing.children if existing is not None else ()), child.id])
        )
        child_cards: list[MemoryCard] = []
        for cid_child in children:
            c = self.read_card(cid_child)
            if c is not None:
                child_cards.append(c)
        entities = tuple(dict.fromkeys(e for c in child_cards for e in c.entities))
        lines = []
        for c in sorted(child_cards, key=lambda x: x.created_at):
            snippet = c.content.replace("\n", " ").strip()[:80]
            lines.append(f"- {c.created_at} [{c.id}] {c.title}：{snippet}")
        if existing is None:
            chain = MemoryCard(
                id=cid, kind="chain", title=chain_title.strip(),
                content="\n".join(lines), source_path=f"events/chains/{cid}.md",
                created_at=now_iso(), run_id=child.run_id,
                confidence=1.0, status="active", weight=1.0,
                entities=entities, children=children,
            )
        else:
            chain = MemoryCard(
                id=existing.id, kind=existing.kind, title=existing.title,
                content="\n".join(lines), source_path=existing.source_path,
                created_at=existing.created_at, run_id=existing.run_id,
                confidence=existing.confidence, status=existing.status, weight=existing.weight,
                last_hit_at=existing.last_hit_at, hit_count=existing.hit_count,
                miss_count=existing.miss_count, parent_id="", children=children,
                aliases=existing.aliases, entities=entities,
                evidence=existing.evidence, corroborations=existing.corroborations,
                summary=existing.summary, updated_at=existing.updated_at, supersedes=existing.supersedes,
                superseded_by=existing.superseded_by, invalid_at=existing.invalid_at,
                ended_at=existing.ended_at, trace_event_id=existing.trace_event_id,
                source_part=existing.source_part, source_card_ids=existing.source_card_ids,
            )
        self.write_card(chain)
        return chain

    def save_stats(
        self,
        card_id: str,
        *,
        weight: float | None = None,
        status: str | None = None,
        last_hit_at: str | None = None,
        hit_count: int | None = None,
        miss_count: int | None = None,
        evidence: str | None = None,
        confidence: float | None = None,
        corroborations: int | None = None,
    ) -> None:
        """更新检索统计 / 校准字段（索引同步 + 明文条件回写）。"""
        updates: dict[str, Any] = {}
        if weight is not None:
            updates["weight"] = float(weight)
        if status is not None:
            updates["status"] = status
        if last_hit_at is not None:
            updates["last_hit_at"] = last_hit_at
        if hit_count is not None:
            updates["hit_count"] = int(hit_count)
        if miss_count is not None:
            updates["miss_count"] = int(miss_count)
        if evidence is not None:
            updates["evidence"] = evidence
        if confidence is not None:
            updates["confidence"] = float(confidence)
        if corroborations is not None:
            updates["corroborations"] = int(corroborations)
        if not updates:
            return
        sets = ", ".join(f"{key} = ?" for key in updates)
        self._exec(f"UPDATE cards SET {sets} WHERE id = ?", [*updates.values(), card_id])
        if (
            status is None and weight is None
            and evidence is None and confidence is None and corroborations is None
        ):
            return  # 运行期统计以索引为准，不回写明文（避免检索热路径重写文件）
        self._sync_md_from_index(card_id)

    # —— B2（ADR-0019）：时序裁决 / 完结萎缩 / 版本链 / 修剪 ——

    def supersede_card(self, old_id: str, new_id: str, *, at: str | None = None) -> bool:
        """时序裁决：旧卡失效（status=superseded，superseded_by/invalid_at 标注，保留审计不删）。

        版本链 v1→v2→v3：旧卡只标失效，内容留存可回滚；decision_log 留痕。
        """
        card = self.read_card(old_id)
        if card is None or card.id == new_id or card.status == "superseded":
            return False
        at = at or now_iso()
        updated = replace(
            card,
            status="superseded",
            superseded_by=new_id,
            invalid_at=at,
            updated_at=at,
        )
        self.write_card(updated)
        self.log_decision("supersede", f"{old_id} <- {new_id} @ {at}")
        return True

    def set_chain_summary(self, chain_id: str, summary: str) -> bool:
        """B4：写入枝的果摘要（幂等：同摘要跳过）；只对链卡生效，明文+索引双写。"""
        summary = summary.strip()
        if not summary:
            return False
        chain = self.read_card(chain_id)
        if chain is None or chain.kind != "chain":
            return False
        if chain.summary == summary:
            return True
        updated = replace(chain, summary=summary, updated_at=now_iso())
        self.write_card(updated)
        self.log_decision("fruit_summary", f"{chain_id}: {summary[:60]}")
        return True

    def mark_ended(self, chain_id: str, *, at: str | None = None, wilt_factor: float = 0.3) -> int:
        """枝完结（事件结束即萎缩）：chain 记 ended_at + updated_at；
        active 子卡（叶）枯萎——status=wilted、weight 降、ended_at 继承。返回枯萎叶数。

        枯萎 = 排除在检索之外（ADR-0019：遗忘的本质），数据保留可翻看。
        """
        chain = self.read_card(chain_id)
        if chain is None or chain.kind != "chain" or chain.ended_at:
            return 0
        at = at or now_iso()
        ended = replace(chain, ended_at=at, updated_at=at)
        self.write_card(ended)
        wilted = 0
        for kid in self.children_of(chain_id):
            updated = replace(
                kid,
                status="wilted",
                weight=kid.weight * wilt_factor,
                ended_at=at,
                updated_at=at,
            )
            self.write_card(updated)
            wilted += 1
        self.log_decision("branch_ended", f"{chain_id} @ {at}，枯萎 {wilted} 张叶")
        return wilted

    def wilted_cards(self) -> list[MemoryCard]:
        """枯枝清单（UI 修剪用）：全部 wilted 卡（含所属枝信息由调用方拼装）。"""
        rows = self._exec(_CARD_SELECT + " WHERE status = 'wilted'").fetchall()
        return [self._row_to_card(r) for r in rows]

    def superseded_cards(self) -> list[MemoryCard]:
        """版本链清单：全部 superseded 卡（被新卡替代的旧事实，审计/对比用）。"""
        rows = self._exec(_CARD_SELECT + " WHERE status = 'superseded'").fetchall()
        return [self._row_to_card(r) for r in rows]

    def conflict_candidates(self, card: MemoryCard) -> list[MemoryCard]:
        """冲突候选：同枝（parent_id 相同）+ 实体有交集 + active 的旧卡（B2 时序裁决用）。"""
        if not card.parent_id or not card.entities:
            return []
        ent_set = set(card.entities)
        rows = self._exec(
            _CARD_SELECT + " WHERE parent_id = ? AND status = 'active' AND id <> ?",
            [card.parent_id, card.id],
        ).fetchall()
        return [
            self._row_to_card(r) for r in rows
            if ent_set & set(self._row_to_card(r).entities)
        ]

    def find_card_by_title(self, title: str) -> MemoryCard | None:
        """按标题近似匹配（LLM supersedes 标注回填用）：精确或互相包含。"""
        if not title.strip():
            return None
        for row in self._exec(_CARD_SELECT).fetchall():
            c = self._row_to_card(row)
            if c.title == title or title in c.title or c.title in title:
                return c
        return None

    def prune_cards(self, card_ids: list[str]) -> int:
        """修剪（人工确认硬删）：删除卡（含链卡级联）。返回删除数。"""
        removed = 0
        for cid in card_ids:
            if self.delete_card(cid):
                removed += 1
        if removed:
            self.log_decision("prune", f"人工修剪 {removed} 张卡")
        return removed

    # —— 偏好信号（M6 提炼：record → aggregate → propose）——

    def record_signal(
        self, topic: str, category: str, statement: str, *, source_path: str = ""
    ) -> str:
        """记录一条偏好信号（内容哈希去重，同句只入账一次）。"""
        ts = now_iso()
        # id 含时间戳：同一秒内重复语句去重，跨秒重复仍计数（同类信号应累计）
        digest = hashlib.sha1(
            f"{ts}|{topic}|{category}|{statement}".encode()
        ).hexdigest()[:12]
        signal_id = f"sig-{digest}"
        self._exec(
            "INSERT OR IGNORE INTO preference_signals "
            "(id, ts, topic, category, statement, source_path) VALUES (?, ?, ?, ?, ?, ?)",
            [signal_id, ts, topic, category, statement, source_path],
        )
        return signal_id

    def signal_groups(self, min_count: int = 3) -> list[dict[str, Any]]:
        """同类信号聚合（topic + category）；返回 count >= min_count 的分组。"""
        rows = self._exec(
            "SELECT topic, COUNT(*) AS n, MIN(ts) AS first_ts, "
            "GROUP_CONCAT(DISTINCT category) AS categories "
            "FROM preference_signals GROUP BY topic "
            "HAVING n >= ? ORDER BY n DESC, first_ts",
            [min_count],
        ).fetchall()
        return [
            {
                "topic": r[0],
                "count": int(r[1]),
                "first_ts": r[2],
                "categories": (r[3] or "").split(","),
            }
            for r in rows
        ]

    def signal_statements(self, topic: str) -> list[tuple[str, str]]:
        """返回该主题的全部 (statement, category)，按时间升序。"""
        rows = self._exec(
            "SELECT statement, category FROM preference_signals "
            "WHERE topic = ? ORDER BY ts",
            [topic],
        ).fetchall()
        return [(r[0], r[1]) for r in rows]

    def promote_lesson(self, card_id: str) -> MemoryCard | None:
        """人工审批固化：lesson_pending → lesson_permanent（§4.3）。"""
        card = self.read_card(card_id)
        if card is None or card.kind != "lesson_pending":
            return None
        promoted = replace(
            card,
            kind="lesson_permanent",
            source_path=f"lessons/permanent/{card.id}.md",
            updated_at=now_iso(),
            confidence=1.0,  # 人工审批 = 权威真值（§9.7）
            evidence="approved",
        )
        self.write_card(promoted)
        self.card_path(card).unlink(missing_ok=True)
        return promoted

    # —— 日记录 ——


    def log_path(self, stem: str) -> Path:
        return self.root / "events" / "logs" / f"{stem}.md"

    def update_log(self, stem: str, content: str) -> bool:
        """Manually edit a daily log file (content = whole file text)."""
        path = self.log_path(stem)
        if not path.exists():
            return False
        path.write_text(content, encoding="utf-8")
        return True

    def delete_log(self, stem: str) -> bool:
        """Manually delete a daily log file."""
        path = self.log_path(stem)
        if not path.exists():
            return False
        try:
            path.unlink(missing_ok=True)
        except OSError:
            return False
        return True

    def daily_log_path(self, date: str) -> Path:
        return self.root / "events" / "logs" / f"{date}.md"

    def append_daily_log(self, date: str, entry: str) -> Path:
        path = self.daily_log_path(date)
        if not path.exists():
            path.write_text(f"# {date}\n\n", encoding="utf-8")
        with path.open("a", encoding="utf-8") as fh:
            fh.write(entry if entry.endswith("\n") else entry + "\n")
        return path

    # —— runs（原始对话落盘 + 提取状态机）——

    def insert_run(self, run: MemoryRun) -> None:
        """INSERT OR IGNORE：同一 run_id 只入队一次（A4）。"""
        self._exec(
            "INSERT OR IGNORE INTO runs "
            "(run_id, session_id, user_text, reply_text, tier, ts, status, error, project_id, trace_event_id, priority) "
            "VALUES (?, ?, ?, ?, ?, ?, 'staged', NULL, ?, ?, ?)",
            [
                run.run_id, run.session_id, run.user_text, run.reply_text,
                run.tier, run.ts, run.project_id, run.trace_event_id or None,
                int(run.priority),
            ],
        )

    def next_staged_run(self) -> MemoryRun | None:
        """取待处理 run（staged/failed 重试）并原子认领为 extracting（B4）。

        旧实现只 SELECT 不改状态：process_staged 的 while 循环（cloud 批量
        take=8）会反复取到同一条 run，同一对话被提取 8 次。现在在锁内
        先认领（UPDATE → extracting）再返回，多 worker 并发也不会撞单；
        failed 重试仍会被再次认领。
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT run_id, session_id, user_text, reply_text, tier, ts, project_id, trace_event_id, priority "
                "FROM runs WHERE status IN ('staged', 'failed') ORDER BY priority DESC, ts LIMIT 1"
            ).fetchone()
            if row is None:
                return None
            self._conn.execute(
                "UPDATE runs SET status = 'extracting', error = NULL WHERE run_id = ?",
                [row[0]],
            )
            self._conn.commit()
        return MemoryRun(
            run_id=row[0], session_id=row[1], user_text=row[2],
            reply_text=row[3], tier=row[4], ts=row[5],
            project_id=row[6], trace_event_id=row[7] or "",
            priority=int(row[8] or 0),
        )

    def staged_backlog(self) -> int:
        """积压水位：当前 staged（未处理）run 数——NPU 慢速下对话高频时用。"""
        row = self._exec("SELECT COUNT(*) FROM runs WHERE status = 'staged'").fetchone()
        return int(row[0])

    def staged_count(self) -> int:
        """staged 未处理 run 数（P2：与 staged_backlog 同义，去孪生化）。"""
        return self.staged_backlog()

    def mark_run(self, run_id: str, status: str, error: str | None = None) -> None:
        self._exec(
            "UPDATE runs SET status = ?, error = ? WHERE run_id = ?", [status, error, run_id]
        )

    def run_status(self, run_id: str) -> str | None:
        row = self._exec("SELECT status FROM runs WHERE run_id = ?", [run_id]).fetchone()
        return row[0] if row else None

    def runs_count(self) -> int:
        """runs 总数（项目映射缓存指纹：新 run 入队才失效）。"""
        row = self._exec("SELECT COUNT(*) FROM runs").fetchone()
        return int(row[0])

    def run_project_map(self) -> dict[str, str]:
        """run_id → 所属项目（仅返回有归属的 run；召回按项目加权用）。"""
        rows = self._exec(
            "SELECT run_id, project_id FROM runs WHERE project_id IS NOT NULL"
        ).fetchall()
        return {r[0]: r[1] for r in rows}

    # —— 决策日志（A5：降级显式化）——

    def log_decision(self, topic: str, detail: str) -> None:
        self._exec(
            "INSERT INTO decision_log (ts, topic, detail) VALUES (?, ?, ?)",
            [now_iso(), topic, detail],
        )

    def decision_log(self, topic: str | None = None) -> list[dict[str, Any]]:
        if topic:
            rows = self._exec(
                "SELECT ts, topic, detail FROM decision_log WHERE topic = ? ORDER BY ts", [topic]
            ).fetchall()
        else:
            rows = self._exec(
                "SELECT ts, topic, detail FROM decision_log ORDER BY ts"
            ).fetchall()
        return [{"ts": r[0], "topic": r[1], "detail": r[2]} for r in rows]

    def _upsert_index(self, card: MemoryCard) -> None:
        self._exec(
            """
            INSERT INTO cards (id, kind, title, content, source_path, created_at, run_id,
                               confidence, status, weight, last_hit_at, hit_count,
                               miss_count, parent_id, entities, children, summary, updated_at,
                               supersedes, superseded_by, invalid_at, ended_at, trace_event_id,
                               source_part, source_card_ids, aliases, evidence, corroborations, tokens)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (id) DO UPDATE SET
                kind=excluded.kind, title=excluded.title, content=excluded.content,
                source_path=excluded.source_path, created_at=excluded.created_at,
                run_id=excluded.run_id, confidence=excluded.confidence, status=excluded.status,
                weight=excluded.weight, last_hit_at=excluded.last_hit_at,
                hit_count=excluded.hit_count, miss_count=excluded.miss_count,
                parent_id=excluded.parent_id, entities=excluded.entities,
                children=excluded.children, summary=excluded.summary,
                aliases=excluded.aliases, evidence=excluded.evidence,
                corroborations=excluded.corroborations, tokens=excluded.tokens,
                updated_at=excluded.updated_at, supersedes=excluded.supersedes,
                superseded_by=excluded.superseded_by, invalid_at=excluded.invalid_at,
                ended_at=excluded.ended_at, trace_event_id=excluded.trace_event_id,
                source_part=excluded.source_part, source_card_ids=excluded.source_card_ids
            """,
            [
                card.id, card.kind, card.title, card.content, card.source_path,
                card.created_at, card.run_id, card.confidence, card.status, card.weight,
                card.last_hit_at, card.hit_count, card.miss_count,
                card.parent_id, ", ".join(card.entities), ", ".join(card.children),
                card.summary, card.updated_at, card.supersedes, card.superseded_by, card.invalid_at,
                card.ended_at, card.trace_event_id, card.source_part, card.source_card_ids,
                ", ".join(card.aliases), card.evidence, card.corroborations,
                " ".join(tokenize(card.content)),
            ],
        )
        # FTS5 同步：title + content 词级分词拼接（jieba 空格 → unicode61 按词切）
        self._exec("DELETE FROM card_fts WHERE card_id = ?", [card.id])
        body = " ".join(tokenize_words(f"{card.title} {card.content}"))
        if body.strip():
            self._exec(
                "INSERT INTO card_fts (body, card_id, status) VALUES (?, ?, ?)",
                [body, card.id, card.status],
            )

    def _row_to_card(self, row) -> MemoryCard:
        columns = [
            "id", "kind", "title", "content", "source_path", "created_at", "run_id",
            "confidence", "status", "weight", "last_hit_at", "hit_count", "miss_count",
            "parent_id", "entities", "children", "summary", "updated_at", "supersedes",
            "superseded_by", "invalid_at", "ended_at", "trace_event_id", "source_part",
            "source_card_ids", "aliases", "evidence", "corroborations", "tokens",
        ]
        d = dict(zip(columns, row, strict=True))
        return MemoryCard(
            id=d["id"], kind=d["kind"], title=d["title"], content=d["content"],
            source_path=d["source_path"], created_at=d["created_at"], run_id=d["run_id"],
            confidence=d["confidence"], status=d["status"], weight=d["weight"],
            last_hit_at=d["last_hit_at"], hit_count=d["hit_count"], miss_count=d["miss_count"],
            parent_id=d["parent_id"] or "",
            entities=tuple(x.strip() for x in str(d["entities"] or "").split(",") if x.strip()),
            children=tuple(x.strip() for x in str(d["children"] or "").split(",") if x.strip()),
            summary=d["summary"] or "",
            aliases=tuple(x.strip() for x in str(d["aliases"] or "").split(",") if x.strip()),
            evidence=d["evidence"] or "",
            corroborations=int(d["corroborations"] or 0),
            updated_at=d["updated_at"] or "",
            supersedes=d["supersedes"] or "",
            superseded_by=d["superseded_by"] or "",
            invalid_at=d["invalid_at"],
            ended_at=d["ended_at"],
            trace_event_id=d["trace_event_id"] or "",
            source_part=d["source_part"] or "",
            source_card_ids=d["source_card_ids"] or "",
        )

    def close(self) -> None:
        self._conn.close()
