window.__ModuleLoader__.load({ id: "dsh-memory-bridge", factory: (require) => {

var module = { exports: {} };
var exports = module.exports;

var React = require("react");

var h = React.createElement;
var useState = React.useState, useEffect = React.useEffect, useCallback = React.useCallback, useMemo = React.useMemo, useRef = React.useRef;

var CSS = [
"#dmb-root, #dmb-root * { box-sizing: border-box; }",
"#dmb-root { --dmb-bg0: #0b1220; --dmb-bg1: #101a30; --dmb-card: rgba(148,163,184,0.08); --dmb-card-solid: #131d33; --dmb-border: rgba(148,163,184,0.16); --dmb-text: #e2e8f0; --dmb-text2: #94a3b8; --dmb-text3: #64748b; --dmb-accent1: #22d3ee; --dmb-accent2: #818cf8; --dmb-accent3: #e879f9; --dmb-ok: #34d399; --dmb-warn: #fbbf24; --dmb-err: #f87171; --dmb-radius: 14px; color: var(--dmb-text); font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; font-size: 13px; line-height: 1.5; height: 100%; overflow: hidden; display: flex; flex-direction: column; }",
"@media (prefers-color-scheme: light) { #dmb-root { --dmb-bg0: #eef2ff; --dmb-bg1: #f8fafc; --dmb-card: rgba(51,65,85,0.06); --dmb-card-solid: #ffffff; --dmb-border: rgba(51,65,85,0.14); --dmb-text: #1e293b; --dmb-text2: #475569; --dmb-text3: #94a3b8; } }",
"#dmb-root { background: linear-gradient(135deg, var(--dmb-bg0) 0%, var(--dmb-bg1) 100%); }",
"@keyframes dmb-fadeUp { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }",
"@keyframes dmb-pulse { 0%,100% { box-shadow: 0 0 0 0 rgba(52,211,153,0.5); } 50% { box-shadow: 0 0 0 6px rgba(52,211,153,0); } }",
"@keyframes dmb-pulse-warn { 0%,100% { box-shadow: 0 0 0 0 rgba(251,191,36,0.5); } 50% { box-shadow: 0 0 0 6px rgba(251,191,36,0); } }",
"@keyframes dmb-pulse-err { 0%,100% { box-shadow: 0 0 0 0 rgba(248,113,113,0.5); } 50% { box-shadow: 0 0 0 6px rgba(248,113,113,0); } }",
"@keyframes dmb-spin { to { transform: rotate(360deg); } }",
"@keyframes dmb-shine { 0% { background-position: 0% 50%; } 50% { background-position: 100% 50%; } 100% { background-position: 0% 50%; } }",
"@keyframes dmb-grow { from { width: 0; } }",
"@keyframes dmb-pop { from { opacity: 0; transform: scale(0.92); } to { opacity: 1; transform: scale(1); } }",
".dmb-header { padding: 18px 22px 14px; background: linear-gradient(120deg, rgba(34,211,238,0.14), rgba(129,140,248,0.14), rgba(232,121,249,0.14)); background-size: 220% 220%; animation: dmb-shine 9s ease infinite; border-bottom: 1px solid var(--dmb-border); display: flex; align-items: center; gap: 14px; }",
".dmb-logo { width: 40px; height: 40px; border-radius: 12px; background: linear-gradient(135deg, var(--dmb-accent1), var(--dmb-accent2), var(--dmb-accent3)); display: flex; align-items: center; justify-content: center; color: #fff; font-size: 20px; box-shadow: 0 6px 18px rgba(129,140,248,0.35); flex: none; }",
".dmb-title { font-size: 16px; font-weight: 700; letter-spacing: 0.2px; }",
".dmb-subtitle { font-size: 11.5px; color: var(--dmb-text2); margin-top: 1px; }",
".dmb-pills { margin-left: auto; display: flex; gap: 8px; align-items: center; }",
".dmb-pill { display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; border-radius: 999px; border: 1px solid var(--dmb-border); background: var(--dmb-card); color: var(--dmb-text2); font-size: 11.5px; font-weight: 600; white-space: nowrap; }",
".dmb-pill b { color: var(--dmb-text); font-weight: 700; }",
".dmb-dot { width: 8px; height: 8px; border-radius: 50%; flex: none; }",
".dmb-dot.ok { background: var(--dmb-ok); animation: dmb-pulse 2.2s ease infinite; }",
".dmb-dot.warn { background: var(--dmb-warn); animation: dmb-pulse-warn 2.2s ease infinite; }",
".dmb-dot.err { background: var(--dmb-err); animation: dmb-pulse-err 2.2s ease infinite; }",
".dmb-dot.idle { background: var(--dmb-text3); }",
".dmb-tabs { display: flex; gap: 4px; padding: 8px 18px 0; background: transparent; border-bottom: 1px solid var(--dmb-border); }",
".dmb-tab { position: relative; padding: 8px 14px; border: 0; background: transparent; color: var(--dmb-text3); font-size: 12.5px; font-weight: 600; cursor: pointer; border-radius: 10px 10px 0 0; transition: color 0.18s ease, background 0.18s ease; }",
".dmb-tab:hover { color: var(--dmb-text); background: var(--dmb-card); }",
".dmb-tab.active { color: var(--dmb-accent1); }",
".dmb-tab.active::after { content: ''; position: absolute; left: 14px; right: 14px; bottom: 0; height: 2.5px; border-radius: 2px; background: linear-gradient(90deg, var(--dmb-accent1), var(--dmb-accent3)); }",
".dmb-tab .dmb-badge { margin-left: 6px; padding: 0 6px; border-radius: 999px; background: rgba(248,113,113,0.16); color: var(--dmb-err); font-size: 10.5px; font-weight: 700; }",
".dmb-body { flex: 1; overflow-y: auto; padding: 16px 18px 22px; }",
".dmb-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin-bottom: 14px; }",
".dmb-stat { position: relative; overflow: hidden; padding: 14px 16px; border-radius: var(--dmb-radius); background: var(--dmb-card); border: 1px solid var(--dmb-border); transition: transform 0.18s ease, box-shadow 0.18s ease; animation: dmb-fadeUp 0.5s ease both; }",
".dmb-stat:hover { transform: translateY(-2px); box-shadow: 0 10px 24px rgba(2,6,23,0.35); }",
".dmb-stat .accent { position: absolute; left: 0; top: 0; bottom: 0; width: 3px; border-radius: 3px; }",
".dmb-stat .label { color: var(--dmb-text2); font-size: 11.5px; font-weight: 600; letter-spacing: 0.4px; text-transform: uppercase; }",
".dmb-stat .value { font-size: 26px; font-weight: 800; margin-top: 4px; letter-spacing: 0.3px; }",
".dmb-stat .sub { color: var(--dmb-text3); font-size: 11px; margin-top: 2px; }",
".dmb-card { border-radius: var(--dmb-radius); background: var(--dmb-card); border: 1px solid var(--dmb-border); padding: 14px 16px; margin-bottom: 12px; animation: dmb-fadeUp 0.45s ease both; }",
".dmb-card h3 { margin: 0 0 10px; font-size: 12.5px; font-weight: 700; color: var(--dmb-text); display: flex; align-items: center; gap: 8px; }",
".dmb-card h3 .ico { font-size: 14px; }",
".dmb-row { display: flex; align-items: center; gap: 10px; padding: 9px 4px; border-bottom: 1px dashed var(--dmb-border); }",
".dmb-row:last-child { border-bottom: 0; }",
".dmb-row .grow { flex: 1; min-width: 0; }",
".dmb-row .k { color: var(--dmb-text2); font-size: 11.5px; }",
".dmb-row .v { color: var(--dmb-text); font-weight: 600; font-size: 12.5px; }",
".dmb-search { position: relative; margin-bottom: 12px; }",
".dmb-search input { width: 100%; padding: 11px 38px 11px 36px; border-radius: 12px; border: 1px solid var(--dmb-border); background: var(--dmb-card-solid); color: var(--dmb-text); font-size: 13px; outline: none; transition: border-color 0.18s ease, box-shadow 0.18s ease; }",
".dmb-search input:focus { border-color: var(--dmb-accent2); box-shadow: 0 0 0 3px rgba(129,140,248,0.18); }",
".dmb-search .mag { position: absolute; left: 12px; top: 50%; transform: translateY(-50%); color: var(--dmb-text3); font-size: 14px; }",
".dmb-search .clear { position: absolute; right: 10px; top: 50%; transform: translateY(-50%); border: 0; background: transparent; color: var(--dmb-text3); cursor: pointer; font-size: 13px; padding: 2px 4px; border-radius: 6px; }",
""
].join("\n");

var CSS2 = [
".dmb-result { padding: 11px 12px; border-radius: 11px; background: var(--dmb-card-solid); border: 1px solid var(--dmb-border); margin-bottom: 8px; cursor: pointer; transition: border-color 0.16s ease, transform 0.16s ease; animation: dmb-fadeUp 0.4s ease both; }",
".dmb-result:hover { border-color: var(--dmb-accent2); transform: translateX(2px); }",
".dmb-result .top { display: flex; align-items: center; gap: 8px; }",
".dmb-result .t { font-weight: 700; font-size: 13px; }",
".dmb-result .chain { font-size: 10.5px; color: var(--dmb-accent1); background: rgba(34,211,238,0.12); padding: 1px 7px; border-radius: 999px; }",
".dmb-result .scorebar { height: 3px; border-radius: 3px; background: rgba(148,163,184,0.15); margin-top: 8px; overflow: hidden; }",
".dmb-result .scorebar i { display: block; height: 100%; border-radius: 3px; background: linear-gradient(90deg, var(--dmb-accent1), var(--dmb-accent3)); animation: dmb-grow 0.7s ease both; }",
".dmb-result .snip { color: var(--dmb-text2); font-size: 11.5px; margin-top: 6px; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }",
".dmb-result .meta { color: var(--dmb-text3); font-size: 10.5px; margin-top: 5px; display: flex; gap: 10px; }",
".dmb-kind { font-size: 10px; font-weight: 700; padding: 1px 7px; border-radius: 999px; letter-spacing: 0.3px; }",
".dmb-kind.event { background: rgba(34,211,238,0.14); color: var(--dmb-accent1); }",
".dmb-kind.chain { background: rgba(232,121,249,0.14); color: var(--dmb-accent3); }",
".dmb-kind.lesson_pending { background: rgba(251,191,36,0.16); color: var(--dmb-warn); }",
".dmb-kind.lesson_permanent { background: rgba(52,211,153,0.14); color: var(--dmb-ok); }",
".dmb-kind.profile { background: rgba(129,140,248,0.16); color: var(--dmb-accent2); }",
".dmb-kind.spec, .dmb-kind.concept, .dmb-kind.tutorial { background: rgba(148,163,184,0.16); color: var(--dmb-text2); }",
".dmb-btn { display: inline-flex; align-items: center; gap: 6px; border: 1px solid var(--dmb-border); background: var(--dmb-card); color: var(--dmb-text); font-size: 12px; font-weight: 600; padding: 6px 12px; border-radius: 9px; cursor: pointer; transition: all 0.16s ease; }",
".dmb-btn:hover { border-color: var(--dmb-accent2); color: var(--dmb-accent1); transform: translateY(-1px); }",
".dmb-btn.primary { background: linear-gradient(135deg, var(--dmb-accent1), var(--dmb-accent2)); border: 0; color: #fff; }",
".dmb-btn.primary:hover { box-shadow: 0 6px 16px rgba(129,140,248,0.4); color: #fff; }",
".dmb-btn.danger:hover { border-color: var(--dmb-err); color: var(--dmb-err); }",
".dmb-btn:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }",
".dmb-field { margin-bottom: 10px; }",
".dmb-field label { display: block; font-size: 11px; font-weight: 600; color: var(--dmb-text2); margin-bottom: 5px; letter-spacing: 0.3px; }",
".dmb-field input, .dmb-field select { width: 100%; padding: 8px 10px; border-radius: 9px; border: 1px solid var(--dmb-border); background: var(--dmb-card-solid); color: var(--dmb-text); font-size: 12.5px; outline: none; }",
".dmb-field input:focus, .dmb-field select:focus { border-color: var(--dmb-accent2); }",
".dmb-field .hint { font-size: 10.5px; color: var(--dmb-text3); margin-top: 3px; }",
".dmb-switch { position: relative; display: inline-flex; align-items: center; cursor: pointer; gap: 8px; }",
".dmb-switch input { display: none; }",
".dmb-switch .track { width: 34px; height: 19px; border-radius: 999px; background: rgba(148,163,184,0.3); transition: background 0.18s ease; position: relative; flex: none; }",
".dmb-switch .track::after { content: ''; position: absolute; top: 2.5px; left: 2.5px; width: 14px; height: 14px; border-radius: 50%; background: #fff; transition: transform 0.18s ease; }",
".dmb-switch input:checked + .track { background: linear-gradient(90deg, var(--dmb-accent1), var(--dmb-accent2)); }",
".dmb-switch input:checked + .track::after { transform: translateX(15px); }",
".dmb-switch .txt { font-size: 12px; color: var(--dmb-text2); }",
".dmb-chip { display: inline-flex; align-items: center; gap: 6px; padding: 5px 12px; border-radius: 999px; border: 1px solid var(--dmb-border); background: var(--dmb-card); color: var(--dmb-text2); font-size: 11.5px; font-weight: 600; cursor: pointer; transition: all 0.16s ease; }",
".dmb-chip:hover { border-color: var(--dmb-accent2); }",
".dmb-chip.active { background: linear-gradient(135deg, rgba(34,211,238,0.22), rgba(129,140,248,0.22)); border-color: var(--dmb-accent2); color: var(--dmb-text); }",
".dmb-empty { text-align: center; color: var(--dmb-text3); padding: 34px 10px; font-size: 12.5px; }",
".dmb-spinner { width: 18px; height: 18px; border-radius: 50%; border: 2.5px solid rgba(148,163,184,0.25); border-top-color: var(--dmb-accent2); animation: dmb-spin 0.8s linear infinite; margin: 26px auto; }",
".dmb-toast { position: fixed; right: 18px; bottom: 18px; z-index: 9999; padding: 11px 16px; border-radius: 12px; background: var(--dmb-card-solid); border: 1px solid var(--dmb-border); box-shadow: 0 12px 32px rgba(2,6,23,0.5); color: var(--dmb-text); font-size: 12.5px; font-weight: 600; display: flex; align-items: center; gap: 10px; animation: dmb-fadeUp 0.3s ease; }",
".dmb-toast.ok { border-color: rgba(52,211,153,0.5); } .dmb-toast.err { border-color: rgba(248,113,113,0.5); }",
".dmb-detail { position: fixed; inset: 0; z-index: 9980; display: flex; align-items: center; justify-content: center; background: rgba(2,6,23,0.6); backdrop-filter: blur(4px); animation: dmb-pop 0.22s ease; }",
".dmb-detail .panel { width: min(560px, 92vw); max-height: 80vh; overflow-y: auto; border-radius: 16px; background: var(--dmb-card-solid); border: 1px solid var(--dmb-border); box-shadow: 0 24px 64px rgba(2,6,23,0.6); padding: 20px; }",
".dmb-detail h2 { margin: 0 0 4px; font-size: 16px; }",
".dmb-detail .raw { white-space: pre-wrap; font-family: 'Cascadia Code', Consolas, monospace; font-size: 11.5px; color: var(--dmb-text2); background: var(--dmb-card); border: 1px solid var(--dmb-border); border-radius: 10px; padding: 10px; margin-top: 10px; max-height: 240px; overflow-y: auto; }",
".dmb-tag { display: inline-flex; align-items: center; gap: 5px; padding: 3px 9px; border-radius: 999px; font-size: 11px; font-weight: 600; border: 1px solid var(--dmb-border); color: var(--dmb-text2); }",
".dmb-tag b { color: var(--dmb-text); }",
".dmb-chart-row { display: flex; gap: 12px; align-items: stretch; }",
".dmb-donut-wrap { flex: none; display: flex; align-items: center; gap: 12px; }",
".dmb-legend { display: flex; flex-direction: column; gap: 5px; font-size: 11.5px; }",
".dmb-legend .it { display: flex; align-items: center; gap: 7px; color: var(--dmb-text2); }",
".dmb-legend .sw { width: 10px; height: 10px; border-radius: 3px; flex: none; }",
".dmb-bars { flex: 1; display: flex; flex-direction: column; gap: 8px; justify-content: center; }",
".dmb-bar { display: flex; align-items: center; gap: 8px; }",
".dmb-bar .nm { width: 76px; color: var(--dmb-text2); font-size: 11px; text-align: right; }",
".dmb-bar .tr { flex: 1; height: 8px; border-radius: 8px; background: rgba(148,163,184,0.14); overflow: hidden; }",
".dmb-bar .fl { height: 100%; border-radius: 8px; animation: dmb-grow 0.8s ease both; }",
".dmb-bar .vl { width: 40px; color: var(--dmb-text); font-size: 11px; font-weight: 700; }",
".dmb-actions { display: flex; gap: 8px; margin-top: 10px; flex-wrap: wrap; }",
".dmb-section-title { font-size: 12px; font-weight: 700; color: var(--dmb-text2); letter-spacing: 0.5px; text-transform: uppercase; margin: 14px 2px 8px; }",
".dmb-log { font-size: 11.5px; color: var(--dmb-text2); padding: 8px 2px; border-bottom: 1px dashed var(--dmb-border); display: flex; gap: 10px; }",
".dmb-log .ts { color: var(--dmb-text3); flex: none; }",
".dmb-log .topic { font-weight: 700; color: var(--dmb-accent2); flex: none; }",
".dmb-log .detail { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }",
".dmb-spark { width: 100%; height: 90px; }",
".dmb-fade { animation: dmb-fadeUp 0.4s ease both; }"
].join("\n");

if (typeof document !== "undefined" && !document.getElementById("dmb-styles")) {
	var style = document.createElement("style");
	style.id = "dmb-styles";
	style.textContent = CSS + "\n" + CSS2;
	document.head.appendChild(style);
}

/* helpers */
var api = {
	get: function (path, params) {
		var q = params ? "?" + Object.keys(params).map(function (k) { return encodeURIComponent(k) + "=" + encodeURIComponent(params[k]); }).join("&") : "";
		return fetch("/dsh-memory/" + path + q, { cache: "no-store" }).then(function (r) { return r.json(); }).then(function (b) { if (!b.ok) throw new Error(b.error || "request failed"); return b.result; });
	},
	post: function (path, body) {
		return fetch("/dsh-memory/" + path, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ params: body || {} }) }).then(function (r) { return r.json(); }).then(function (b) { if (!b.ok) throw new Error(b.error || "request failed"); return b.result; });
	}
};

