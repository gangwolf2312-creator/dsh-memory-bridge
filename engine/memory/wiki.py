"""知识库存储（LLM Wiki 支线）：明文 markdown 真源 + sqlite 索引 + 条文倒排。

与记忆库（MemoryStore）同构但独立：知识条目不进记忆树（避免污染画像/经历），
检索走条文级倒排（规范量大，不能全量 BM25）。

目录约定（全部 gitignore，明文可找回）：
  wiki/specs/<slug>.md        规范全文（kind=spec，真源）
  wiki/concepts/<slug>.md     概念/术语（kind=concept）
  wiki/tutorials/<slug>.md    教程/指南（kind=tutorial）
  wiki/figures/<编号>.png     图件（引用目标，不进索引）
  wiki/.index/wiki.db         sqlite 索引（可重建；明文仍是事实来源）

条文切块（仅 kind=spec）：按"第X章 → 第X节 → 第X条"语义结构切，
不按 token 数硬切——每条带溯源路径（spec_id + 章/节/条号），
原文件保留为真源，chunk 只是索引视图。
"""

from __future__ import annotations

import contextlib
import hashlib
import re
import sqlite3
import threading
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable

from memory.models import MemoryRun, WikiEntry, WikiSearchResult
from memory.store import _Rows
from memory.tokenize import tokenize, tokenize_words

__all__ = [
    "WikiStore",
    "WikiSearch",
    "WikiWritePipeline",
    "wiki_id",
    "split_spec_sections",
    "now_iso",
]

_KIND_DIRS = {
    "spec": "specs",
    "concept": "concepts",
    "tutorial": "tutorials",
}

# 条文切块：章/节/条 标题正则（中文规范常见结构，含"第2.1条"带点小节号；
# P1b：数字类补 零——"第一百零一条"旧正则漏配）
_CHAPTER_RE = re.compile(r"^\s*(第[一二三四五六七八九十百零0-9]+章)\s*(.*)$")
_SECTION_RE = re.compile(r"^\s*(第[一二三四五六七八九十百零0-9]+节)\s*(.*)$")
_ARTICLE_RE = re.compile(r"^\s*(第[一二三四五六七八九十百零0-9]+(?:[.．][0-9]+)*条)\s*(.*)$")

# 标题尾部标点剥离（"适用范围。" → "适用范围"）
_TRAIL_PUNCT = re.compile(r"[。．.，,；;：:\s]+$")

_ENTRIES_SCHEMA = """
CREATE TABLE IF NOT EXISTS entries (
    id VARCHAR PRIMARY KEY,
    kind VARCHAR, title VARCHAR, content TEXT,
    spec_id VARCHAR, level VARCHAR, admin VARCHAR, parent_ref VARCHAR,
    tags TEXT, aliases TEXT, entities TEXT,
    source_path VARCHAR, created_at VARCHAR, updated_at VARCHAR,
    source_run_id VARCHAR, source_part VARCHAR,
    supersedes VARCHAR, superseded_by VARCHAR, invalid_at VARCHAR,
    status VARCHAR, confidence REAL, evidence VARCHAR
)
"""

# 条文倒排：token → (entry_id, section_path)；条文本身存 section_texts 表
_SECTIONS_SCHEMA = """
CREATE TABLE IF NOT EXISTS sections (
    entry_id VARCHAR, section_path VARCHAR, section_text TEXT,
    PRIMARY KEY (entry_id, section_path)
)
"""

# FTS5 全文索引（jieba 预处理：中文按词空格拼接后入索引，unicode61 按空格切词）
# entry_id / section_path 是 UNINDEXED 元数据列；body 是 jieba 空格拼接的条文文本
_FTS_SCHEMA = """
CREATE VIRTUAL TABLE IF NOT EXISTS wiki_fts USING fts5(
    body,
    entry_id UNINDEXED,
    section_path UNINDEXED
)
"""

