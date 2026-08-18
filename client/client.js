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
	".dmb-logo { width: 26px; height: 26px; border-radius: 7px; background: linear-gradient(150deg, #3a3f47 0%, #1b1e23 100%); box-shadow: inset 0 0 0 1px rgba(255,255,255,0.13), 0 1px 3px rgba(0,0,0,0.3); display: flex; align-items: center; justify-content: center; flex: none; }",
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
	".dmb-switch .track { width: 32px; height: 18px; border-radius: 999px; background: color-mix(in srgb, var(--dmb-text3) 40%, transparent); box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--dmb-text3) 20%, transparent); transition: background 0.15s ease, box-shadow 0.15s ease; position: relative; flex: none; }",
	".dmb-switch .track::after { content: ''; position: absolute; top: 2px; left: 2px; width: 14px; height: 14px; border-radius: 50%; background: #fff; box-shadow: 0 1px 3px rgba(0,0,0,0.4), 0 0 0 1px rgba(0,0,0,0.06); transition: transform 0.15s ease; }",
	".dmb-switch input:checked + .track { background: var(--dmb-brand); box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--dmb-brand) 70%, #000); }",
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
	".dmb-ic { display: inline-flex; align-items: center; gap: 5px; }",
	".dmb-ic-line { display: inline-flex; align-items: center; gap: 4px; }",
	".dmb-field label.dmb-switch { display: inline-flex; align-items: center; gap: 8px; position: relative; cursor: pointer; margin-bottom: 6px; }",
	".dmb-result .chain, .dmb-tag { display: inline-flex; align-items: center; gap: 4px; }",
].join("\n");

var CSS2 = [
	/* graph tab (Obsidian 式关系图谱) */
	".dmb-graph-toolbar { display: flex; align-items: center; gap: 12px; padding: 8px 12px; border-bottom: 1px solid var(--dmb-border); flex-wrap: wrap; }",
	".dmb-graph-toolbar .grow { flex: 1; }",
	".dmb-check { display: inline-flex; align-items: center; gap: 6px; font-size: 12px; color: var(--dmb-text2); cursor: pointer; user-select: none; }",
	".dmb-check input { accent-color: var(--dmb-brand); cursor: pointer; }",
	".dmb-graph-wrap { position: relative; border: 1px solid var(--dmb-border); border-radius: var(--dmb-radius); background-image: radial-gradient(circle, rgba(148,163,184,0.2) 1px, transparent 1.3px); background-size: 20px 20px; overflow: hidden; }",
	".dmb-graph-svg { width: 100%; height: 540px; display: block; cursor: grab; touch-action: none; }",
	".dmb-graph-svg.panning { cursor: grabbing; }",
	".dmb-graph-node { cursor: pointer; }",
	".dmb-graph-node circle { transition: r 0.12s ease, opacity 0.18s ease; stroke: var(--dmb-card); stroke-width: 1.5px; filter: drop-shadow(0 1px 2px rgba(0,0,0,0.22)); }",
	".dmb-graph-node:hover circle, .dmb-graph-node.active circle { filter: drop-shadow(0 0 5px rgba(255,255,255,0.5)); }",
	".dmb-graph-node text { font-size: 10.5px; fill: var(--dmb-text3); opacity: 0.82; pointer-events: none; user-select: none; paint-order: stroke; stroke: var(--dmb-card); stroke-width: 2.5px; transition: opacity 0.15s ease; }",
	".dmb-graph-node:hover text, .dmb-graph-node.active text { fill: var(--dmb-text); font-weight: 600; opacity: 1; }",
	".dmb-graph-edge { transition: opacity 0.18s ease; opacity: 0.45; }",
	"@keyframes dmb-dashflow { to { stroke-dashoffset: -36; } }",
	".dmb-graph-edge.lit { stroke-dasharray: 9 7 !important; animation: dmb-dashflow 0.7s linear infinite; stroke-width: 2 !important; opacity: 1 !important; filter: drop-shadow(0 0 5px rgba(96,165,250,0.85)); }",
	".dmb-graph-tip { position: absolute; pointer-events: none; z-index: 30; max-width: 280px; padding: 9px 11px; border-radius: 9px; background: var(--dmb-card); border: 1px solid var(--dmb-border2); box-shadow: 0 10px 28px rgba(0,0,0,0.28); font-size: 12px; color: var(--dmb-text); opacity: 0; transition: opacity 0.12s ease; }",
	".dmb-graph-tip .t { font-weight: 600; margin-bottom: 2px; }",
	".dmb-graph-tip .k { color: var(--dmb-text3); font-size: 10.5px; }",
	".dmb-graph-side { border: 1px solid var(--dmb-border); border-radius: var(--dmb-radius); background: var(--dmb-card); padding: 14px 16px; margin-top: 12px; animation: dmb-fadeUp 0.25s ease both; }",
	".dmb-graph-side h4 { margin: 0 0 10px; font-size: 13px; display: flex; align-items: center; gap: 8px; }",
	".dmb-graph-side .meta { display: grid; grid-template-columns: auto 1fr; gap: 5px 12px; font-size: 12px; }",
	".dmb-graph-side .meta .k { color: var(--dmb-text3); }",
	".dmb-graph-side .meta .v { color: var(--dmb-text2); word-break: break-all; }",
	".dmb-graph-side .neigh { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }",
	".dmb-graph-side .neigh span { font-size: 11px; padding: 2px 9px; border-radius: 999px; background: var(--dmb-hover); color: var(--dmb-text2); cursor: pointer; }",
	".dmb-graph-side .neigh span:hover { color: var(--dmb-text); background: var(--dmb-active); }",
	".dmb-graph-legend { display: flex; gap: 10px; flex-wrap: wrap; font-size: 11px; color: var(--dmb-text3); align-items: center; }",
	".dmb-graph-legend i { display: inline-block; width: 9px; height: 9px; border-radius: 50%; margin-right: 4px; vertical-align: -1px; }",
	".dmb-graph-hint { font-size: 11px; color: var(--dmb-text3); }",
	/* tree tab: 记忆树层级视图 */
	".dmb-tree-wrap { border: 1px solid var(--dmb-border); border-radius: var(--dmb-radius); background: var(--dmb-card); padding: 8px 6px; }",
	".dmb-tree-group { font-size: 11px; font-weight: 600; color: var(--dmb-text3); letter-spacing: 0.6px; text-transform: uppercase; margin: 12px 8px 4px; }",
	".dmb-tree-item { font-size: 12.5px; }",
	".dmb-tree-row { display: flex; align-items: center; gap: 7px; padding: 5px 8px; border-radius: 7px; cursor: pointer; min-width: 0; }",
	".dmb-tree-row:hover { background: var(--dmb-hover); }",
	".dmb-tree-chain > .dmb-tree-row { font-weight: 600; color: var(--dmb-text); }",
	".dmb-tree-leaf.active > .dmb-tree-row { background: color-mix(in srgb, var(--dmb-brand) 12%, transparent); }",
	".dmb-tree-arrow { width: 12px; flex: none; color: var(--dmb-text3); font-size: 9px; transition: transform 0.15s ease; text-align: center; }",
	".dmb-tree-arrow.open { transform: rotate(90deg); }",
	".dmb-tree-dot { width: 8px; height: 8px; border-radius: 50%; flex: none; }",
	".dmb-tree-title { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }",
	".dmb-tree-badge { margin-left: auto; flex: none; padding: 0 7px; border-radius: 999px; background: var(--dmb-hover); color: var(--dmb-text3); font-size: 10.5px; font-weight: 600; }",
	".dmb-tree-time { margin-left: auto; flex: none; color: var(--dmb-text3); font-size: 10.5px; font-variant-numeric: tabular-nums; }",
	".dmb-tree-summary { flex: none; max-width: 38%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--dmb-accent2); font-size: 11px; font-weight: 400; }",
	".dmb-tree-snip { margin: 0 8px 6px 29px; color: var(--dmb-text2); font-size: 11.5px; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }",
	".dmb-tree-kids { margin-left: 14px; border-left: 1px solid var(--dmb-border); padding-left: 4px; }",
	/* event graph: 图在上、树导航在下（上下布局） */
	".dmb-eg-nav { width: 100%; display: flex; flex-direction: column; margin-top: 10px; }",
	".dmb-eg-nav-head { display: flex; align-items: center; gap: 8px; padding: 0 2px 6px; }",
	".dmb-eg-nav-body { display: flex; flex-direction: column; gap: 6px; }",
	".dmb-nav-search { height: 28px; padding: 0 9px; border-radius: 7px; border: 1px solid var(--dmb-border2); background: var(--dmb-card2); color: var(--dmb-text); font-size: 12px; outline: none; }",
	".dmb-eg-tree { max-height: 220px; overflow-y: auto; }",
	".dmb-eg-main { width: 100%; }",
	".dmb-eg-main .dmb-graph-svg { height: 560px; }",
	".dmb-tree-chain > .dmb-tree-row.active { background: color-mix(in srgb, var(--dmb-accent2) 14%, transparent); }",
	/* timeline tab */
	".dmb-tl-day { font-size: 11px; font-weight: 600; color: var(--dmb-text3); letter-spacing: 0.6px; text-transform: uppercase; margin: 14px 2px 6px; }",
	".dmb-tl-item { display: flex; gap: 10px; padding: 9px 12px; border-radius: 10px; background: var(--dmb-card); border: 1px solid var(--dmb-border); margin-bottom: 6px; cursor: pointer; transition: border-color 0.15s ease, background 0.15s ease; }",
	".dmb-tl-item:hover { border-color: var(--dmb-border2); background: var(--dmb-hover); }",
	".dmb-tl-item.active { border-color: var(--dmb-brand); background: color-mix(in srgb, var(--dmb-brand) 8%, transparent); }",
	".dmb-tl-item .dmb-tree-dot { margin-top: 4px; flex: none; }",
	".dmb-tl-item .t { font-weight: 600; font-size: 13px; }",
	".dmb-tl-item .c { color: var(--dmb-text2); font-size: 12px; margin-top: 3px; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }",
	".dmb-tl-item .m { color: var(--dmb-text3); font-size: 10.5px; margin-top: 4px; display: flex; gap: 10px; flex-wrap: wrap; }",
	/* knowledge graph tab */
	".dmb-wg-list { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 8px; margin-top: 10px; }",
	".dmb-wg-item { padding: 8px 10px; border-radius: 9px; background: var(--dmb-card); border: 1px solid var(--dmb-border); cursor: pointer; font-size: 12px; display: flex; align-items: center; gap: 6px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }",
	".dmb-wg-item:hover { border-color: var(--dmb-border2); background: var(--dmb-hover); }",
	".dmb-wg-item.active { border-color: var(--dmb-brand); background: color-mix(in srgb, var(--dmb-brand) 8%, transparent); }",
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
		// M6：本地标记 header（跨站 img/script 无法携带，防 GET 写副作用被跨站触发）
		return fetch("/dsh-memory/" + path + q, { cache: "no-store", headers: { "x-dsh-memory": "1" } }).then(function (r) { return r.json(); }).then(function (b) { if (!b.ok) throw new Error(b.error || "request failed"); return b.result; });
	},
	post: function (path, body) {
		return fetch("/dsh-memory/" + path, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ params: body || {} }) }).then(function (r) { return r.json(); }).then(function (b) { if (!b.ok) throw new Error(b.error || "request failed"); return b.result; });
	}
};

