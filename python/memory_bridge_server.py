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
import re
import sys
import threading
from dataclasses import asdict, replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

# --- bootstrap ------------------------------------------------------------
# The harness host passes --root <engine root>; it must be on sys.path before
# any ``memory.*`` top-level import below.  main() also prepends the root, but
# that runs after module-level imports, so the bootstrap mirrors it here.
def _prepend_engine_root() -> None:
    for idx, arg in enumerate(sys.argv):
        if arg == "--root" and idx + 1 < len(sys.argv):
            root = Path(sys.argv[idx + 1]).resolve()
            if str(root) not in sys.path:
                sys.path.insert(0, str(root))
            return


_prepend_engine_root()

# 顶层 import 容错：jieba/引擎依赖缺失时不至于整个 sidecar 崩溃退出，
# 而是记录错误，让 HTTP 服务器照常监听，所有 RPC 经 ensure_engine 返回
# 可操作的安装指引（而非裸 ModuleNotFoundError / 进程直接退出）。
_import_error: str | None = None
try:
    from memory.store import now_iso  # noqa: F401  (rpc_add_run 时间戳)
except ModuleNotFoundError as exc:  # noqa: PERF203
    _import_error = str(exc)
    now_iso = None  # type: ignore[assignment]

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
        "apiKeyEnv": "",  # 优先读环境变量（渐进迁移：设了环境变量即不再用明文）
        "sanitize": True,
    },
    "cloud": {
        "baseUrl": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
        "apiKey": "",
        "apiKeyEnv": "",
        "sanitize": True,
        "batchSize": 8,
        "maxCallsPerMinute": 10,
    },
    "main": {"sanitize": True},
}