var KIND_LABEL = { event: "事件", chain: "事件链", lesson_pending: "经验·待审", lesson_permanent: "经验", profile: "画像" };
var KIND_COLOR = { event: "#22d3ee", chain: "#e879f9", lesson_pending: "#fbbf24", lesson_permanent: "#34d399", profile: "#818cf8" };

/* atoms */
function Counter(props) {
	var value = props.value, suffix = props.suffix || "", prefix = props.prefix || "";
	var _s = useState(0), shown = _s[0], setShown = _s[1];
	useEffect(function () {
		var from = 0, to = value || 0, start = performance.now(), dur = 650, raf;
		function tick(now) {
			var p = Math.min(1, (now - start) / dur);
			var eased = 1 - Math.pow(1 - p, 3);
			setShown(Math.round(from + (to - from) * eased));
			if (p < 1) raf = requestAnimationFrame(tick);
		}
		raf = requestAnimationFrame(tick);
		return function () { cancelAnimationFrame(raf); };
	}, [value]);
	return h("span", null, prefix, shown, suffix);
}

function Stat(props) {
	return h("div", { className: "dmb-stat", style: { animationDelay: (props.delay || 0) + "ms" } },
		h("div", { className: "accent", style: { background: props.accent } }),
		h("div", { className: "label" }, props.label),
		h("div", { className: "value", style: { color: props.accent } }, h(Counter, { value: props.value, suffix: props.suffix || "", prefix: props.prefix || "" })),
		props.sub ? h("div", { className: "sub" }, props.sub) : null
	);
}

