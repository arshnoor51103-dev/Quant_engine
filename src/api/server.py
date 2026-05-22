"""
FastAPI server for the Quant Engine dashboard.

# Retained as API backend layer. Superseded as primary
# UI by Streamlit dashboard but kept for future external
# access. Do not delete.

Serves portfolio data, metrics, and signals over HTTP.
Local access only by default. Add Tailscale/ngrok for phone access.

Endpoints:
    GET /api/universe     — list of ETFs with metadata
    GET /api/metrics      — risk/return metrics for all tickers
    GET /api/signals      — current signal scores
    GET /api/status       — portfolio NAV, holdings, bucket drift
    GET /api/backtest     — run a backtest and return results
    GET /                 — serve the dashboard HTML
"""
from __future__ import annotations

from datetime import date, timedelta
from functools import lru_cache

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from ..data.ingest import load_universe
from ..portfolio.model import (
    bucket_allocation,
    get_holdings,
    nav,
    price_series,
)
from ..portfolio import metrics as m
from ..signals.momentum import MomentumSignal
from ..signals.vol_regime import VolRegimeSignal

app = FastAPI(title="Quant Engine", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # local dev only — lock down for prod
    allow_methods=["*"],
    allow_headers=["*"],
)


@lru_cache(maxsize=1)
def _cached_universe() -> list:
    return load_universe()


def _load_prices(lookback: int = 1260) -> dict:
    """Helper: load price series for all tickers."""
    prices = {}
    for a in _cached_universe():
        ps = price_series(a["ticker"], lookback_days=lookback)
        if not ps.empty:
            prices[a["ticker"]] = ps
    return prices


@app.get("/api/universe")
def get_universe():
    return _cached_universe()


@app.get("/api/metrics")
def get_metrics(lookback: int = Query(1260, description="Lookback in trading days")):
    universe = _cached_universe()
    results = []
    for a in universe:
        ps = price_series(a["ticker"], lookback_days=lookback)
        if ps.empty:
            results.append({"ticker": a["ticker"], "error": "no data"})
            continue
        rets = m.daily_returns(ps)
        s = m.summary(rets)
        s["ticker"] = a["ticker"]
        s["bucket"] = a["bucket"]
        s["name"] = a["name"]
        results.append(s)
    return results


@app.get("/api/signals")
def get_signals(signal_type: str = Query("momentum")):
    signal_map = {
        "momentum": MomentumSignal(),
        "vol_regime": VolRegimeSignal(),
    }
    sig = signal_map.get(signal_type)
    if not sig:
        return {"error": f"Unknown signal: {signal_type}"}
    prices = _load_prices(sig.lookback_days)
    result = sig.generate(prices)
    return {
        "signal_name": result.signal_name,
        "run_date": result.run_date.isoformat(),
        "scores": result.scores,
        "metadata": result.metadata,
    }


@app.get("/api/status")
def get_status():
    holdings = get_holdings()
    return {
        "nav": nav(holdings),
        "holdings": [
            {
                "ticker": h.ticker,
                "units": h.units,
                "avg_cost": h.avg_cost,
                "bucket": h.bucket,
                "last_price": h.last_price,
                "market_value": h.market_value,
                "unrealized_pnl": h.unrealized_pnl,
            }
            for h in holdings
        ],
        "bucket_allocation": bucket_allocation(holdings),
    }


@app.get("/", response_class=HTMLResponse)
def dashboard():
    """Serve the Bloomberg-terminal-style dashboard."""
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>QUANT ENGINE · TFSA</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;700&display=swap" rel="stylesheet">
<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; border-radius: 0; }

:root {
  --bg:          #07090d;
  --bg-panel:    #0b0e14;
  --bg-row:      #0e1218;
  --bg-hover:    #131820;
  --border:      #1a2230;
  --border-dim:  #111820;
  --text:        #b8c8d8;
  --text-bright: #ddeeff;
  --text-dim:    #3a5060;
  --text-muted:  #222e3a;
  --amber:       #f5c518;
  --amber-dim:   #7a6010;
  --green:       #00c97a;
  --green-dim:   #005535;
  --red:         #f04747;
  --red-dim:     #6a2020;
  --orange:      #e07830;
  --orange-dim:  #6a3510;
  --cyan:        #40a8c8;
  --font: 'JetBrains Mono', 'Courier New', monospace;
}

