"""Global CSS for the Quant Engine dashboard."""

GLOBAL_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600&display=swap');

[data-testid="stHeader"]  { display: none !important; }
[data-testid="stToolbar"] { display: none !important; }
.stDeployButton           { display: none !important; }
footer                    { visibility: hidden !important; }

.block-container { max-width: 1200px !important; padding: 1.5rem 2rem !important; }
html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif; }

/* ── Cards ──────────────────────────────────────────── */
.qt-card { background:#0f1419; border:1px solid #1c2333; border-radius:4px;
           padding:14px 18px; margin-bottom:10px; }
.qt-section-label { font-size:10px; font-weight:600; text-transform:uppercase;
                    letter-spacing:.1em; color:#384352; margin-bottom:6px;
                    font-family:'IBM Plex Sans',sans-serif; }

/* ── Chips ──────────────────────────────────────────── */
.qt-chip { display:inline-block; padding:2px 7px; border-radius:3px; font-size:10px;
           font-weight:600; letter-spacing:.06em; text-transform:uppercase;
           font-family:'JetBrains Mono',monospace; }
.qt-chip-buy    { background:rgba(0,200,150,.15); color:#00c896; }
.qt-chip-warn   { background:rgba(232,160,32,.15); color:#e8a020; }
.qt-chip-limit  { background:rgba(232,49,74,.15);  color:#e8314a; }
.qt-chip-pass   { background:rgba(77,158,247,.15); color:#4d9ef7; }
.qt-chip-skip   { background:rgba(45,55,72,.6);    color:#68788f; }
.qt-chip-hold   { background:rgba(45,55,72,.3);    color:#4a5568; }
.qt-bucket-gr   { background:rgba(0,200,150,.1);   color:#00c896; }
.qt-bucket-st   { background:rgba(77,158,247,.1);  color:#4d9ef7; }
.qt-bucket-dv   { background:rgba(232,160,32,.1);  color:#e8a020; }

/* ── Regime badge ───────────────────────────────────── */
.qt-regime { border-radius:4px; padding:14px 18px; margin-bottom:10px;
             border-left:3px solid; }
.qt-regime-name { font-family:'JetBrains Mono',monospace; font-size:26px;
                  font-weight:600; letter-spacing:.05em; margin:0 0 6px 0; }
.qt-regime-meta { font-size:11px; color:#68788f; font-family:'JetBrains Mono',monospace; }

/* ── CRA counter ────────────────────────────────────── */
.qt-cra-count { font-family:'JetBrains Mono',monospace; font-size:20px;
                font-weight:600; color:#dce6f0; margin-bottom:6px; }
.qt-cra-bar   { display:flex; gap:2px; margin-top:4px; }
.qt-cra-seg   { height:5px; flex:1; border-radius:1px; }

/* ── Recommendation cards ───────────────────────────── */
.qt-rec { background:#0f1419; border:1px solid #1c2333; border-left:3px solid;
          border-radius:4px; padding:14px 18px; margin-bottom:8px; }
.qt-rec-buy  { border-left-color:#00c896; background:rgba(0,200,150,.025); }
.qt-rec-warn { border-left-color:#e8a020; background:rgba(232,160,32,.025); }
.qt-rec-hold { border-left-color:#1c2333; }
.qt-rec-header { display:flex; align-items:center; gap:10px; margin-bottom:10px; }
.qt-ticker { font-family:'JetBrains Mono',monospace; font-size:17px;
             font-weight:600; color:#dce6f0; }
.qt-rec-id { font-family:'JetBrains Mono',monospace; font-size:11px; color:#2d3748; }
.qt-rec-grid { display:grid; grid-template-columns:1fr 1fr 1fr; gap:8px 16px; }
.qt-field    { display:flex; flex-direction:column; }
.qt-lbl  { font-size:10px; color:#68788f; text-transform:uppercase;
           letter-spacing:.05em; margin-bottom:2px; }
.qt-val  { font-family:'JetBrains Mono',monospace; font-size:13px; color:#dce6f0; }
.qt-val-buy  { color:#00c896; }
.qt-val-warn { color:#e8a020; }
.qt-val-dim  { color:#2d3748; }
.qt-rec-footer { margin-top:10px; padding-top:8px; border-top:1px solid #1c2333;
                 font-family:'JetBrains Mono',monospace; font-size:11px; color:#2d3748; }

/* ── Scorecard table ────────────────────────────────── */
.qt-table { width:100%; border-collapse:collapse; font-size:13px;
            font-family:'IBM Plex Sans',sans-serif; }
.qt-table th { text-align:left; color:#68788f; font-size:10px; text-transform:uppercase;
               letter-spacing:.06em; padding:0 8px 8px 0; border-bottom:1px solid #1c2333;
               font-weight:500; }
.qt-table td { padding:7px 8px 7px 0; border-bottom:1px solid #111820;
               color:#dce6f0; vertical-align:middle; }
.qt-table tr:last-child td { border-bottom:none; }
.qt-mono { font-family:'JetBrains Mono',monospace; }
.qt-pos  { font-family:'JetBrains Mono',monospace; color:#00c896; }
.qt-neg  { font-family:'JetBrains Mono',monospace; color:#e8314a; }
.qt-dim  { font-family:'JetBrains Mono',monospace; color:#2d3748; }
.qt-bold { font-weight:600; }

/* ── Holdings / empty state ─────────────────────────── */
.qt-empty { color:#384352; font-size:13px; padding:16px 0;
            font-family:'IBM Plex Sans',sans-serif; }

/* ── Warning banner ─────────────────────────────────── */
.qt-warn-banner { background:rgba(232,160,32,.08); border:1px solid rgba(232,160,32,.25);
                  border-left:3px solid #e8a020; border-radius:4px; padding:10px 14px;
                  margin-bottom:14px; font-size:13px; color:#e8a020;
                  font-family:'IBM Plex Sans',sans-serif; }
.qt-warn-banner code { background:rgba(232,160,32,.15); padding:1px 5px; border-radius:2px;
                       font-family:'JetBrains Mono',monospace; font-size:12px; }
</style>
"""