var KIND_LABEL = { event: "事件", chain: "事件链", lesson_pending: "经验·待审", lesson_permanent: "经验", profile: "画像" };
var KIND_COLOR = { event: "var(--dmb-accent)", chain: "var(--dmb-accent2)", lesson_pending: "var(--dmb-warn)", lesson_permanent: "var(--dmb-ok)", profile: "var(--dmb-brand)" };

/* svg icons */
var ICONS = {
	branch: { paths: ["M6 3v12", "M18 9a9 9 0 0 1-9 9"], circles: [[18, 6, 3], [6, 18, 3]] },
	pie: { paths: ["M21.21 15.89A10 10 0 1 1 8 2.83", "M22 12A10 10 0 0 0 12 2v10z"] },
	server: { paths: ["M4 4h16v6H4z", "M4 14h16v6H4z", "M12 7h.01", "M12 17h.01"] },
	compass: { circles: [[12, 12, 10]], paths: ["M16.24 7.76l-2.12 6.36-6.36 2.12 2.12-6.36z"] },
	check: { paths: ["M20 6 9 17l-5-5"] },
	bolt: { paths: ["M13 2 3 14h9l-1 8 10-12h-9l1-8z"] },
	sliders: { paths: ["M4 21v-7", "M4 10V3", "M12 21v-9", "M12 8V3", "M20 21v-5", "M20 12V3", "M1 14h6", "M9 8h6", "M17 16h6"] },
	save: { paths: ["M15.2 3a2 2 0 0 1 1.4.6l3.8 3.8a2 2 0 0 1 .6 1.4V19a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z", "M17 21v-7a1 1 0 0 0-1-1H8a1 1 0 0 0-1 1v7", "M7 3v4a1 1 0 0 0 1 1h8"] },
	search: { circles: [[11, 11, 8]], paths: ["m21 21-4.3-4.3"] },
	x: { paths: ["M18 6 6 18", "M6 6l12 12"] },
	clock: { circles: [[12, 12, 10]], paths: ["M12 6v6l4 2"] },
	file: { paths: ["M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7z", "M14 2v4a2 2 0 0 0 2 2h4", "M16 13H8", "M16 17H8"] },
	archive: { paths: ["M21 8v13H3V8", "M1 3h22v5H1z", "M10 12h4"] },
	trash: { paths: ["M3 6h18", "M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6", "M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2", "M10 11v6", "M14 11v6"] },
	book: { paths: ["M4 19.5A2.5 2.5 0 0 1 6.5 17H20", "M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"] },
	ruler: { paths: ["M21.3 15.3a2.4 2.4 0 0 1 0 3.4l-2.6 2.6a2.4 2.4 0 0 1-3.4 0L2.7 8.7a2.4 2.4 0 0 1 0-3.4l2.6-2.6a2.4 2.4 0 0 1 3.4 0Z", "M14.5 12.5l2-2", "M11.5 9.5l2-2", "M8.5 6.5l2-2"] },
	pin: { paths: ["M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"], circles: [[12, 10, 3]] },
	trend: { paths: ["M22 7l-8.5 8.5-5-5L2 17", "M16 7h6v6"] },
	xcircle: { circles: [[12, 12, 10]], paths: ["M15 9l-6 6", "M9 9l6 6"] },
	link: { paths: ["M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71", "M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"] },
	help: { circles: [[12, 12, 10]], paths: ["M12 8.5a2.5 2.5 0 1 1 2 4c-1 .7-2 1.2-2 2.5", "M12 17h.01"] }
};
function Icon(props) {
	var name = props.name || "help";
	var size = props.size || 14;
	var spec = ICONS[name] || ICONS.help;
	return h("svg", { width: size, height: size, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 2, strokeLinecap: "round", strokeLinejoin: "round", "aria-hidden": true, style: { flex: "none" } },
		(spec.circles || []).map(function (c) { return h("circle", { key: "c" + c.join("-"), cx: c[0], cy: c[1], r: c[2] }); }),
		(spec.paths || []).map(function (d, i) { return h("path", { key: "p" + i, d: d }); })
	);
}