function Dot(props) {
	return h("span", { className: "dmb-dot " + (props.state || "idle"), title: props.title || "" });
}

function KindBadge(props) {
	return h("span", { className: "dmb-kind " + props.kind }, KIND_LABEL[props.kind] || props.kind);
}

function Spinner() { return h("div", { className: "dmb-spinner" }); }

function Empty(props) { return h("div", { className: "dmb-empty" }, props.children || "暂无数据"); }

function ToastEl(props) {
	if (!props.msg) return null;
	return h("div", { className: "dmb-toast " + (props.type || "ok") }, h(Dot, { state: props.type === "err" ? "err" : "ok" }), props.msg);
}

function useToast() {
	var _s2 = useState(null), toast = _s2[0], setToast = _s2[1];
	var timer = useRef(null);
	var show = useCallback(function (msg, type) {
		setToast({ msg: msg, type: type || "ok" });
		if (timer.current) clearTimeout(timer.current);
		timer.current = setTimeout(function () { setToast(null); }, 3200);
	}, []);
	return { toast: toast, show: show, node: h(ToastEl, { msg: toast && toast.msg, type: toast && toast.type }) };
}

function Donut(props) {
	var data = props.data || [];
	var total = data.reduce(function (s, d) { return s + d.value; }, 0) || 1;
	var R = 44, C = 2 * Math.PI * R, offset = 0;
	return h("div", { className: "dmb-donut-wrap" },
		h("svg", { width: 110, height: 110, viewBox: "0 0 110 110" },
			h("circle", { cx: 55, cy: 55, r: R, fill: "none", stroke: "rgba(148,163,184,0.12)", "stroke-width": 13 }),
			data.map(function (d) {
				var len = (d.value / total) * C;
				var el = h("circle", { key: d.name, cx: 55, cy: 55, r: R, fill: "none", stroke: d.color, "stroke-width": 13,
					"stroke-dasharray": len + " " + (C - len), "stroke-dashoffset": -offset, "stroke-linecap": "round",
					style: { transition: "stroke-dasharray 0.7s ease, stroke-dashoffset 0.7s ease", transform: "rotate(-90deg)", transformOrigin: "center" } });
				offset += len;
				return el;
			}),
			h("text", { x: 55, y: 52, "text-anchor": "middle", fill: "currentColor", "font-size": "18", "font-weight": "800" }, String(total)),
			h("text", { x: 55, y: 70, "text-anchor": "middle", fill: "currentColor", opacity: 0.55, "font-size": "9" }, "记忆卡")
		),
		h("div", { className: "dmb-legend" }, data.map(function (d) {
			return h("div", { key: d.name, className: "it" }, h("span", { className: "sw", style: { background: d.color } }), KIND_LABEL[d.name] || d.name, " · ", d.value);
		}))
	);
}

