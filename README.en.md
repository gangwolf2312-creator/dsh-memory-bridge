# dsh-memory-bridge

English | [中文](README.md)

A **long-term memory** bridge plugin for DeepSeek Harness: conversations are distilled into a searchable, auditable, governable memory tree, and relevant context is injected on demand in later conversations. It began as a personal **evolvable private memory system** and is now open-sourced for anyone interested.

- **Storage**: plain-Markdown source of truth + SQLite index (readable, editable, portable)
- **Retrieval**: BM25 + multi-way RRF relevance-ranked recall (zero-LLM, zero external service)
- **Governance**: decay curve, audit loop, global contraction — memory ages but stays explainable
- **UI**: 7 visual tabs in Settings (Overview / Event Graph / Knowledge Graph / Timeline / Review / Profile / Audit)

---

## Positioning

**Core use case: memory under a constrained context window.**

DeepSeek cloud models (V4) offer a **1M-token context window** ([public source](https://www.orcarouter.ai/blog/deepseek-v4-review)). Within that, DSH's built-in mechanisms (resume the full session + compaction for over-long context) can carry memory — "stuff all history into the window" is viable.

But with **local models** (Ollama et al.) the situation is different: context windows are typically **4K-32K and require explicit configuration, with performance degrading noticeably as length grows** ([Ollama docs](https://docs.ollama.com/context-length)) — the window shrinks by tens of times, so "stuff everything in" is no longer feasible. **Memory must be structured, searchable, and injected on demand** instead of riding on a long window.

**This plugin targets exactly that practical scenario:**

> How do you still have usable long-term memory when the context window is constrained (local / small-window models)?

Approach: extract, structure, and store what's worth keeping (who you are, what you did, which decisions were accepted, which lessons were validated), then **inject only the relevant few items** each turn (not the whole history). Memory stays usable even with a small window.

**Relationship to DSH's native context (boundary)**:

| Scenario | DSH native behavior | This plugin's role |
|---|---|---|
| **Fresh session** | history empty | Plugin injection is the **only cross-session memory source** (core value) |
| **Resumed session** | full history replayed into context | Plugin injection **adds to** the history (does not replace it); both occupy the window in parallel |
| **Over-window session** | compaction summarizes history | Plugin injection **supplements** details the summary lacks (complementary) |

> **Explicit boundary**: this plugin injects into the **dynamic context of the system prompt** (`systemPrompt.context`); it does **not replace or suppress DSH's session-history injection** (history is fully derived by dsh-session's `deriveMessages`; the plugin has no API to trim it). **In-session history slimming is DSH compaction's job**; this plugin handles **cross-session persistent facts** — complementary, not overlapping.

**Audience**:

| Audience | How they use it |
|---|---|
| **Local-model users** | Small windows (4K-32K) need "inject on demand" rather than "stuff everything in" — the core scenario |
| **DeepSeek cloud users** | With a 1M window it's a nice-to-have: structured retrieval, governance, visualization instead of brute-forcing the window |
| **Memory-conscious users** | Plain-text storage, full provenance, human-approval channel — transparent and controllable |
| **Developers / self-hosters** | Engine and bridge are separated, zero external dependencies, extensible |

**Boundary statement**: this is a **memory infrastructure**, not a "perfect-memory agent" — extraction quality depends on the chosen LLM; retrieval is **relevance-ranked recall** (not semantic association, though it does multi-hop expansion). These trade-offs are stated honestly in "Known limitations".

---

## What it provides / solves / values (in Harness)

### Provides (capability list, from a user's perspective)

| Capability | How |
|---|---|
| **Cross-session persistent memory** | Conversations are distilled into memory cards; later sessions retrieve and inject on demand — a persistent fact layer beyond DSH's session context |
| **Memory tools for the agent** | `memory_search` / `memory_add_run` / `memory_review` let the agent read/write memory proactively |
| **Memory visualization** | 7 tabs: Event Graph, Knowledge Graph, Timeline, Review, Profile, Audit, Overview |
| **Lessons & profile** | "记住教训/踩坑" records permanent lessons instantly; preference signals aggregate into proposals; profile distillation with human approval |
| **Governance loop** | Decay curve, utilization contraction, audit feedback — the memory store doesn't grow without bound |

### Solves (pain points)

| Pain point | How this plugin addresses it |
|---|---|
| **Cross-session memory missing**: new/compacted sessions don't carry old facts; resume only continues an old conversation | Auto-extract to a persistent layer, inject relevant memories to restore context (cross-session facts, not in-session history) |
| **Small window can't hold all memory**: local models 4K-32K can't fit history; in-session overrun is DSH compaction's job, cross-session facts come from on-demand injection (tiered, capped) | Injects only the relevant few memories (L2≤3/L1≤1/greetings 0), avoids stuffing all history into the prompt |
| **History isn't searchable/governable**: session logs are raw text — can't ask "what preference did I state before?" | Structured memory cards + relevance-ranked retrieval + tiered injection + governance loop |
| **Memory can't be trusted**: model "remembering" may be hallucination | Zero-LLM relevance retrieval on read; evidence tags + provenance on write; low-confidence goes to human review |
| **Data black box**: memory locked in a database/vector store, unreadable/uneditable | Plain-Markdown source of truth, readable/editable/portable |
| **Memory bloat**: grows without bound, noise drowns signal | Decay curve (30-day idle branches end) + utilization governance + weight fade |
| **No ROI visibility**: installed memory plugin, unclear if it helps | Audit tab: injection hit rate / utilization / extraction cost — quantified loop |

### Values

- **Conversation quality**: relevant memories (preferences, project context, accepted decisions) are injected at key turns, reducing repeated explanations and contradictions — the model responds from retrieved memory, not from mere recall.
- **Cost**: tiered capped injection + zero-injection greetings + extraction gate (skip LLM on chit-chat) keep memory from becoming a per-turn token burden; KV-cache friendly (resident baseline digest unchanged → no rebuild).
- **Reliability**: memory is an independent data layer, not model discipline — retrieval reproducible, writes traceable, governance auditable; even if extraction fails, the raw conversation stays in the `runs` table.
- **Control**: plain-text local data, manually editable/deletable; lessons and profiles solidify only after human approval; every decision is written to `decision_log`.

---

## Design philosophy

**In one sentence: memory is an independent, reliable data layer — not a product of model discipline.**

Four principles:

1. **Plain text as source of truth, index as acceleration only.** Each memory card is a Markdown file; SQLite is only a rebuildable retrieval index — data is not locked away, is manually editable, and survives index loss.
2. **Deterministic-algorithm retrieval, zero-LLM read path.** Retrieval is zero-LLM: BM25 + multi-way RRF fusion, reproducible and auditable for the same data state. LLM participates only on the write side (extraction); uncertainty is confined to the write pipeline.
3. **Write actively, read sparingly.** Every turn auto-extracts (LLM + zero-LLM rule dual channel); injection is tiered by conversational intent (key ≤3, general ≤1, greetings 0) — memory is "consulted on demand", not blindly stuffed into context.
4. **Forgetting is part of memory.** 30-day idle branches end, low-utilization cards fade, key facts are exempt — forgetting is rule-driven, explainable, traceable, recoverable.

**Memory-tree shape**: memory is not a flat list but a tree growing over time — **branches = event chains (topic evolution), leaves = event cards (what happened)**; when a branch ends it produces a "fruit summary" as a navigation landmark; version evolution uses `supersedes` temporal chains (old facts invalidated but kept for audit); every card carries provenance (source file / turn / evidence tag / corroboration count) — **each memory can be traced back to the original conversation**.

**Memory vs knowledge separation**: `memory-tree` (about *you* — experiences) and `memory-wiki` (about *the world* — norms) are two separate stores; knowledge entries never enter the memory tree, so profile and experience aren't polluted.

---

## Key decisions

| Decision | Choice | Rationale (rejected alternative) |
|---|---|---|
| Memory storage | Markdown source of truth + SQLite index | Pure DB is unreadable/not manually checkable; pure files are slow to search. Dual write balances transparency and speed |
| Retrieval algorithm | BM25 + RRF (jieba tokenization + FTS5) | Vector DB requires a resident model, non-reproducible results, external dependency; word-level relevance ranking + multi-hop expansion suffices for memory and is auditable |
| Write pipeline | LLM extraction + zero-LLM rules (dual channel) | LLM-only extraction is slow and costly; the rule channel makes "记住/踩坑/preferences" land instantly |
| Read injection | Pull retrieval + resident baseline, tiered & capped | Full-history injection pollutes context and dilutes attention |
| Truth adjudication | LLM outputs only "evidence tags"; the system computes confidence and gates admission | Model self-assessment as fact source amplifies hallucination; directive/explicit auto-commit, uncertain forces human review |
| Chain attribution | Deterministic (`resolve_chain`, alias/similarity/entity disambiguation) | Hashing the LLM title directly would silently split into "same-name fake chains" under wording drift |
| Conversation safety net | Raw conversation lands in the `runs` table first, idempotent state machine | Extraction failure/disable never deletes the original — if the memory pipeline fails, raw material is always there |
| Process model | host JS + Python sidecar (process isolation) | Mature engine ecosystem; a sidecar crash only affects memory, not the harness |
| Python deps | Declarative (`install-deps.ps1`), not bundled, no silent install | Silent pip install = running arbitrary code on the user's machine |
| Secrets | `apiKeyEnv` env var preferred, plaintext fallback for compatibility | Plaintext keys must not land in the repo; `.gitignore` excludes `config.json` |

---

## Key engineering implementation

### Architecture

```
DeepSeek Harness (host plugin process)
├── lib/index.js                host: spawns sidecar, HTTP routes, agent tools,
│                               event hooks (auto-extract / zero-LLM recorder / inject / audit loop)
├── python/memory_bridge_server.py  sidecar: JSON-RPC over HTTP (127.0.0.1 random port),
│                                   hosts the engine, decay governance, profile distillation
├── engine/                     memory-tree engine source (core/ + memory/, declarative deps)
└── client/client.js            Settings UI (7 tabs, browser talks to the host proxy)
```

### Storage: plain-text source + idempotent writes

- Card = Markdown file (front-matter metadata + body), directories by type (`events/cards`, `events/chains`, `lessons/pending`, `lessons/permanent`, `profiles`)
- All writes idempotent (same-id overwrite / `INSERT OR IGNORE`), crash-recovery reconciliation (`extracting` rolled back to `staged`)
- Provenance fields throughout: `source_path` (file), `trace_event_id` (turn), `evidence` (tag), `corroborations` (count)

### Write pipeline (dual channel)

1. **LLM extraction** (auto on turn/end): incrementally scan this turn's user+assistant text → enqueue into `runs` → gate `should_extract` (zero-LLM; chit-chat turns marked `skipped` to save calls) → LLM extraction → events/lessons/knowledge routed and stored → chain attribution → conflict resolution → backoff on failure. JSON output has truncation tolerance (fix quotes/commas/closing brackets); **truncation downgrade** (v0.3 rescue): `finish_reason=length` or JSON needing structural repair forces `evidence=uncertain` on that batch → cards become `lesson_pending` / wiki entries `pending` (review), truncated content never auto-solidifies (previously the repairer masked incomplete content); single-card `max_tokens` raised 1024 → 2048.
2. **Zero-LLM rule recorder** (instant on user/message, pure rules, doesn't steal TTFT):
   - "记住教训/踩坑/经验教训" → **lesson_permanent immediately** (permanent lesson)
   - "记住/记下/别忘了" → event card immediately
   - "我喜欢/习惯/别用" → preference signal ledger → aggregate ≥3 of the same topic → lesson_pending proposal

### Read pipeline (injection + audit loop)

- **user/message prefetch**: intent tiers (L2 ≤3 / L1 ≤1 / greetings L0 zero-inject — greetings judged by **whole-utterance approximate match** so real questions containing "好/行/嗯" are not misjudged; 50ms timeout — better none than late) + **fact-card priority** (v0.3 rescue: lessons/permanent/preference cards get a supplementary token-overlap lookup and are injected ahead of event streams, which only fill remaining slots — prevents the multi-column RRF from squeezing zero-usage fact cards out) + **resident baseline snapshot** (approved profile + high-confidence permanent lessons, **relevance gate**: without identity/preference/experience-type words in the query the profile/lessons are not injected, preventing off-topic noise; digest change detection, KV-cache friendly) → cache → injected into system prompt render with provenance text
- **Audit loop**: after turn end, judge whether injected memory was actually used in the reply (rule-based attribution, zero-LLM) → hit rolls / ≥3 consecutive misses fade weight ("not used" ≠ "memory wrong")

### Lifecycle governance (rule-driven, zero-LLM)

- **Decay curve**: 30-day idle branches auto-end, child cards wilt (`status=wilted`, excluded from retrieval but data retained)
- **Global governance**: `inject_used_rate < 0.3` → auto-shrink injection count (3→2→1); actions written to `decision_log` for audit
- **Safety exemption**: lesson_permanent / approved / explicit / directive / corroborated ≥1 cards are exempt from decay

### Profile distillation

- Manual trigger (Profile tab or RPC `distill`): collect event tree → LLM generates profile summary + user personality dimensions (MBTI + 8 axes, profile data not a persona library) → debounce/dedup → draft → **human approval** solidifies (version+1, draft moved to `approved/` to prevent repeat approval) → enters the injection resident baseline
- Profile = user profile info (identity/preferences/collaboration style) as stable model background; **relevance gate** (v0.3 rescue): injected with the resident baseline only when the query contains identity/preference/experience-type words — off-topic and greeting turns carry no profile

### Engineering safeguards

- **Fault isolation**: sidecar crash affects only memory, not the harness; missing jieba returns an actionable install hint instead of crashing
- **Security**: POST strict same-origin check; GET without Origin must carry the local-marker header (blocks cross-site state pollution); RPC param path-traversal whitelist; sidecar listens only on 127.0.0.1; secrets masked on read + `apiKeyEnv` gradual migration
- **Portability**: engine path auto-detection (env → config → auto), same for the Python executable; no Node native deps
- **Testability**: standalone smoke script (spawns the real sidecar), 324 engine unit tests, dedicated JSON-fixer cases
- **Versioning** (since 2026-08-19): every bug fix or feature update bumps the version (semver: fixes = patch, features = minor), committed with the code, tagged `vX.Y.Z` and pushed together; current `v0.1.1`

---

## Features

- **Built for constrained contexts**: local models with 4K-32K windows still get usable long-term memory — inject only the relevant few, don't brute-force a big window (cloud also saves tokens on a 1M window)
- **Local, zero external service**: read path (retrieval/injection/governance) is zero-LLM, zero-vector-DB, zero external dependency; write path can use a local model or cloud API (mode decides)
- **Memory vs knowledge separation**: memory = about *you* (changes, time-bound); knowledge = about *the world* (stable, reusable). **Separate stores so retrieval isn't polluted** — searching norms won't surface private experiences and vice versa; retrieval strategies differ too (memory BM25+RRF, knowledge clause-level inverted index)
- **Tree organization, weak graph**: events aggregate by **chain** (branch = topic evolution, leaf = single event). The tree is **deterministic chain attribution** (`resolve_chain`, title/alias/entity disambiguation); the graph is just a visualization projection of the tree — it doesn't depend on a fragile entity-relationship web
- **Memory "grows"**: event → event chain → lesson → profile distillation path, not log accumulation
- **Dual-channel write**: LLM extraction breadth + rule instant response ("记住教训" lands immediately)
- **Restrained injection**: tiered by intent + resident baseline + audit feedback — controls injection volume, avoids filling the context
- **Visualization**: force-directed Event Graph / Knowledge Graph / Timeline, graph-tree linkage

---

## Known limitations

**Honestly disclosed** (not bugs — design boundaries or unfinished items):

| Item | Status | Note |
|---|---|---|
| Extraction quality depends on the chosen LLM | Design boundary | Write side uses LLM; picking the wrong model (e.g. a reasoner/thinking model) pollutes extraction; the default preset disables thinking, and the docs give a "non-thinking model" selection guide |
| Retrieval is word-level relevance ranking, not semantic association | Design boundary | BM25+RRF ranks by word hits (with along-chain/entity multi-hop expansion); recall under **wording drift** is limited (mitigated by aliases/chain attribution); not suited to "semantic-association" queries |
| Profile distillation is manual-triggered | Not finished | `DistillWorker` (weekly + idle-gate auto scheduling) is implemented but the sidecar doesn't start the background thread; currently click "Distill profile" manually |
| `persona.py` (engine's built-in persona library) | Deliberately not wired | Agent personality is managed by **DSH's own persona plugin / system prompt** (engine README §9.5 exclusion list); this plugin handles memory, not agent persona |
| Preference signals need ≥3 same-topic mentions to propose | Design boundary | Avoids a one-off mention becoming a permanent card; only repeated expression enters pending |
| **Cannot replace full session-history replay** | Design boundary | On resume, DSH replays the entire history into context; plugin injection **adds to** the history and **cannot replace or suppress it** (history is fully derived by dsh-session `deriveMessages`; the plugin has no trimming API). In-session history slimming relies on DSH compaction |
| Small local-model edge cases | Design boundary | 4B-class local models fluctuate on spec-clause/alias edge cases; cloud is fully green; low confidence goes to pending human review |

### Language note (currently Chinese-first)

**The plugin is currently optimized for Chinese.** The following parts depend heavily on Chinese; English users would need to adapt them:

| Part | Where Chinese is used | What English users would change |
|---|---|---|
| **Zero-LLM rule triggers** | `rules.py` (记住/记下/记住教训/踩坑/我喜欢/习惯/别用 etc.) + `guard.py` (_DIRECTIVE / _FACT_HINTS / _CHIT_CHAT) | **Append English triggers** to the tuples (remember / lesson learned / I like / don't use / today / project / thanks) — pure data change, logic untouched |
| **LLM extraction prompts** | `extract.py` `_EXTRACT_PROMPT` / `_EXTRACT_PROMPT_SMALL` (Chinese extraction instructions + examples) | Write an **English prompt variant** and measure extraction quality (the prompt is the quality gate; do not just translate) |
| **Profile distillation prompt** | `distill.py` `DISTILL_PROMPT` (Chinese) | Same, English variant |
| **UI strings** | `client/client.js`, 141 Chinese UI strings (tab names / labels / hints) | Replace with English, or bilingual |
| **Agent tool descriptions** | `lib/index.js`, 3 tool `description` fields (model-visible) | English helps the model understand tool purpose |

> **Note**: for bilingual coexistence with automatic prompt selection by conversation language, a **language-detection step** would need to be added (not implemented; the extraction prompt is fixed to Chinese). Without it the plugin still works — English content is extracted by the Chinese prompt (LLMs understand Chinese instructions) — but English users should evaluate whether extraction quality is acceptable.

---

## Installation

### Supported versions

| Dependency | Version | Basis |
|---|---|---|
| DeepSeek Harness | **0.1.0-rc.7+** | Plugin depends on `@deepseek-ai/dsh-tools@^0.1.0-rc.7`; the 5 injected client services (connection/runtime/locale/ui-settings/ui-theme) are verified working on rc.7 |
| Python | 3.10+ | sidecar uses `X \| Y` type syntax (3.10+) |
| Node native deps | none | pure-JS host + Python sidecar |

> Note: pre-rc.7 versions are unverified (the settings mount mechanism changed in rc.7); rc.7 or later is recommended.

```bat
:: 1) Install from GitHub
dsh plugin --profile web add github:<owner>/dsh-memory-bridge

:: 2) Install Python deps (jieba tokenization, declarative; Tsinghua mirror, falls back to Aliyun)
pwsh <your-plugin-dir>/engine/install-deps.ps1
```

Restart the harness to activate. Uninstall: `dsh plugin --profile web remove dsh-memory-bridge`

> Carries the `dsh-plugin` / `dsh-category-memory` topics — discoverable and one-click installable under the memory category in **DSH Settings → Plugins → Marketplace**.

> Dependency policy: jieba is declarative — not bundled, no silent pip install at install time; when missing, the sidecar returns an actionable hint instead of crashing the harness.

---

## Configuration (Settings → Memory → Extraction config)

| Item | Meaning |
|---|---|
| mode | `off` rules-only / `local` local model / `cloud` cloud memory API / `main` main-chat-model fallback / `hybrid` local-first·cloud-fallback |
| local.preset | `qwen3-it-4b-flm` (recommended, thinking off) or `custom` (fill baseUrl/model/apiKey/apiKeyEnv) |
| cloud.* | Cloud memory API (baseUrl / model / apiKey / apiKeyEnv / batchSize / maxCallsPerMinute) |
| sanitize | Pre-extraction sanitization (phone/email/ID/secrets), on by default for cloud |

- **Model selection**: **non-thinking models** are most stable for extraction/injection (reasoning chains pollute JSON extraction); the default preset disables thinking; for `custom` pick an instruct variant; for cloud use `deepseek-chat`, not `deepseek-reasoner`
- **API key**: `apiKeyEnv` env var preferred, plaintext fallback; masked on read-back; config validated before saving

---

## UI (Settings → Memory)

| Tab | Content |
|---|---|
| Overview | stats / status / audit summary / recent activity |
| Event Graph | force-directed graph + memory-tree nav linkage, isolated-node/entity toggles, directional arrow flows |
| Knowledge Graph | wiki-entry force graph (parent/version relations) + search + list |
| Timeline | event stream grouped by day (today/yesterday/2-6 days ago), descending |
| Review | extraction queue / pending lesson approval |
| Profile | approved profile + "Distill profile" + draft approve/reject |
| Audit | injection/extraction stats + "Maintain now" + decision log |

## Screenshots

| | |
|---|---|
| **Overview**: stat cards / memory composition / local inference status / extraction-injection audit / config form | **Event Graph**: force-directed graph + memory-tree linked nav |
| ![Overview](docs/screenshots/overview.png) | ![Event Graph](docs/screenshots/event-graph.png) |
| **Audit**: injection/extraction stats + manual maintenance + decision log | |
| ![Audit](docs/screenshots/audit.png) | |

---

## Agent tools

| Tool | Purpose |
|---|---|
| `memory_search` | Deterministic-algorithm retrieval of memory cards (BM25+RRF, zero-LLM), returns chain context and feedback hints |
| `memory_add_run` | Agent actively writes the current turn into the run queue (tier selectable) |
| `memory_review` | View the pending extraction queue / a specific run's status |

---

## HTTP API

- `GET`: `overview` `health` `search?q=` `browse?kind=` `card?id=` `review?runId=` `wiki?q=` `config` `lemonade-status` `audit` `graph` `profile-status` (needs `x-dsh-memory: 1` header or same-origin)
- `POST`: `card-action` `add-run` `config` `lemonade-ensure` `extract` `maintenance` `distill` `distill-approve` `distill-reject` (same-origin check)
- `inject` / `recordUsage` / `recorder` are not HTTP routes: the host calls the sidecar directly inside event hooks

---

## Development & testing

```bat
REM Run the sidecar standalone (outside the harness)
python -u <plugin-dir>\python\memory_bridge_server.py --root <engine-dir> --config <plugin-dir>\config.example.json

REM Smoke test (bundled engine missing jieba → actionable hint; local engine → full function)
python smoke_sidecar.py

REM Engine unit tests (324)
python -m pytest <engine-dir>\tests -q
```
