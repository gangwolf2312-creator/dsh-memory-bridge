/**
 * dsh-memory-bridge host entry: spawns the Memory Tree sidecar, proxies
 * /dsh-memory/* browser requests to it, and registers memory tools for the
 * agent loop.
 */
import { spawn } from "node:child_process";
import { createHash } from "node:crypto";
import { appendFileSync, existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { defineTool } from "@deepseek-ai/dsh-tools";

const __dirname = dirname(fileURLToPath(import.meta.url));
const PLUGIN_ROOT = join(__dirname, "..");
const SIDECAR_SCRIPT = join(PLUGIN_ROOT, "python", "memory_bridge_server.py");
const CONFIG_PATH = join(PLUGIN_ROOT, "config.json");

export const name = "dsh-memory-bridge";

const DEFAULT_OPTIONS = {
	engineRoot: "D:\\dsh\\plugins\\Memory Tree System",
	pythonExe: "D:\\Python312\\python.exe",
	sidecarStartupTimeoutMs: 20000,
};

function resolveOptions(config) {
	const fromEnv = process.env.DSH_MEMORY_BRIDGE_ENGINE_ROOT;
	const engineRoot = fromEnv?.trim()
		|| config?.engineRoot?.trim()
		|| DEFAULT_OPTIONS.engineRoot;
	return {
		...DEFAULT_OPTIONS,
		...(config || {}),
		engineRoot,
	};
}

/** Minimal JSON-RPC client over HTTP for the local sidecar. */
class RpcClient {
	constructor(base) {
		this.base = base;
		this.seq = 0;
	}
	async call(method, params) {
		const res = await fetch(`${this.base}/rpc`, {
			method: "POST",
			headers: { "content-type": "application/json" },
			body: JSON.stringify({ id: ++this.seq, method, params: params || {} }),
		});
		const body = await res.json();
		if (body.ok !== true) throw new Error(body.error || "rpc failed");
		return body.result;
	}
}

function startSidecar(options, logger) {
	const child = spawn(options.pythonExe, [
		"-u", SIDECAR_SCRIPT,
		"--root", options.engineRoot,
		"--config", CONFIG_PATH,
	], {
		stdio: ["ignore", "pipe", "pipe"],
		windowsHide: true,
	});

	let buffer = "";
	let port = null;
	let ready;
	let readyTimer;
	ready = new Promise((resolve, reject) => {
		const onData = (chunk) => {
			buffer += chunk.toString();
			const lines = buffer.split(/\r?\n/);
			buffer = lines.pop() ?? "";
			for (const line of lines) {
				const match = /^DMB_PORT\s+(\d+)$/.exec(line.trim());
				if (match) {
					port = Number(match[1]);
					child.stdout.off("data", onData);
					clearTimeout(readyTimer);
					resolve(port);
					return;
				}
				if (line.trim()) logger?.warn?.("[dsh-memory-bridge] sidecar: " + line.trim());
			}
		};
		child.stdout.on("data", onData);
		child.stderr.on("data", (chunk) => {
			const text = chunk.toString().trim();
			if (text) logger?.warn?.("[dsh-memory-bridge] sidecar stderr: " + text);
		});
		child.once("exit", (code) => {
			clearTimeout(readyTimer);
			reject(new Error(`memory sidecar exited (code ${code})`));
		});
		readyTimer = setTimeout(() => {
			reject(new Error("memory sidecar startup timeout"));
		}, options.sidecarStartupTimeoutMs);
		readyTimer.unref?.();
	});

	let client = null;
	async function call(method, params) {
		if (client === null) {
			const p = await ready;
			client = new RpcClient(`http://127.0.0.1:${p}`);
		}
		return client.call(method, params);
	}
	return {
		call,
		stop() {
			try { child.kill(); } catch { /* already gone */ }
		},
	};
}

/* ------------------------------------------------------------------ HTTP */

function sendJson(response, status, payload) {
	response.writeHead(status, {
		"cache-control": "no-store",
		"content-type": "application/json; charset=utf-8",
	});
	response.end(JSON.stringify(payload));
}

function sameOrigin(request) {
	const origin = request.headers.origin;
	const host = request.headers.host;
	if (origin === undefined || host === undefined) return false;
	try { return new URL(origin).host === host; } catch { return false; }
}

async function readJsonBody(request, maxBytes = 65536) {
	const chunks = [];
	let size = 0;
	for await (const chunk of request) {
		const buffer = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
		size += buffer.length;
		if (size > maxBytes) throw new Error("request body too large");
		chunks.push(buffer);
	}
	return JSON.parse(Buffer.concat(chunks).toString("utf8"));
}

function parseQuery(url) {
	const out = {};
	const search = new URL(url, "http://x").searchParams;
	for (const [key, value] of search.entries()) out[key] = value;
	return out;
}

/** Path segment -> sidecar RPC method for GET routes. */
const GET_METHODS = {
	"health": { method: "health" },
	"overview": { method: "overview" },
	"search": { method: "search", query: "q", limit: "limit" },
	"browse": { method: "browse", kind: "kind", limit: "limit" },
	"card": { method: "card", id: "id" },
	"review": { method: "review", runId: "runId", limit: "limit" },
	"wiki": { method: "wikiSearch", query: "q", limit: "limit" },
	"config": { method: "configGet" },
	"lemonade-status": { method: "lemonadeStatus" },
	"audit": { method: "audit" },
	"graph": { method: "graph" },
};

function mountRoutes(host, sidecar, logger) {
	const disposers = [];
	const getParams = (spec, query) => {
		const params = {};
		for (const [paramName, queryKey] of Object.entries(spec)) {
			const raw = query[queryKey];
			if (raw !== undefined) {
				if (paramName === "limit") params[paramName] = Number(raw);
				else params[paramName] = raw;
			}
		}
		return params;
	};
	const POST_METHODS = {
		"card-action": "cardAction",
		"add-run": "addRun",
		"config": "configSet",
		"lemonade-ensure": "lemonadeEnsure",
		"extract": "extract",
	};
	disposers.push(host.webServer.register({
		kind: "prefix",
		path: "/dsh-memory",
		handler: async (request, response) => {
			const pathname = new URL(request.url || "/", "http://x").pathname;
			const segment = pathname.startsWith("/dsh-memory/") ? pathname.slice("/dsh-memory/".length) : "";
			const isPost = (request.method || "GET") === "POST";
			try {
				if (isPost) {
					if (!sameOrigin(request)) {
						sendJson(response, 403, { ok: false, error: "untrusted origin" });
						return;
					}
					const method = POST_METHODS[segment];
					if (method === undefined) {
						sendJson(response, 404, { ok: false, error: "unknown route" });
						return;
					}
					const body = await readJsonBody(request);
					const result = await sidecar.call(method, body.params || body);
					sendJson(response, 200, { ok: true, result });
					return;
				}
				const spec = GET_METHODS[segment];
				if (spec === undefined) {
					sendJson(response, 404, { ok: false, error: "unknown route" });
					return;
				}
				const params = getParams(spec, parseQuery(request.url));
				const result = await sidecar.call(spec.method, params);
				sendJson(response, 200, { ok: true, result });
			} catch (error) {
				sendJson(response, 500, { ok: false, error: error instanceof Error ? error.message : String(error) });
			}
		},
	}));
	logger?.info?.(`[dsh-memory-bridge] mounted ${Object.keys(GET_METHODS).length + Object.keys(POST_METHODS).length} routes`);
	return () => { for (const dispose of disposers) dispose(); };
}

/* ----------------------------------------------------------------- tools */

function registerTools(ctx, sidecar, logger) {
	ctx.tools.register(defineTool({
		name: "memory_search",
		description: "Search the personal memory tree (BM25 + RRF, deterministic, zero-LLM). Returns ranked memory cards with chain context. Use when the user references past facts, preferences, projects, or your own earlier conclusions.",
		parameters: {
			query: {
				type: "string", required: true,
				description: "Natural-language search query (Chinese supported; relative time like 昨天/上周/最近N天 is auto-resolved).",
			},
			limit: { type: "integer", description: "Max results (default 8)." },
		},
		output: {
			schema: {
				type: "object", additionalProperties: false,
				properties: {
					results: {
						type: "array", required: true,
						items: {
							type: "object", additionalProperties: false,
							properties: {
								cardId: { type: "string", required: true },
								title: { type: "string", required: true },
								snippet: { type: "string", required: true },
								score: { type: "number", required: true },
								chainTitle: { type: "string" },
								createdAt: { type: "string" },
							},
						},
					},
					note: { type: "string" },
				},
			},
		},
		async execute(args, exec) {
			const data = await sidecar.call("search", {
				query: args.query,
				limit: args.limit ?? 8,
				feedback: true,
			});
			return {
				results: data.results || [],
				...(data.feedbackHint ? { note: `detected feedback signal: ${data.feedbackHint}` } : {}),
			};
		},
	}));

	ctx.tools.register(defineTool({
		name: "memory_add_run",
		description: "Explicitly record one conversation turn into the memory run queue (rules/LLM extraction later decides whether it becomes a memory card). Use when the user says to remember something, or when a turn carries durable facts worth persisting.",
		parameters: {
			userText: { type: "string", required: true, description: "The user turn text." },
			replyText: { type: "string", description: "Your reply text." },
			sessionId: { type: "string", description: "Session identifier (defaults to current session)." },
			tier: { type: "string", enum: ["L0", "L1", "L2"], description: "Priority tier (default L0)." },
		},
		output: {
			schema: {
				type: "object", additionalProperties: false,
				properties: { runId: { type: "string", required: true } },
			},
		},
		async execute(args, exec) {
			const data = await sidecar.call("addRun", {
				sessionId: args.sessionId || exec.sessionId || "unknown",
				userText: args.userText,
				replyText: args.replyText || "",
				tier: args.tier || "L0",
			});
			return { runId: data.runId };
		},
	}));

	ctx.tools.register(defineTool({
		name: "memory_review",
		description: "List pending memory runs (staged conversations awaiting extraction) or inspect a specific run. Use to check what the memory system is about to extract, or to audit the extraction queue.",
		parameters: {
			runId: { type: "string", description: "Optional specific run id." },
			limit: { type: "integer", description: "Max runs (default 20)." },
		},
		output: {
			schema: {
				type: "object", additionalProperties: false,
				properties: {
					runs: {
						type: "array", required: true,
						items: {
							type: "object", additionalProperties: false,
							properties: {
								runId: { type: "string", required: true },
								userText: { type: "string", required: true },
								replyText: { type: "string", required: true },
								tier: { type: "string", required: true },
								status: { type: "string", required: true },
								ts: { type: "string" },
							},
						},
					},
					staged: { type: "integer" },
				},
			},
		},
		async execute(args) {
			return sidecar.call("review", {
				runId: args.runId || null,
				limit: args.limit ?? 20,
			});
		},
	}));

	logger?.info?.("[dsh-memory-bridge] tools registered: memory_search / memory_add_run / memory_review");
}

/* ------------------------------------------------------------ auto-extract */

/** 从消息载荷提取纯文本（user/message 的 data 即 UserMessage；assistant/message 需取 .message）。 */
function textOf(message) {
	if (!message || !Array.isArray(message.content)) return "";
	return message.content
		.filter((block) => block && block.type === "text" && typeof block.text === "string")
		.map((block) => block.text)
		.join("")
		.trim();
}

/**
 * Auto memory pipeline: after each completed conversation turn, stage the
 * turn's direct human prompt + final assistant text as a run, then ask the
 * sidecar to drain the staged queue (cloud/local extractor decides what
 * becomes a card). Subscribes to the harness's live session event stream;
 * replayed seed history never reaches this observer, and the per-session
 * turn watermark dedupes any re-delivered turn/end.
 */
function registerAutoExtract(ctx, sidecar, logger) {
	const lastSeen = new Map();  // sessionId -> {turn, seq}：已处理的 turn/end 水位
	const pending = new Map();   // sessionId -> 入队失败的 stage（稳定 runId 幂等重试）
	const DEBUG_LOG = join(PLUGIN_ROOT, "memory-hook.log");
	const debug = (line) => {
		try {
			appendFileSync(DEBUG_LOG, `[${new Date().toISOString()}] ${line}\n`);
		} catch { /* logging must never break the pipeline */ }
	};

	// 稳定 runId（sessionId|turn 哈希）：addRun 失败重试时 INSERT OR IGNORE 幂等去重
	const runIdFor = (sessionId, turn) =>
		`run-${createHash("sha1").update(`${sessionId}|t${turn}`).digest("hex").slice(0, 12)}`;

	const stageAndExtract = async (sessionId, entry) => {
		try {
			const run = await sidecar.call("addRun", {
				sessionId, runId: entry.runId, userText: entry.userText,
				replyText: entry.replyText, tier: "L0",
			});
			pending.delete(sessionId);
			logger?.info?.(`[dsh-memory-bridge] auto-staged run ${run.runId} (turn ${entry.turn})`);
			debug(`staged ${run.runId} (turn ${entry.turn})`);
			try {
				const res = await sidecar.call("extract", {});
				debug(`extract -> ${JSON.stringify(res)}`);
			} catch (err) {
				logger?.warn?.(`[dsh-memory-bridge] auto-extract failed: ${err.message}`);
				debug(`extract FAILED: ${err.message}`);
			}
		} catch (err) {
			pending.set(sessionId, entry);  // 保留待下轮重试（不丢轮）
			logger?.warn?.(`[dsh-memory-bridge] auto-stage failed (will retry): ${err.message}`);
			debug(`stage FAILED (pending): ${err.message}`);
		}
	};

	const handler = (session, event) => {
		try {
			if (!event || event.type !== "turn/end") return;
			// Session observers receive the envelope {type, seq, time, data};
			// the turn payload lives in event.data.
			const data = event.data || {};
			const reasonKind = data.reason && data.reason.kind;
			if (reasonKind !== "completed" && reasonKind !== "max-tokens") return;
			const sessionId = String(session.id ?? "unknown");
			const turn = data.turn;
			const seq = event.seq;
			const last = lastSeen.get(sessionId);
			if (last && turn <= last.turn) return;
			// 乐观推进水位（重试由 pending + 稳定 runId 兜底，不依赖水位回滚）
			lastSeen.set(sessionId, { turn, seq });

			// 先重试上一轮入队失败项（同轮幂等）
			const prev = pending.get(sessionId);
			if (prev) {
				debug(`retrying pending stage for turn ${prev.turn}`);
				void stageAndExtract(sessionId, prev);
			}

			// 只扫增量（seq > 上次水位），避免跨轮串文本
			let userText = "";
			let replyText = "";
			for (const ev of session.events || []) {
				if (ev.seq <= (last ? last.seq : -1)) continue;
				if (ev.type === "user/message") {
					const msg = ev.data;  // user/message 载荷即 UserMessage 本体
					if (msg && msg.source && msg.source.kind === "user") {
						const t = textOf(msg);
						if (t) userText = t;
					}
				} else if (ev.type === "assistant/message") {
					// assistant/message 载荷是 {turn, step, message, usage?}，
					// 消息本体在 ev.data.message
					const t = textOf(ev.data && ev.data.message);
					if (t) replyText = t;
				}
			}
			if (!userText && !replyText) {
				debug(`turn ${turn} skipped: no text`);
				return;
			}
			debug(`turn ${turn} completed -> staging (user ${userText.length}, reply ${replyText.length})`);
			void stageAndExtract(sessionId, {
				userText, replyText, turn, seq, runId: runIdFor(sessionId, turn),
			});
		} catch (err) {
			logger?.warn?.(`[dsh-memory-bridge] auto-extract hook error: ${err.message}`);
			debug(`hook ERROR: ${err.stack || err.message}`);
		}
	};

	// 经验证（2026-08-18 线上实跑）：session/event 普通作用域注册即可收到事件。
	ctx.on("session/event", handler);
	// 水位/待重试随会话结束清理，避免长期运行无界增长
	ctx.on("session/disposed", (session) => {
		try {
			lastSeen.delete(session.id);
			pending.delete(session.id);
		} catch { /* no-op */ }
	});
	debug("hook registered");
	return () => {
		try { ctx.off("session/event", handler); } catch { /* no-op */ }
	};
}

/* -------------------------------------------------------- memory-inject */

/**
 * 拉式记忆注入（读取端）：user/message 时异步检索相关记忆（sidecar
 * inject → 缓存本会话），system prompt 渲染时同步注入带溯源文本（context
 * 空则自动省略）；turn 结束后回传回复做审计闭环（inject_used）。
 * 实现对齐引擎 MemoryInjector（L2 ≤3 条、50ms 超时宁缺勿滥）。
 */
function registerMemoryInject(ctx, sidecar, logger) {
	const cache = new Map();  // sessionId -> { text, cards }（最近一次注入）
	const DEBUG_LOG = join(PLUGIN_ROOT, "memory-hook.log");
	const debug = (line) => {
		try {
			appendFileSync(DEBUG_LOG, `[${new Date().toISOString()}] ${line}\n`);
		} catch { /* logging must never break the pipeline */ }
	};

	// user/message → 预取检索（缓存，渲染时同步读）
	const onUserMessage = (session, event) => {
		try {
			if (!event || event.type !== "user/message") return;
			const msg = event.data;  // user/message 载荷即 UserMessage 本体
			if (!msg || !msg.source || msg.source.kind !== "user") return;
			const query = textOf(msg);
			if (!query) return;
			const sessionId = String(session.id ?? "unknown");
			void sidecar.call("inject", { sessionId, query: query.slice(0, 2000), tier: "L2" })
				.then((res) => {
					cache.set(sessionId, { text: res.text || "", cards: res.cards || [], at: Date.now() });
					if ((res.cards || []).length) {
						logger?.info?.(`[dsh-memory-bridge] injected ${res.cards.length} memory card(s) for ${sessionId.slice(0, 8)}`);
						debug(`inject ${res.cards.length} cards (${sessionId.slice(0, 8)})`);
					} else {
						debug(`inject 0 cards (${sessionId.slice(0, 8)})`);
					}
				})
				.catch((err) => debug(`inject FAILED: ${err.message}`));
		} catch (err) {
			logger?.warn?.(`[dsh-memory-bridge] memory-inject hook error: ${err.message}`);
		}
	};

	// turn/end → 审计闭环：模型是否利用了注入记忆
	const onTurnEnd = (session, event) => {
		try {
			if (!event || event.type !== "turn/end") return;
			const data = event.data || {};
			const reasonKind = data.reason && data.reason.kind;
			if (reasonKind !== "completed" && reasonKind !== "max-tokens") return;
			const sessionId = String(session.id ?? "unknown");
			const hit = cache.get(sessionId);
			if (!hit || !hit.cards.length) return;
			let replyText = "";
			for (const ev of session.events || []) {
				if (ev.type === "assistant/message") {
					const t = textOf(ev.data && ev.data.message);
					if (t) replyText = t;
				}
			}
			if (!replyText) return;
			void sidecar.call("recordUsage", { sessionId, replyText })
				.then((res) => debug(`recordUsage -> ${JSON.stringify(res.usage || {})}`))
				.catch((err) => debug(`recordUsage FAILED: ${err.message}`));
		} catch (err) { /* no-op */ }
	};

	// 事件预取 + 审计闭环注册（不依赖 systemPrompt，保证不因服务缺失而整体失效）
	ctx.on("session/event", onUserMessage);
	ctx.on("session/event", onTurnEnd);
	ctx.on("session/disposed", (session) => {
		try { cache.delete(session.id); } catch { /* no-op */ }
	});

	// system prompt 动态上下文：每轮渲染时同步返回本会话最近注入文本（空 → 自动省略）。
	// Cordis 服务须经 ctx.inject 声明才能访问（直接 ctx.systemPrompt 抛
	// "cannot get property without inject"）；子作用域 inject 失败只挂起该
	// 回调，不影响插件其余部分（事件预取 + 审计闭环已先注册）。
	let disposeContext = () => {};
	ctx.inject(["systemPrompt"], (spCtx) => {
		try {
			const sp = spCtx.systemPrompt;
			if (sp && typeof sp.context === "function") {
				disposeContext = sp.context({
					name: "memory-inject",
					order: 90,
					text: (context) => {
						try {
							const agent = context && context.agent;
							const sid = agent && agent.session ? String(agent.session.id) : "";
							const hit = sid ? cache.get(sid) : null;
							return hit && hit.text ? hit.text : "";
						} catch { return ""; }
					},
				});
				debug("inject context registered");
			} else {
				debug("inject WARN: systemPrompt unavailable -> rendering injection disabled");
			}
		} catch (err) {
			logger?.warn?.(`[dsh-memory-bridge] systemPrompt.context failed: ${err.message}`);
			debug(`inject context ERROR: ${err.stack || err.message}`);
		}
	});

	debug("inject registered");
	return () => {
		try {
			ctx.off("session/event", onUserMessage);
			ctx.off("session/event", onTurnEnd);
			disposeContext();
		} catch { /* no-op */ }
	};
}

/* ------------------------------------------------------------------ apply */

export function apply(ctx, config) {
	const options = resolveOptions(config);
	ctx.inject(["webServer", "tools"], (host) => {
		host.effect(() => {
			const sidecar = startSidecar(options, host.logger);
			const disposeRoutes = mountRoutes(host, sidecar, host.logger);
			registerTools(host, sidecar, host.logger);
			const disposeAutoExtract = registerAutoExtract(ctx, sidecar, host.logger);
			const disposeMemoryInject = registerMemoryInject(ctx, sidecar, host.logger);
			return () => {
				disposeRoutes();
				disposeAutoExtract();
				disposeMemoryInject();
				sidecar.stop();
			};
		}, "dsh-memory-bridge: sidecar + routes + tools + auto-extract + inject");
	});
}



