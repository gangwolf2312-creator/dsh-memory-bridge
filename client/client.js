window.__ModuleLoader__.load({ id: "dsh-memory-bridge", factory: (require) => {

var module = { exports: {} };
var exports = module.exports;

var React = require("react");

var h = React.createElement;
var useState = React.useState, useEffect = React.useEffect, useCallback = React.useCallback, useMemo = React.useMemo, useRef = React.useRef;

var CSS = [
	"#dmb-root, #dmb-root * { box-sizing: border-box; }",
	"#dmb-root { --dmb-brand: var(--dsw-alias-brand-primary, #3964fe); --dmb-brand-hover: var(--dsw-alias-button-primary-hover, #2f55e0); --dmb-text: var(--dsw-alias-label-primary, #17181c); --dmb-text2: var(--dsw-alias-label-secondary, #555a63); --dmb-text3: var(--dsw-alias-label-tertiary, #838a94); --dmb-border: var(--dsw-alias-border-l1, rgba(0,0,0,0.07)); --dmb-border2: var(--dsw-alias-border-l2, rgba(0,0,0,0.13)); --dmb-card: var(--dsw-alias-bg-layer-1, #ffffff); --dmb-card2: var(--dsw-alias-bg-layer-2, #f7f8fa); --dmb-hover: var(--dsw-alias-interactive-bg-hover, rgba(0,0,0,0.05)); --dmb-active: var(--dsw-alias-interactive-bg-active, rgba(0,0,0,0.08)); --dmb-ok: var(--dsw-alias-state-success-primary, #17a34a); --dmb-warn: var(--dsw-alias-state-warn-primary, #d97706); --dmb-err: var(--dsw-alias-state-error-primary, #dc2626); --dmb-accent: var(--dsw-alias-state-business-primary, #3b82f6); --dmb-accent2: var(--dsw-alias-state-business-tertiary, #7c5cf0); --dmb-radius: 12px; font-family: var(--dsw-font-family, -apple-system, BlinkMacSystemFont, \"Segoe UI\", \"PingFang SC\", \"Microsoft YaHei\", sans-serif); color: var(--dmb-text); font-size: 13px; line-height: 1.5; height: 100%; min-height: 0; display: flex; flex-direction: column; background: transparent; overflow: hidden; }",
	"@keyframes dmb-fadeUp { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: translateY(0); } }",
	"@keyframes dmb-pulse { 0%,100% { box-shadow: 0 0 0 0 color-mix(in srgb, var(--dmb-ok) 45%, transparent); } 50% { box-shadow: 0 0 0 5px transparent; } }",
	"@keyframes dmb-pulse-warn { 0%,100% { box-shadow: 0 0 0 0 color-mix(in srgb, var(--dmb-warn) 45%, transparent); } 50% { box-shadow: 0 0 0 5px transparent; } }",
	"@keyframes dmb-pulse-err { 0%,100% { box-shadow: 0 0 0 0 color-mix(in srgb, var(--dmb-err) 45%, transparent); } 50% { box-shadow: 0 0 0 5px transparent; } }",
	"@keyframes dmb-spin { to { transform: rotate(360deg); } }",
	"@keyframes dmb-grow { from { width: 0; } }",
	"@keyframes dmb-pop { from { opacity: 0; transform: scale(0.9); } to { opacity: 1; transform: scale(1); } }",
	".dmb-header { display: flex; align-items: center; gap: 10px; padding: 14px 18px 12px; border-bottom: 1px solid var(--dmb-border); flex-wrap: wrap; }",
	".dmb-logo { width: 26px; height: 26px; border-radius: 7px; background: var(--dmb-brand); color: #fff; display: flex; align-items: center; justify-content: center; font-size: 13px; flex: none; }",
	".dmb-title { font-size: 14px; font-weight: 600; letter-spacing: 0.1px; }",
	".dmb-subtitle { font-size: 12px; color: var(--dmb-text3); margin-top: 1px; }",
	".dmb-pills { margin-left: auto; display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }",
	".dmb-pill { display: inline-flex; align-items: center; gap: 5px; height: 24px; padding: 0 9px; border-radius: 999px; border: 1px solid var(--dmb-border2); background: var(--dmb-card); color: var(--dmb-text3); font-size: 11px; font-weight: 500; white-space: nowrap; }",
	".dmb-pill b { color: var(--dmb-text2); font-weight: 600; }",
	".dmb-dot { width: 7px; height: 7px; border-radius: 50%; flex: none; }",
	".dmb-dot.ok { background: var(--dmb-ok); animation: dmb-pulse 2.4s ease infinite; }",
	".dmb-dot.warn { background: var(--dmb-warn); animation: dmb-pulse-warn 2.4s ease infinite; }",
	".dmb-dot.err { background: var(--dmb-err); animation: dmb-pulse-err 2.4s ease infinite; }",
	".dmb-dot.idle { background: var(--dmb-text3); }",
	".dmb-tabs { display: flex; gap: 2px; padding: 0 18px; border-bottom: 1px solid var(--dmb-border); overflow-x: auto; scrollbar-width: none; }",
	".dmb-tab { position: relative; padding: 9px 12px; border: 0; background: transparent; color: var(--dmb-text3); font-size: 13px; font-weight: 500; cursor: pointer; white-space: nowrap; border-radius: 8px 8px 0 0; transition: color 0.15s ease, background 0.15s ease; }",
	".dmb-tab:hover { color: var(--dmb-text2); background: var(--dmb-hover); }",
	".dmb-tab.active { color: var(--dmb-text); font-weight: 600; }",
	".dmb-tab.active::after { content: ''; position: absolute; left: 10px; right: 10px; bottom: -1px; height: 2px; border-radius: 2px; background: var(--dmb-brand); }",
	".dmb-tab .dmb-badge { margin-left: 6px; padding: 0 6px; border-radius: 999px; background: color-mix(in srgb, var(--dmb-warn) 16%, transparent); color: var(--dmb-warn); font-size: 10px; font-weight: 700; }",
	".dmb-body { flex: 1; min-height: 0; overflow-y: auto; padding: 16px 18px 24px; scrollbar-width: thin; scrollbar-color: var(--dsh-scrollbar-thumb, rgba(0,0,0,0.18)) transparent; }",
	".dmb-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(148px, 1fr)); gap: 10px; margin-bottom: 14px; }",
	".dmb-stat { position: relative; overflow: hidden; padding: 12px 14px; border-radius: var(--dmb-radius); background: var(--dmb-card); border: 1px solid var(--dmb-border); transition: border-color 0.15s ease, background 0.15s ease; animation: dmb-fadeUp 0.35s ease both; }",
	".dmb-stat:hover { border-color: var(--dmb-border2); background: var(--dmb-hover); }",
	".dmb-stat .accent { position: absolute; left: 0; top: 0; bottom: 0; width: 3px; border-radius: 0 3px 3px 0; }",
	".dmb-stat .label { color: var(--dmb-text3); font-size: 11px; font-weight: 600; letter-spacing: 0.3px; }",
	".dmb-stat .value { font-size: 22px; font-weight: 700; margin-top: 2px; letter-spacing: 0.2px; }",
	".dmb-stat .sub { color: var(--dmb-text3); font-size: 11px; margin-top: 2px; }",
	".dmb-card { border-radius: var(--dmb-radius); background: var(--dmb-card); border: 1px solid var(--dmb-border); padding: 14px 16px; margin-bottom: 12px; }",
	".dmb-card h3 { margin: 0 0 12px; font-size: 13px; font-weight: 600; color: var(--dmb-text); display: flex; align-items: center; gap: 8px; }",
	".dmb-card h3 .ico { font-size: 13px; }",
	".dmb-row { display: flex; align-items: center; gap: 10px; padding: 8px 2px; border-bottom: 1px solid var(--dmb-border); }",
	".dmb-row:last-child { border-bottom: 0; }",
	".dmb-row .grow { flex: 1; min-width: 0; }",
	".dmb-row .k { color: var(--dmb-text2); font-size: 12px; }",
	".dmb-row .v { color: var(--dmb-text); font-weight: 600; font-size: 12.5px; }",
	".dmb-search { position: relative; margin-bottom: 12px; }",
	".dmb-search input { width: 100%; height: 34px; padding: 0 34px 0 34px; border-radius: 9px; border: 1px solid var(--dmb-border2); background: var(--dmb-card2); color: var(--dmb-text); font-size: 13px; outline: none; transition: border-color 0.15s ease, box-shadow 0.15s ease; }",
	".dmb-search input::placeholder { color: var(--dsw-alias-label-dimmed, var(--dmb-text3)); }",
	".dmb-search input:focus { border-color: var(--dmb-brand); box-shadow: 0 0 0 3px color-mix(in srgb, var(--dmb-brand) 16%, transparent); }",
	".dmb-search .mag { position: absolute; left: 11px; top: 50%; transform: translateY(-50%); color: var(--dmb-text3); font-size: 14px; pointer-events: none; }",
	".dmb-search .clear { position: absolute; right: 8px; top: 50%; transform: translateY(-50%); border: 0; background: transparent; color: var(--dmb-text3); cursor: pointer; font-size: 13px; padding: 2px 5px; border-radius: 6px; }",
	".dmb-search .clear:hover { color: var(--dmb-text2); background: var(--dmb-hover); }",
	".dmb-result { padding: 11px 12px; border-radius: 10px; background: var(--dmb-card); border: 1px solid var(--dmb-border); margin-bottom: 8px; cursor: pointer; transition: border-color 0.15s ease, background 0.15s ease; animation: dmb-fadeUp 0.3s ease both; }",
	".dmb-result:hover { border-color: var(--dmb-border2); background: var(--dmb-hover); }",
	".dmb-result .top { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }",
	".dmb-result .t { font-weight: 600; font-size: 13px; }",
	".dmb-result .chain { font-size: 10.5px; color: var(--dmb-accent); background: color-mix(in srgb, var(--dmb-accent) 12%, transparent); padding: 1px 7px; border-radius: 999px; }",
	".dmb-result .scorebar { height: 3px; border-radius: 3px; background: var(--dmb-border); margin-top: 8px; overflow: hidden; }",
	".dmb-result .scorebar i { display: block; height: 100%; border-radius: 3px; background: var(--dmb-accent); animation: dmb-grow 0.6s ease both; }",
	".dmb-result .snip { color: var(--dmb-text2); font-size: 12px; margin-top: 6px; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }",
	".dmb-result .meta { color: var(--dmb-text3); font-size: 11px; margin-top: 5px; display: flex; gap: 10px; flex-wrap: wrap; }",
	".dmb-kind { font-size: 10px; font-weight: 600; padding: 1px 7px; border-radius: 999px; letter-spacing: 0.2px; }",
	".dmb-kind.event { background: color-mix(in srgb, var(--dmb-accent) 12%, transparent); color: var(--dmb-accent); }",
	".dmb-kind.chain { background: color-mix(in srgb, var(--dmb-accent2) 14%, transparent); color: var(--dmb-accent2); }",
	".dmb-kind.lesson_pending { background: color-mix(in srgb, var(--dmb-warn) 14%, transparent); color: var(--dmb-warn); }",
	".dmb-kind.lesson_permanent { background: color-mix(in srgb, var(--dmb-ok) 12%, transparent); color: var(--dmb-ok); }",
	".dmb-kind.profile { background: color-mix(in srgb, var(--dmb-brand) 12%, transparent); color: var(--dmb-brand); }",
	".dmb-kind.spec, .dmb-kind.concept, .dmb-kind.tutorial { background: var(--dmb-hover); color: var(--dmb-text2); }",
	".dmb-btn { display: inline-flex; align-items: center; gap: 6px; height: 30px; padding: 0 12px; border-radius: 8px; border: 1px solid var(--dmb-border2); background: transparent; color: var(--dmb-text); font-size: 12px; font-weight: 500; cursor: pointer; transition: background 0.15s ease, border-color 0.15s ease, color 0.15s ease; }",
	".dmb-btn:hover { background: var(--dmb-hover); }",
	".dmb-btn.primary { background: var(--dsw-alias-button-primary-fill, var(--dmb-brand)); border-color: transparent; color: var(--dsw-alias-label-primary-foreground, #fff); }",
	".dmb-btn.primary:hover { background: var(--dsw-alias-button-primary-hover, var(--dmb-brand-hover)); }",
	".dmb-btn.danger:hover { color: var(--dmb-err); border-color: var(--dmb-err); background: color-mix(in srgb, var(--dmb-err) 8%, transparent); }",
	".dmb-btn:disabled { opacity: 0.5; cursor: not-allowed; }",
	".dmb-field { margin-bottom: 12px; min-width: 0; }",
	".dmb-field label { display: block; font-size: 12px; font-weight: 500; color: var(--dmb-text2); margin-bottom: 6px; }",
	".dmb-field input, .dmb-field select { width: 100%; height: 32px; padding: 0 10px; border-radius: 8px; border: 1px solid var(--dmb-border2); background: var(--dmb-card2); color: var(--dmb-text); font-size: 13px; outline: none; transition: border-color 0.15s ease, box-shadow 0.15s ease; }",
	".dmb-field input::placeholder { color: var(--dsw-alias-label-dimmed, var(--dmb-text3)); }",
	".dmb-field input:focus, .dmb-field select:focus { border-color: var(--dmb-brand); box-shadow: 0 0 0 3px color-mix(in srgb, var(--dmb-brand) 16%, transparent); }",
	".dmb-field .hint { font-size: 11px; color: var(--dmb-text3); margin-top: 4px; }",
	".dmb-switch { position: relative; display: inline-flex; align-items: center; cursor: pointer; gap: 8px; }",
	".dmb-switch input { display: none; }",
	".dmb-switch .track { width: 32px; height: 18px; border-radius: 999px; background: var(--dmb-border2); transition: background 0.15s ease; position: relative; flex: none; }",
	".dmb-switch .track::after { content: ''; position: absolute; top: 2px; left: 2px; width: 14px; height: 14px; border-radius: 50%; background: #fff; box-shadow: 0 1px 2px rgba(0,0,0,0.25); transition: transform 0.15s ease; }",
	".dmb-switch input:checked + .track { background: var(--dmb-brand); }",
	".dmb-switch input:checked + .track::after { transform: translateX(14px); }",
	".dmb-switch .txt { font-size: 12px; color: var(--dmb-text2); }",
	".dmb-chip { display: inline-flex; align-items: center; gap: 6px; height: 28px; padding: 0 12px; border-radius: 8px; border: 1px solid var(--dmb-border2); background: transparent; color: var(--dmb-text2); font-size: 12px; font-weight: 500; cursor: pointer; transition: all 0.15s ease; }",
	".dmb-chip:hover { background: var(--dmb-hover); color: var(--dmb-text); }",
	".dmb-chip.active { background: color-mix(in srgb, var(--dmb-brand) 10%, transparent); border-color: var(--dmb-brand); color: var(--dmb-text); }",
	".dmb-empty { text-align: center; color: var(--dmb-text3); padding: 30px 10px; font-size: 12.5px; }",
	".dmb-spinner { width: 18px; height: 18px; border-radius: 50%; border: 2px solid var(--dmb-border2); border-top-color: var(--dmb-brand); animation: dmb-spin 0.7s linear infinite; margin: 28px auto; }",
	".dmb-toast { position: fixed; right: 18px; bottom: 18px; z-index: 9999; padding: 10px 14px; border-radius: 10px; background: var(--dsw-alias-toast-bg, var(--dmb-card)); border: 1px solid var(--dmb-border); box-shadow: var(--dsw-shadow-lv2, 0 8px 24px rgba(0,0,0,0.12)); color: var(--dmb-text); font-size: 12.5px; font-weight: 500; display: flex; align-items: center; gap: 10px; animation: dmb-fadeUp 0.25s ease; }",
	".dmb-toast.ok { border-color: color-mix(in srgb, var(--dmb-ok) 45%, transparent); } .dmb-toast.err { border-color: color-mix(in srgb, var(--dmb-err) 45%, transparent); }",
	".dmb-detail { position: fixed; inset: 0; z-index: 9980; display: flex; align-items: center; justify-content: center; background: var(--dsw-alias-bg-mask-1, rgba(0,0,0,0.45)); backdrop-filter: var(--dsw-mask-blur, blur(2px)); animation: dmb-pop 0.18s ease; padding: 24px; }",
	".dmb-detail .panel { width: min(560px, 100%); max-height: 80vh; overflow-y: auto; border-radius: 14px; background: var(--dsw-alias-bg-layer-2, var(--dmb-card)); border: 1px solid var(--dmb-border); box-shadow: var(--dsw-shadow-lv3, 0 20px 48px rgba(0,0,0,0.18)); padding: 18px; }",
	".dmb-detail h2 { margin: 0 0 4px; font-size: 15px; }",
	".dmb-detail .raw { white-space: pre-wrap; font-family: var(--ds-font-family-code, ui-monospace, SFMono-Regular, Consolas, monospace); font-size: 11.5px; color: var(--dmb-text2); background: var(--dmb-card2); border: 1px solid var(--dmb-border); border-radius: 9px; padding: 10px; margin-top: 10px; max-height: 240px; overflow-y: auto; }",
	".dmb-tag { display: inline-flex; align-items: center; gap: 5px; padding: 3px 9px; border-radius: 999px; font-size: 11px; font-weight: 500; border: 1px solid var(--dmb-border2); color: var(--dmb-text2); }",
	".dmb-tag b { color: var(--dmb-text); }",
	".dmb-chart-row { display: flex; gap: 12px; align-items: stretch; flex-wrap: wrap; }",
	".dmb-donut-wrap { flex: none; display: flex; align-items: center; gap: 14px; }",
	".dmb-donut-wrap svg { width: min(104px, 30vw); height: auto; }",
	".dmb-legend { display: flex; flex-direction: column; gap: 5px; font-size: 11.5px; }",
	".dmb-legend .it { display: flex; align-items: center; gap: 7px; color: var(--dmb-text2); }",
	".dmb-legend .sw { width: 10px; height: 10px; border-radius: 3px; flex: none; }",
	".dmb-bars { flex: 1; display: flex; flex-direction: column; gap: 8px; justify-content: center; min-width: 180px; }",
	".dmb-bar { display: flex; align-items: center; gap: 8px; }",
	".dmb-bar .nm { width: 72px; color: var(--dmb-text2); font-size: 11px; text-align: right; }",
	".dmb-bar .tr { flex: 1; height: 7px; border-radius: 7px; background: var(--dmb-border); overflow: hidden; }",
	".dmb-bar .fl { height: 100%; border-radius: 7px; animation: dmb-grow 0.7s ease both; }",
	".dmb-bar .vl { width: 38px; color: var(--dmb-text); font-size: 11px; font-weight: 600; }",
	".dmb-actions { display: flex; gap: 8px; margin-top: 12px; flex-wrap: wrap; align-items: center; }",
	".dmb-section-title { font-size: 11px; font-weight: 600; color: var(--dmb-text3); letter-spacing: 0.6px; text-transform: uppercase; margin: 16px 2px 8px; }",
	".dmb-log { font-size: 12px; color: var(--dmb-text2); padding: 8px 2px; border-bottom: 1px solid var(--dmb-border); display: flex; gap: 10px; min-width: 0; }",
	".dmb-log .ts { color: var(--dmb-text3); flex: none; font-variant-numeric: tabular-nums; }",
	".dmb-log .topic { font-weight: 600; color: var(--dmb-accent); flex: none; }",
	".dmb-log .detail { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }",
	".dmb-spark { width: 100%; height: 84px; }",
	".dmb-fade { animation: dmb-fadeUp 0.3s ease both; }",
].join("\n");

var CSS2 = [].join("\n");

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
var KIND_COLOR = { event: "var(--dmb-accent)", chain: "var(--dmb-accent2)", lesson_pending: "var(--dmb-warn)", lesson_permanent: "var(--dmb-ok)", profile: "var(--dmb-brand)" };

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
			h("circle", { cx: 55, cy: 55, r: R, fill: "none", stroke: "var(--dmb-border)", "stroke-width": 13 }),
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
			h(Stat, { accent: "var(--dmb-accent)", label: "事件卡", value: counts.event || 0 }),
			h(Stat, { accent: "var(--dmb-accent2)", label: "事件链", value: counts.chain || 0, delay: 60 }),
			h(Stat, { accent: "var(--dmb-warn)", label: "待审经验", value: counts.lesson_pending || 0, delay: 120 }),
			h(Stat, { accent: "var(--dmb-ok)", label: "沉淀经验", value: counts.lesson_permanent || 0, delay: 180 }),
			h(Stat, { accent: "var(--dmb-brand)", label: "用户画像", value: counts.profile || 0, delay: 240 }),
			h(Stat, { accent: "var(--dmb-text3)", label: "对话 Run", value: runs.total || 0, sub: (runs.staged || 0) + " 待提取", delay: 300 })
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
			h(Stat, { accent: "var(--dmb-accent)", label: "注入命中", value: s.inject_hits || 0 }),
			h(Stat, { accent: "var(--dmb-ok)", label: "注入被用", value: s.inject_used || 0, delay: 60 }),
			h(Stat, { accent: "var(--dmb-warn)", label: "注入未用", value: s.inject_unused || 0, delay: 120 }),
			h(Stat, { accent: "var(--dmb-brand)", label: "注入利用率", value: usedRate, delay: 180 }),
			h(Stat, { accent: "var(--dmb-accent2)", label: "提取 Run", value: s.extract_runs || 0, delay: 240 }),
			h(Stat, { accent: "var(--dmb-text3)", label: "提取跳过", value: s.extract_skips || 0, delay: 300 })
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
	var colors = { inject_hit: "var(--dmb-accent)", inject_used: "var(--dmb-ok)", inject_unused: "var(--dmb-warn)", extract_runs: "var(--dmb-accent2)", extract_skip: "var(--dmb-text3)", lemonade_start: "var(--dmb-warn)", lemonade_load: "var(--dmb-warn)", local_backend_ready: "var(--dmb-ok)" };
	var pts = data.map(function (topic, i) { return { x: pad + (i / Math.max(1, n - 1)) * (W - pad * 2), y: H / 2, color: colors[topic] || "var(--dmb-text3)" }; });
	var line = pts.map(function (p, i) { return (i === 0 ? "M" : "L") + p.x.toFixed(1) + " " + p.y.toFixed(1); }).join(" ");
	return h("svg", { className: "dmb-spark", viewBox: "0 0 " + W + " " + H, preserveAspectRatio: "none" },
		h("path", { d: "M" + pad + " " + (H / 2) + " L" + (W - pad) + " " + (H / 2), stroke: "var(--dmb-border)", "stroke-width": 1 }),
		h("path", { d: line, fill: "none", stroke: "var(--dmb-accent)", "stroke-width": 1.5, "stroke-dasharray": "4 3" }),
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
	var t = ctx.locale.bind("dsh-memory");
	ctx.slots.inject("settings.section", function () {
		return ctx.slots.register({
			name: "settings.section",
			id: "memory",
			order: 30,
			label: function () { return t("nav"); },
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