_FIGURES_SCHEMA = """
CREATE TABLE IF NOT EXISTS figures (
    ref VARCHAR PRIMARY KEY, entry_id VARCHAR, path VARCHAR, caption VARCHAR
)
"""


def now_iso() -> str:
    import datetime as _dt

    return _dt.datetime.now().astimezone().isoformat(timespec="seconds")


def wiki_id(title: str, kind: str = "concept") -> str:
    """条目 id：标题哈希稳定（同标题幂等，版本链靠 supersedes）。"""
    digest = hashlib.sha1(f"{kind}|{title.strip()}".encode()).hexdigest()[:12]
    return f"wk-{digest}"


def split_spec_sections(text: str) -> list[tuple[str, str]]:
    """规范全文 → 条文列表 [(section_path, section_text)]，按语义结构切。

    规则：第X章/第X节/第X条 标题开启新条文；正文归属最近标题；
    无标题的头部内容归 "前言"（P1b：无论有无章节都保留，不再丢弃）。
    纯无结构文本整体归 "前言"（容错，非空返回）。
    """
    if not text:
        return []
    sections: list[tuple[str, str]] = []
    current_path = ""
    current_lines: list[str] = []
    head_lines: list[str] = []

    def flush() -> None:
        nonlocal current_lines
        if current_path and current_lines:
            body = "\n".join(current_lines).strip()
            if body:
                sections.append((current_path, body))
        current_lines = []

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        m_ch = _CHAPTER_RE.match(stripped)
        m_se = _SECTION_RE.match(stripped)
        m_ar = _ARTICLE_RE.match(stripped)
        if m_ch:
            flush()
            current_path = _TRAIL_PUNCT.sub("", f"{m_ch.group(1)} {m_ch.group(2)}").strip()
        elif m_se:
            flush()
            base = current_path.split("/")[0] if current_path else ""
            # P1b：无章时路径不再带前导斜杠（旧实现产出 "/第一节 …"）
            heading = f"{m_se.group(1)} {m_se.group(2)}"
            current_path = _TRAIL_PUNCT.sub(
                "", f"{base}/{heading}" if base else heading
            ).strip()
        elif m_ar:
            flush()
            base = current_path.split("/")[0] if current_path else ""
            heading = f"{m_ar.group(1)} {m_ar.group(2)}"
            current_path = _TRAIL_PUNCT.sub(
                "", f"{base}/{heading}" if base else heading
            ).strip()
            # 条文标题行自身的文字（group(2)）并入正文——标题行常是完整条文
            inline = (m_ar.group(2) or "").strip()
            if inline:
                current_lines.append(inline)
        else:
            if current_path:
                current_lines.append(stripped)
            else:
                head_lines.append(stripped)
    flush()
    # P1b：前言无论有无章节都保留（旧实现：有章节时头部内容被整体丢弃）
    if head_lines:
        head = "\n".join(head_lines).strip()
        if head:
            return [("前言", head), *sections] if sections else [("前言", head)]
    return sections


def _title_similar(a: str, b: str) -> bool:
    """标题近似：共享词元过半，或共享字符占比 ≥ 0.4（中文措辞漂移兜底信号）。

    如"三区三线" vs "三条控制线"：词元可能不重叠（jieba 整词切分），
    但共享字符 {三,线} 占少数侧 2/3 → 判近似。
    """
    ta = {t for t in tokenize_words(a) if t}
    tb = {t for t in tokenize_words(b) if t}
    if ta and tb and (len(ta & tb) / min(len(ta), len(tb))) >= 0.5:
        return True
    ca, cb = set(a), set(b)
    if ca and cb:
        return (len(ca & cb) / min(len(ca), len(cb))) >= 0.4
    return False


def _entity_overlap(a: WikiEntry, b: WikiEntry) -> bool:
    """实体重叠：共享专有名词 → 大概率同一主题（概念合并的主信号）。"""
    return bool(set(a.entities) & set(b.entities))


