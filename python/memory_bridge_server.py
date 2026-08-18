"""dsh-memory-bridge sidecar: JSON-RPC HTTP service wrapping the Memory Tree engine.

The harness host spawns this process, reads the "DMB_PORT <n>" banner line from
stdout, and proxies /dsh-memory/* browser requests here as JSON-RPC.

Engine loading: the memory tree root (containing ``memory/``, ``core/`` and the
bundled pure-python ``jieba/``) is prepended to sys.path, so the sidecar needs
no pip installs. Bridge configuration is a plain JSON file the UI edits through
``configGet`` / ``configSet``; api keys are masked when read back.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
import threading
from dataclasses import asdict, replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

BANNER = "DMB_PORT"

_engine_root: str | None = None
_engine_lock = threading.Lock()
_engine: dict[str, Any] | None = None
_config_lock = threading.Lock()
_config: dict[str, Any] = {}
_config_path: Path | None = None

DEFAULT_CONFIG: dict[str, Any] = {
    "mode": "main",  # off | local | cloud | main | hybrid
    "local": {
        "preset": "qwen3-it-4b-flm",  # qwen3-it-4b-flm | custom
        "autoManage": True,
        "baseUrl": "",
        "model": "",
        "apiKey": "",
        "sanitize": True,
    },
    "cloud": {
        "baseUrl": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
        "apiKey": "",
        "sanitize": True,
        "batchSize": 8,
        "maxCallsPerMinute": 10,
    },
    "main": {"sanitize": True},
}


# ---------------------------------------------------------------------------
# config IO
# ---------------------------------------------------------------------------

def load_config() -> dict[str, Any]:
    global _config
    if _config_path is None or not _config_path.is_file():
        _config = json.loads(json.dumps(DEFAULT_CONFIG))
        return _config
    try:
        raw = json.loads(_config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raw = {}
    merged = json.loads(json.dumps(DEFAULT_CONFIG))
    for key in ("mode",):
        if key in raw:
            merged[key] = raw[key]
    for section in ("local", "cloud", "main"):
        src = raw.get(section) if isinstance(raw.get(section), dict) else {}
        merged[section].update({k: v for k, v in src.items() if k in merged[section]})
    _config = merged
    return merged


def save_config() -> None:
    """Write _config to disk. Caller MUST hold _config_lock (non-reentrant)."""
    if _config_path is None:
        return
    _config_path.write_text(
        json.dumps(_config, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def masked_config() -> dict[str, Any]:
    cfg = json.loads(json.dumps(_config or load_config()))
    for section in ("local", "cloud"):
        key = cfg.get(section, {}).get("apiKey", "")
        if key:
            cfg[section]["apiKey"] = _mask_key(key)
    return cfg


def _mask_key(key: str) -> str:
    if len(key) <= 8:
        return "*" * len(key)
    return key[:4] + "*" * (len(key) - 8) + key[-4:]


# ---------------------------------------------------------------------------
# engine
# ---------------------------------------------------------------------------

def ensure_engine() -> dict[str, Any]:
    global _engine
    with _engine_lock:
        if _engine is not None:
            return _engine
        root = Path(_engine_root or ".").resolve()
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        import jieba  # noqa: F401  (bundled pure-python package)
        import memory as mem
        from memory.audit import audit_summary
        from memory.extract import MemoryWritePipeline
        from memory.injector import MemoryInjector
        from memory.lemonade import LemonadeManager
        from memory.search import MemorySearch
        from memory.store import MemoryStore
        from memory.wiki import WikiSearch, WikiStore

        memory_root = mem.resolve_memory_root()
        wiki_root = mem.resolve_wiki_root()
        store = MemoryStore(memory_root)
        wiki_store = WikiStore(wiki_root)
        search = MemorySearch(store)
        wiki_search = WikiSearch(wiki_store)
        lemonade = LemonadeManager()
        # 崩溃/重启对账：遗留 extracting 认领回滚为 staged（引擎管道只认 staged/failed）
        with contextlib.suppress(Exception):
            store._exec("UPDATE runs SET status = 'staged' WHERE status = 'extracting'")
        _engine = {
            "mem": mem,
            "store": store,
            "wiki_store": wiki_store,
            "search": search,
            "wiki_search": wiki_search,
            "lemonade": lemonade,
            "injector": MemoryInjector(search),
            "pipeline_cls": MemoryWritePipeline,
            "memory_root": str(memory_root),
            "wiki_root": str(wiki_root),
            "engine_root": str(root),
            "audit_summary": audit_summary,
        }
        return _engine


def to_extract_config(cfg: dict[str, Any]):
    mem = ensure_engine()["mem"]
    local = cfg.get("local", {})
    cloud = cfg.get("cloud", {})
    main = cfg.get("main", {})
    return mem.ExtractConfig(
        mode=cfg.get("mode", "main"),
        local=mem.LocalConfig(
            preset=local.get("preset", "qwen3-it-4b-flm"),
            auto_manage=bool(local.get("autoManage", True)),
            base_url=local.get("baseUrl", ""),
            model=local.get("model", ""),
            api_key=local.get("apiKey", ""),
            sanitize=bool(local.get("sanitize", True)),
        ),
        cloud=mem.CloudConfig(
            base_url=cloud.get("baseUrl", "https://api.deepseek.com/v1"),
            model=cloud.get("model", "deepseek-chat"),
            api_key=cloud.get("apiKey", ""),
            sanitize=bool(cloud.get("sanitize", True)),
            batch_size=int(cloud.get("batchSize", 8)),
            max_calls_per_minute=int(cloud.get("maxCallsPerMinute", 10)),
        ),
        main=mem.MainModelConfig(sanitize=bool(main.get("sanitize", True))),
    )


def _card_payload(card) -> dict[str, Any]:
    d = asdict(card)
    for key in ("entities", "children", "aliases"):
        if key in d and isinstance(d[key], tuple):
            d[key] = list(d[key])
    return d


# ---------------------------------------------------------------------------
# 提取管道缓存：engine 的 MemoryWritePipeline 自带门卫/归链/冲突裁决/知识管道/
# 失败退避上限，sidecar 只负责装配与调用。管道（含提取器）按配置指纹缓存，
# 复用实例才让云端限流/成本记账持续生效（每调用重建会把 10 次/分限流清零）。
# ---------------------------------------------------------------------------

_pipeline_cache: dict[str, Any] = {}


def _config_fingerprint(cfg: dict[str, Any]) -> str:
    c = cfg.get("cloud", {})
    l = cfg.get("local", {})
    return json.dumps(
        {
            "mode": cfg.get("mode"),
            "cloud": (c.get("baseUrl"), c.get("model")),
            "local": (l.get("baseUrl"), l.get("model"), l.get("preset")),
        },
        sort_keys=True,
    )


def get_pipeline(eng: dict[str, Any]) -> Any:
    """按当前配置取（缓存）提取管道；off/未配置返回 None。"""
    cfg = load_config()
    fp = _config_fingerprint(cfg)
    pipe = _pipeline_cache.get(fp)
    if pipe is not None:
        return pipe
    extractor = eng["mem"].build_extractor(to_extract_config(cfg))
    if extractor is None:
        return None
    pipe = eng["pipeline_cls"](
        eng["store"],
        extractor=extractor,
        wiki_store=eng["wiki_store"],
        enabled=True,
        worker=False,
    )
    _pipeline_cache.clear()
    _pipeline_cache[fp] = pipe
    return pipe


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _make_run_id(session_id: str, user_text: str) -> str:
    import hashlib
    import time as _t

    digest = hashlib.sha1(f"{session_id}|{_t.time()}|{user_text}".encode()).hexdigest()[:12]
    return f"run-{digest}"


# ---------------------------------------------------------------------------
# RPC methods
# ---------------------------------------------------------------------------

def rpc_health(_params: dict[str, Any] | None = None) -> dict[str, Any]:
    eng = ensure_engine()
    return {"ok": True, "engine": "memory-tree", "memoryRoot": eng["memory_root"]}


def rpc_overview(_params: dict[str, Any] | None = None) -> dict[str, Any]:
    eng = ensure_engine()
    store = eng["store"]
    counts: dict[str, int] = {}
    by_status: dict[str, int] = {}
    for kind in ("event", "chain", "lesson_pending", "lesson_permanent", "profile"):
        counts[kind] = store.count_cards(kind=kind)
    for status in ("active", "archived"):
        by_status[status] = store.count_cards(status=status)
    wiki_counts: dict[str, int] = {}
    for kind in ("spec", "concept", "tutorial"):
        wiki_counts[kind] = sum(
            1 for e in eng["wiki_store"].all_entries() if e.kind == kind
        )
    lemonade = _lemonade_payload()
    return {
        "memoryRoot": eng["memory_root"],
        "wikiRoot": eng["wiki_root"],
        "engineRoot": eng["engine_root"],
        "counts": counts,
        "byStatus": by_status,
        "pendingCount": counts.get("lesson_pending", 0),
        "wiki": wiki_counts,
        "runs": {"total": store.runs_count(), "staged": store.staged_backlog()},
        "lemonade": lemonade,
        "config": masked_config(),
        "recent": store.browse(limit=8),
        "audit": eng["audit_summary"](store),
    }


def rpc_search(params: dict[str, Any]) -> dict[str, Any]:
    eng = ensure_engine()
    query = str(params.get("query", "")).strip()
    if not query:
        return {"results": [], "feedbackHint": None}
    top_k = int(params.get("limit", 10))
    since = params.get("since") or None
    until = params.get("until") or None
    results = eng["search"].search(query, top_k=top_k, since=since, until=until)
    hint = None
    if params.get("feedback") is True:
        from memory.search import detect_feedback

        hint = detect_feedback(query)
    return {
        "results": [
            {
                "cardId": r.card_id,
                "score": round(r.score, 3),
                "title": r.title,
                "snippet": r.snippet,
                "chainId": r.chain_id,
                "chainTitle": r.chain_title,
                "branchSummary": r.branch_summary,
                "createdAt": r.created_at,
                "sourcePath": r.source_path,
            }
            for r in results
        ],
        "feedbackHint": hint,
    }


def rpc_browse(params: dict[str, Any]) -> dict[str, Any]:
    eng = ensure_engine()
    store = eng["store"]
    kind = params.get("kind") or None
    limit = int(params.get("limit", 200))
    cards = store.active_cards() if kind is None else [
        c for c in store.active_cards() if c.kind == kind
    ]
    cards.sort(key=lambda c: c.created_at, reverse=True)
    cards = cards[:limit]
    return {
        "cards": [
            {
                "id": c.id,
                "kind": c.kind,
                "title": c.title,
                "content": c.content[:200],
                "status": c.status,
                "confidence": c.confidence,
                "evidence": c.evidence,
                "createdAt": c.created_at,
                "updatedAt": c.updated_at,
                "sourcePath": c.source_path,
                "chainTitle": eng["store"].chain_title_map().get(c.parent_id, ""),
            }
            for c in cards
        ]
    }


def rpc_card(params: dict[str, Any]) -> dict[str, Any]:
    eng = ensure_engine()
    card_id = str(params.get("id", ""))
    card = eng["store"].read_card(card_id)
    if card is None:
        return {"card": None}
    return {"card": _card_payload(card)}


def rpc_card_action(params: dict[str, Any]) -> dict[str, Any]:
    eng = ensure_engine()
    store = eng["store"]
    card_id = str(params.get("id", ""))
    action = str(params.get("action", ""))
    card = store.read_card(card_id)
    if card is None:
        return {"ok": False, "error": "card not found"}
    if action == "approve":
        if card.kind == "lesson_pending":
            promoted = store.promote_lesson(card_id)
            if promoted is None:
                return {"ok": False, "error": "promote failed"}
            store.log_decision("card_approve", f"{card_id}: pending -> permanent")
            return {"ok": True, "card": _card_payload(promoted)}
        store._exec("UPDATE cards SET status = ? WHERE id = ?", ["active", card_id])
        store._sync_md_from_index(card_id)
        store.log_decision("card_approve", f"{card_id}: active")
        return {"ok": True, "card": _card_payload(store.read_card(card_id))}
    if action == "archive":
        store.archive_cards([card_id])
        store.log_decision("card_archive", card_id)
        return {"ok": True, "card": _card_payload(store.read_card(card_id))}
    if action == "restore":
        store._exec("UPDATE cards SET status = ? WHERE id = ?", ["active", card_id])
        store._sync_md_from_index(card_id)
        return {"ok": True, "card": _card_payload(store.read_card(card_id))}
    if action == "delete":
        store.delete_card(card_id)
        store.log_decision("card_delete", card_id)
        return {"ok": True, "card": None}
    if action == "promote":
        promoted = store.promote_lesson(card_id)
        return {"ok": promoted is not None, "card": _card_payload(promoted) if promoted else None}
    return {"ok": False, "error": f"unknown action: {action}"}


def rpc_add_run(params: dict[str, Any]) -> dict[str, Any]:
    eng = ensure_engine()
    mem = eng["mem"]
    store = eng["store"]
    user_text = str(params.get("userText", ""))
    reply_text = str(params.get("replyText", ""))
    if not user_text and not reply_text:
        return {"ok": False, "error": "empty run"}
    import hashlib
    run_id = str(params.get("runId") or "").strip() or _make_run_id(params.get("sessionId", ""), user_text)
    from memory.models import MemoryRun

    run = MemoryRun(
        run_id=run_id,
        session_id=str(params.get("sessionId", "")),
        user_text=user_text,
        reply_text=reply_text,
        tier=str(params.get("tier", "L0")),
        project_id=str(params.get("projectId") or None),
        trace_event_id=str(params.get("traceEventId", "")),
        priority=int(params.get("priority", 0)),
    )
    store.insert_run(run)
    # §9.7 门卫粗筛（与引擎 enqueue 同口径）：寒暄/无事实信号 → 落盘但跳过提取
    with contextlib.suppress(Exception):
        from memory.guard import should_extract

        worth, reason = should_extract(user_text, reply_text)
        if not worth:
            store.mark_run(run.run_id, "skipped", reason)
            store.log_decision("extract_skip", f"{run.run_id}: {reason}")
    return {"ok": True, "runId": run.run_id}


def rpc_review(params: dict[str, Any]) -> dict[str, Any]:
    eng = ensure_engine()
    store = eng["store"]
    run_id = params.get("runId") or None
    rows = store._exec(
        "SELECT run_id, session_id, user_text, reply_text, tier, ts, status, error, priority "
        "FROM runs ORDER BY ts DESC LIMIT ?",
        [int(params.get("limit", 100))],
    ).fetchall()
    runs = [
        {
            "runId": r[0], "sessionId": r[1], "userText": r[2], "replyText": r[3],
            "tier": r[4], "ts": r[5], "status": r[6], "error": r[7], "priority": r[8] or 0,
        }
        for r in rows
        if run_id is None or r[0] == run_id
    ]
    return {"runs": runs, "staged": store.staged_backlog()}


def rpc_wiki_search(params: dict[str, Any]) -> dict[str, Any]:
    eng = ensure_engine()
    query = str(params.get("query", "")).strip()
    if not query:
        return {"results": []}
    top_k = int(params.get("limit", 10))
    results = eng["wiki_search"].search(query, top_k=top_k)
    return {
        "results": [
            {
                "entryId": r.entry_id,
                "score": round(r.score, 3),
                "title": r.title,
                "snippet": r.snippet,
                "sectionPath": r.section_path,
                "specId": r.spec_id,
                "createdAt": r.created_at,
            }
            for r in results
        ]
    }


def _lemonade_payload() -> dict[str, Any]:
    eng = ensure_engine()
    try:
        st = eng["lemonade"].status()
        return {
            "serverUp": st.server_up,
            "modelLoaded": st.model_loaded,
            "loadedModels": list(st.loaded_models),
            "version": st.version,
        }
    except Exception as exc:  # pragma: no cover - CLI 级异常
        return {"serverUp": False, "modelLoaded": False, "loadedModels": [], "version": "", "error": str(exc)}


def rpc_lemonade_status(_params: dict[str, Any] | None = None) -> dict[str, Any]:
    return _lemonade_payload()


def rpc_lemonade_ensure(params: dict[str, Any]) -> dict[str, Any]:
    eng = ensure_engine()
    cfg = load_config()
    local = cfg.get("local", {})
    preset = local.get("preset", "qwen3-it-4b-flm")
    resolved = eng["mem"].resolve_local_config(
        eng["mem"].LocalConfig(preset=preset, base_url=local.get("baseUrl", ""), model=local.get("model", ""))
    )
    model = params.get("model") or resolved.model
    if not model:
        return {"ok": False, "error": "model not resolved"}
    status = eng["lemonade"].ensure_ready(model=model)
    return {"ok": True, "status": {"serverUp": status.server_up, "modelLoaded": status.model_loaded,
                                    "loadedModels": list(status.loaded_models), "version": status.version}}


def rpc_config_get(_params: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"config": masked_config(), "lemonade": _lemonade_payload()}


def rpc_config_set(params: dict[str, Any]) -> dict[str, Any]:
    cfg = params.get("config")
    if not isinstance(cfg, dict):
        return {"ok": False, "error": "config must be an object"}
    load_config()
    merged = json.loads(json.dumps(DEFAULT_CONFIG))
    merged["mode"] = str(cfg.get("mode", "main"))
    for section in ("local", "cloud", "main"):
        src = cfg.get(section) if isinstance(cfg.get(section), dict) else {}
        merged[section].update({k: v for k, v in src.items() if k in merged[section]})
    # 校验：开关激活后的必填项立即报错，避免"保存了但提取必挂"
    try:
        to_extract_config(merged)
    except Exception as exc:
        return {"ok": False, "error": f"config invalid: {exc}"}
    with _config_lock:
        _config.clear()
        _config.update(merged)
        save_config()
    _pipeline_cache.clear()  # 配置变更 → 下个 extract 重建提取管道
    return {"ok": True, "config": masked_config()}


def rpc_extract(params: dict[str, Any]) -> dict[str, Any]:
    eng = ensure_engine()
    cfg = load_config()
    mode = cfg.get("mode", "main")
    if mode in ("off", "main"):
        return {
            "ok": True,
            "mode": mode,
            "note": "off=纯规则零调用；main=主对话模型提取需在 DSH 会话内接线（P1），此界面仅展示状态",
        }
    pipe = get_pipeline(eng)
    if pipe is None:
        return {"ok": True, "mode": mode, "note": "extractor disabled"}
    # 清空积压：process_staged 按 batch_size 取量（云端攒批），循环至空；
    # 门卫/归链/冲突裁决/知识管道/失败退避上限全部由引擎管道处理。
    # runIds 参数保留兼容（无调用方依赖），实际以队列为准。
    total = 0
    while True:
        n = pipe.process_staged(limit=None)
        if n <= 0:
            break
        total += n
    return {"ok": True, "mode": mode, "extracted": total, "processed": total}


def rpc_audit(_params: dict[str, Any] | None = None) -> dict[str, Any]:
    eng = ensure_engine()
    store = eng["store"]
    rows = store.decision_log()
    return {"summary": eng["audit_summary"](store), "log": list(reversed(rows[-200:]))}


def rpc_graph(_params: dict[str, Any] | None = None) -> dict[str, Any]:
    """关系图谱数据：节点=卡/链/wiki 条目，边=归链/版本/上位规划/共享实体。

    前端据此渲染 Obsidian 式力导向图。全部读操作，无写入。
    """
    eng = ensure_engine()
    store = eng["store"]
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    by_id: dict[str, dict[str, Any]] = {}
    seen_edges: set[tuple[str, str, str]] = set()

    def add_node(nid: str, kind: str, title: str, weight: float = 1.0, **extra: Any) -> None:
        if nid in by_id:
            return
        node = {"id": nid, "kind": kind, "title": title, "weight": round(float(weight), 3)}
        if extra:
            node.update(extra)
        by_id[nid] = node
        nodes.append(node)

    def add_edge(src: str, dst: str, kind: str) -> None:
        if src == dst or src not in by_id or dst not in by_id:
            return
        key = (src, dst, kind)
        if key in seen_edges:
            return
        seen_edges.add(key)
        edges.append({"source": src, "target": dst, "kind": kind})

    # 1) 记忆卡（含链卡）：节点
    for c in store.active_cards():
        add_node(c.id, c.kind, c.title, weight=c.confidence or 1.0,
                 created_at=c.created_at, updated_at=c.updated_at,
                 source_path=c.source_path, evidence=c.evidence)

    # 2) 归链边：链 → 叶（parent_id 单向，链卡 children 冗余不重复加）
    for c in store.active_cards():
        if c.parent_id:
            add_edge(c.parent_id, c.id, "belongs")

    # 3) 版本链：supersedes / superseded_by（字段可能是 id 或标题，都尝试匹配）
    title_to_id = {n["title"]: n["id"] for n in nodes}
    for c in store.active_cards():
        for field, direction in (("supersedes", "out"), ("superseded_by", "in")):
            ref = getattr(c, field, "")
            target = by_id.get(ref) or title_to_id.get(ref)
            if target:
                if direction == "out":
                    add_edge(c.id, target, "supersedes")
                else:
                    add_edge(target, c.id, "supersedes")

    # 4) wiki 条目：节点 + 上位规划/版本边
    with contextlib.suppress(Exception):
        entries = list(eng["wiki_store"].all_entries())
        wiki_titles: dict[str, str] = {}
        for e in entries:
            add_node(e.id, f"wiki:{e.kind}", e.title, weight=e.confidence or 1.0,
                     status=e.status, created_at=e.created_at,
                     source_path=e.source_path, evidence=e.evidence)
            wiki_titles[e.title] = e.id
        for e in entries:
            if e.parent_ref:
                add_edge(e.id, by_id.get(e.parent_ref) or wiki_titles.get(e.parent_ref) or e.parent_ref, "parent")
            for field, direction in (("supersedes", "out"), ("superseded_by", "in")):
                ref = getattr(e, field, "")
                target = by_id.get(ref) or wiki_titles.get(ref)
                if target:
                    if direction == "out":
                        add_edge(e.id, target, "supersedes")
                    else:
                        add_edge(target, e.id, "supersedes")

    # 5) 跨卡共享实体：弱关联（星型连法限量，避免全连通爆炸）
    from collections import defaultdict

    ent_cards: dict[str, list[str]] = defaultdict(list)
    for c in store.active_cards():
        if c.kind == "chain":
            continue  # 链实体与叶实体天然重叠，跳过避免冗余
        for ent in c.entities:
            ent_cards[ent].append(c.id)
    entity_edges = 0
    for ids in ent_cards.values():
        if len(ids) < 2:
            continue
        ids = ids[:8]
        for other in ids[1:]:
            add_edge(ids[0], other, "entity")
            entity_edges += 1
            if entity_edges >= 300:
                break
        if entity_edges >= 300:
            break

    counts = {
        "cards": sum(1 for n in nodes if not n["kind"].startswith("wiki:")),
        "chains": sum(1 for n in nodes if n["kind"] == "chain"),
        "wiki": sum(1 for n in nodes if n["kind"].startswith("wiki:")),
        "edges": len(edges),
    }
    return {"nodes": nodes, "edges": edges, "counts": counts}


# ---------------------------------------------------------------------------
# 拉式记忆注入（读取端）：host 在 user/message 时预取检索 → 缓存本会话最近
# 注入结果；system prompt 渲染时同步取文本；turn 结束后回传审计闭环。
# ---------------------------------------------------------------------------

_inject_cache: dict[str, list] = {}  # session_id -> list[SearchResult]（最近注入）


def rpc_inject(params: dict[str, Any]) -> dict[str, Any]:
    """按用户消息检索相关记忆，返回带溯源的注入文本（L2 档 ≤3 条，50ms 超时）。"""
    eng = ensure_engine()
    query = str(params.get("query", "")).strip()[:2000]
    if not query:
        return {"text": "", "cards": [], "count": 0}
    session_id = str(params.get("sessionId", ""))
    tier = str(params.get("tier", "L2"))
    inj = eng["injector"]
    results = inj.inject_for_tier(tier, query)
    if session_id:
        _inject_cache[session_id] = results
    text = "\n".join(inj.format_result(r) for r in results)
    return {
        "text": text,
        "cards": [
            {
                "cardId": r.card_id,
                "title": r.title,
                "snippet": r.snippet,
                "chainTitle": r.chain_title,
                "chainId": r.chain_id,
            }
            for r in results
        ],
        "count": len(results),
    }


def rpc_record_usage(params: dict[str, Any]) -> dict[str, Any]:
    """审计闭环：判定模型回复是否利用了注入记忆（inject_used 落 decision_log）。"""
    eng = ensure_engine()
    session_id = str(params.get("sessionId", ""))
    reply = str(params.get("replyText", ""))
    results = _inject_cache.pop(session_id, [])
    if not results or not reply.strip():
        return {"ok": True, "usage": {}}
    usage = eng["injector"].record_usage(results, reply)
    return {"ok": True, "usage": usage}


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

METHODS: dict[str, Any] = {
    "health": rpc_health,
    "overview": rpc_overview,
    "search": rpc_search,
    "browse": rpc_browse,
    "card": rpc_card,
    "cardAction": rpc_card_action,
    "addRun": rpc_add_run,
    "review": rpc_review,
    "wikiSearch": rpc_wiki_search,
    "lemonadeStatus": rpc_lemonade_status,
    "lemonadeEnsure": rpc_lemonade_ensure,
    "configGet": rpc_config_get,
    "configSet": rpc_config_set,
    "extract": rpc_extract,
    "audit": rpc_audit,
    "graph": rpc_graph,
    "inject": rpc_inject,
    "recordUsage": rpc_record_usage,
}


class Handler(BaseHTTPRequestHandler):
    server_version = "dsh-memory-bridge/0.1"

    def log_message(self, fmt, *args):  # keep stdout clean for the PORT banner
        return

    def do_POST(self):  # noqa: N802
        if self.path != "/rpc":
            self._send(404, {"ok": False, "error": "not found"})
            return
        try:
            length = int(self.headers.get("content-length", "0"))
            body = json.loads(self.rfile.read(length) or b"{}")
        except Exception as exc:
            self._send(400, {"ok": False, "error": f"bad json: {exc}"})
            return
        method = body.get("method")
        params = body.get("params") or {}
        handler = METHODS.get(method)
        if handler is None:
            self._send(404, {"ok": False, "error": f"unknown method: {method}"})
            return
        try:
            result = handler(params)
            self._send(200, {"ok": True, "result": result})
        except Exception as exc:
            import traceback

            traceback.print_exc()
            self._send(500, {"ok": False, "error": str(exc)})

    def do_GET(self):  # noqa: N802
        if self.path == "/health":
            self._send(200, {"ok": True})
        else:
            self._send(404, {"ok": False, "error": "not found"})

    def _send(self, status: int, payload: dict[str, Any]) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "application/json; charset=utf-8")
        self.send_header("cache-control", "no-store")
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=None, help="memory tree engine root (contains memory/, jieba/)")
    parser.add_argument("--config", default=None, help="bridge config JSON path")
    parser.add_argument("--port", type=int, default=0, help="listen port; 0 = OS-assigned")
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()

    global _config_path, _engine_root
    if args.root:
        _engine_root = Path(args.root).resolve()
        root = Path(args.root).resolve()
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
    if args.config:
        _config_path = Path(args.config).resolve()
        load_config()

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"{BANNER} {server.server_address[1]}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()