html, body {
  height: 100%;
  background: var(--bg);
  color: var(--text);
  font-family: var(--font);
  font-size: 12px;
  line-height: 1.5;
  overflow-x: hidden;
}

/* CRT scanline overlay */
body::after {
  content: '';
  position: fixed;
  inset: 0;
  background: repeating-linear-gradient(
    0deg, transparent, transparent 2px,
    rgba(0,0,0,0.06) 2px, rgba(0,0,0,0.06) 4px
  );
  pointer-events: none;
  z-index: 9999;
}

/* ── HEADER ─────────────────────────────────────────── */
#header {
  display: flex;
  align-items: stretch;
  background: var(--bg-panel);
  border-bottom: 1px solid var(--amber-dim);
  position: sticky;
  top: 0;
  z-index: 100;
  height: 40px;
}

.h-cell {
  display: flex;
  align-items: center;
  padding: 0 20px;
  border-right: 1px solid var(--border);
}

.h-cell:last-child { border-right: none; margin-left: auto; }

.brand {
  font-size: 13px;
  font-weight: 700;
  color: var(--amber);
  letter-spacing: 3px;
}

.brand-cursor {
  display: inline-block;
  width: 8px;
  height: 14px;
  background: var(--amber);
  margin-left: 3px;
  vertical-align: middle;
  animation: blink 1.1s step-end infinite;
}

@keyframes blink { 0%,100%{opacity:1} 50%{opacity:0} }

.h-tag {
  font-size: 9px;
  letter-spacing: 2px;
  color: var(--text-dim);
  text-transform: uppercase;
}

.live-pip {
  width: 6px; height: 6px;
  border-radius: 50%;
  background: var(--green);
  margin-right: 8px;
  animation: livepulse 2.4s ease-in-out infinite;
  flex-shrink: 0;
}

@keyframes livepulse {
  0%,100%{ opacity:1; box-shadow:0 0 5px var(--green); }
  50%{ opacity:0.35; box-shadow:none; }
}

#clock {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-bright);
  letter-spacing: 1px;
  min-width: 75px;
}

/* ── CONTENT ─────────────────────────────────────────── */
#app {
  display: flex;
  flex-direction: column;
  gap: 1px;
  background: var(--border-dim);
  min-height: calc(100vh - 40px - 28px);
}

/* ── REGIME BANNER ───────────────────────────────────── */
#regime-row {
  display: flex;
  align-items: stretch;
  background: var(--bg-panel);
  min-height: 52px;
}

.regime-section-tag {
  display: flex;
  align-items: center;
  padding: 0 18px;
  font-size: 8px;
  font-weight: 700;
  letter-spacing: 3px;
  text-transform: uppercase;
  color: var(--text-dim);
  border-right: 1px solid var(--border);
  white-space: nowrap;
  min-width: 110px;
}

#regime-pill {
  display: flex;
  align-items: center;
  padding: 0 24px;
  font-size: 15px;
  font-weight: 700;
  letter-spacing: 5px;
  text-transform: uppercase;
  border-right: 1px solid var(--border);
  min-width: 170px;
  transition: color 0.4s;
}

#regime-meta-row {
  display: flex;
  align-items: center;
  padding: 0 24px;
  gap: 36px;
  flex: 1;
}

.rmeta {
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.rmeta-label {
  font-size: 8px;
  letter-spacing: 2px;
  color: var(--text-dim);
  text-transform: uppercase;
}

.rmeta-value {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-bright);
}

#regime-posture {
  margin-left: auto;
  display: flex;
  align-items: center;
  padding-right: 20px;
  font-size: 9px;
  letter-spacing: 3px;
  font-weight: 700;
  text-transform: uppercase;
}

/* Regime colours */
.r-low_vol  { color: var(--green);  border-color: var(--green-dim) !important; }
.r-normal   { color: var(--amber);  border-color: var(--amber-dim) !important; }
.r-high_vol { color: var(--orange); border-color: var(--orange-dim) !important; }
.r-crisis   { color: var(--red);    border-color: var(--red-dim) !important; }
.r-unknown  { color: var(--text-dim); }