class WikiStore:
    """明文 markdown + sqlite 索引（幂等写，同 id 覆盖；条文倒排可重建）。"""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self._lock = threading.Lock()
        for sub in _KIND_DIRS.values():
            (self.root / sub).mkdir(parents=True, exist_ok=True)
        (self.root / "pending").mkdir(parents=True, exist_ok=True)
        (self.root / "figures").mkdir(parents=True, exist_ok=True)
        (self.root / ".index").mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(
            str(self.root / ".index" / "wiki.db"), check_same_thread=False
        )
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._exec(_ENTRIES_SCHEMA)
        self._exec(_SECTIONS_SCHEMA)
        self._exec(_FTS_SCHEMA)
        self._exec(_FIGURES_SCHEMA)
        # V3.5 旧库补列（status/confidence/evidence）；列已存在则跳过（同 MemoryStore ALTER 手法）
        cols = {row[1] for row in self._exec("PRAGMA table_info(entries)").fetchall()}
        if "status" not in cols:
            self._exec("ALTER TABLE entries ADD COLUMN status VARCHAR DEFAULT 'active'")
        if "confidence" not in cols:
            self._exec("ALTER TABLE entries ADD COLUMN confidence REAL DEFAULT 1.0")
        if "evidence" not in cols:
            self._exec("ALTER TABLE entries ADD COLUMN evidence VARCHAR DEFAULT ''")

    def _exec(self, sql: str, params: list | None = None) -> _Rows | None:
        """线程安全执行：execute + 读取 + 提交全部在锁内完成（同 MemoryStore B2 修复）。

        旧实现锁只覆盖 execute/commit，游标惰性读取在锁外——DSH 多线程宿主
        下与 MemoryStore 同类的并发崩溃风险。写语句返回 None。
        """
        with self._lock:
            cur = self._conn.execute(sql, params or [])
            if sql.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE", "ALTER", "CREATE")):
                self._conn.commit()
                return None
            return _Rows(cur.fetchall())

    # —— 条目读写（明文 + 索引双写）——

    def entry_path(self, entry: WikiEntry) -> Path:
        if entry.status == "pending":
            return self.root / "pending" / f"{entry.id}.md"
        sub = _KIND_DIRS.get(entry.kind, "concepts")
        return self.root / sub / f"{entry.id}.md"

    def write_entry(self, entry: WikiEntry) -> Path:
        """幂等写条目（同 id 覆盖）；明文 + 索引 + 条文倒排。

        pending 条目落 wiki/pending/<id>.md（待审，不进检索），
        审核通过由 promote_entry 移入正式目录。
        """
        path = self.entry_path(entry)
        path.write_text(self._entry_to_md(entry), encoding="utf-8")
        self._upsert_entry(entry)
        self._reindex_sections(entry)  # spec 按章/节/条切；concept/tutorial 整体一条
        return path

    def _upsert_entry(self, entry: WikiEntry) -> None:
        """条目索引 upsert（同 id 覆盖）。"""
        self._exec(
            """
            INSERT INTO entries (id, kind, title, content, spec_id, level, admin, parent_ref,
                                 tags, aliases, entities, source_path, created_at, updated_at,
                                 source_run_id, source_part, supersedes, superseded_by, invalid_at,
                                 status, confidence, evidence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (id) DO UPDATE SET
                kind=excluded.kind, title=excluded.title, content=excluded.content,
                spec_id=excluded.spec_id, level=excluded.level, admin=excluded.admin,
                parent_ref=excluded.parent_ref, tags=excluded.tags, aliases=excluded.aliases,
                entities=excluded.entities, source_path=excluded.source_path,
                created_at=excluded.created_at, updated_at=excluded.updated_at,
                source_run_id=excluded.source_run_id, source_part=excluded.source_part,
                supersedes=excluded.supersedes, superseded_by=excluded.superseded_by,
                invalid_at=excluded.invalid_at, status=excluded.status,
                confidence=excluded.confidence, evidence=excluded.evidence
            """,
            [
                entry.id, entry.kind, entry.title, entry.content,
                entry.spec_id, entry.level, entry.admin, entry.parent_ref,
                ", ".join(entry.tags), ", ".join(entry.aliases), ", ".join(entry.entities),
                entry.source_path, entry.created_at, entry.updated_at,
                entry.source_run_id, entry.source_part,
                entry.supersedes, entry.superseded_by, entry.invalid_at,
                entry.status, entry.confidence, entry.evidence,
            ],
        )

    def read_entry(self, entry_id: str) -> WikiEntry | None:
        for sub in ("pending", *_KIND_DIRS.values()):
            path = self.root / sub / f"{entry_id}.md"
            if path.exists():
                return self._parse_md(path.read_text(encoding="utf-8"), entry_id, sub)
        return None

    def all_entries(self) -> list[WikiEntry]:
        rows = self._exec("SELECT id FROM entries ORDER BY created_at").fetchall()
        out = []
        for (eid,) in rows:
            e = self.read_entry(str(eid))
            if e is not None:
                out.append(e)
        return out

    def delete_entry(self, entry_id: str) -> bool:
        entry = self.read_entry(entry_id)
        if entry is None:
            return False
        with contextlib.suppress(OSError):
            self.entry_path(entry).unlink(missing_ok=True)
        self._exec("DELETE FROM entries WHERE id = ?", [entry_id])
        self._exec("DELETE FROM sections WHERE entry_id = ?", [entry_id])
        self._exec("DELETE FROM wiki_fts WHERE entry_id = ?", [entry_id])
        self._exec("DELETE FROM figures WHERE entry_id = ?", [entry_id])
        return True

    def supersede_entry(self, old_id: str, new_id: str) -> bool:
        """版本链：旧条目失效（superseded_by 标注 + status=superseded，保留审计不删）。

        P1a：旧实现不改 status——被覆盖的旧规范仍进检索 / find_entry_by_title /
        实体传导链，"版本链"形同虚设。现在置 superseded，检索层只认 active。
        """
        old = self.read_entry(old_id)
        if old is None or old.id == new_id:
            return False
        updated = replace(
            old, status="superseded", superseded_by=new_id, invalid_at=now_iso()
        )
        self.write_entry(updated)
        return True

    # —— 别名吸收 / 待审提升 ——

    def find_entry_by_title(
        self, title: str, kind: str | None = None
    ) -> WikiEntry | None:
        """按标题或别名精确查找（仅 active 条目；spec 只认规范名精确匹配）。

        P1a：superseded 的旧条目不进查找——被覆盖的旧规范不能再被
        别名吸收/版本链/新 supersedes 当作 canonical 目标。
        """
        wanted = title.strip()
        if not wanted:
            return None
        for cand in self.all_entries():
            if cand.status != "active":
                continue
            if kind and cand.kind != kind:
                continue
            if cand.title.strip() == wanted:
                return cand
            if wanted in {a.strip() for a in cand.aliases}:
                return cand
        return None

    def resolve_entry(self, entry: WikiEntry) -> WikiEntry:
        """别名吸收/去重合并：返回应落盘的最终条目。

        - 精确命中（同标题或同别名）→ 合并进 canonical：标题保持首写，
          aliases/entities/tags 取并集（首写内容为真源，新措辞只作别名吸收）；
        - concept/tutorial 允许模糊合并（标题近似 + 实体重叠），spec 只精确匹配；
        - 无命中 → 原样返回（新条目，pending 仍按 status 落 pending 目录）。
        """
        existing = self.find_entry_by_title(entry.title, entry.kind)
        if existing is None and entry.kind in ("concept", "tutorial"):
            for cand in self.all_entries():
                if cand.status != "active" or cand.kind != entry.kind:
                    continue
                if cand.id == entry.id:
                    continue
                if _entity_overlap(entry, cand) and _title_similar(entry.title, cand.title):
                    existing = cand
                    break
        if existing is None:
            return entry
        merged = replace(
            existing,
            aliases=tuple(
                dict.fromkeys(existing.aliases + (entry.title,) + entry.aliases)
            ),
            entities=tuple(dict.fromkeys(existing.entities + entry.entities)),
            tags=tuple(dict.fromkeys(existing.tags + entry.tags)),
            updated_at=now_iso(),
        )
        return merged

    def promote_entry(self, entry_id: str) -> WikiEntry | None:
        """审核通过：pending → active（移入正式目录、置信置 1.0、重建索引）。"""
        path = self.root / "pending" / f"{entry_id}.md"
        if not path.exists():
            return None
        entry = self._parse_md(path.read_text(encoding="utf-8"), entry_id, "pending")
        if entry is None:
            return None
        promoted = replace(
            entry,
            status="active",
            confidence=1.0,
            updated_at=now_iso(),
        )
        # P2：先写正式、后删待审（旧实现先 unlink 再写——write_entry 失败会丢待审内容）
        self.write_entry(promoted)
        path.unlink(missing_ok=True)
        return promoted

    # —— 条文倒排（kind=spec）——

    def _reindex_sections(self, entry: WikiEntry) -> None:
        """清空重建该条目的 FTS5 索引（幂等：先删后插）。

        spec 按章/节/条切块；concept/tutorial 整体作为一条（"全文"路径）。
        FTS5 body = jieba 分词空格拼接（中文按词检索，unicode61 按空格切词）。
        """
        self._exec("DELETE FROM sections WHERE entry_id = ?", [entry.id])
        self._exec("DELETE FROM wiki_fts WHERE entry_id = ?", [entry.id])
        if entry.kind == "spec":
            sections = split_spec_sections(entry.content)
        else:
            sections = [("全文", entry.content.strip())] if entry.content.strip() else []
        for path, text in sections:
            self._exec(
                "INSERT OR REPLACE INTO sections (entry_id, section_path, section_text) VALUES (?, ?, ?)",
                [entry.id, path, text],
            )
            # FTS5 索引：jieba 词级空格拼接（查询侧同样处理；字符 n-gram 是噪音不进索引）
            # body 前缀拼标题+别名（全 kind）：措辞漂移（如"三条控制线"→"三区三线"）也能召回
            head_terms = " ".join(
                tokenize_words(f"{entry.title} {' '.join(entry.aliases)}")
            )
            body = f"{head_terms} {' '.join(tokenize_words(text))}".strip()
            if body.strip():
                self._exec(
                    "INSERT INTO wiki_fts (body, entry_id, section_path) VALUES (?, ?, ?)",
                    [body, entry.id, path],
                )

    def section_count(self, entry_id: str) -> int:
        row = self._exec("SELECT COUNT(*) FROM sections WHERE entry_id = ?", [entry_id]).fetchone()
        return int(row[0])

    def section_text(self, entry_id: str, section_path: str) -> str | None:
        row = self._exec(
            "SELECT section_text FROM sections WHERE entry_id = ? AND section_path = ?",
            [entry_id, section_path],
        ).fetchone()
        return row[0] if row else None

    # —— 图件引用 ——

    def add_figure(self, entry_id: str, ref: str, path: str, caption: str = "") -> None:
        self._exec(
            "INSERT OR REPLACE INTO figures (ref, entry_id, path, caption) VALUES (?, ?, ?, ?)",
            [ref, entry_id, path, caption],
        )

    def figures_of(self, entry_id: str) -> list[tuple[str, str, str]]:
        rows = self._exec(
            "SELECT ref, path, caption FROM figures WHERE entry_id = ? ORDER BY ref", [entry_id]
        ).fetchall()
        return [(r[0], r[1], r[2]) for r in rows]

    # —— 内部：明文序列化 / 解析 ——

    @staticmethod
    def _entry_to_md(entry: WikiEntry) -> str:
        lines = [
            "---",
            f"id: {entry.id}",
            f"kind: {entry.kind}",
            f"title: {entry.title}",
            f"spec_id: {entry.spec_id}",
            f"level: {entry.level}",
            f"admin: {entry.admin}",
            f"parent_ref: {entry.parent_ref}",
            f"tags: {', '.join(entry.tags)}",
            f"aliases: {', '.join(entry.aliases)}",
            f"entities: {', '.join(entry.entities)}",
            f"source_path: {entry.source_path}",
            f"created_at: {entry.created_at}",
            f"updated_at: {entry.updated_at}",
            f"source_run_id: {entry.source_run_id}",
            f"source_part: {entry.source_part}",
            f"evidence: {entry.evidence}",
            f"status: {entry.status}",
            f"confidence: {entry.confidence}",
            f"supersedes: {entry.supersedes}",
            f"superseded_by: {entry.superseded_by}",
            f"invalid_at: {entry.invalid_at or ''}",
            "---",
            entry.content,
        ]
        return "\n".join(lines)

    @staticmethod
    def _parse_md(text: str, entry_id: str, sub: str) -> WikiEntry | None:
        if not text.startswith("---"):
            return None
        _, _, rest = text.partition("---")
        head, sep, body = rest.partition("\n---\n")
        if not sep:
            return None
        fields: dict[str, str] = {}
        for line in head.splitlines():
            if ":" in line:
                key, _, value = line.partition(":")
                fields[key.strip()] = value.strip()
        return WikiEntry(
            id=fields.get("id", entry_id),
            kind=fields.get("kind", "concept"),
            title=fields.get("title", entry_id),
            content=body.strip(),
            spec_id=fields.get("spec_id", ""),
            level=fields.get("level", ""),
            admin=fields.get("admin", ""),
            parent_ref=fields.get("parent_ref", ""),
            tags=tuple(x.strip() for x in fields.get("tags", "").split(",") if x.strip()),
            aliases=tuple(x.strip() for x in fields.get("aliases", "").split(",") if x.strip()),
            entities=tuple(x.strip() for x in fields.get("entities", "").split(",") if x.strip()),
            source_path=fields.get("source_path", f"{sub}/{entry_id}.md"),
            created_at=fields.get("created_at", ""),
            updated_at=fields.get("updated_at", ""),
            source_run_id=fields.get("source_run_id", ""),
            source_part=fields.get("source_part", ""),
            evidence=fields.get("evidence", ""),
            status=fields.get("status", "active"),
            confidence=float(fields.get("confidence", "1.0") or 1.0),
            supersedes=fields.get("supersedes", ""),
            superseded_by=fields.get("superseded_by", ""),
            invalid_at=fields.get("invalid_at") or None,
        )

    def close(self) -> None:
        self._conn.close()