/* 九宫格贪吃蛇 logo */
var SNAKE_DIRS = [[0, 1], [0, -1], [1, 0], [-1, 0]];
function SnakeLogo(props) {
	var size = props.size || 26;
	var _sl0 = useState([[1, 1]]), trail = _sl0[0], setTrail = _sl0[1];
	useEffect(function () {
		var timer = setInterval(function () {
			setTrail(function (prev) {
				var head = prev[0] || [1, 1];
				var nexts = [];
				for (var i = 0; i < SNAKE_DIRS.length; i++) {
					var nx = head[0] + SNAKE_DIRS[i][0];
					var ny = head[1] + SNAKE_DIRS[i][1];
					if (nx >= 0 && nx < 3 && ny >= 0 && ny < 3) nexts.push([nx, ny]);
				}
				var back = prev[1];
				var pool = nexts.filter(function (c) { return !back || c[0] !== back[0] || c[1] !== back[1]; });
				if (!pool.length) pool = nexts;
				var n = pool[Math.floor(Math.random() * pool.length)];
				return [n, head].concat(prev.slice(1, 3));
			});
		}, 320);
		return function () { clearInterval(timer); };
	}, []);
	var dots = [];
	for (var r = 0; r < 3; r++) {
		for (var c = 0; c < 3; c++) {
			dots.push(h("circle", { key: "g" + r + "_" + c, cx: 5 + c * 5, cy: 5 + r * 5, r: 1.3, fill: "rgba(255,255,255,0.18)" }));
		}
	}
	var segs = trail.map(function (p, i) {
		var head = i === 0;
		return h("circle", {
			key: "s" + i,
			cx: 5 + p[1] * 5,
			cy: 5 + p[0] * 5,
			r: head ? 2.2 : 1.7,
			fill: head ? "#ffffff" : "#c9cdd4",
			style: {
				opacity: head ? 1 : (i === 1 ? 0.65 : 0.4),
				filter: head ? "drop-shadow(0 0 3.5px rgba(255,255,255,0.85)) drop-shadow(0 0 9px rgba(255,255,255,0.35))" : "none",
				transition: "cx 0.3s ease, cy 0.3s ease"
			}
		});
	});
	return h("svg", { width: size, height: size, viewBox: "0 0 20 20", "aria-hidden": true, style: { display: "block" } }, dots.concat(segs));
}
/* atoms */
function Counter(props) {
	var value = props.value, suffix = props.suffix || "", prefix = props.prefix || "";
	// 非数字值（如 "100%" / "—"）直接原样显示，不做计数动画（数字动画对字符串会算出 NaN）
	var numeric = typeof value === "number" && Number.isFinite(value);
	var _s = useState(numeric ? 0 : value), shown = _s[0], setShown = _s[1];
	useEffect(function () {
		if (!numeric) return;  // 字符串/其它：静态显示
		var from = 0, to = value, start = performance.now(), dur = 650, raf;
		function tick(now) {
			var p = Math.min(1, (now - start) / dur);
			var eased = 1 - Math.pow(1 - p, 3);
			setShown(Math.round(from + (to - from) * eased));
			if (p < 1) raf = requestAnimationFrame(tick);
		}
		raf = requestAnimationFrame(tick);
		return function () { cancelAnimationFrame(raf); };
	}, [value, numeric]);
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
	var rawTotal = data.reduce(function (s, d) { return s + d.value; }, 0);
	var total = rawTotal || 1;
	var R = 44, C = 2 * Math.PI * R, offset = 0;
	return h("div", { className: "dmb-donut-wrap" },
		h("svg", { width: 110, height: 110, viewBox: "0 0 110 110" },
			h("circle", { cx: 55, cy: 55, r: R, fill: "none", stroke: "var(--dmb-border)", "stroke-width": 13 }),
			data.map(function (d) {
				var len = (d.value / total) * C;
				var el = h("circle", { key: d.name, cx: 55, cy: 55, r: R, fill: "none", stroke: d.color, "stroke-width": 13,
					"stroke-dasharray": len + " " + (C - len), "stroke-dashoffset": -offset, strokeLinecap: "round",
					style: { transition: "stroke-dasharray 0.7s ease, stroke-dashoffset 0.7s ease", transform: "rotate(-90deg)", transformOrigin: "center" } });
				offset += len;
				return el;
			}),
			h("text", { x: 55, y: 52, "text-anchor": "middle", fill: "currentColor", "font-size": "18", "font-weight": "800" }, String(rawTotal)),
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
	var _s8 = useState(0), profileDrafts = _s8[0], setProfileDrafts = _s8[1];

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

	// 画像草稿数（badge）
	useEffect(function () {
		api.get("profile-status").then(function (data) {
			setProfileDrafts((data && data.drafts && data.drafts.length) || 0);
		}).catch(function () { /* badge optional */ });
	}, [refreshKey]);

	var lemonade = overview && overview.lemonade;
	var counts = (overview && overview.counts) || {};
	var mode = (overview && overview.config && overview.config.mode) || "main";

	var tabs = [
		{ id: "overview", label: "总览" },
		{ id: "eventgraph", label: "事件图谱" },
		{ id: "wikigraph", label: "知识图谱" },
		{ id: "timeline", label: "时间线" },
		{ id: "review", label: "待审", badge: pendingCount || undefined },
		{ id: "profile", label: "画像", badge: profileDrafts || undefined },
		{ id: "audit", label: "审计" }
	];

	return h("div", { id: "dmb-root" },
		h("div", { className: "dmb-header" },
			h("div", { className: "dmb-logo" }, h(SnakeLogo, { size: 26 })),
			h("div", null,
				h("div", { className: "dmb-title" }, "记忆树 · Memory Bridge"),
				h("div", { className: "dmb-subtitle" }, overview ? (overview.memoryRoot || "") : "加载中…")
			),
			h("div", { className: "dmb-pills" },
				mode === "local" || mode === "hybrid" ? h("span", { className: "dmb-pill" }, h(Dot, { state: lemonade && lemonade.serverUp ? "ok" : "err" }), "本地推理 ", lemonade && lemonade.serverUp ? "在线" : "离线") : null,
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
			tab === "eventgraph" ? h(EventGraphTab, { refreshKey: refreshKey }) : null,
			tab === "wikigraph" ? h(WikiGraphTab, { refreshKey: refreshKey }) : null,
			tab === "timeline" ? h(TimelineTab, { refreshKey: refreshKey }) : null,
			tab === "review" ? h(ReviewTab, { onPendingChange: setPendingCount }) : null,
			tab === "profile" ? h(ProfileTab, { onDraftChange: setProfileDrafts }) : null,
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
	var usedRate = Number.isFinite(audit.inject_used_rate) ? (audit.inject_used_rate * 100).toFixed(0) + "%" : "—";
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
			h("h3", null, h(Icon, { name: "pie", size: 14 }), "记忆构成"),
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
				h("h3", null, h(Icon, { name: "server", size: 14 }), "本地推理服务"),
				h("div", { className: "dmb-row" }, h("div", { className: "grow" }, h("div", { className: "k" }, "服务状态")), h("div", null, h("span", { className: "dmb-pill" }, h(Dot, { state: lemonade.serverUp ? "ok" : "err" }), lemonade.serverUp ? "运行中" : "离线"))),
				h("div", { className: "dmb-row" }, h("div", { className: "grow" }, h("div", { className: "k" }, "目标模型加载")), h("div", { className: "v" }, lemonade.modelLoaded ? h("span", { className: "dmb-ic" }, h(Icon, { name: "check", size: 12 }), "已就绪") : "未加载")),
				h("div", { className: "dmb-row" }, h("div", { className: "grow" }, h("div", { className: "k" }, "已加载模型")), h("div", { className: "v" }, (lemonade.loadedModels || []).join(", ") || "—")),
				h("div", { className: "dmb-row" }, h("div", { className: "grow" }, h("div", { className: "k" }, "版本")), h("div", { className: "v" }, lemonade.version || "—")),
				h("div", { className: "dmb-actions" }, h(LemonadeEnsure, { onDone: props.refresh }))
			),
			h("div", { className: "dmb-card", style: { marginBottom: 0 } },
				h("h3", null, h(Icon, { name: "compass", size: 14 }), "提取与注入"),
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
			toast.show(res.status && res.status.modelLoaded ? "模型就绪" : "服务已就绪", "ok");
			props.onDone && props.onDone();
		}).catch(function (err) { toast.show("拉起失败：" + ((err && err.message) || err), "err"); }).finally(function () { setBusy(false); });
	};
	return h("span", null,
		h("button", { className: "dmb-btn primary", onClick: run, disabled: busy }, busy ? "拉起中…" : h("span", { className: "dmb-ic" }, h(Icon, { name: "bolt", size: 13 }), "拉起本地推理")),
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
		{ id: "local", label: "本地模型", desc: "本地推理（预设或自定义端点）" },
		{ id: "cloud", label: "云端专用", desc: "独立提取 API" },
		{ id: "main", label: "主对话模型", desc: "复用会话模型" },
		{ id: "hybrid", label: "混合", desc: "本地优先·云端兜底" }
	];

	return h("div", { className: "dmb-card" },
		h("h3", null, h(Icon, { name: "sliders", size: 14 }), "提取配置（面板内保存，重启后完全生效）"),
		h("div", { className: "dmb-section-title", style: { marginTop: 4 } }, "模式"),
		h("div", { style: { display: "flex", flexWrap: "wrap", gap: 8 } },
			modes.map(function (m) {
				return h("button", { key: m.id, className: "dmb-chip" + (form.mode === m.id ? " active" : ""), onClick: function () { set("mode", m.id); }, title: m.desc }, m.label);
			})
		),
		form.mode === "local" || form.mode === "hybrid" ? h("div", null,
			h("div", { className: "dmb-section-title" }, "本地轨"),
			h("div", { className: "dmb-grid", style: { gridTemplateColumns: "repeat(auto-fit,minmax(200px,1fr))" } },
				h("div", { className: "dmb-field" }, h("label", null, "预设"), h("select", { value: local.preset, onChange: function (e) { set("local.preset", e.target.value); } }, h("option", { value: "qwen3-it-4b-flm" }, "qwen3-it-4b-flm（推荐）"), h("option", { value: "custom" }, "自定义（OpenAI 兼容端点）"))),
				local.preset === "custom" ? h("div", { className: "dmb-field" }, h("label", null, "Base URL"), h("input", { value: local.baseUrl, placeholder: "http://127.0.0.1:11434/v1", onChange: function (e) { set("local.baseUrl", e.target.value); } })) : null,
				local.preset === "custom" ? h("div", { className: "dmb-field" }, h("label", null, "模型名"), h("input", { value: local.model, placeholder: "qwen2.5:7b", onChange: function (e) { set("local.model", e.target.value); } }), h("div", { className: "dmb-hint" }, "建议选非思考模型（thinking 会污染提取质量）")) : null,
				local.preset === "custom" ? h("div", { className: "dmb-field" }, h("label", null, "API Key（本地一般免鉴权）"), h("input", { value: local.apiKey, type: "password", placeholder: "留空", onChange: function (e) { set("local.apiKey", e.target.value); } })) : null,
				local.preset === "custom" ? h("div", { className: "dmb-field" }, h("label", null, "API Key 环境变量名"), h("input", { value: local.apiKeyEnv, placeholder: "留空则用上面的明文", onChange: function (e) { set("local.apiKeyEnv", e.target.value); } })) : null,
				h("div", { className: "dmb-field" }, h("label", { className: "dmb-switch" }, h("input", { type: "checkbox", checked: !!local.autoManage, onChange: function (e) { set("local.autoManage", e.target.checked); } }), h("span", { className: "track" }), h("span", { className: "txt" }, "自动健康检查 + 拉起本地推理服务" + (local.preset === "custom" ? "（自定义端点不自动拉起）" : "")))),
				h("div", { className: "dmb-field" }, h("label", { className: "dmb-switch" }, h("input", { type: "checkbox", checked: !!local.sanitize, onChange: function (e) { set("local.sanitize", e.target.checked); } }), h("span", { className: "track" }), h("span", { className: "txt" }, "发送前脱敏")))
			),
			local.preset !== "custom" ? h("div", { className: "dmb-field" }, h("label", null, "API Key（本地一般免鉴权）"), h("input", { value: local.apiKey, type: "password", placeholder: "留空", onChange: function (e) { set("local.apiKey", e.target.value); } })) : null
		) : null,
		form.mode === "cloud" || form.mode === "hybrid" ? h("div", null,
			h("div", { className: "dmb-section-title" }, "云端轨"),
			h("div", { className: "dmb-grid", style: { gridTemplateColumns: "repeat(auto-fit,minmax(200px,1fr))" } },
				h("div", { className: "dmb-field" }, h("label", null, "Base URL"), h("input", { value: cloud.baseUrl, placeholder: "https://api.deepseek.com/v1", onChange: function (e) { set("cloud.baseUrl", e.target.value); } })),
				h("div", { className: "dmb-field" }, h("label", null, "模型名"), h("input", { value: cloud.model, placeholder: "deepseek-chat", onChange: function (e) { set("cloud.model", e.target.value); } }), h("div", { className: "dmb-hint" }, "建议选非思考模型（如 deepseek-chat，勿用 deepseek-reasoner）")),
				h("div", { className: "dmb-field" }, h("label", null, "API Key（脱敏显示）"), h("input", { value: cloud.apiKey, type: "password", placeholder: "sk-…", onChange: function (e) { set("cloud.apiKey", e.target.value); } })),
				h("div", { className: "dmb-field" }, h("label", null, "批大小"), h("input", { value: cloud.batchSize, type: "number", min: 1, max: 32, onChange: function (e) { set("cloud.batchSize", Number(e.target.value)); } }))
			),
			h("div", { className: "dmb-field" }, h("label", { className: "dmb-switch" }, h("input", { type: "checkbox", checked: !!cloud.sanitize, onChange: function (e) { set("cloud.sanitize", e.target.checked); } }), h("span", { className: "track" }), h("span", { className: "txt" }, "发送前脱敏（密钥/凭证 → 占位符）")))
		) : null,
		h("div", { className: "dmb-actions" },
			h("button", { className: "dmb-btn primary", onClick: save, disabled: saving }, saving ? "保存中…" : h("span", { className: "dmb-ic" }, h(Icon, { name: "save", size: 13 }), "保存配置")),
			h("span", { style: { color: "var(--dmb-text3)", fontSize: "11px", alignSelf: "center" } }, "重启后对提取管线完全生效")
		),
		toast.node
	);
}

/* cards tab */
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
			toast.show(action, "ok");
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
						h("button", { className: "dmb-btn primary", onClick: function () { act(c.id, "approve"); } }, h("span", { className: "dmb-ic" }, h(Icon, { name: "check", size: 13 }), "采纳")),
						h("button", { className: "dmb-btn danger", onClick: function () { act(c.id, "archive"); } }, h("span", { className: "dmb-ic" }, h(Icon, { name: "xcircle", size: 13 }), "拒绝"))
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
	var _s26 = useState(false), maintBusy = _s26[0], setMaintBusy = _s26[1];
	var toast = useToast();

	var load = useCallback(function () {
		api.get("audit", {}).then(function (r) { setData(r); }).catch(function (e) { toast.show(String((e && e.message) || e), "err"); }).finally(function () { setLoading(false); });
	}, []);
	useEffect(function () { load(); }, [load]);

	// 手动触发一轮衰减 + 全局治理（sidecar maintenance）
	var runMaintenance = function () {
		if (maintBusy) return;
		setMaintBusy(true);
		api.post("maintenance", {}).then(function (r) {
			var g = (r && r.govern) || {};
			var d = (r && r.decay) || {};
			toast.show("维护完成：完结 " + (d.ended || 0) + " 枝 · 枯萎 " + (d.wilted || 0) + " 叶 · 治理：" + ((g.actions || [])[0] || "无"));
			load();
		}).catch(function (e) { toast.show("维护失败：" + ((e && e.message) || e), "err"); }).finally(function () { setMaintBusy(false); });
	};

	if (loading) return h(Spinner, null);
	if (!data) return null;
	var s = data.summary || {};
	var usedRate = Number.isFinite(s.inject_used_rate) ? (s.inject_used_rate * 100).toFixed(0) + "%" : "—";
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
		h("div", { className: "dmb-actions" },
			h("button", { className: "dmb-btn" + (maintBusy ? "" : " primary"), onClick: runMaintenance, disabled: maintBusy, title: "立即执行一轮衰减判定 + 健康治理（30天闲置枝完结、低使用率卡降权）" }, "立即维护")),
		h("div", { className: "dmb-card" },
			h("h3", null, h(Icon, { name: "trend", size: 14 }), "最近活动轨迹（按事件）"),
			h(Sparks, { data: sparkData }),
			h("div", { style: { color: "var(--dmb-text3)", fontSize: 11, marginTop: 6 } }, "绿=注入被用 · 黄=注入未用 · 蓝=注入命中 · 紫=提取/衰减 · 橙=治理 · 灰=跳过")
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

/* profile tab: 画像蒸馏 / 审批 / 状态 */
function ProfileTab(props) {
	var _p0 = useState(null), data = _p0[0], setData = _p0[1];
	var _p1 = useState(true), loading = _p1[0], setLoading = _p1[1];
	var _p2 = useState(false), distillBusy = _p2[0], setDistillBusy = _p2[1];
	var _p3 = useState(false), actingDraft = _p3[0], setActingDraft = _p3[1];
	var toast = useToast();

	var load = useCallback(function () {
		setLoading(true);
		api.get("profile-status", {}).then(function (r) {
			setData(r);
			props.onDraftChange && props.onDraftChange(((r && r.drafts) || []).length);
		}).catch(function (e) { toast.show(String((e && e.message) || e), "err"); }).finally(function () { setLoading(false); });
	}, []);
	useEffect(function () { load(); }, [load]);

	var runDistill = function () {
		if (distillBusy) return;
		setDistillBusy(true);
		api.post("distill", {}).then(function (r) {
			if (r && r.draft) toast.show("画像草稿已产出，待审批", "ok");
			else toast.show((r && r.note) || "蒸馏完成（无新草稿）", "ok");
			load();
		}).catch(function (e) { toast.show("蒸馏失败：" + ((e && e.message) || e), "err"); }).finally(function () { setDistillBusy(false); });
	};

	var act = function (draftId, action) {
		if (actingDraft) return;
		setActingDraft(draftId);
		api.post(action === "approve" ? "distill-approve" : "distill-reject", { draftId: draftId }).then(function () {
			toast.show(action === "approve" ? "画像已固化" : "草稿已驳回", "ok");
			load();
		}).catch(function (e) { toast.show("操作失败：" + ((e && e.message) || e), "err"); }).finally(function () { setActingDraft(null); });
	};

	if (loading && !data) return h(Spinner, null);
	if (!data) return null;

	var approved = data.approved;
	var drafts = data.drafts || [];

	return h("div", null,
		h("div", { className: "dmb-card" },
			h("h3", null, h(Icon, { name: "pin", size: 14 }), "用户画像"),
			approved ? h("div", null,
				h("div", { className: "dmb-row" }, h("div", { className: "grow" }, h("div", { className: "k" }, "状态")), h("div", { className: "v" }, h("span", { className: "dmb-pill" }, h(Dot, { state: "ok" }), "已固化 v" + approved.version))),
				h("div", { className: "dmb-row" }, h("div", { className: "grow" }, h("div", { className: "k" }, "更新时间")), h("div", { className: "v" }, (approved.updatedAt || "").slice(0, 19) || "—")),
				approved.mbti ? h("div", { className: "dmb-row" }, h("div", { className: "grow" }, h("div", { className: "k" }, "MBTI")), h("div", { className: "v" }, approved.mbti)) : null,
				h("div", { style: { marginTop: 8, whiteSpace: "pre-wrap", lineHeight: 1.6, color: "var(--dmb-text1)" } }, approved.summary || "—")
			) : h(Empty, null, "暂无已审批画像——点击下方「蒸馏画像」从事件树生成"),
			h("div", { className: "dmb-actions" },
				h("button", { className: "dmb-btn primary", onClick: runDistill, disabled: distillBusy }, distillBusy ? "蒸馏中…" : h("span", { className: "dmb-ic" }, h(Icon, { name: "bolt", size: 13 }), "蒸馏画像"))
			)
		),
		h("div", { className: "dmb-section-title" }, "待审草稿（" + drafts.length + "）"),
		drafts.length === 0 ? h(Empty, null, "没有待审画像草稿") :
			drafts.map(function (d, i) {
				return h("div", { key: d.draftId, className: "dmb-result", style: { animationDelay: (i * 50) + "ms" } },
					h("div", { className: "top" },
						h("span", { className: "t" }, d.mbti ? "MBTI " + d.mbti : "画像草稿"),
						h("span", { className: "dmb-tag" }, (d.updatedAt || "").slice(0, 16) || ""),
						h("div", { className: "grow" }),
						h("button", { className: "dmb-btn primary", disabled: !!actingDraft, onClick: function () { act(d.draftId, "approve"); } }, "采纳"),
						h("button", { className: "dmb-btn", disabled: !!actingDraft, onClick: function () { act(d.draftId, "reject"); } }, "驳回")
					),
					h("div", { className: "snip" }, d.summary || "—")
				);
			}),
		toast.node
	);
}

/* graph tab: Obsidian 式动态关系图谱（力导向 SVG，直接 DOM 操作） */
// 低饱和现代色板：稳定质感，深浅主题下都清晰
var GRAPH_KIND_COLOR = {
	chain: "#8b7cf6", event: "#60a5fa",
	lesson_pending: "#f59e0b", lesson_permanent: "#34d399", profile: "#f472b6",
	"wiki:spec": "#818cf8", "wiki:concept": "#2dd4bf", "wiki:tutorial": "#fb923c"
};
var GRAPH_KIND_LABEL = {
	chain: "事件链", event: "事件", lesson_pending: "经验·待审", lesson_permanent: "经验",
	profile: "画像", "wiki:spec": "规范", "wiki:concept": "概念", "wiki:tutorial": "教程"
};
var EDGE_STYLE = {
	belongs: { color: "rgba(148,163,184,0.55)", dash: "" },
	entity: { color: "rgba(148,163,184,0.5)", dash: "4 4" },
	supersedes: { color: "rgba(248,113,113,0.6)", dash: "2 3" },
	parent: { color: "rgba(100,116,139,0.6)", dash: "6 3" }
};
// 激活高亮色（按边类型提亮，用于选中节点的相邻边）
var HIGHLIGHT_EDGE = {
	belongs: "#93c5fd", entity: "#a5f3fc", supersedes: "#fca5a5", parent: "#cbd5e1"
};
var _svgNS = "http://www.w3.org/2000/svg";

function GraphCanvas(props) {
	var svgRef = useRef(null);
	var gRef = useRef(null);
	var tipRef = useRef(null);
	var simRef = useRef(null);

	useEffect(function () {
		var svg = svgRef.current, g = gRef.current;
		if (!svg || !g) return;
		var nodes = props.nodes || [];
		var edges = props.edges || [];
		var prev = simRef.current;
		var forceRandom = !prev || prev.layoutKey !== props.layoutKey;
		var sim = {
			pos: {}, k: 1, tx: 70, ty: 70, layoutKey: props.layoutKey,
			raf: null, running: false, stableFrames: 0, temp: (prev && !forceRandom) ? prev.temp : 1, hardAny: false,
			fitPending: forceRandom,
			drag: null, pan: null, hoverId: null,
			edgeEls: [], nodeEls: [], index: {}
		};
		simRef.current = sim;
		sim.g = g;  // 模块级 applyTransform 需要 g 引用
		var W = svg.clientWidth || 900, H = svg.clientHeight || 540;

		// 聚类初始布局：链居中铺开，事件环绕其父链，其余螺旋（避免初始过挤引发斥力爆炸）；
		// 重新布局时加随机角度偏移 → 每次生成不同形态（Obsidian 重排同款）
		var jitter = forceRandom ? Math.random() * Math.PI * 2 : 0;
		var chainIds = [];
		nodes.forEach(function (n) { if (n.kind === "chain") chainIds.push(n.id); });
		var parentOf = {};
		edges.forEach(function (e) { if (e.kind === "belongs") parentOf[e.target] = e.source; });
		var chainIndex = {};
		chainIds.forEach(function (id, i) { chainIndex[id] = i; });
		nodes.forEach(function (n) {
			var old = !forceRandom && prev && prev.pos[n.id];
			if (old) { sim.pos[n.id] = { x: old.x, y: old.y, vx: 0, vy: 0 }; return; }
			if (n.kind === "chain") {
				var ci = chainIndex[n.id] || 0;
				var angC = ci * 2.399963 + 1 + jitter, radC = 80 + ci * 48;
				sim.pos[n.id] = { x: W / 2 + Math.cos(angC) * radC, y: H / 2 + Math.sin(angC) * radC, vx: 0, vy: 0 };
			}
		});
		var placed = 0, groupCount = {};
		nodes.forEach(function (n) {
			if (sim.pos[n.id]) return;
			var par = parentOf[n.id];
			if (par && sim.pos[par]) {
				// 组内顺序黄金角 + 半径递增：同链事件卡均匀环绕，绝不重叠
				var gi = groupCount[par] || 0;
				groupCount[par] = gi + 1;
				var angE = gi * 2.399963 + 1 + jitter;
				var radE = 90 + gi * 42;
				sim.pos[n.id] = { x: sim.pos[par].x + Math.cos(angE) * radE, y: sim.pos[par].y + Math.sin(angE) * radE, vx: 0, vy: 0 };
			} else {
				var ang = placed * 2.399963 + 1 + jitter, rad = 120 + placed * 34;
				sim.pos[n.id] = { x: W / 2 + Math.cos(ang) * rad, y: H / 2 + Math.sin(ang) * rad, vx: 0, vy: 0 };
			}
			placed++;
		});

		g.innerHTML = "";
		// 方向箭头 marker（fill: context-stroke → 箭头颜色跟随边颜色）
		var defs = document.createElementNS(_svgNS, "defs");
		var arrowMarker = document.createElementNS(_svgNS, "marker");
		arrowMarker.setAttribute("id", "dmb-arrow");
		arrowMarker.setAttribute("viewBox", "0 0 10 10");
		arrowMarker.setAttribute("refX", "9");
		arrowMarker.setAttribute("refY", "5");
		arrowMarker.setAttribute("markerWidth", "7");
		arrowMarker.setAttribute("markerHeight", "7");
		arrowMarker.setAttribute("orient", "auto-start-reverse");
		var arrowPath = document.createElementNS(_svgNS, "path");
		arrowPath.setAttribute("d", "M0,0 L10,5 L0,10 z");
		arrowPath.setAttribute("fill", "context-stroke");
		arrowMarker.appendChild(arrowPath);
		defs.appendChild(arrowMarker);
		g.appendChild(defs);
		var edgeG = document.createElementNS(_svgNS, "g");
		var nodeG = document.createElementNS(_svgNS, "g");
		g.appendChild(edgeG); g.appendChild(nodeG);

		edges.forEach(function (e) {
			if (!sim.pos[e.source] || !sim.pos[e.target]) return;
			var st = EDGE_STYLE[e.kind] || EDGE_STYLE.belongs;
			var line = document.createElementNS(_svgNS, "line");
			line.setAttribute("stroke", st.color);
			if (st.dash) line.setAttribute("stroke-dasharray", st.dash);
			line.setAttribute("stroke-width", e.kind === "belongs" ? 1.2 : 1);
			line.setAttribute("class", "dmb-graph-edge");
			line.setAttribute("data-id", e.source + "~" + e.target);
			// 有向边（归链=链→事件、版本=旧→新、上位=子→父）加方向箭头
			if (e.kind !== "entity") line.setAttribute("marker-end", "url(#dmb-arrow)");
			edgeG.appendChild(line);
			sim.edgeEls.push({ line: line, e: e });
		});

		nodes.forEach(function (n) {
			var el = document.createElementNS(_svgNS, "g");
			el.setAttribute("class", "dmb-graph-node");
			el.setAttribute("data-id", n.id);
			var r = n.kind === "chain" ? 14 : (n.kind === "event" ? 8 : (n.kind.indexOf("wiki:") === 0 ? 9 : 7));
			var circle = document.createElementNS(_svgNS, "circle");
			circle.setAttribute("r", r);
			circle.setAttribute("fill", GRAPH_KIND_COLOR[n.kind] || "var(--dmb-text3)");
			var text = document.createElementNS(_svgNS, "text");
			text.setAttribute("text-anchor", "middle");
			text.setAttribute("dy", r + 14);
			text.textContent = n.title.length > 16 ? n.title.slice(0, 15) + "…" : n.title;
			el.appendChild(circle); el.appendChild(text);
			nodeG.appendChild(el);
			var item = { g: el, circle: circle, text: text, n: n, r: r };
			sim.nodeEls.push(item);
			sim.index[n.id] = item;
			el.addEventListener("pointerdown", function (ev) {
				ev.stopPropagation();
				sim.drag = n.id;
				var p = sim.pos[n.id];
				p.vx = 0; p.vy = 0; p.fixed = true;
				try { el.setPointerCapture(ev.pointerId); } catch (e) { /* no-op */ }
				wake(sim);
			});
			el.addEventListener("pointerenter", function (ev) {
				sim.hoverId = n.id;
				showTip(sim, n, ev.clientX, ev.clientY);
			});
			el.addEventListener("pointerleave", function () {
				sim.hoverId = null;
				if (tipRef.current) tipRef.current.style.opacity = 0;
			});
			el.addEventListener("click", function () {
				if (props.onSelect) props.onSelect(n.id);
			});
		});

		function wake(s) {
			if (s.running) return;
			s.running = true;
			s.stableFrames = 0;
			s.raf = requestAnimationFrame(function step() {
				tick(s, W, H);
				if (!s.running) return;
				s.raf = requestAnimationFrame(step);
			});
		}
		wake(sim);

		var onPointerMove = function (ev) {
			var rect = svg.getBoundingClientRect();
			var mx = ev.clientX - rect.left, my = ev.clientY - rect.top;
			if (sim.drag) {
				var p = sim.pos[sim.drag];
				p.x = (mx - sim.tx) / sim.k;
				p.y = (my - sim.ty) / sim.k;
				p.vx = 0; p.vy = 0;
				applyPos(sim);
			} else if (sim.pan) {
				sim.tx = sim.pan.tx0 + (mx - sim.pan.x0);
				sim.ty = sim.pan.ty0 + (my - sim.pan.y0);
				// 位移超过阈值 → 视为平移（否则是空白点击，用于取消选中）
				if (Math.abs(mx - sim.pan.x0) + Math.abs(my - sim.pan.y0) > 5) sim.pan.moved = true;
				applyTransform(sim);
			}
			if (sim.hoverId && tipRef.current) {
				showTip(sim, sim.index[sim.hoverId] && sim.index[sim.hoverId].n, ev.clientX, ev.clientY);
			}
		};
		var onPointerDown = function (ev) {
			if (ev.button !== 0 && ev.button !== undefined) return;
			var rect = svg.getBoundingClientRect();
			sim.pan = { x0: ev.clientX - rect.left, y0: ev.clientY - rect.top, tx0: sim.tx, ty0: sim.ty, moved: false };
			svg.classList.add("panning");
			try { svg.setPointerCapture(ev.pointerId); } catch (e) { /* no-op */ }
		};
		var onPointerUp = function () {
			// 空白点击（无位移、未拖节点）→ 取消选中（Obsidian 行为）
			var blankClick = !sim.drag && sim.pan && !sim.pan.moved;
			if (sim.drag) {
				var p = sim.pos[sim.drag];
				if (p) p.fixed = false;
				sim.drag = null;
			}
			sim.pan = null;
			svg.classList.remove("panning");
			wake(sim);
			if (blankClick && props.onSelect) props.onSelect(null);
		};
		var onWheel = function (ev) {
			ev.preventDefault();
			var rect = svg.getBoundingClientRect();
			var mx = ev.clientX - rect.left, my = ev.clientY - rect.top;
			var oldK = sim.k;
			var newK = Math.max(0.15, Math.min(3.5, oldK * (ev.deltaY < 0 ? 1.12 : 0.89)));
			sim.k = newK;
			sim.tx = mx - ((mx - sim.tx) / oldK) * newK;
			sim.ty = my - ((my - sim.ty) / oldK) * newK;
			applyTransform(sim);
		};
		var onDblClick = function (ev) {
			ev.preventDefault();
			sim.k = 1; sim.tx = 70; sim.ty = 70;
			applyTransform(sim);
		};
		svg.addEventListener("pointermove", onPointerMove);
		svg.addEventListener("pointerdown", onPointerDown);
		svg.addEventListener("pointerup", onPointerUp);
		// M5：指针被 OS 抢断（触摸滚动/Alt-Tab/右键）时复位拖拽，防 rAF 永续空转
		svg.addEventListener("pointercancel", onPointerUp);
		svg.addEventListener("lostpointercapture", onPointerUp);
		svg.addEventListener("wheel", onWheel, { passive: false });
		svg.addEventListener("dblclick", onDblClick);

		return function () {
			sim.running = false;
			if (sim.raf) cancelAnimationFrame(sim.raf);
			svg.removeEventListener("pointermove", onPointerMove);
			svg.removeEventListener("pointerdown", onPointerDown);
			svg.removeEventListener("pointerup", onPointerUp);
			svg.removeEventListener("pointercancel", onPointerUp);
			svg.removeEventListener("lostpointercapture", onPointerUp);
			svg.removeEventListener("wheel", onWheel);
			svg.removeEventListener("dblclick", onDblClick);
		};
	}, [props.nodes, props.edges, props.layoutKey]);

	// 选中高亮邻居（Obsidian 效果）
	useEffect(function () {
		var sim = simRef.current;
		if (!sim || !sim.nodeEls) return;
		var sel = props.selected;
		var nbr = {};
		if (sel) {
			sim.edgeEls.forEach(function (item) {
				var e = item.e;
				if (e.source === sel) nbr[e.target] = 1;
				if (e.target === sel) nbr[e.source] = 1;
			});
			nbr[sel] = 1;
		}
		sim.nodeEls.forEach(function (item) {
			var dim = sel && !nbr[item.n.id];
			item.g.setAttribute("class", "dmb-graph-node" + (item.n.id === sel ? " active" : ""));
			item.circle.setAttribute("opacity", dim ? 0.18 : 1);
			item.text.setAttribute("opacity", dim ? 0.12 : 1);
			if (item.n.id === sel) item.circle.setAttribute("r", item.r + 4);
			else item.circle.setAttribute("r", item.r);
		});
		sim.edgeEls.forEach(function (item) {
			var e = item.e;
			var lit = !sel || e.source === sel || e.target === sel;
			item.line.setAttribute("opacity", lit ? 1 : 0.08);
			// 激活节点的相邻边：提亮 + 加粗 + 发光 + 流动（与未激活拉开明显差距）
			if (lit && sel) {
				item.line.classList.add("lit");
				item.line.setAttribute("stroke", HIGHLIGHT_EDGE[e.kind] || "#93c5fd");
			} else {
				item.line.classList.remove("lit");
				item.line.setAttribute("stroke", (EDGE_STYLE[e.kind] || EDGE_STYLE.belongs).color);
			}
		});
	}, [props.selected]);

	// applyTransform / applyPos 已提升为模块级（tick 需要调用；见 GraphCanvas 之后定义）

	function showTip(sim, n, cx, cy) {
		if (!tipRef.current || !n) return;
		var rect = svgRef.current.getBoundingClientRect();
		var tip = tipRef.current;
		tip.innerHTML = "";
		var t = document.createElement("div");
		t.className = "t";
		t.textContent = n.title;
		var k = document.createElement("div");
		k.className = "k";
		k.textContent = GRAPH_KIND_LABEL[n.kind] || n.kind;
		tip.appendChild(t); tip.appendChild(k);
		tip.style.opacity = 1;
		var tw = tip.offsetWidth, th = tip.offsetHeight;
		var x = cx - rect.left + 14, y = cy - rect.top + 14;
		if (x + tw > rect.width) x = cx - rect.left - tw - 10;
		if (y + th > rect.height) y = cy - rect.top - th - 10;
		tip.style.left = x + "px";
		tip.style.top = y + "px";
	}

	return h("div", { className: "dmb-graph-wrap" },
		h("svg", { className: "dmb-graph-svg", ref: svgRef }, h("g", { ref: gRef })),
		h("div", { className: "dmb-graph-tip", ref: tipRef })
	);
}

/* 模块级 DOM 应用 + 整体适配（tick 与组件事件共用） */
function applyTransform(sim) {
	var g = sim.g;
	if (g) g.setAttribute("transform", "translate(" + sim.tx.toFixed(1) + "," + sim.ty.toFixed(1) + ") scale(" + sim.k.toFixed(3) + ")");
}
function applyPos(sim) {
	sim.nodeEls.forEach(function (item) {
		var p = sim.pos[item.n.id];
		if (p) item.g.setAttribute("transform", "translate(" + p.x.toFixed(1) + "," + p.y.toFixed(1) + ")");
	});
	sim.edgeEls.forEach(function (item) {
		var a = sim.pos[item.e.source], b = sim.pos[item.e.target];
		if (a && b) {
			item.line.setAttribute("x1", a.x.toFixed(1));
			item.line.setAttribute("y1", a.y.toFixed(1));
			item.line.setAttribute("x2", b.x.toFixed(1));
			item.line.setAttribute("y2", b.y.toFixed(1));
		}
	});
}
function doFit(sim, W, H) {
	// 整体形态约束：布局冻结后自动缩放平移，使全部节点完整可见并居中（留边距）
	var minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
	Object.keys(sim.pos).forEach(function (id) {
		var p = sim.pos[id];
		if (p.x < minX) minX = p.x;
		if (p.y < minY) minY = p.y;
		if (p.x > maxX) maxX = p.x;
		if (p.y > maxY) maxY = p.y;
	});
	var bw = Math.max(maxX - minX, 60), bh = Math.max(maxY - minY, 60);
	var k = Math.min((W - 90) / bw, (H - 90) / bh, 1.6);
	if (k < 0.12) k = 0.12;
	if (k > 1) k = 1;  // 图小于画布时不放大
	sim.k = k;
	var cx = (minX + maxX) / 2, cy = (minY + maxY) / 2;
	sim.tx = W / 2 - cx * k;
	sim.ty = H / 2 - cy * k;
}

function tick(sim, W, H) {
	var ids = Object.keys(sim.pos);
	var n = ids.length;
	if (n === 0) { sim.running = false; return; }
	var arr = ids.map(function (id) { return sim.pos[id]; });
	// 温度：拖拽时**平滑升温**（lerp 至 0.5，避免第一次拖动瞬间解冻导致整图跳动）；
	// 硬重叠未解决前不冻结（温度维持 0.25 继续推开，直到彻底分离）
	if (sim.drag) sim.temp = Math.min(1, sim.temp + (0.5 - sim.temp) * 0.06);
	else sim.temp *= 0.965;
	if (sim.hardAny) sim.temp = Math.max(sim.temp, 0.25);
	if (sim.temp < 0.04) {
		sim.running = false;
		// 初始/重新布局冻结后自动适配画布（整体形态约束：图完整可见、居中）
		if (sim.fitPending) {
			sim.fitPending = false;
			doFit(sim, W, H);
			applyTransform(sim);
		}
		applyPos(sim);
		return;
	}
	var K = 90;
	// 每帧合力清零（_id 用于同点方向退化；kind 用于链骨架引力）
	for (var i = 0; i < n; i++) {
		var idx = sim.index[ids[i]];
		arr[i]._id = ids[i];
		arr[i].kind = idx ? idx.n.kind : "";
		arr[i].fx = 0; arr[i].fy = 0; arr[i].hard = 0;
	}
	// 斥力 fr = K²/d（clamp 上限）+ 硬性防重叠（d<34 强推开，穿透温度冷却）
	for (var i = 0; i < n; i++) {
		var a = arr[i];
		for (var j = i + 1; j < n; j++) {
			var b = arr[j];
			var dx = a.x - b.x, dy = a.y - b.y;
			var d2 = dx * dx + dy * dy;
			var d = Math.sqrt(d2) || 1;
			if (dx === 0 && dy === 0) {
				// 完全同点：合力方向退化 → 按 id 哈希给固定方向，保证可推开
				var h = 0;
				for (var c = 0; c < a._id.length; c++) h = (h * 31 + a._id.charCodeAt(c)) >>> 0;
				var angZ = ((h % 360) * Math.PI) / 180;
				dx = Math.cos(angZ); dy = Math.sin(angZ);
				d = 1;
			}
			var hard = d < 34 ? (34 - d) * 0.45 : 0;
			// 斥力随距离 d² 衰减（近距有限、远距趋零）：节点簇平衡后不再互相推开
			var f = 30000 / (d * d) + hard;
			if (f > 2.5) f = 2.5;
			if (hard > f) f = hard;
			var fx = (dx / d) * f, fy = (dy / d) * f;
			// 斥力：a 沿 dx 方向（远离 b），b 反向（远离 a）
			if (!a.fixed) { a.fx += fx; a.fy += fy; if (hard > a.hard) a.hard = hard; }
			if (!b.fixed) { b.fx -= fx; b.fy -= fy; if (hard > b.hard) b.hard = hard; }
		}
	}
	// 弹簧（线性，平衡于 rest 附近）
	sim.edgeEls.forEach(function (item) {
		var a = sim.pos[item.e.source], b = sim.pos[item.e.target];
		if (!a || !b) return;
		var dx = b.x - a.x, dy = b.y - a.y;
		var d = Math.sqrt(dx * dx + dy * dy) || 1;
		var rest = item.e.kind === "parent" ? 170 : (item.e.kind === "belongs" ? 110 : 100);
		var f = 0.05 * (d - rest);
		var fx = (dx / d) * f, fy = (dy / d) * f;
		if (!a.fixed) { a.fx += fx; a.fy += fy; }
		if (!b.fixed) { b.fx -= fx; b.fy -= fy; }
	});
	// 弱向心力（每节点，d3 forceX/forceY 同款）：与斥力形成平衡点 → 整体呈圆形聚合（Obsidian 观感）
	for (var i2 = 0; i2 < n; i2++) {
		var a2 = arr[i2];
		if (a2.fixed) continue;
		a2.fx += (W / 2 - a2.x) * 0.007;
		a2.fy += (H / 2 - a2.y) * 0.007;
	}
	// 质心轻居中（Obsidian/d3 forceCenter 同款：整体平移，不改变节点相对位置 → 不会压缩成团）
	var cx = 0, cy = 0;
	for (var i5 = 0; i5 < n; i5++) { cx += arr[i5].x; cy += arr[i5].y; }
	cx /= n; cy /= n;
	for (var i6 = 0; i6 < n; i6++) {
		var a6 = arr[i6];
		if (a6.fixed) continue;
		a6.x += (W / 2 - cx) * 0.08;
		a6.y += (H / 2 - cy) * 0.08;
	}
	// 积分：位移 = 合力方向 × min(合力, 2.5) × 温度（无速度累积 → 无爆发）；
	// 硬重叠时位移不低于 min(hard, 3)，保证即使温度已冷却也必然分开
	var maxMove = 0, hardAny = false;
	for (var i3 = 0; i3 < n; i3++) {
		var p = arr[i3];
		if (p.fixed) continue;
		if (p.hard > 0.5) hardAny = true;
		var mag = Math.sqrt(p.fx * p.fx + p.fy * p.fy);
		if (mag <= 0) continue;
		var step = Math.min(mag, 2.5) * sim.temp;
		if (p.hard > 0) {
			var hs = Math.min(p.hard, 3);
			if (hs > step) step = hs;
		}
		p.x += (p.fx / mag) * step;
		p.y += (p.fy / mag) * step;
		if (step > maxMove) maxMove = step;
	}
	sim.hardAny = hardAny;
	// DOM 应用
	sim.nodeEls.forEach(function (item) {
		var p = sim.pos[item.n.id];
		if (p) item.g.setAttribute("transform", "translate(" + p.x.toFixed(1) + "," + p.y.toFixed(1) + ")");
	});
	sim.edgeEls.forEach(function (item) {
		var a = sim.pos[item.e.source], b = sim.pos[item.e.target];
		if (a && b) {
			item.line.setAttribute("x1", a.x.toFixed(1));
			item.line.setAttribute("y1", a.y.toFixed(1));
			item.line.setAttribute("x2", b.x.toFixed(1));
			item.line.setAttribute("y2", b.y.toFixed(1));
		}
	});
	if (sim.drag) {
		sim.stableFrames = 0;
	} else if (maxMove < 0.3) {
		sim.stableFrames++;
		if (sim.stableFrames > 40) { sim.running = false; return; }
	} else {
		sim.stableFrames = 0;
	}
}

function EventGraphTab(props) {
	var _e0 = useState(null), data = _e0[0], setData = _e0[1];
	var _e1 = useState(true), loading = _e1[0], setLoading = _e1[1];
	var _e2 = useState({}), expanded = _e2[0], setExpanded = _e2[1];
	var _e3 = useState(null), selected = _e3[0], setSelected = _e3[1];
	var _e4 = useState(""), navQuery = _e4[0], setNavQuery = _e4[1];
	var _e5 = useState(0), layoutKey = _e5[0], setLayoutKey = _e5[1];
	var _e6 = useState(true), showEntity = _e6[0], setShowEntity = _e6[1];
	var _e7 = useState(true), showIsolated = _e7[0], setShowIsolated = _e7[1];
	var _e8 = useState(true), navOpen = _e8[0], setNavOpen = _e8[1];

	var load = useCallback(function () {
		setLoading(true);
		api.get("graph").then(function (d) { setData(d); }).catch(function (err) {
			setData({ error: String((err && err.message) || err) });
		}).finally(function () { setLoading(false); });
	}, []);
	useEffect(function () { load(); }, [load, props.refreshKey]);

	// 树构建：链=父，事件卡按 belongs 边归入（wiki 归知识图谱，不在此）
	var tree = useMemo(function () {
		if (!data || !data.nodes) return null;
		var parentOf = {};
		(data.edges || []).forEach(function (e) { if (e.kind === "belongs") parentOf[e.target] = e.source; });
		var chains = [], loose = [], others = [];
		(data.nodes || []).forEach(function (n) {
			if (n.kind === "chain") chains.push(n);
			else if (n.kind === "event" && !parentOf[n.id]) loose.push(n);
			else if (n.kind.indexOf("wiki:") !== 0) others.push(n);
		});
		var byTime = function (a, b) { return (a.created_at || "").localeCompare(b.created_at || ""); };
		chains.forEach(function (ch) {
			ch.kids = (data.nodes || []).filter(function (n) { return parentOf[n.id] === ch.id; }).sort(byTime);
		});
		chains.sort(function (a, b) { return (b.kids ? b.kids.length : 0) - (a.kids ? a.kids.length : 0); });
		loose.sort(byTime);
		others.sort(byTime);
		return { chains: chains, loose: loose, others: others, parentOf: parentOf };
	}, [data]);

	// 图谱过滤（事件记忆：排除 wiki）
	var gNodes = useMemo(function () {
		if (!data || !data.nodes) return [];
		var connected = {};
		(data.edges || []).forEach(function (e) { connected[e.source] = 1; connected[e.target] = 1; });
		return (data.nodes || []).filter(function (n) {
			if (n.kind.indexOf("wiki:") === 0) return false;
			if (!showIsolated && !connected[n.id]) return false;
			return true;
		});
	}, [data, showIsolated]);
	var gEdges = useMemo(function () {
		if (!data || !data.edges) return [];
		var keep = {};
		gNodes.forEach(function (n) { keep[n.id] = 1; });
		return (data.edges || []).filter(function (e) {
			if (e.kind === "entity" && !showEntity) return false;
			return keep[e.source] && keep[e.target];
		});
	}, [data, showEntity, gNodes]);

	// 联动①：点图 → 树自动展开到所属链
	var onGraphSelect = function (id) {
		setSelected(id);
		if (tree && tree.parentOf[id]) {
			setExpanded(function (prev) {
				var next = {};
				Object.keys(prev).forEach(function (k) { next[k] = prev[k]; });
				next[tree.parentOf[id]] = true;
				return next;
			});
		}
	};

	// 联动②：点树 → 图谱聚焦（选中即高亮邻居）；链行点击 = 切换收折
	var toggle = function (id) {
		setExpanded(function (prev) {
			var next = {};
			Object.keys(prev).forEach(function (k) { next[k] = prev[k]; });
			// 当前态：显式 false=收，显式 true=展，undefined=跟随聚焦默认（展开）
			var cur = prev[id] === false ? false : true;
			next[id] = !cur;
			return next;
		});
		setSelected(id);
	};

	var q = navQuery.trim().toLowerCase();
	var renderLeaf = function (n) {
		var active = selected === n.id;
		return h("div", { key: n.id, className: "dmb-tree-item dmb-tree-leaf" + (active ? " active" : ""), onClick: function () { setSelected(n.id); } },
			h("div", { className: "dmb-tree-row" },
				h("span", { className: "dmb-tree-dot", style: { background: GRAPH_KIND_COLOR[n.kind] || "var(--dmb-text3)" } }),
				h("span", { className: "dmb-tree-title", title: n.title }, n.title),
				h("span", { className: "dmb-tree-time" }, (n.created_at || "").slice(5, 10))
			)
		);
	};
	var renderChain = function (ch) {
		// 聚焦/搜索时默认展开，但允许手动收折（expanded 显式 false 优先）
		var isOpen = expanded[ch.id] === false ? false : ((q || focusNode) ? true : !!expanded[ch.id]);
		var kids = ch.kids || [];
		return h("div", { key: ch.id, className: "dmb-tree-item dmb-tree-chain" },
			h("div", { className: "dmb-tree-row" + (selected === ch.id ? " active" : ""), onClick: function () { toggle(ch.id); } },
				h("span", { className: "dmb-tree-arrow" + (isOpen ? " open" : "") }, "▸"),
				h("span", { className: "dmb-tree-dot", style: { background: GRAPH_KIND_COLOR.chain } }),
				h("span", { className: "dmb-tree-title", title: ch.title }, ch.title),
				h("span", { className: "dmb-tree-badge" }, kids.length)
			),
			isOpen && kids.length ? h("div", { className: "dmb-tree-kids" }, kids.map(renderLeaf)) : null
		);
	};

	if (loading && !data) return h("div", { className: "dmb-empty" }, h("div", { className: "dmb-spinner" }));
	if (data && data.error) return h("div", { className: "dmb-empty" }, "事件图谱加载失败：" + data.error);
	if (!data || !tree) return null;

	var counts = data.counts || {};
	// 按图搜索联动：点图选中节点 → 树只显示相关事件（所属链 + 子卡，或未归类/经验画像单节点）
	var focusNode = null;
	if (selected && data.nodes) {
		for (var _fi = 0; _fi < data.nodes.length; _fi++) {
			if (data.nodes[_fi].id === selected) { focusNode = data.nodes[_fi]; break; }
		}
	}
	var navChains, navLoose, navOthers;
	if (q) {
		navChains = tree.chains.map(function (ch) {
			var kids = (ch.kids || []).filter(function (n) { return (n.title || "").toLowerCase().indexOf(q) >= 0; });
			return (((ch.title || "").toLowerCase().indexOf(q) >= 0) || kids.length) ? { ...ch, kids: kids } : null;
		}).filter(Boolean);
		navLoose = tree.loose.filter(function (n) { return (n.title || "").toLowerCase().indexOf(q) >= 0; });
		navOthers = tree.others.filter(function (n) { return (n.title || "").toLowerCase().indexOf(q) >= 0; });
	} else if (focusNode) {
		if (focusNode.kind === "chain") {
			navChains = tree.chains.filter(function (c) { return c.id === focusNode.id; });
			navLoose = [];
			navOthers = [];
		} else if (focusNode.kind === "event") {
			var _pc = tree.parentOf[focusNode.id];
			if (_pc) {
				navChains = tree.chains.filter(function (c) { return c.id === _pc; });
				navLoose = [];
				navOthers = [];
			} else {
				navChains = [];
				navLoose = [focusNode];
				navOthers = [];
			}
		} else {
			navChains = [];
			navLoose = [];
			navOthers = [focusNode];
		}
	} else {
		navChains = tree.chains;
		navLoose = tree.loose;
		navOthers = tree.others;
	}

	return h("div", { className: "dmb-fade" },
		h("div", { className: "dmb-graph-toolbar" },
			h("span", { className: "dmb-hint" }, "共 " + counts.cards + " 卡 · " + counts.chains + " 链 · " + counts.edges + " 关联"),
			h("div", { className: "grow" }),
			h("label", { className: "dmb-check" }, h("input", { type: "checkbox", checked: showEntity, onChange: function (e) { setShowEntity(e.target.checked); } }), "实体关联"),
			h("label", { className: "dmb-check" }, h("input", { type: "checkbox", checked: showIsolated, onChange: function (e) { setShowIsolated(e.target.checked); } }), "孤立节点"),
			h("button", { className: "dmb-btn", onClick: function () { setLayoutKey(function (k) { return k + 1; }); } }, "重新布局")
		),
		h("div", { className: "dmb-eg-main" },
			h(GraphCanvas, { nodes: gNodes, edges: gEdges, selected: selected, onSelect: onGraphSelect, layoutKey: layoutKey })
		),
		h("div", { className: "dmb-eg-nav" },
			h("div", { className: "dmb-eg-nav-head" },
				h("span", { className: "dmb-hint" }, focusNode ? "相关事件：聚焦 " + focusNode.title : "记忆树 · 点击聚焦图谱"),
				h("div", { className: "grow" }),
				focusNode ? h("button", { className: "dmb-btn", onClick: function () { setSelected(null); }, title: "显示全部" }, "✕ 清除") : null,
				h("button", { className: "dmb-btn", onClick: function () { setNavOpen(!navOpen); }, title: navOpen ? "收起导航" : "展开导航" }, navOpen ? "▼ 收起" : "▲ 展开")
			),
			navOpen ? h("div", { className: "dmb-eg-nav-body" },
				h("input", { className: "dmb-nav-search", value: navQuery, placeholder: "过滤树…", onChange: function (e) { setNavQuery(e.target.value); } }),
				h("div", { className: "dmb-tree-wrap dmb-eg-tree" },
					navChains.map(renderChain),
					navLoose.length ? h("div", { key: "g-loose" }, h("div", { className: "dmb-tree-group" }, "未归类"), navLoose.map(renderLeaf)) : null,
					navOthers.length ? h("div", { key: "g-other" }, h("div", { className: "dmb-tree-group" }, "经验画像"), navOthers.map(renderLeaf)) : null
				)
			) : null
		)
	);
}

/* timeline tab: 时间倒序事件流 */
function TimelineTab(props) {
	var _l0 = useState(null), data = _l0[0], setData = _l0[1];
	var _l1 = useState(true), loading = _l1[0], setLoading = _l1[1];
	var _l2 = useState(null), selected = _l2[0], setSelected = _l2[1];
	var _l3 = useState(null), detail = _l3[0], setDetail = _l3[1];

	var load = useCallback(function () {
		setLoading(true);
		api.get("browse", { limit: 200 }).then(function (d) { setData(d); }).catch(function (err) {
			setData({ error: String((err && err.message) || err) });
		}).finally(function () { setLoading(false); });
	}, []);
	useEffect(function () { load(); }, [load, props.refreshKey]);

	useEffect(function () {
		if (!selected) { setDetail(null); return; }
		setDetail(null);
		var stale = false;
		api.get("card", { id: selected }).then(function (d) {
			if (!stale) setDetail(d.card || null);
		}).catch(function () { if (!stale) setDetail(null); });
		return function () { stale = true; };
	}, [selected]);

	// 按日期分组、时间倒序（事件流）
	var groups = useMemo(function () {
		if (!data || !data.cards) return [];
		var list = (data.cards || []).filter(function (c) {
			return c.kind === "event" || c.kind === "lesson_pending" || c.kind === "lesson_permanent";
		});
		list.sort(function (a, b) { return (b.createdAt || "").localeCompare(a.createdAt || ""); });
		var map = {}, order = [];
		list.forEach(function (c) {
			var day = (c.createdAt || "").slice(0, 10);
			if (!map[day]) { map[day] = []; order.push(day); }
			map[day].push(c);
		});
		return order.map(function (day) { return { day: day, items: map[day] }; });
	}, [data]);

	if (loading && !data) return h("div", { className: "dmb-empty" }, h("div", { className: "dmb-spinner" }));
	if (data && data.error) return h("div", { className: "dmb-empty" }, "时间线加载失败：" + data.error);
	if (!data) return null;

	var today = new Date().toISOString().slice(0, 10);
	var dayLabel = function (day) {
		if (day === today) return "今天";
		var y = new Date(day + "T00:00:00");
		var t = new Date(today + "T00:00:00");
		var diff = Math.round((t - y) / 86400000);
		if (diff === 1) return "昨天";
		if (diff > 1 && diff < 7) return diff + " 天前";
		return day;
	};

	var side = null;
	if (detail) {
		var rows = [];
		var pushRow = function (k, v) { if (v !== undefined && v !== null && v !== "") rows.push(h("div", { key: k }, h("span", { className: "k" }, k), h("span", { className: "v" }, String(v)))); };
		pushRow("创建", (detail.createdAt || "").slice(0, 19));
		pushRow("链", detail.chainTitle || "");
		pushRow("来源", detail.sourcePart || "");
		pushRow("证据", detail.evidence || "");
		pushRow("路径", detail.sourcePath || "");
		if (detail.content) rows.push(h("div", { key: "content", style: { gridColumn: "1 / -1" } }, h("span", { className: "k" }, "内容"), h("span", { className: "v" }, detail.content)));
		side = h("div", { className: "dmb-graph-side" },
			h("h4", null, h("span", { className: "dmb-kind " + (detail.kind || "") }, KIND_LABEL[detail.kind] || detail.kind || ""), detail.title || ""),
			h("div", { className: "meta" }, rows),
			h("div", { className: "dmb-actions" }, h("button", { className: "dmb-btn", onClick: function () { setDetail(null); setSelected(null); } }, "关闭"))
		);
	}

	return h("div", { className: "dmb-fade" },
		groups.length === 0 ? h(Empty, null, "暂无事件") : groups.map(function (g) {
			return h("div", { key: g.day },
				h("div", { className: "dmb-tl-day" }, dayLabel(g.day)),
				g.items.map(function (c) {
					return h("div", { key: c.id, className: "dmb-tl-item" + (selected === c.id ? " active" : ""), onClick: function () { setSelected(c.id); } },
						h("span", { className: "dmb-tree-dot", style: { background: KIND_COLOR[c.kind] || "var(--dmb-text3)" } }),
						h("div", { style: { flex: 1, minWidth: 0 } },
							h("div", { className: "t" }, c.title || c.id),
							c.content ? h("div", { className: "c" }, c.content) : null,
							h("div", { className: "m" },
								h("span", null, KIND_LABEL[c.kind] || c.kind),
								c.chainTitle ? h("span", null, "链 · " + c.chainTitle) : null,
								h("span", null, (c.createdAt || "").slice(11, 16))
							)
						)
					);
				})
			);
		}),
		side
	);
}

/* knowledge graph tab: wiki 力导向图 + 搜索 + 条目列表 */
function WikiGraphTab(props) {
	var _w0 = useState(null), data = _w0[0], setData = _w0[1];
	var _w1 = useState(true), loading = _w1[0], setLoading = _w1[1];
	var _w2 = useState(""), query = _w2[0], setQuery = _w2[1];
	var _w3 = useState(null), selected = _w3[0], setSelected = _w3[1];
	var _w4 = useState(0), layoutKey = _w4[0], setLayoutKey = _w4[1];

	var load = useCallback(function () {
		setLoading(true);
		api.get("graph").then(function (d) { setData(d); }).catch(function (err) {
			setData({ error: String((err && err.message) || err) });
		}).finally(function () { setLoading(false); });
	}, []);
	useEffect(function () { load(); }, [load, props.refreshKey]);

	var wNodes = useMemo(function () {
		if (!data || !data.nodes) return [];
		var q = query.trim().toLowerCase();
		return (data.nodes || []).filter(function (n) {
			if (n.kind.indexOf("wiki:") !== 0) return false;
			if (q && (n.title || "").toLowerCase().indexOf(q) < 0) return false;
			return true;
		});
	}, [data, query]);
	var wEdges = useMemo(function () {
		if (!data || !data.edges) return [];
		var keep = {};
		wNodes.forEach(function (n) { keep[n.id] = 1; });
		return (data.edges || []).filter(function (e) {
			if (e.kind === "belongs" || e.kind === "entity") return false;  // 事件关系不适用
			return keep[e.source] && keep[e.target];
		});
	}, [data, wNodes]);

	var wikiList = useMemo(function () {
		if (!data || !data.nodes) return [];
		var q = query.trim().toLowerCase();
		return (data.nodes || []).filter(function (n) {
			if (n.kind.indexOf("wiki:") !== 0) return false;
			if (q && (n.title || "").toLowerCase().indexOf(q) < 0) return false;
			return true;
		}).sort(function (a, b) { return (a.title || "").localeCompare(b.title || ""); });
	}, [data, query]);

	if (loading && !data) return h("div", { className: "dmb-empty" }, h("div", { className: "dmb-spinner" }));
	if (data && data.error) return h("div", { className: "dmb-empty" }, "知识图谱加载失败：" + data.error);
	if (!data) return null;

	var side = null;
	if (selected) {
		var node = null;
		for (var i = 0; i < (data.nodes || []).length; i++) {
			if (data.nodes[i].id === selected) { node = data.nodes[i]; break; }
		}
		if (node) {
			var rows = [];
			var pushRow = function (k, v) { if (v !== undefined && v !== null && v !== "") rows.push(h("div", { key: k }, h("span", { className: "k" }, k), h("span", { className: "v" }, String(v)))); };
			pushRow("类型", GRAPH_KIND_LABEL[node.kind] || node.kind);
			pushRow("状态", node.status);
			pushRow("创建", (node.created_at || "").slice(0, 10));
			pushRow("路径", node.source_path);
			side = h("div", { className: "dmb-graph-side" },
				h("h4", null, h("span", { className: "dmb-kind " + node.kind.replace(":", "-") }, GRAPH_KIND_LABEL[node.kind] || node.kind), node.title),
				h("div", { className: "meta" }, rows),
				h("div", { className: "dmb-actions" }, h("button", { className: "dmb-btn", onClick: function () { setSelected(null); } }, "关闭"))
			);
		}
	}

	return h("div", { className: "dmb-fade" },
		h("div", { className: "dmb-graph-toolbar" },
			h("span", { className: "dmb-hint" }, "知识条目 " + wikiList.length + " 条"),
			h("div", { className: "grow" }),
			h("button", { className: "dmb-btn", onClick: function () { setLayoutKey(function (k) { return k + 1; }); } }, "重新布局")
		),
		h("div", { className: "dmb-search" },
			h("span", { className: "mag" }, "🔍"),
			h("input", { value: query, placeholder: "搜索知识…", onChange: function (e) { setQuery(e.target.value); } })
		),
		h(GraphCanvas, { nodes: wNodes, edges: wEdges, selected: selected, onSelect: setSelected, layoutKey: layoutKey }),
		wikiList.length ? h("div", { className: "dmb-wg-list" }, wikiList.map(function (n) {
			return h("div", { key: n.id, className: "dmb-wg-item" + (selected === n.id ? " active" : ""), onClick: function () { setSelected(n.id); } },
				h("span", { className: "dmb-tree-dot", style: { background: GRAPH_KIND_COLOR[n.kind] } }), " ", n.title);
		})) : h(Empty, null, "暂无知识条目（知识问答会沉淀到此处）"),
		side
	);
}
function Sparks(props) {
	var data = props.data || [];
	if (data.length < 2) return h("div", { className: "dmb-empty" }, "活动数据不足");
	var W = 560, H = 90, pad = 4, n = data.length;
	var colors = { inject_hit: "var(--dmb-accent)", inject_used: "var(--dmb-ok)", inject_unused: "var(--dmb-warn)", extract_runs: "var(--dmb-accent2)", extract_skip: "var(--dmb-text3)", lemonade_start: "var(--dmb-warn)", lemonade_load: "var(--dmb-warn)", local_backend_ready: "var(--dmb-ok)", decay: "var(--dmb-accent2)", govern_action: "var(--dmb-warn)", extract_done: "var(--dmb-accent2)", extract_cost: "var(--dmb-text3)" };
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