/* panel */
function MemoryPanel() {
	var _s3 = useState("overview"), tab = _s3[0], setTab = _s3[1];
	var _s4 = useState(null), overview = _s4[0], setOverview = _s4[1];
	var _s5 = useState(true), loading = _s5[0], setLoading = _s5[1];
	var _s6 = useState(0), refreshKey = _s6[0], setRefreshKey = _s6[1];
	var _s7 = useState(0), pendingCount = _s7[0], setPendingCount = _s7[1];

	var refresh = useCallback(function () { setRefreshKey(function (k) { return k + 1; }); }, []);

	useEffect(function () {
		setLoading(true);
		api.get("overview").then(function (data) {
			setOverview(data);
			setPendingCount(data.pendingCount || 0);
		}).catch(function (err) {
			console.error("[dsh-memory] overview failed", err);
			setOverview({ error: String((err && err.message) || err) });
		}).finally(function () { setLoading(false); });
	}, [refreshKey]);

	var lemonade = overview && overview.lemonade;
	var counts = (overview && overview.counts) || {};
	var mode = (overview && overview.config && overview.config.mode) || "main";

	var tabs = [
		{ id: "overview", label: "总览" },
		{ id: "cards", label: "记忆卡" },
		{ id: "wiki", label: "知识库" },
		{ id: "review", label: "待审", badge: pendingCount || undefined },
		{ id: "audit", label: "审计" }
	];

	return h("div", { id: "dmb-root" },
		h("div", { className: "dmb-header" },
			h("div", { className: "dmb-logo" }, "🧠"),
			h("div", null,
				h("div", { className: "dmb-title" }, "记忆树 · Memory Bridge"),
				h("div", { className: "dmb-subtitle" }, overview ? (overview.memoryRoot || "") : "加载中…")
			),
			h("div", { className: "dmb-pills" },
				h("span", { className: "dmb-pill" }, h(Dot, { state: lemonade && lemonade.serverUp ? "ok" : "err" }), "Lemonade ", lemonade && lemonade.serverUp ? "在线" : "离线"),
				h("span", { className: "dmb-pill" }, "模式 ", h("b", null, mode)),
				h("button", { className: "dmb-btn", onClick: refresh, title: "刷新" }, "↻")
			)
		),
		h("div", { className: "dmb-tabs" }, tabs.map(function (t) {
			return h("button", { key: t.id, className: "dmb-tab" + (tab === t.id ? " active" : ""), onClick: function () { setTab(t.id); } },
				t.label, t.badge ? h("span", { className: "dmb-badge" }, t.badge) : null);
		})),
		h("div", { className: "dmb-body" },
			loading && tab === "overview" ? h(Spinner, null) : null,
			tab === "overview" ? h(OverviewTab, { data: overview, refresh: refresh }) : null,
			tab === "cards" ? h(CardsTab, { onPendingChange: setPendingCount }) : null,
			tab === "wiki" ? h(WikiTab, null) : null,
			tab === "review" ? h(ReviewTab, { onPendingChange: setPendingCount }) : null,
			tab === "audit" ? h(AuditTab, null) : null
		)
	);
}