/* ── PANELS ──────────────────────────────────────────── */
#panels {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1px;
  background: var(--border-dim);
  flex: 1;
}

.panel {
  background: var(--bg-panel);
  display: flex;
  flex-direction: column;
}

.panel-hdr {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 18px;
  border-bottom: 1px solid var(--border);
  background: var(--bg-row);
  flex-shrink: 0;
}

.panel-title {
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 3px;
  color: var(--amber);
  text-transform: uppercase;
}

.panel-sub {
  font-size: 8px;
  letter-spacing: 1px;
  color: var(--text-dim);
  text-transform: uppercase;
}

/* ── DATA TABLE ──────────────────────────────────────── */
.dt {
  width: 100%;
  border-collapse: collapse;
}

.dt th {
  padding: 6px 18px;
  text-align: right;
  font-size: 8px;
  font-weight: 400;
  letter-spacing: 2px;
  text-transform: uppercase;
  color: var(--text-dim);
  border-bottom: 1px solid var(--border-dim);
  background: var(--bg-row);
  white-space: nowrap;
}

.dt th.left { text-align: left; }

.dt td {
  padding: 7px 18px;
  text-align: right;
  font-size: 12px;
  border-bottom: 1px solid var(--border-dim);
  color: var(--text);
  white-space: nowrap;
  transition: background 0.08s;
}

.dt td.left { text-align: left; }
.dt tr:last-child td { border-bottom: none; }
.dt tbody tr:hover td { background: var(--bg-hover); }

.ticker-cell { color: var(--amber); font-weight: 500; letter-spacing: 1px; font-size: 11px; }
.bucket-tag  { font-size: 8px; color: var(--text-muted); margin-left: 8px; letter-spacing: 1px; }
.rank-cell   { color: var(--text-muted); font-size: 10px; width: 28px; text-align: center; }

/* score bar */
.score-wrap { display: flex; align-items: center; gap: 10px; justify-content: flex-end; }
.score-num  { min-width: 54px; text-align: right; font-weight: 500; }
.bar-track  { width: 72px; height: 2px; background: var(--border); flex-shrink: 0; overflow: hidden; }
.bar-fill   { height: 100%; transition: width 0.5s ease; }

/* signal label */
.sig-tag {
  font-size: 8px;
  letter-spacing: 1px;
  text-transform: uppercase;
  padding: 2px 6px;
  font-weight: 700;
}

/* numeric colouring */
.pos { color: var(--green); }
.neg { color: var(--red); }
.neu { color: var(--text); }
.dim { color: var(--text-dim); }

/* loading / error */
.loading-cell {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 32px;
  color: var(--text-muted);
  font-size: 9px;
  letter-spacing: 3px;
  text-transform: uppercase;
  animation: blink 1.2s step-end infinite;
}

.error-cell {
  padding: 16px 18px;
  color: var(--red-dim);
  font-size: 10px;
  letter-spacing: 1px;
}

/* ── STATUS BAR ──────────────────────────────────────── */
#statusbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 5px 20px;
  background: var(--bg-panel);
  border-top: 1px solid var(--border-dim);
  font-size: 8px;
  letter-spacing: 1px;
  color: var(--text-muted);
  height: 28px;
}

.sb-items { display: flex; gap: 24px; }
.sb-item span { color: var(--text-dim); }
#last-update { color: var(--text-dim); }
</style>
</head>
<body>

<!-- ── HEADER ─────────────────────────────────────────── -->
<div id="header">
  <div class="h-cell">
    <div class="brand">◆ QUANT ENGINE<span class="brand-cursor"></span></div>
  </div>
  <div class="h-cell">
    <div class="h-tag">TFSA &middot; CAD &middot; TIER 1</div>
  </div>
  <div class="h-cell">
    <div class="h-tag">WEALTHSIMPLE</div>
  </div>
  <div class="h-cell">
    <div class="live-pip"></div>
    <div id="clock">--:--:--</div>
  </div>
</div>

