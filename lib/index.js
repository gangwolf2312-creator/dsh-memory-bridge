/**
 * dsh-memory-bridge host entry: spawns the Memory Tree sidecar, proxies
 * /dsh-memory/* browser requests to it, and registers memory tools for the
 * agent loop.
 */
import { spawn } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
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

/* ------------------------------------------------------------------ apply */

export function apply(ctx, config) {
	const options = resolveOptions(config);
	ctx.inject(["webServer", "tools"], (host) => {
		host.effect(() => {
			const sidecar = startSidecar(options, host.logger);
			const disposeRoutes = mountRoutes(host, sidecar, host.logger);
			registerTools(host, sidecar, host.logger);
			return () => {
				disposeRoutes();
				sidecar.stop();
			};
		}, "dsh-memory-bridge: sidecar + routes + tools");
	});
}