/* overview */
function OverviewTab(props) {
	var data = props.data;
	if (!data) return null;
	if (data.error) return h("div", { className: "dmb-card" }, h("div", { style: { color: "var(--dmb-err)" } }, "加载失败：", data.error));

	var counts = data.counts || {};
	var byStatus = data.byStatus || {};
	var wiki = data.wiki || {};
	var runs = data.runs || {};
	var lemonade = data.lemonade || {};
	var audit = data.audit || {};
	var recent = data.recent || [];
	var donutData = Object.keys(KIND_COLOR).map(function (k) { return { name: k, value: counts[k] || 0, color: KIND_COLOR[k] }; });
	var maxStatus = Math.max(byStatus.active || 0, byStatus.archived || 0, 1);
	var extractMode = (data.config && data.config.mode) || "main";
	var usedRate = audit.inject_used_rate !== undefined ? (audit.inject_used_rate * 100).toFixed(0) + "%" : "—";
	var wikiMax = Math.max(wiki.spec || 0, wiki.concept || 0, 1);

	return h("div", null,
		h("div", { className: "dmb-grid" },
			h(Stat, { accent: "#22d3ee", label: "事件卡", value: counts.event || 0 }),
			h(Stat, { accent: "#e879f9", label: "事件链", value: counts.chain || 0, delay: 60 }),
			h(Stat, { accent: "#fbbf24", label: "待审经验", value: counts.lesson_pending || 0, delay: 120 }),
			h(Stat, { accent: "#34d399", label: "沉淀经验", value: counts.lesson_permanent || 0, delay: 180 }),
			h(Stat, { accent: "#818cf8", label: "用户画像", value: counts.profile || 0, delay: 240 }),
			h(Stat, { accent: "#94a3b8", label: "对话 Run", value: runs.total || 0, sub: (runs.staged || 0) + " 待提取", delay: 300 })
		),
		h("div", { className: "dmb-card", style: { animationDelay: "120ms" } },
			h("h3", null, h("span", { className: "ico" }, "📊"), "记忆构成"),
			h("div", { className: "dmb-chart-row" },
				h(Donut, { data: donutData }),
				h("div", { className: "dmb-bars" },
					h("div", { className: "dmb-bar" }, h("span", { className: "nm" }, "活跃"), h("div", { className: "tr" }, h("div", { className: "fl", style: { width: Math.max(2, ((byStatus.active || 0) / maxStatus) * 100) + "%", background: "linear-gradient(90deg,#22d3ee,#818cf8)" } })), h("span", { className: "vl" }, String(byStatus.active || 0))),
					h("div", { className: "dmb-bar" }, h("span", { className: "nm" }, "已归档"), h("div", { className: "tr" }, h("div", { className: "fl", style: { width: Math.max(2, ((byStatus.archived || 0) / maxStatus) * 100) + "%", background: "linear-gradient(90deg,#64748b,#94a3b8)" } })), h("span", { className: "vl" }, String(byStatus.archived || 0))),
					h("div", { className: "dmb-bar" }, h("span", { className: "nm" }, "规范知识"), h("div", { className: "tr" }, h("div", { className: "fl", style: { width: Math.max(2, ((wiki.spec || 0) / wikiMax) * 100) + "%", background: "linear-gradient(90deg,#e879f9,#818cf8)" } })), h("span", { className: "vl" }, String(wiki.spec || 0))),
					h("div", { className: "dmb-bar" }, h("span", { className: "nm" }, "概念知识"), h("div", { className: "tr" }, h("div", { className: "fl", style: { width: Math.max(2, ((wiki.concept || 0) / wikiMax) * 100) + "%", background: "linear-gradient(90deg,#818cf8,#22d3ee)" } })), h("span", { className: "vl" }, String(wiki.concept || 0)))
				)
			)
		),
		h("div", { className: "dmb-grid", style: { gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))" } },
			h("div", { className: "dmb-card", style: { marginBottom: 0 } },
				h("h3", null, h("span", { className: "ico" }, "🦙"), "本地推理 Lemonade"),
				h("div", { className: "dmb-row" }, h("div", { className: "grow" }, h("div", { className: "k" }, "服务状态")), h("div", null, h("span", { className: "dmb-pill" }, h(Dot, { state: lemonade.serverUp ? "ok" : "err" }), lemonade.serverUp ? "运行中" : "离线"))),
				h("div", { className: "dmb-row" }, h("div", { className: "grow" }, h("div", { className: "k" }, "目标模型加载")), h("div", { className: "v" }, lemonade.modelLoaded ? "✓ 已就绪" : "未加载")),
				h("div", { className: "dmb-row" }, h("div", { className: "grow" }, h("div", { className: "k" }, "已加载模型")), h("div", { className: "v" }, (lemonade.loadedModels || []).join(", ") || "—")),
				h("div", { className: "dmb-row" }, h("div", { className: "grow" }, h("div", { className: "k" }, "版本")), h("div", { className: "v" }, lemonade.version || "—")),
				h("div", { className: "dmb-actions" }, h(LemonadeEnsure, { onDone: props.refresh }))
			),
			h("div", { className: "dmb-card", style: { marginBottom: 0 } },
				h("h3", null, h("span", { className: "ico" }, "🧭"), "提取与注入"),
				h("div", { className: "dmb-row" }, h("div", { className: "grow" }, h("div", { className: "k" }, "提取模式")), h("div", { className: "v" }, extractMode)),
				h("div", { className: "dmb-row" }, h("div", { className: "grow" }, h("div", { className: "k" }, "注入命中")), h("div", { className: "v" }, String(audit.inject_hits || 0))),
				h("div", { className: "dmb-row" }, h("div", { className: "grow" }, h("div", { className: "k" }, "注入利用率")), h("div", { className: "v" }, usedRate)),
				h("div", { className: "dmb-row" }, h("div", { className: "grow" }, h("div", { className: "k" }, "提取 Run / 跳过")), h("div", { className: "v" }, String(audit.extract_runs || 0) + " / " + String(audit.extract_skips || 0))),
				h("div", { className: "dmb-actions" }, h("button", { className: "dmb-btn", onClick: props.refresh }, "↻ 刷新状态"))
			)
		),
		h(ConfigForm, { initial: data.config, onSaved: props.refresh }),
		h("div", { className: "dmb-section-title" }, "最近记忆"),
		recent.length === 0 ? h(Empty, null, "暂无记忆卡——对话结束后提取会自动沉淀") :
			recent.map(function (r, i) {
				return h("div", { key: r.path, className: "dmb-result", style: { animationDelay: (i * 50) + "ms" } },
					h("div", { className: "top" }, h("span", { className: "t" }, r.title), h(KindBadge, { kind: r.kind })),
					h("div", { className: "snip" }, r.snippet || ""));
			})
	);
}

function LemonadeEnsure(props) {
	var _s8 = useState(false), busy = _s8[0], setBusy = _s8[1];
	var toast = useToast();
	var run = function () {
		setBusy(true);
		api.post("lemonade-ensure", {}).then(function (res) {
			toast.show(res.status && res.status.modelLoaded ? "模型就绪 ✓" : "服务已就绪", "ok");
			props.onDone && props.onDone();
		}).catch(function (err) { toast.show("拉起失败：" + ((err && err.message) || err), "err"); }).finally(function () { setBusy(false); });
	};
	return h("span", null,
		h("button", { className: "dmb-btn primary", onClick: run, disabled: busy }, busy ? "拉起中…" : "⚡ 拉起模型"),
		toast.node
	);
}