<!-- ── APP ───────────────────────────────────────────── -->
<div id="app">

  <!-- REGIME BANNER -->
  <div id="regime-row">
    <div class="regime-section-tag">VOL REGIME</div>
    <div id="regime-pill" class="r-unknown">—</div>
    <div id="regime-meta-row">
      <div class="loading-cell" style="padding:0;animation:none;color:var(--text-dim);font-size:9px">FETCHING</div>
    </div>
    <div id="regime-posture"></div>
  </div>

  <!-- PANELS -->
  <div id="panels">

    <div class="panel">
      <div class="panel-hdr">
        <div class="panel-title">MOMENTUM SIGNAL</div>
        <div class="panel-sub">12M &ndash; 1M CROSS-SECTIONAL</div>
      </div>
      <div id="signals-wrap"><div class="loading-cell">LOADING</div></div>
    </div>

    <div class="panel">
      <div class="panel-hdr">
        <div class="panel-title">RISK / RETURN MATRIX</div>
        <div class="panel-sub">TRAILING 5YR</div>
      </div>
      <div id="metrics-wrap"><div class="loading-cell">LOADING</div></div>
    </div>

  </div>
</div>

<!-- ── STATUS BAR ─────────────────────────────────────── -->
<div id="statusbar">
  <div class="sb-items">
    <div class="sb-item"><span>ENGINE</span> v2.0</div>
    <div class="sb-item"><span>UNIVERSE</span> CANADIAN ETF</div>
    <div class="sb-item"><span>BENCHMARK</span> VBAL / VFV</div>
    <div class="sb-item"><span>AUTO-REFRESH</span> 60s</div>
  </div>
  <div id="last-update">&mdash;</div>
</div>

<script>
/* ── CLOCK ─────────────────────────────────────────────── */
function tick() {
  const n = new Date();
  const pad = x => String(x).padStart(2,'0');
  document.getElementById('clock').textContent =
    pad(n.getHours()) + ':' + pad(n.getMinutes()) + ':' + pad(n.getSeconds());
}
setInterval(tick, 1000);
tick();

/* ── HELPERS ────────────────────────────────────────────── */
function pct(v, d=1) { return v != null ? (v*100).toFixed(d)+'%' : '—'; }
function numCls(v)   { return v > 0.005 ? 'pos' : v < -0.005 ? 'neg' : 'neu'; }

function scoreMeta(s) {
  const color = s >= 0.7 ? '#00ff99' : s >= 0.3 ? '#00c97a' : s >= 0.05 ? '#559966' :
                s <= -0.7 ? '#ff3333' : s <= -0.3 ? '#f04747' : s <= -0.05 ? '#994444' : '#3a5060';
  const label = s >= 0.7 ? 'STR BUY' : s >= 0.3 ? 'BUY' : s >= 0.05 ? 'MILD' :
                s <= -0.7 ? 'STR SELL' : s <= -0.3 ? 'SELL' : s <= -0.05 ? 'MILD' : 'NEUTRAL';
  return { color, label };
}

/* ── REGIME ─────────────────────────────────────────────── */
async function loadRegime() {
  try {
    const d = await (await fetch('/api/signals?signal_type=vol_regime')).json();
    const regime  = d.metadata?.regime || 'unknown';
    const volPct  = d.metadata?.vol_percentile;
    const curVol  = d.metadata?.current_annualized_vol;
    const bench   = d.metadata?.benchmark || 'XIC.TO';

    const pill = document.getElementById('regime-pill');
    pill.textContent = regime.toUpperCase().replace(/_/g,' ');
    pill.className = 'r-' + regime;

    const posture = regime === 'low_vol' ? 'RISK-ON' : regime === 'normal' ? 'NEUTRAL' :
                    regime === 'high_vol' ? 'RISK-OFF' : regime === 'crisis' ? 'DEFENSIVE' : '';
    const postureEl = document.getElementById('regime-posture');
    postureEl.textContent = posture;
    postureEl.className = 'r-' + regime;
    postureEl.style.paddingRight = '20px';
    postureEl.style.letterSpacing = '3px';
    postureEl.style.fontSize = '9px';
    postureEl.style.fontWeight = '700';

    document.getElementById('regime-meta-row').innerHTML =
      '<div class="rmeta"><div class="rmeta-label">ANN VOL</div><div class="rmeta-value">' + pct(curVol) + '</div></div>' +
      '<div class="rmeta"><div class="rmeta-label">PERCENTILE</div><div class="rmeta-value">' + pct(volPct) + '</div></div>' +
      '<div class="rmeta"><div class="rmeta-label">BENCHMARK</div><div class="rmeta-value">' + bench + '</div></div>';
  } catch(e) {
    document.getElementById('regime-pill').textContent = 'ERR';
    document.getElementById('regime-meta-row').innerHTML = '<div class="error-cell">FETCH FAILED: ' + e.message + '</div>';
  }
}