class WikiSearch:
    """知识检索：FTS5 全文（jieba 预处理 + MATCH + bm25() 内置排名）。

    两级检索：
      第一级（命中）：FTS5 MATCH 取候选条文 → bm25() 排名 → 条文级结果（带溯源路径）
      第二级（阅读）：命中条文后由 spec_read 读整章（调用方按 section_path 取）
    记忆卡（小库）走全量 BM25；规范条文（万级）走 FTS5——这是分层的依据。
    """

    def __init__(self, store: WikiStore, *, top_k: int = 5) -> None:
        self.store = store
        self.top_k = top_k

    def search(self, query: str, *, top_k: int | None = None, level: str | None = None) -> list[WikiSearchResult]:
        k = top_k or self.top_k
        tokens = [t for t in tokenize_words(query) if t]
        if not tokens:
            return []
        # FTS5 查询：jieba 词级空格拼接（与写入侧同口径），OR 匹配任一词
        match_q = " OR ".join(f'"{t}"' for t in tokens)
        rows = self.store._exec(
            "SELECT entry_id, section_path, bm25(wiki_fts) AS score "
            "FROM wiki_fts WHERE wiki_fts MATCH ? ORDER BY score LIMIT ?",
            [match_q, k * 4],  # 取 4 倍候选，过滤层级后仍有富余
        ).fetchall()
        if not rows:
            return []
        out: list[WikiSearchResult] = []
        for entry_id, section_path, score in rows:
            entry = self.store.read_entry(str(entry_id))
            if entry is None:
                continue
            if entry.status != "active":
                continue  # P1a：待审/已失效（superseded）知识不进检索
            if level and entry.level != level:
                continue
            text = self.store.section_text(str(entry_id), str(section_path)) or ""
            out.append(
                WikiSearchResult(
                    entry_id=str(entry_id),
                    score=round(-float(score), 4),  # FTS5 bm25 为负（越小越相关），取正
                    source_path=entry.source_path,
                    title=entry.title,
                    snippet=text[:120],
                    spec_id=entry.spec_id,
                    section_path=str(section_path),
                    level=entry.level,
                    created_at=entry.created_at,
                )
            )
            if len(out) >= k:
                break
        return out

    def related_by_entities(
        self,
        entry_id: str,
        *,
        top_k: int | None = None,
        min_shared: int = 1,
    ) -> list[WikiSearchResult]:
        """实体传导链：与目标条目共享专有名词的关联条目（验收 #4"一并带出"）。

        语义：目标条目 entities 中的每个专有名词是一个"传导节点"；库中其他条目
        若共享节点，即传导链成员——如"耕地保有量指标"命中后，带出省级约束、
        市级落实等实体相关的规范/概念（节点即传导轴，条目即链节）。

        规则：
          - 按共享实体数降序返回（传导强度），同数按 created_at 升序（旧条目前）；
          - 排除自身与 pending/superseded 条目（待审/已失效不参与传导）；
          - 无实体或零共享返回 []；
          - 结果的 section_path 为空（条目级关联，非条文命中），
            snippet 标注共享实体，供调用方解释"为什么带出"。

        Args:
            entry_id: 目标条目 id（先 search 命中，再带出传导链）。
            top_k: 返回条数上限（默认 self.top_k）。
            min_shared: 最少共享实体数（过滤弱关联，默认 1）。
        """
        k = top_k or self.top_k
        target = self.store.read_entry(entry_id)
        if target is None or not target.entities:
            return []
        want = set(target.entities)
        rows = self.store._exec(
            "SELECT id, title, spec_id, level, created_at, entities, source_path, status "
            "FROM entries WHERE status = 'active'"
        ).fetchall()
        found: list[tuple[int, str, WikiSearchResult]] = []
        for rid, rtitle, rspec, rlevel, rcreated, rent, rsrc, rstatus in rows:
            rid = str(rid)
            if rid == entry_id:
                continue
            ent_set = {e.strip() for e in (rent or "").split(",") if e.strip()}
            shared = want & ent_set
            if not shared:
                continue
            n = len(shared)
            if n < min_shared:
                continue
            shared_str = ", ".join(sorted(shared))
            found.append(
                (
                    n,
                    shared_str,
                    WikiSearchResult(
                        entry_id=rid,
                        score=float(n),
                        source_path=rsrc or "",
                        title=rtitle or "",
                        snippet=f"共享实体：{shared_str}",
                        spec_id=rspec or "",
                        section_path="",
                        level=rlevel or "",
                        created_at=rcreated or "",
                    ),
                )
            )
        found.sort(key=lambda x: (-x[0], x[1]))
        return [r for _, _, r in found[:k]]