/* config form */
function ConfigForm(props) {
	var cfg = props.initial;
	var _s9 = useState(null), form = _s9[0], setForm = _s9[1];
	var _s10 = useState(false), saving = _s10[0], setSaving = _s10[1];
	var toast = useToast();

	useEffect(function () { if (cfg) setForm(JSON.parse(JSON.stringify(cfg))); }, [props.initial && props.initial.mode]);

	if (!form) return null;
	var local = form.local || {};
	var cloud = form.cloud || {};

	var set = function (path, value) {
		setForm(function (f) {
			var next = JSON.parse(JSON.stringify(f));
			var parts = path.split(".");
			var o = next;
			for (var i = 0; i < parts.length - 1; i++) { if (!o[parts[i]]) o[parts[i]] = {}; o = o[parts[i]]; }
			o[parts[parts.length - 1]] = value;
			return next;
		});
	};

	var save = function () {
		setSaving(true);
		api.post("config", { config: form }).then(function () {
			toast.show("配置已保存（重启后对提取管线完全生效）", "ok");
			props.onSaved && props.onSaved();
		}).catch(function (err) { toast.show("保存失败：" + ((err && err.message) || err), "err"); }).finally(function () { setSaving(false); });
	};

	var modes = [
		{ id: "off", label: "纯规则", desc: "零 LLM 调用" },
		{ id: "local", label: "本地模型", desc: "Lemonade 自动拉起" },
		{ id: "cloud", label: "云端专用", desc: "独立提取 API" },
		{ id: "main", label: "主对话模型", desc: "复用会话模型" },
		{ id: "hybrid", label: "混合", desc: "本地优先·云端兜底" }
	];

	return h("div", { className: "dmb-card" },
		h("h3", null, h("span", { className: "ico" }, "⚙️"), "提取配置（面板内保存，重启后完全生效）"),
		h("div", { className: "dmb-section-title", style: { marginTop: 4 } }, "模式"),
		h("div", { style: { display: "flex", flexWrap: "wrap", gap: 8 } },
			modes.map(function (m) {
				return h("button", { key: m.id, className: "dmb-chip" + (form.mode === m.id ? " active" : ""), onClick: function () { set("mode", m.id); }, title: m.desc }, m.label);
			})
		),
		form.mode === "local" || form.mode === "hybrid" ? h("div", null,
			h("div", { className: "dmb-section-title" }, "本地轨"),
			h("div", { className: "dmb-grid", style: { gridTemplateColumns: "repeat(auto-fit,minmax(200px,1fr))" } },
				h("div", { className: "dmb-field" }, h("label", null, "预设"), h("select", { value: local.preset, onChange: function (e) { set("local.preset", e.target.value); } }, h("option", { value: "qwen3-it-4b-flm" }, "qwen3-it-4b-flm（推荐）"), h("option", { value: "custom" }, "自定义"))),
				local.preset === "custom" ? h("div", { className: "dmb-field" }, h("label", null, "Base URL"), h("input", { value: local.baseUrl, placeholder: "http://127.0.0.1:xxxx/v1", onChange: function (e) { set("local.baseUrl", e.target.value); } })) : null,
				local.preset === "custom" ? h("div", { className: "dmb-field" }, h("label", null, "模型名"), h("input", { value: local.model, placeholder: "model-name", onChange: function (e) { set("local.model", e.target.value); } })) : null,
				h("div", { className: "dmb-field" }, h("label", { className: "dmb-switch" }, h("input", { type: "checkbox", checked: !!local.autoManage, onChange: function (e) { set("local.autoManage", e.target.checked); } }), h("span", { className: "track" }), h("span", { className: "txt" }, "自动健康检查 + 拉起 Lemonade")))
			),
			h("div", { className: "dmb-field" }, h("label", null, "API Key（本地一般免鉴权）"), h("input", { value: local.apiKey, type: "password", placeholder: "留空", onChange: function (e) { set("local.apiKey", e.target.value); } }))
		) : null,
		form.mode === "cloud" || form.mode === "hybrid" ? h("div", null,
			h("div", { className: "dmb-section-title" }, "云端轨"),
			h("div", { className: "dmb-grid", style: { gridTemplateColumns: "repeat(auto-fit,minmax(200px,1fr))" } },
				h("div", { className: "dmb-field" }, h("label", null, "Base URL"), h("input", { value: cloud.baseUrl, placeholder: "https://api.deepseek.com/v1", onChange: function (e) { set("cloud.baseUrl", e.target.value); } })),
				h("div", { className: "dmb-field" }, h("label", null, "模型名"), h("input", { value: cloud.model, placeholder: "deepseek-chat", onChange: function (e) { set("cloud.model", e.target.value); } })),
				h("div", { className: "dmb-field" }, h("label", null, "API Key（脱敏显示）"), h("input", { value: cloud.apiKey, type: "password", placeholder: "sk-…", onChange: function (e) { set("cloud.apiKey", e.target.value); } })),
				h("div", { className: "dmb-field" }, h("label", null, "批大小"), h("input", { value: cloud.batchSize, type: "number", min: 1, max: 32, onChange: function (e) { set("cloud.batchSize", Number(e.target.value)); } }))
			),
			h("div", { className: "dmb-field" }, h("label", { className: "dmb-switch" }, h("input", { type: "checkbox", checked: !!cloud.sanitize, onChange: function (e) { set("cloud.sanitize", e.target.checked); } }), h("span", { className: "track" }), h("span", { className: "txt" }, "发送前脱敏（密钥/凭证 → 占位符）")))
		) : null,
		h("div", { className: "dmb-actions" },
			h("button", { className: "dmb-btn primary", onClick: save, disabled: saving }, saving ? "保存中…" : "💾 保存配置"),
			h("span", { style: { color: "var(--dmb-text3)", fontSize: "11px", alignSelf: "center" } }, "重启后对提取管线完全生效")
		),
		toast.node
	);
}

/* cards tab */
function CardsTab(props) {
	var _s11 = useState(""), query = _s11[0], setQuery = _s11[1];
	var _s12 = useState(null), data = _s12[0], setData = _s12[1];
	var _s13 = useState(true), loading = _s13[0], setLoading = _s13[1];
	var _s14 = useState(null), detail = _s14[0], setDetail = _s14[1];
	var _s15 = useState("all"), kind = _s15[0], setKind = _s15[1];
	var _s16 = useState(0), version = _s16[0], setVersion = _s16[1];
	var toast = useToast();

	var load = useCallback(function (q, k) {
		setLoading(true);
		if (q && q.trim()) {
			api.get("search", { q: q.trim(), limit: 40 }).then(function (r) {
				setData({ mode: "search", items: (r.results || []).map(function (x) { return { id: x.cardId, title: x.title, snippet: x.snippet, kind: x.kind || "event", score: x.score, chainTitle: x.chainTitle, createdAt: x.createdAt }; }) });
			}).catch(function (e) { toast.show(String((e && e.message) || e), "err"); }).finally(function () { setLoading(false); });
		} else {
			api.get("browse", { kind: k === "all" ? "" : k, limit: 200 }).then(function (r) { setData({ mode: "browse", items: r.cards || [] }); }).catch(function (e) { toast.show(String((e && e.message) || e), "err"); }).finally(function () { setLoading(false); });
		}
	}, [toast]);

	useEffect(function () { load("", kind); }, [version]);

	var open = function (id) {
		api.get("card", { id: id }).then(function (r) { setDetail(r.card); }).catch(function (e) { toast.show(String((e && e.message) || e), "err"); });
	};

	var act = function (id, action) {
		api.post("card-action", { id: id, action: action }).then(function () {
			toast.show(action + " ✓", "ok");
			setDetail(null);
			setVersion(function (v) { return v + 1; });
			props.onPendingChange && props.onPendingChange();
		}).catch(function (e) { toast.show(String((e && e.message) || e), "err"); });
	};

	var filters = [["all", "全部"], ["event", "事件"], ["chain", "事件链"], ["lesson_pending", "待审"], ["lesson_permanent", "经验"], ["profile", "画像"]];

	return h("div", null,
		h("div", { className: "dmb-search" },
			h("span", { className: "mag" }, "🔍"),
			h("input", { placeholder: "搜索记忆：如「上次搬家注意什么」「服务器端口」", value: query, onChange: function (e) { setQuery(e.target.value); }, onKeyDown: function (e) { if (e.key === "Enter") load(query, kind); } }),
			query ? h("button", { className: "clear", onClick: function () { setQuery(""); load("", kind); } }, "✕") : null
		),
		h("div", { style: { display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 12 } },
			filters.map(function (f) {
				return h("button", { key: f[0], className: "dmb-chip" + (kind === f[0] ? " active" : ""), onClick: function () { setKind(f[0]); load(query, f[0]); } }, f[1]);
			})
		),
		loading ? h(Spinner, null) : !data || data.items.length === 0 ? h(Empty, null, "没有匹配的记忆卡") :
			data.items.map(function (item, i) {
				return h("div", { key: item.id, className: "dmb-result", style: { animationDelay: Math.min(i * 40, 300) + "ms" }, onClick: function () { open(item.id); } },
					h("div", { className: "top" }, h("span", { className: "t" }, item.title || item.id), h(KindBadge, { kind: item.kind }), item.chainTitle ? h("span", { className: "chain" }, "⛓ " + item.chainTitle) : null),
					typeof item.score === "number" ? h("div", { className: "scorebar" }, h("i", { style: { width: Math.max(4, Math.min(100, item.score * 100)) + "%" } })) : null,
					item.snippet ? h("div", { className: "snip" }, item.snippet) : null,
					h("div", { className: "meta" }, item.createdAt ? h("span", null, "🕒 " + item.createdAt) : null, item.sourcePath ? h("span", null, "📄 " + item.sourcePath) : null)
				);
			}),
		detail ? h(CardDetail, { card: detail, onClose: function () { setDetail(null); }, onAction: act }) : null,
		toast.node
	);
}