/* ── SIGNALS ─────────────────────────────────────────────── */
async function loadSignals() {
  try {
    const d = await (await fetch('/api/signals?signal_type=momentum')).json();
    const sorted = Object.entries(d.scores || {}).sort((a,b) => b[1]-a[1]);

    const rows = sorted.map(([ticker, score], i) => {
      const m = scoreMeta(score);
      const barW = Math.min(Math.abs(score)*100, 100).toFixed(1);
      const sign = score >= 0 ? '+' : '';
      return '<tr>' +
        '<td class="left rank-cell">' + (i+1) + '</td>' +
        '<td class="left"><span class="ticker-cell">' + ticker + '</span></td>' +
        '<td><div class="score-wrap">' +
          '<span class="score-num" style="color:' + m.color + '">' + sign + score.toFixed(3) + '</span>' +
          '<div class="bar-track"><div class="bar-fill" style="width:' + barW + '%;background:' + m.color + '"></div></div>' +
        '</div></td>' +
        '<td><span class="sig-tag" style="color:' + m.color + '">' + m.label + '</span></td>' +
        '</tr>';
    }).join('');

    document.getElementById('signals-wrap').innerHTML =
      '<table class="dt"><thead><tr>' +
      '<th class="left" style="width:28px">#</th>' +
      '<th class="left">TICKER</th>' +
      '<th>SCORE &middot; STRENGTH</th>' +
      '<th>SIGNAL</th>' +
      '</tr></thead><tbody>' + rows + '</tbody></table>';
  } catch(e) {
    document.getElementById('signals-wrap').innerHTML = '<div class="error-cell">ERROR: ' + e.message + '</div>';
  }
}

/* ── METRICS ─────────────────────────────────────────────── */
async function loadMetrics() {
  try {
    const data = await (await fetch('/api/metrics')).json();
    const valid = data.filter(d => !d.error).sort((a,b) => b.sharpe - a.sharpe);

    const rows = valid.map(d => {
      const ret = d.annualized_return, vol = d.annualized_vol;
      const retSign = ret > 0 ? '+' : '';
      return '<tr>' +
        '<td class="left"><span class="ticker-cell">' + d.ticker + '</span>' +
          '<span class="bucket-tag">' + (d.bucket||'').toUpperCase() + '</span></td>' +
        '<td class="' + numCls(ret) + '">' + retSign + (ret*100).toFixed(1) + '%</td>' +
        '<td class="neu">' + (vol*100).toFixed(1) + '%</td>' +
        '<td class="' + numCls(d.sharpe) + '">' + d.sharpe.toFixed(2) + '</td>' +
        '<td class="' + numCls(d.sortino) + '">' + d.sortino.toFixed(2) + '</td>' +
        '<td class="neg">' + (d.max_drawdown*100).toFixed(1) + '%</td>' +
        '</tr>';
    }).join('');

    document.getElementById('metrics-wrap').innerHTML =
      '<table class="dt"><thead><tr>' +
      '<th class="left">TICKER</th>' +
      '<th>ANN RET</th><th>ANN VOL</th><th>SHARPE</th><th>SORTINO</th><th>MAX DD</th>' +
      '</tr></thead><tbody>' + rows + '</tbody></table>';
  } catch(e) {
    document.getElementById('metrics-wrap').innerHTML = '<div class="error-cell">ERROR: ' + e.message + '</div>';
  }
}

/* ── LOAD ALL ─────────────────────────────────────────────── */
async function loadAll() {
  await Promise.all([loadRegime(), loadSignals(), loadMetrics()]);
  const n = new Date();
  const pad = x => String(x).padStart(2,'0');
  document.getElementById('last-update').textContent =
    'UPDATED ' + pad(n.getHours()) + ':' + pad(n.getMinutes()) + ':' + pad(n.getSeconds());
}

loadAll();
setInterval(loadAll, 60000);
</script>
</body>
</html>"""