def _resolve_api_key(section: dict[str, Any]) -> str:
    """apiKey 解析：环境变量（apiKeyEnv 指定）优先，回退明文配置。"""
    env_name = str(section.get("apiKeyEnv", "") or "").strip()
    if env_name:
        env_val = os.environ.get(env_name, "")
        if env_val.strip():
            return env_val.strip()
    return str(section.get("apiKey", "") or "")


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
        if _import_error is not None:
            # 顶层 import 已失败（如 jieba 缺失）：给出可操作指引，不重复裸异常
            raise RuntimeError(
                "Memory Tree engine dependency missing: "
                f"{_import_error}. Install once, e.g.: "
                f"pip install -r {root / 'requirements.txt'} "
                "(or run: pwsh <engine>/install-deps.ps1). The sidecar needs "
                "jieba for tokenization before any memory operation."
            )
        try:
            import jieba  # noqa: F401  (bundled pure-python package)
        except ModuleNotFoundError:
            raise RuntimeError(
                "Memory Tree engine dependency missing: jieba. "
                f"Install it once, e.g.: pip install -r {root / 'requirements.txt'} "
                "(or run: pwsh <engine>/install-deps.ps1). The sidecar needs jieba "
                "for tokenization before any memory operation."
            ) from None
        import memory as mem
        from memory.audit import audit_summary
        from memory.decay import DecayMaintenance
        from memory.extract import MemoryWritePipeline
        from memory.govern import apply_usage_feedback, govern_injection
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
        decay = DecayMaintenance(store, branch_idle_days=30)
        # 启动对账：清理历史积压（30 天 idle 的枝完结 + 子卡枯萎；幂等）
        with contextlib.suppress(Exception):
            decay.run_once()
        # 画像蒸馏装配（distill.py 已实现未接线 → 桥接层补入口）：
        # backends 复用提取器后端链（role=extract 优先，蒸馏不额外要求 LLM 通道）
        from memory.profile import ProfileStore

        _profile_store = ProfileStore(Path(mem.resolve_memory_root()))
        _engine = {
            "mem": mem,
            "store": store,
            "wiki_store": wiki_store,
            "search": search,
            "wiki_search": wiki_search,
            "lemonade": lemonade,
            "injector": MemoryInjector(search),
            "profile_store": _profile_store,
            "decay": decay,
            "apply_usage_feedback": apply_usage_feedback,
            "govern_injection": govern_injection,
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
            api_key=_resolve_api_key(local),
            sanitize=bool(local.get("sanitize", True)),
        ),
        cloud=mem.CloudConfig(
            base_url=cloud.get("baseUrl", "https://api.deepseek.com/v1"),
            model=cloud.get("model", "deepseek-chat"),
            api_key=_resolve_api_key(cloud),
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
    # 画像不在 cards 表（ProfileStore 管理 profiles/PROFILE.md）：真实状态覆盖计数
    with contextlib.suppress(Exception):
        profile = eng["profile_store"].load()
        if profile is not None and profile.status == "approved":
            counts["profile"] = 1
    for status in ("active", "archived"):
        by_status[status] = store.count_cards(status=status)
    wiki_counts: dict[str, int] = {}
    for kind in ("spec", "concept", "tutorial"):
        wiki_counts[kind] = sum(
            1 for e in eng["wiki_store"].all_entries() if e.kind == kind
        )
    lemonade = _lemonade_payload()
    # 画像草稿数（badge 用）
    profile_drafts = 0
    with contextlib.suppress(Exception):
        profile_drafts = len(eng["profile_store"].list_drafts())
    return {
        "memoryRoot": eng["memory_root"],
        "wikiRoot": eng["wiki_root"],
        "engineRoot": eng["engine_root"],
        "counts": counts,
        "byStatus": by_status,
        "pendingCount": counts.get("lesson_pending", 0),
        "profileDrafts": profile_drafts,
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
        ts=now_iso(),  # M2：缺省 ts 会让 ORDER BY ts 排序失效、时间列全空
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


# ---------------------------------------------------------------------------
# 画像蒸馏（distill.py 接线：手动触发 + 审批 + 状态）
# ---------------------------------------------------------------------------

def _profile_distiller(eng: dict[str, Any]):
    """按当前配置装配 ProfileDistiller（复用提取器后端链）。"""
    from memory.distill import ProfileDistiller

    cfg = load_config()
    extractor = eng["mem"].build_extractor(to_extract_config(cfg))
    if extractor is None:
        raise ValueError("distill 需要激活提取后端（off 模式无 LLM 可用）：请先配置 mode=local/cloud/main/hybrid")
    backends: list = []
    if getattr(extractor, "backend", None) is not None:
        backends.append(extractor.backend)
    if getattr(extractor, "fallback_backend", None) is not None:
        backends.append(extractor.fallback_backend)
    if not backends:
        raise ValueError("distill 无可用 LLM 后端")
    # count_tokens：启发式（字符 / 2 近似；引擎无 tokenizer 契约）
    def _count_tokens(text: str) -> int:
        return max(1, len(text) // 2)

    return ProfileDistiller(
        store=eng["profile_store"],
        memory=eng["store"],
        backends=backends,
        count_tokens=_count_tokens,
    )


def rpc_distill(params: dict[str, Any] | None = None) -> dict[str, Any]:
    """手动触发一轮画像蒸馏；产出 profiles/drafts/*.md 待审批。"""
    eng = ensure_engine()
    try:
        distiller = _profile_distiller(eng)
        draft = distiller.distill()
    except Exception as exc:  # noqa: BLE001
        eng["store"].log_decision("distill_rpc_error", str(exc)[:300])
        return {"ok": False, "error": f"distill failed: {exc}"}
    if draft is None:
        return {"ok": True, "draft": None, "note": "无事件可蒸馏 / 防抖跳过 / 去重跳过"}
    return {"ok": True, "draft": {"summary": draft.summary[:120], "status": draft.status}}


def _safe_draft_id(draft_id: str) -> str:
    """画像草稿 id 白名单：只允许纯文件名（防路径穿越）。"""
    draft_id = str(draft_id or "").strip()
    name = Path(draft_id).name
    if name != draft_id or name.startswith(".") or "/" in draft_id or "\\" in draft_id:
        raise ValueError("invalid draft id")
    return name


def rpc_distill_approve(params: dict[str, Any]) -> dict[str, Any]:
    """审批画像草稿 → PROFILE.md（status=approved，version+1）。"""
    eng = ensure_engine()
    try:
        draft_id = _safe_draft_id(str(params.get("draftId", "")))
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    try:
        approved = eng["profile_store"].approve(draft_id)
    except KeyError as exc:
        return {"ok": False, "error": str(exc)}
    eng["store"].log_decision("distill_approve", f"{draft_id} -> approved")
    return {"ok": True, "profile": {"summary": approved.summary[:120], "version": approved.version, "status": approved.status}}


def rpc_distill_reject(params: dict[str, Any]) -> dict[str, Any]:
    """驳回画像草稿 → profiles/rejected/（明文保留）。"""
    eng = ensure_engine()
    try:
        draft_id = _safe_draft_id(str(params.get("draftId", "")))
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    try:
        eng["profile_store"].reject(draft_id)
    except KeyError as exc:
        return {"ok": False, "error": str(exc)}
    eng["store"].log_decision("distill_reject", draft_id)
    return {"ok": True}


def rpc_profile_status(_params: dict[str, Any] | None = None) -> dict[str, Any]:
    """画像状态：approved 主画像 + 待审草稿列表。"""
    eng = ensure_engine()
    store = eng["profile_store"]
    approved = store.load()
    drafts = []
    for name, p in store.list_drafts():
        drafts.append({"draftId": name, "summary": p.summary[:100], "mbti": p.mbti, "updatedAt": p.updated_at})
    return {
        "ok": True,
        "approved": {
            "summary": approved.summary,
            "mbti": approved.mbti,
            "updatedAt": approved.updated_at,
            "version": approved.version,
        } if approved is not None and approved.status == "approved" else None,
        "drafts": drafts,
    }


def rpc_config_set(params: dict[str, Any]) -> dict[str, Any]:
    cfg = params.get("config")
    if not isinstance(cfg, dict):
        return {"ok": False, "error": "config must be an object"}
    load_config()
    merged = json.loads(json.dumps(DEFAULT_CONFIG))
    merged["mode"] = str(cfg.get("mode", "main"))
    for section in ("local", "cloud", "main"):
        src = cfg.get(section) if isinstance(cfg.get(section), dict) else {}
        incoming = {k: v for k, v in src.items() if k in merged[section]}
        # B2 防护：UI 回读的是掩码 key（sk-****…）。用户改任意配置保存时若
        # 提交的仍是掩码串 → 视为"未修改 key"，保留旧值，避免明文 key 被覆盖丢失。
        if "apiKey" in incoming and isinstance(incoming["apiKey"], str) and "*" in incoming["apiKey"]:
            old_key = _config.get(section, {}).get("apiKey", "")
            incoming["apiKey"] = old_key
        merged[section].update(incoming)
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
    # 提取后自动维护：衰减判定（30 天 idle 枝完结）+ 节流全局治理（6h 一次）
    with contextlib.suppress(Exception):
        eng["decay"].run_once() if _decay_due() else None
        _run_govern_if_due(eng)
    return {"ok": True, "mode": mode, "extracted": total, "processed": total}


def rpc_recorder(params: dict[str, Any]) -> dict[str, Any]:
    """零 LLM 即时记忆（rules.py 设计原意：用户消息到达即规则扫描，不依赖 LLM 提取）。

    三条规则通道（全部只扫用户文本，零模型调用，不抢 TTFT）：
    ① extract_direct_lesson  "记住教训/踩坑/经验教训" → 立即沉淀 lesson_permanent（永久经验卡）
    ② extract_direct_memory  "记住/记下/别忘了" → 立即沉淀 event 卡
    ③ extract_signal         "我喜欢/更喜欢/习惯/别用" → 偏好信号入账 → 聚合 ≥3 同类 → lesson_pending 提案
    """
    from memory.rules import (
        PreferenceLedger,
        extract_direct_lesson,
        extract_direct_memory,
    )

    eng = ensure_engine()
    store = eng["store"]
    user_text = str(params.get("userText", ""))
    if not user_text.strip():
        return {"ok": True, "recorded": 0, "proposed": [], "cards": []}
    import hashlib as _hashlib

    def _now():
        from memory.store import now_iso as _now_iso
        return _now_iso()

    source = str(params.get("sourcePath", "")) or "runs/staged"
    cards_created: list[dict] = []

    # ① 教训指令 → 永久经验卡（最高优先级，先于"记住"检查——rules.py 注释）
    lesson = extract_direct_lesson(user_text)
    if lesson:
        digest = _hashlib.sha1(f"lesn|{lesson}".encode()).hexdigest()[:12]
        card_id = f"lesn-{digest}"
        if store.read_card(card_id) is None:
            from memory.models import MemoryCard
            card = MemoryCard(
                id=card_id,
                kind="lesson_permanent",
                title=f"经验：{lesson[:40]}",
                content=lesson,
                source_path=f"lessons/permanent/{card_id}.md",
                created_at=_now(),
                confidence=0.95,  # 用户明确指令表达，高置信直接固化
                status="active",
            )
            store.write_card(card)
            store.log_decision("lesson_direct", f"{card_id}: {lesson[:60]}")
            cards_created.append({"cardId": card_id, "kind": "lesson_permanent", "title": card.title})
        return {"ok": True, "recorded": 0, "proposed": [], "cards": cards_created}

    # ② 直接记忆指令 → 事件卡（"记住：X"）
    memo = extract_direct_memory(user_text)
    if memo:
        digest = _hashlib.sha1(f"mem|{memo}".encode()).hexdigest()[:12]
        card_id = f"evt-{digest}"
        if store.read_card(card_id) is None:
            from memory.models import MemoryCard
            card = MemoryCard(
                id=card_id,
                kind="event",
                title=f"记住：{memo[:40]}",
                content=memo,
                source_path=f"events/cards/{card_id}.md",
                created_at=_now(),
                confidence=0.9,
                status="active",
            )
            store.write_card(card)
            store.log_decision("memory_direct", f"{card_id}: {memo[:60]}")
            cards_created.append({"cardId": card_id, "kind": "event", "title": card.title})
        return {"ok": True, "recorded": 0, "proposed": [], "cards": cards_created}

    # ③ 偏好信号 → 入账 + 聚合提案（≥3 同类 → lesson_pending）
    ledger = PreferenceLedger(store, source_path=source)
    sig = ledger.record(user_text)
    recorded = 1 if sig is not None else 0
    proposed = []
    if sig is not None:
        with contextlib.suppress(Exception):
            for card in ledger.propose():
                proposed.append({"cardId": card.id, "title": card.title})
        if proposed:
            store.log_decision("lesson_propose", f"{len(proposed)} 张偏好提案")
    return {"ok": True, "recorded": recorded, "proposed": proposed, "cards": cards_created}


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

_inject_cache: dict[str, tuple[float, list]] = {}  # session_id -> (ts, list[SearchResult])
_INJECT_CACHE_MAX = 256          # M3：容量上限（防无界增长）
_INJECT_CACHE_TTL = 30 * 60      # M3：TTL 秒（惰性淘汰，会话中断/无 turn/end 也不残留）


def _cache_put(session_id: str, results: list) -> None:
    """写注入缓存（带 TTL + 容量上限惰性淘汰）。"""
    import time as _t

    now = _t.time()
    if len(_inject_cache) >= _INJECT_CACHE_MAX:
        # 超限：淘汰最旧条目（惰性扫描，量小可接受）
        oldest = min(_inject_cache, key=lambda k: _inject_cache[k][0])
        _inject_cache.pop(oldest, None)
    _inject_cache[session_id] = (now, results)


def _cache_get(session_id: str) -> list:
    """读注入缓存（过期即弃）。"""
    import time as _t

    hit = _inject_cache.get(session_id)
    if hit is None:
        return []
    ts, results = hit
    if _t.time() - ts > _INJECT_CACHE_TTL:
        _inject_cache.pop(session_id, None)
        return []
    return results


def _cache_pop(session_id: str) -> list:
    hit = _inject_cache.pop(session_id, None)
    return hit[1] if hit else []


def _dedup_inject(results: list) -> list:
    """注入去重：多轮重复提取会生成标题/内容相同的卡，全量注入浪费上下文。

    - 标题完全相同 → 只保留 score 最高的一条
    - 同一链下最多 2 条（不同标题的卡同链可能都有价值，但限流保多样性）
    """
    if len(results) <= 1:
        return results
    by_title: dict[str, list] = {}
    for r in results:
        by_title.setdefault(r.title.strip(), []).append(r)
    picked: list = []
    for _title, group in by_title.items():
        picked.append(max(group, key=lambda r: r.score))
    seen_chain: dict[str, int] = {}
    final: list = []
    for r in picked:
        chain = r.chain_id or ""
        if seen_chain.get(chain, 0) >= 2:
            continue
        seen_chain[chain] = seen_chain.get(chain, 0) + 1
        final.append(r)
    return final


def _inject_tier(text: str) -> str:
    """注入档位自动判定：指令/计划/目标 → L2(≤3 条)；一般消息 → L1(≤1 条)；寒暄 → L0(不注入省 token)。

    v0.3 抢救修复：寒暄词表补全（你好/在吗/天气/早上好/晚安/哈哈/哦/好吧/拜拜/没问题 等），
    短寒暄句不再漏判为 L1（8 场景审计场景 4：寒暄应零注入）。

    v0.3 二次修复：寒暄判定改为**整句近似匹配**而非子串——单字词（好/行/嗯/哦）
    子串匹配会把真实问题误判为寒暄（实测："我的回答风格偏好是什么" 因含"好"
    被误判 L0 零注入）。现规则：去标点后的整句须以寒暄词开头且超出部分 ≤4 字。
    """
    t = text.strip()
    if not t:
        return "L0"
    # minor-1：先查 L2 指令关键词（"好的，继续"含"继续"应判 L2，不能因含寒暄词被 L0 吞掉）
    if any(k in t for k in (
        "记住", "以后", "计划", "目标", "我们需要", "帮我", "继续", "修复",
        "完善", "改成", "方案", "我们要", "接下来", "把", "用", "请",
    )):
        return "L2"
    # 寒暄/无信息量：短句整句近似命中寒暄词 → 零注入
    if len(t) < 20:
        _CHIT_CHAT = (
            "谢谢", "感谢", "好的", "ok", "OK", "嗯", "可以", "再见", "了解",
            "收到", "你好", "您好", "在吗", "早上好", "下午好", "晚上好",
            "晚安", "哈哈", "哦", "好吧", "拜拜", "没问题", "行", "好",
            "明白", "明白了", "辛苦了",
        )
        core = re.sub(r"[\s,，。.!！?？~～、]+", "", t)
        if core and any(
            core == word or (core.startswith(word) and len(core) - len(word) <= 4)
            for word in _CHIT_CHAT
        ):
            return "L0"
    return "L1"


def rpc_inject(params: dict[str, Any]) -> dict[str, Any]:
    """按用户消息检索相关记忆，返回带溯源的注入文本（tier 自动判定，已去重，50ms 超时）。"""
    eng = ensure_engine()
    query = str(params.get("query", "")).strip()[:2000]
    if not query:
        return {"text": "", "cards": [], "count": 0}
    session_id = str(params.get("sessionId", ""))
    tier = str(params.get("tier", "auto") or "auto")
    if tier in ("auto", ""):
        tier = _inject_tier(query)
    inj = eng["injector"]
    results = _dedup_inject(inj.inject_for_tier(tier, query))
    if session_id:
        _cache_put(session_id, results)
    # 常驻基线快照（低频推式层）：approved 画像 + 高置信永久经验，digest 变更检测
    # v0.3 抢救修复：传 query 做相关性闸门——无关主题/寒暄/无匹配时不注入画像经验（防噪音）
    snapshot_text = ""
    snapshot_digest = ""
    try:
        profile = eng["profile_store"].load()
        approved = profile if (profile is not None and profile.status == "approved") else None
        snapshot_text, snapshot_digest = inj.build_static_snapshot(profile=approved, query=query)
    except Exception as exc:  # noqa: BLE001 - 快照失败不拖垮注入，但必须留痕可查
        with contextlib.suppress(Exception):
            eng["store"].log_decision("inject_snapshot_error", f"{type(exc).__name__}: {exc}")
    text = "\n".join(inj.format_result(r) for r in results)
    if snapshot_text:
        text = (snapshot_text + "\n" + text).strip()
    return {
        "text": text,
        "tier": tier,
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
        "snapshotDigest": snapshot_digest,
    }


def rpc_record_usage(params: dict[str, Any]) -> dict[str, Any]:
    """审计闭环：判定模型回复是否利用了注入记忆（inject_used 落 decision_log）。"""
    eng = ensure_engine()
    session_id = str(params.get("sessionId", ""))
    reply = str(params.get("replyText", ""))
    results = _cache_pop(session_id)
    if not results or not reply.strip():
        return {"ok": True, "usage": {}}
    usage = eng["injector"].record_usage(results, reply)
    # 审计回流：used→命中滚动 / unused→miss 累计、达阈值降权淡出（治理闭环）
    if usage:
        with contextlib.suppress(Exception):
            eng["apply_usage_feedback"](eng["store"], usage)
    return {"ok": True, "usage": usage}


# ---------------------------------------------------------------------------
# 衰减治理（P2 接线）：提取后自动衰减 + 节流全局治理 + 手动维护端点
# ---------------------------------------------------------------------------

_last_govern_at: float = 0.0
_GOVERN_INTERVAL_SECONDS = 6 * 3600  # 全局治理节流：6 小时一次
_last_decay_at: float = 0.0
_DECAY_INTERVAL_SECONDS = 30 * 60   # M7：decay 全树扫描节流：30 分钟一次


def _decay_due() -> bool:
    """decay 节流（M7）：全树扫描开销大，不随每次提取执行。"""
    global _last_decay_at
    import time as _t

    now = _t.time()
    if now - _last_decay_at < _DECAY_INTERVAL_SECONDS:
        return False
    _last_decay_at = now
    return True


def _run_govern_if_due(eng: dict[str, Any]) -> None:
    """健康指标驱动的全局治理（govern_injection），节流执行。"""
    global _last_govern_at
    import time as _t

    now = _t.time()
    if now - _last_govern_at < _GOVERN_INTERVAL_SECONDS:
        return
    _last_govern_at = now
    with contextlib.suppress(Exception):
        eng["govern_injection"](eng["store"])


def rpc_maintenance(_params: dict[str, Any] | None = None) -> dict[str, Any]:
    """手动触发一轮衰减 + 全局治理；返回报告（写 decision_log 可审计）。"""
    eng = ensure_engine()
    decay_res = eng["decay"].run_once()
    report = eng["govern_injection"](eng["store"])
    return {
        "ok": True,
        "decay": decay_res,
        "govern": {
            "inject_used_rate": report.inject_used_rate,
            "judged_cards": report.judged_cards,
            "degradedCards": len(report.degraded_cards),
            "suggestedLimits": list(report.suggested_limits),
            "actions": list(report.actions),
        },
    }


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
    "recorder": rpc_recorder,
    "audit": rpc_audit,
    "graph": rpc_graph,
    "inject": rpc_inject,
    "recordUsage": rpc_record_usage,
    "maintenance": rpc_maintenance,
    "distill": rpc_distill,
    "distillApprove": rpc_distill_approve,
    "distillReject": rpc_distill_reject,
    "profileStatus": rpc_profile_status,
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
            if length <= 0 or length > 1_048_576:  # 1MB 上限（host 层 64KB 的宽松后备）
                self._send(413, {"ok": False, "error": "request body too large"})
                return
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