function CardDetail(props) {
	var card = props.card;
	var kind = card.kind || "event";
	var pending = kind === "lesson_pending";
	return h("div", { className: "dmb-detail", onClick: function (e) { if (e.target === e.currentTarget) props.onClose(); } },
		h("div", { className: "panel" },
			h("div", { style: { display: "flex", gap: 8, alignItems: "center" } }, h("span", { style: { fontSize: 15, fontWeight: 800 } }, card.title || card.id), h(KindBadge, { kind: kind })),
			h("div", { style: { display: "flex", gap: 8, flexWrap: "wrap", margin: "10px 0" } },
				h("span", { className: "dmb-tag" }, "置信 ", h("b", null, ((card.confidence || 0) * 100).toFixed(0) + "%")),
				h("span", { className: "dmb-tag" }, "佐证 ", h("b", null, String(card.corroborations || 0))),
				h("span", { className: "dmb-tag" }, "命中 ", h("b", null, String(card.hit_count || 0))),
				h("span", { className: "dmb-tag" }, "证据 ", h("b", null, card.evidence || "—")),
				h("span", { className: "dmb-tag" }, "状态 ", h("b", null, card.status || "active"))
			),
			h("div", { style: { color: "var(--dmb-text2)", fontSize: 12, whiteSpace: "pre-wrap" } }, card.content || ""),
			card.source_path ? h("div", { className: "raw" }, card.source_path) : null,
			h("div", { className: "dmb-actions" },
				pending ? h("button", { className: "dmb-btn primary", onClick: function () { props.onAction(card.id, "approve"); } }, "✓ 采纳") : null,
				pending ? h("button", { className: "dmb-btn danger", onClick: function () { props.onAction(card.id, "archive"); } }, "🗄 归档") : null,
				card.status === "archived" ? h("button", { className: "dmb-btn", onClick: function () { props.onAction(card.id, "restore"); } }, "↩ 恢复") : null,
				h("button", { className: "dmb-btn", onClick: function () { props.onAction(card.id, "archive"); } }, "🗄 归档"),
				h("button", { className: "dmb-btn danger", onClick: function () { props.onAction(card.id, "delete"); } }, "🗑 删除"),
				h("button", { className: "dmb-btn", onClick: props.onClose }, "关闭")
			)
		)
	);
}

/* wiki tab */
function WikiTab() {
	var _s17 = useState(""), query = _s17[0], setQuery = _s17[1];
	var _s18 = useState(null), data = _s18[0], setData = _s18[1];
	var _s19 = useState(false), loading = _s19[0], setLoading = _s19[1];
	var toast = useToast();

	var search = function () {
		if (!query.trim()) return;
		setLoading(true);
		api.get("wiki", { q: query.trim(), limit: 30 }).then(function (r) { setData(r.results || []); }).catch(function (e) { toast.show(String((e && e.message) || e), "err"); }).finally(function () { setLoading(false); });
	};

	return h("div", null,
		h("div", { className: "dmb-search" },
			h("span", { className: "mag" }, "📚"),
			h("input", { placeholder: "搜索知识库：规范、概念、教程", value: query, onChange: function (e) { setQuery(e.target.value); }, onKeyDown: function (e) { if (e.key === "Enter") search(); } }),
			query ? h("button", { className: "clear", onClick: function () { setQuery(""); setData(null); } }, "✕") : null
		),
		loading ? h(Spinner, null) : !data ? h(Empty, null, "输入关键词检索知识库") :
			data.length === 0 ? h(Empty, null, "无命中") :
			data.map(function (r, i) {
				return h("div", { key: r.entryId + r.sectionPath, className: "dmb-result", style: { animationDelay: Math.min(i * 40, 300) + "ms" } },
					h("div", { className: "top" }, h("span", { className: "t" }, r.title), r.specId ? h("span", { className: "chain" }, "📐 " + r.specId) : null),
					h("div", { className: "snip" }, r.snippet || ""),
					h("div", { className: "meta" }, r.sectionPath ? h("span", null, "📍 " + r.sectionPath) : null, h("span", null, "score " + ((r.score || 0)).toFixed(2)))
				);
			}),
		toast.node
	);
}

