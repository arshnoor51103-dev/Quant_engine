"""
FastAPI server for the Quant Engine dashboard.

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


def _load_prices(lookback: int = 1260) -> dict:
    """Helper: load price series for all tickers."""
    universe = load_universe()
    prices = {}
    for a in universe:
        ps = price_series(a["ticker"], lookback_days=lookback)
        if not ps.empty:
            prices[a["ticker"]] = ps
    return prices


@app.get("/api/universe")
def get_universe():
    return load_universe()


@app.get("/api/metrics")
def get_metrics(lookback: int = Query(1260, description="Lookback in trading days")):
    universe = load_universe()
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
    prices = _load_prices()
    signal_map = {
        "momentum": MomentumSignal(),
        "vol_regime": VolRegimeSignal(),
    }
    sig = signal_map.get(signal_type)
    if not sig:
        return {"error": f"Unknown signal: {signal_type}"}
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
        "nav": nav(),
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
        "bucket_allocation": bucket_allocation(),
    }


@app.get("/", response_class=HTMLResponse)
def dashboard():
    """Serve a minimal dashboard page that hits the API endpoints."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Quant Engine — Dashboard</title>
        <meta charset="utf-8" />
        <style>
            body { background: #050d05; color: #c0e8c0; font-family: 'Courier New', monospace; margin: 0; padding: 20px; }
            h1 { color: #00ff87; letter-spacing: 3px; font-size: 18px; }
            .section { margin: 20px 0; padding: 16px; border: 1px solid #1a2a1a; border-radius: 4px; }
            table { border-collapse: collapse; width: 100%; }
            th, td { padding: 6px 10px; text-align: right; border-bottom: 1px solid #0d1a0d; font-size: 12px; }
            th { color: #446644; font-size: 10px; text-transform: uppercase; letter-spacing: 1px; }
            .loading { color: #557755; animation: pulse 1s infinite; }
            @keyframes pulse { 0%,100% { opacity: 0.4; } 50% { opacity: 1; } }
            #error { color: #ff4444; display: none; }
        </style>
    </head>
    <body>
        <h1>◆ QUANT ENGINE</h1>
        <div id="error"></div>

        <div class="section">
            <h3 style="color:#00ff87;font-size:11px;letter-spacing:2px;">RISK · RETURN MATRIX</h3>
            <div id="metrics" class="loading">Loading metrics...</div>
        </div>

        <div class="section">
            <h3 style="color:#00ff87;font-size:11px;letter-spacing:2px;">MOMENTUM SIGNAL</h3>
            <div id="signals" class="loading">Loading signals...</div>
        </div>

        <div class="section">
            <h3 style="color:#00ff87;font-size:11px;letter-spacing:2px;">VOLATILITY REGIME</h3>
            <div id="regime" class="loading">Loading regime...</div>
        </div>

        <script>
            async function load() {
                try {
                    // Metrics
                    const metrics = await (await fetch('/api/metrics')).json();
                    const mHead = '<table><tr><th>Ticker</th><th>Bucket</th><th>Ann Ret</th><th>Vol</th><th>Sharpe</th><th>Sortino</th><th>Max DD</th><th>Calmar</th></tr>';
                    const mRows = metrics.filter(m=>!m.error).sort((a,b)=>b.sharpe-a.sharpe).map(m =>
                        `<tr><td style="color:#00ff87;text-align:left">${m.ticker}</td><td style="text-align:left">${m.bucket}</td>` +
                        `<td>${(m.annualized_return*100).toFixed(1)}%</td><td>${(m.annualized_vol*100).toFixed(1)}%</td>` +
                        `<td>${m.sharpe.toFixed(2)}</td><td>${m.sortino.toFixed(2)}</td>` +
                        `<td>${(m.max_drawdown*100).toFixed(1)}%</td><td>${m.calmar.toFixed(2)}</td></tr>`
                    ).join('');
                    document.getElementById('metrics').innerHTML = mHead + mRows + '</table>';

                    // Momentum signals
                    const sig = await (await fetch('/api/signals?signal_type=momentum')).json();
                    const sorted = Object.entries(sig.scores).sort((a,b)=>b[1]-a[1]);
                    const sRows = sorted.map(([t,s]) => {
                        const color = s > 0.3 ? '#00ff87' : s > 0 ? '#ffb700' : '#ff4444';
                        const bar = '█'.repeat(Math.round(Math.abs(s)*20));
                        return `<tr><td style="text-align:left;color:${color}">${t}</td><td style="color:${color}">${s > 0 ? '+' : ''}${s.toFixed(3)}</td><td style="text-align:left;color:${color}">${bar}</td></tr>`;
                    }).join('');
                    document.getElementById('signals').innerHTML = `<table><tr><th>Ticker</th><th>Score</th><th>Strength</th></tr>${sRows}</table>`;

                    // Vol regime
                    const reg = await (await fetch('/api/signals?signal_type=vol_regime')).json();
                    const regime = reg.metadata?.regime || 'unknown';
                    const volPct = reg.metadata?.vol_percentile;
                    const curVol = reg.metadata?.current_annualized_vol;
                    const rColor = regime === 'crisis' ? '#ff4444' : regime === 'high_vol' ? '#ffb700' : regime === 'low_vol' ? '#00ff87' : '#c0e8c0';
                    document.getElementById('regime').innerHTML =
                        `<div style="font-size:24px;color:${rColor};font-weight:bold;text-transform:uppercase">${regime.replace('_',' ')}</div>` +
                        `<div style="margin-top:8px">Vol percentile: ${volPct !== undefined ? (volPct*100).toFixed(1)+'%' : 'n/a'}</div>` +
                        `<div>Current annualized vol: ${curVol !== undefined ? (curVol*100).toFixed(1)+'%' : 'n/a'}</div>`;
                } catch(e) {
                    document.getElementById('error').style.display = 'block';
                    document.getElementById('error').textContent = 'API Error: ' + e.message;
                }
            }
            load();
            setInterval(load, 60000); // refresh every 60s
        </script>
    </body>
    </html>
    """