class WikiWritePipeline:
    """知识库写入管道：幂等写（别名吸收/去重）+ 版本链（supersedes）+ 待审路由。

    与 MemoryWritePipeline 平级的写侧服务——提取分流产出的 wiki 条目、
    未来的 wiki_add 工具、DSH backfill 都经它落盘（单一写侧权威）：
      - submit(run, entries)：同步幂等写一批 → 摘要（worker=False 主路径 / 测试直调）；
      - enqueue(run, entries)：非阻塞入队（对话不阻塞，永不抛错）→ 后台 worker 消化；
      - flush()：同步清空队列（close 前自动调用，退出不丢）；
      - close()：停 worker（应用退出/测试清理）。

    每条写决策：store.resolve_entry（精确/模糊合并去重，spec 只精确匹配）
    → store.write_entry（status 路由：pending 待审 / active 正式目录）
    → supersedes 标题查表建版本链（新规范覆盖旧版：旧条目标 superseded_by + invalid_at，
    不删，保留审计）。

    审计：可选 log(name, detail) 回调（MemoryWritePipeline 接记忆库 log_decision，
    统一决策轨迹）；每次写决策记 wiki_write（含 merged/superseded 标志），失败记
    wiki_write_failed，入队记 wiki_enqueue。
    """

    def __init__(
        self,
        store: WikiStore,
        *,
        enabled: bool = True,
        worker: bool = False,
        poll_seconds: float = 0.5,
        log: Callable[[str, str], None] | None = None,
    ) -> None:
        self.store = store
        self.enabled = enabled
        self.log = log
        self._queue: list[tuple[MemoryRun | None, WikiEntry]] = []
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        if worker and enabled:
            self._thread = threading.Thread(
                target=self._worker_loop, args=(poll_seconds,), daemon=True
            )
            self._thread.start()

    # —— 写侧主路径 ——

    def submit(self, run: MemoryRun | None, entries: list[WikiEntry]) -> list[dict]:
        """同步幂等写一批条目；返回每条摘要（含 merged/superseded 标志）。"""
        if not self.enabled or not entries:
            return []
        out: list[dict] = []
        for entry in entries:
            summary = self._write_one(run, entry)
            if summary is not None:
                out.append(summary)
        return out

    def enqueue(self, run: MemoryRun | None, entries: list[WikiEntry]) -> None:
        """非阻塞入队（对话不阻塞）；永不抛错。"""
        if not self.enabled or not entries:
            return
        with self._lock:
            self._queue.extend((run, e) for e in entries)
        self._log("wiki_enqueue", f"{len(entries)} 条（队列 {len(self._queue)}）")

    def flush(self) -> int:
        """同步消化队列；返回成功写条数。"""
        with self._lock:
            items, self._queue = self._queue, []
        written = 0
        for run, entry in items:
            if self._write_one(run, entry) is not None:
                written += 1
        return written

    def close(self) -> None:
        """停 worker（先 flush 队列，退出不丢）；应用退出/测试清理。"""
        self.flush()
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)

    # —— 内部 ——

    def _write_one(self, run: MemoryRun | None, entry: WikiEntry) -> dict | None:
        """单条幂等写：别名吸收合并 → 落盘（pending/active 路由）→ supersedes 版本链。"""
        try:
            resolved = self.store.resolve_entry(entry)
            merged = resolved.id != entry.id  # 别名吸收合并到既有 canonical（未产生新条目）
            self.store.write_entry(resolved)
            superseded = False
            if resolved.supersedes.strip():
                old = self.store.find_entry_by_title(
                    resolved.supersedes, kind=resolved.kind
                )
                if old is not None and old.id != resolved.id:
                    self.store.supersede_entry(old.id, resolved.id)
                    superseded = True
            self._log(
                "wiki_write",
                f"{resolved.id}: kind={resolved.kind} title={resolved.title!r} "
                f"status={resolved.status} merged={merged} superseded={superseded}",
            )
            return {
                "id": resolved.id,
                "kind": resolved.kind,
                "title": resolved.title,
                "status": resolved.status,
                "confidence": resolved.confidence,
                "merged": merged,
                "superseded": superseded,
            }
        except Exception as exc:  # noqa: BLE001 - 单条失败不拖垮整批
            self._log("wiki_write_failed", f"{entry.id}: {exc}")
            return None

    def _worker_loop(self, poll_seconds: float) -> None:
        while not self._stop.is_set():
            self.flush()
            self._stop.wait(poll_seconds)

    def _log(self, name: str, detail: str) -> None:
        if self.log is None:
            return
        with contextlib.suppress(Exception):
            self.log(name, detail)