/* review tab */
function ReviewTab(props) {
	var _s20 = useState(null), data = _s20[0], setData = _s20[1];
	var _s21 = useState(null), pendingLessons = _s21[0], setPendingLessons = _s21[1];
	var _s22 = useState(true), loading = _s22[0], setLoading = _s22[1];
	var _s23 = useState(0), version = _s23[0], setVersion = _s23[1];
	var toast = useToast();

	var load = useCallback(function () {
		setLoading(true);
		Promise.all([
			api.get("review", { limit: 60 }),
			api.get("browse", { kind: "lesson_pending", limit: 100 })
		]).then(function (arr) {
			setData(arr[0]);
			setPendingLessons((arr[1].cards || []));
			props.onPendingChange && props.onPendingChange((arr[1].cards || []).length);
		}).catch(function (e) { toast.show(String((e && e.message) || e), "err"); }).finally(function () { setLoading(false); });
	}, [props]);

	useEffect(function () { load(); }, [version]);

	var act = function (id, action) {
		api.post("card-action", { id: id, action: action }).then(function () {
			toast.show(action + " ✓", "ok");
			setVersion(function (v) { return v + 1; });
		}).catch(function (e) { toast.show(String((e && e.message) || e), "err"); });
	};

	return h("div", null,
		h("div", { className: "dmb-section-title" }, "待审经验（低置信 / 推断）"),
		loading ? h(Spinner, null) : !pendingLessons || pendingLessons.length === 0 ? h(Empty, null, "没有待审经验") :
			pendingLessons.map(function (c, i) {
				return h("div", { key: c.id, className: "dmb-result", style: { animationDelay: Math.min(i * 40, 300) + "ms" } },
					h("div", { className: "top" }, h("span", { className: "t" }, c.title || c.id), h(KindBadge, { kind: "lesson_pending" }), h("span", { className: "dmb-tag" }, "置信 ", h("b", null, ((c.confidence || 0) * 100).toFixed(0) + "%"))),
					h("div", { className: "snip" }, c.content || ""),
					h("div", { className: "dmb-actions" },
						h("button", { className: "dmb-btn primary", onClick: function () { act(c.id, "approve"); } }, "✓ 采纳"),
						h("button", { className: "dmb-btn danger", onClick: function () { act(c.id, "archive"); } }, "🗄 拒绝")
					)
				);
			}),
		h("div", { className: "dmb-section-title", style: { marginTop: 18 } }, "对话 Run（" + ((data && data.staged) || 0) + " 待提取）"),
		loading ? null : !data || data.runs.length === 0 ? h(Empty, null, "暂无对话 Run") :
			data.runs.map(function (r, i) {
				return h("div", { key: r.runId, className: "dmb-log", style: { animationDelay: Math.min(i * 30, 240) + "ms" } },
					h("span", { className: "ts" }, r.ts || "—"),
					h("span", { className: "topic" }, r.status),
					h("span", { className: "detail" }, (r.userText || "").slice(0, 120) || "(空)"),
					h("span", { className: "dmb-tag", style: { flex: "none" } }, r.tier)
				);
			}),
		toast.node
	);
}

/* audit tab */
function AuditTab() {
	var _s24 = useState(null), data = _s24[0], setData = _s24[1];
	var _s25 = useState(true), loading = _s25[0], setLoading = _s25[1];
	var toast = useToast();

	useEffect(function () {
		api.get("audit", {}).then(function (r) { setData(r); }).catch(function (e) { toast.show(String((e && e.message) || e), "err"); }).finally(function () { setLoading(false); });
	}, []);

	if (loading) return h(Spinner, null);
	if (!data) return null;
	var s = data.summary || {};
	var usedRate = s.inject_used_rate !== undefined ? (s.inject_used_rate * 100).toFixed(0) + "%" : "—";
	var sparkData = (data.log || []).slice(-40).map(function (entry) { return entry.topic; });

	return h("div", null,
		h("div", { className: "dmb-grid", style: { gridTemplateColumns: "repeat(auto-fit,minmax(140px,1fr))" } },
			h(Stat, { accent: "#22d3ee", label: "注入命中", value: s.inject_hits || 0 }),
			h(Stat, { accent: "#34d399", label: "注入被用", value: s.inject_used || 0, delay: 60 }),
			h(Stat, { accent: "#fbbf24", label: "注入未用", value: s.inject_unused || 0, delay: 120 }),
			h(Stat, { accent: "#818cf8", label: "注入利用率", value: usedRate, delay: 180 }),
			h(Stat, { accent: "#e879f9", label: "提取 Run", value: s.extract_runs || 0, delay: 240 }),
			h(Stat, { accent: "#94a3b8", label: "提取跳过", value: s.extract_skips || 0, delay: 300 })
		),
		h("div", { className: "dmb-card" },
			h("h3", null, h("span", { className: "ico" }, "📈"), "最近活动轨迹（按事件）"),
			h(Sparks, { data: sparkData }),
			h("div", { style: { color: "var(--dmb-text3)", fontSize: 11, marginTop: 6 } }, "绿=注入被用 · 黄=注入未用 · 蓝=注入命中 · 紫=提取 · 灰=跳过")
		),
		h("div", { className: "dmb-section-title" }, "决策日志（最近 " + (data.log || []).length + " 条）"),
		(data.log || []).length === 0 ? h(Empty, null, "暂无日志") :
			data.log.slice(-80).reverse().map(function (entry, i) {
				return h("div", { key: i, className: "dmb-log", style: { animationDelay: Math.min(i * 20, 200) + "ms" } },
					h("span", { className: "ts" }, entry.ts || ""),
					h("span", { className: "topic" }, entry.topic),
					h("span", { className: "detail" }, entry.detail || "")
				);
			}),
		toast.node
	);
}

function Sparks(props) {
	var data = props.data || [];
	if (data.length < 2) return h("div", { className: "dmb-empty" }, "活动数据不足");
	var W = 560, H = 90, pad = 4, n = data.length;
	var colors = { inject_hit: "#22d3ee", inject_used: "#34d399", inject_unused: "#fbbf24", extract_runs: "#e879f9", extract_skip: "#94a3b8", lemonade_start: "#fbbf24", lemonade_load: "#fbbf24", local_backend_ready: "#34d399" };
	var pts = data.map(function (topic, i) { return { x: pad + (i / Math.max(1, n - 1)) * (W - pad * 2), y: H / 2, color: colors[topic] || "#64748b" }; });
	var line = pts.map(function (p, i) { return (i === 0 ? "M" : "L") + p.x.toFixed(1) + " " + p.y.toFixed(1); }).join(" ");
	return h("svg", { className: "dmb-spark", viewBox: "0 0 " + W + " " + H, preserveAspectRatio: "none" },
		h("path", { d: "M" + pad + " " + (H / 2) + " L" + (W - pad) + " " + (H / 2), stroke: "rgba(148,163,184,0.2)", "stroke-width": 1 }),
		h("path", { d: line, fill: "none", stroke: "rgba(129,140,248,0.5)", "stroke-width": 1.5, "stroke-dasharray": "4 3" }),
		pts.map(function (p, i) { return h("circle", { key: i, cx: p.x, cy: p.y, r: 4, fill: p.color, style: { animation: "dmb-pop 0.3s ease " + (i * 0.04) + "s both" } }); })
	);
}

/* app entry */
var name = "dsh-memory-bridge";
var inject = ["slots", "locale", "theme"];

var zh = { nav: "记忆" };
var en = { nav: "Memory" };

function apply(ctx) {
	ctx.effect(function () {
		ctx.locale.register("dsh-memory", { zh: zh, en: en });
	}, "dsh-memory: dictionaries");
	ctx.slots.inject("settings.section", function () {
		return ctx.slots.register({
			name: "settings.section",
			id: "memory",
			order: 30,
			label: function () { return ctx.locale.t("dsh-memory", "nav"); },
			locale: "dsh-memory"
		}, function () {
			return h(MemoryPanel, null);
		});
	});
}

exports.name = name;
exports.inject = inject;
exports.apply = apply;

module.exports = exports;
return module.exports;
} });

