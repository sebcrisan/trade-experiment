from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from crypto_sim.db import connect
from crypto_sim.repository import Repository
from crypto_sim.simulator import trader_configs


HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Crypto Sim Dashboard</title>
  <style>
    :root {
      --bg: #07111f;
      --panel: #0f1a2b;
      --panel-soft: #111f34;
      --border: rgba(148, 163, 184, 0.16);
      --border-strong: rgba(148, 163, 184, 0.28);
      --text: #e5edf8;
      --muted: #93a4bc;
      --muted-2: #6f839f;
      --accent: #67b3ff;
      --accent-soft: rgba(103, 179, 255, 0.14);
      --success: #35d0a1;
      --danger: #ff6b7c;
      --shadow: 0 16px 36px rgba(2, 8, 23, 0.34);
      --shadow-soft: 0 8px 24px rgba(2, 8, 23, 0.22);
      --radius: 18px;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Aptos", "Segoe UI Variable", "Segoe UI", sans-serif;
      color: var(--text);
      background:
        radial-gradient(circle at top left, rgba(103, 179, 255, 0.12), transparent 22%),
        radial-gradient(circle at top right, rgba(53, 208, 161, 0.08), transparent 18%),
        linear-gradient(180deg, #06101d 0%, var(--bg) 100%);
    }
    .wrap {
      width: min(1360px, calc(100% - 32px));
      margin: 0 auto;
      padding: 28px 0 40px;
    }
    .topbar {
      display: flex;
      justify-content: space-between;
      align-items: end;
      gap: 16px;
      margin-bottom: 22px;
    }
    .page-kicker {
      color: var(--accent);
      text-transform: uppercase;
      letter-spacing: 0.12em;
      font-size: 11px;
      font-weight: 700;
    }
    .page-title {
      margin: 6px 0 0;
      font-size: clamp(28px, 4vw, 40px);
      line-height: 1.05;
      letter-spacing: -0.03em;
    }
    .page-copy {
      margin: 10px 0 0;
      color: var(--muted);
      max-width: 70ch;
      font-size: 14px;
      line-height: 1.6;
    }
    .updated-at {
      flex-shrink: 0;
      color: var(--muted);
      font-size: 13px;
      white-space: nowrap;
    }
    .summary-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 14px;
      margin-bottom: 24px;
    }
    .card,
    .panel,
    .trader-card,
    .strategy-card {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      box-shadow: var(--shadow-soft);
    }
    .card {
      padding: 18px;
      min-width: 0;
    }
    .metric-label,
    .meta-label,
    th {
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.08em;
      font-size: 11px;
      font-weight: 700;
    }
    .metric-value {
      margin-top: 10px;
      font-size: clamp(24px, 3vw, 32px);
      line-height: 1.05;
      font-weight: 700;
      letter-spacing: -0.03em;
      overflow-wrap: anywhere;
    }
    .metric-foot {
      margin-top: 8px;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.5;
    }
    .section {
      margin-bottom: 24px;
    }
    .section-head {
      display: flex;
      justify-content: space-between;
      align-items: end;
      gap: 14px;
      margin-bottom: 14px;
    }
    .section-title {
      margin: 0;
      font-size: 20px;
      line-height: 1.2;
      letter-spacing: -0.02em;
    }
    .section-copy {
      margin-top: 4px;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.5;
    }
    .leaderboard-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 16px;
    }
    .panel {
      padding: 18px;
      min-width: 0;
    }
    .panel-head {
      display: flex;
      justify-content: space-between;
      align-items: start;
      gap: 14px;
      margin-bottom: 16px;
    }
    .panel-head h3,
    .panel-head h2 {
      margin: 0;
      font-size: 18px;
      letter-spacing: -0.02em;
    }
    .panel-kicker {
      color: var(--muted-2);
      font-size: 12px;
      white-space: nowrap;
    }
    .trader-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 14px;
    }
    .trader-card {
      padding: 16px;
      color: inherit;
      text-decoration: none;
      min-width: 0;
      transition: transform 140ms ease, box-shadow 140ms ease, border-color 140ms ease;
    }
    .trader-card:hover {
      transform: translateY(-2px);
      border-color: var(--border-strong);
      box-shadow: var(--shadow);
    }
    .trader-top {
      display: flex;
      justify-content: space-between;
      align-items: start;
      gap: 12px;
    }
    .trader-heading {
      min-width: 0;
    }
    .trader-name {
      font-size: 18px;
      line-height: 1.1;
      font-weight: 700;
      letter-spacing: -0.03em;
      overflow-wrap: normal;
      word-break: normal;
    }
    .trader-family {
      margin-top: 6px;
      color: var(--muted);
      font-size: 13px;
    }
    .trader-pill {
      flex-shrink: 0;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 6px 10px;
      border-radius: 999px;
      border: 1px solid var(--border);
      background: var(--panel-soft);
      color: var(--muted);
      font-size: 11px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      white-space: nowrap;
    }
    .trader-actions {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-shrink: 0;
    }
    .info-menu {
      position: relative;
      flex-shrink: 0;
    }
    .info-menu summary {
      list-style: none;
      width: 26px;
      height: 26px;
      border-radius: 999px;
      border: 1px solid var(--border);
      background: var(--panel-soft);
      color: var(--accent);
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      font-size: 13px;
      font-weight: 700;
      user-select: none;
    }
    .info-menu summary::-webkit-details-marker {
      display: none;
    }
    .tooltip {
      position: absolute;
      top: calc(100% + 10px);
      left: 50%;
      z-index: 4;
      width: min(240px, 72vw);
      padding: 12px 14px;
      border-radius: 12px;
      border: 1px solid var(--border-strong);
      background: #13233a;
      color: var(--text);
      box-shadow: var(--shadow);
      font-size: 12px;
      line-height: 1.55;
      opacity: 0;
      pointer-events: none;
      transform: translate(-50%, -4px);
      transition: opacity 140ms ease, transform 140ms ease;
    }
    .info-menu:hover .tooltip,
    .info-menu:focus-within .tooltip,
    .info-menu[open] .tooltip {
      opacity: 1;
      pointer-events: auto;
      transform: translate(-50%, 0);
    }
    .trader-net {
      margin-top: 18px;
      font-size: clamp(28px, 3vw, 36px);
      line-height: 1;
      font-weight: 700;
      letter-spacing: -0.04em;
      overflow-wrap: anywhere;
    }
    .trader-meta {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
      margin-top: 16px;
      padding-top: 16px;
      border-top: 1px solid var(--border);
    }
    .meta-value {
      margin-top: 6px;
      font-size: 15px;
      font-weight: 700;
      overflow-wrap: anywhere;
    }
    .strategy-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 16px;
    }
    .strategy-card {
      padding: 18px;
      min-width: 0;
    }
    .strategy-family {
      color: var(--accent);
      text-transform: uppercase;
      letter-spacing: 0.08em;
      font-size: 11px;
      font-weight: 700;
    }
    .strategy-card h3 {
      margin: 8px 0 8px;
      font-size: 20px;
      letter-spacing: -0.02em;
    }
    .strategy-card p {
      margin: 0;
      color: var(--muted);
      font-size: 14px;
      line-height: 1.6;
    }
    .strategy-tags {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 16px;
    }
    .tag {
      display: inline-flex;
      align-items: center;
      padding: 6px 10px;
      border-radius: 999px;
      background: var(--accent-soft);
      color: var(--accent);
      border: 1px solid rgba(37, 99, 235, 0.12);
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 0.04em;
      text-transform: uppercase;
      white-space: nowrap;
    }
    .table-wrap {
      overflow-x: auto;
      margin: 0 -18px -18px;
      padding: 0 18px 18px;
      scrollbar-width: thin;
    }
    table {
      width: 100%;
      min-width: 760px;
      border-collapse: separate;
      border-spacing: 0;
      table-layout: fixed;
    }
    th, td {
      padding: 14px 12px;
      border-top: 1px solid var(--border);
      text-align: left;
      vertical-align: top;
      font-size: 13px;
      overflow-wrap: anywhere;
    }
    th {
      background: var(--panel);
    }
    tbody tr:hover td {
      background: rgba(255, 255, 255, 0.02);
    }
    .token-primary {
      font-size: 14px;
      font-weight: 700;
      line-height: 1.4;
    }
    .mono {
      font-family: Consolas, monospace;
      font-size: 12px;
      color: var(--muted);
    }
    .token-links {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 6px;
    }
    a {
      color: var(--accent);
      text-decoration: none;
    }
    a:hover {
      text-decoration: underline;
    }
    .pos { color: var(--success); }
    .neg { color: var(--danger); }
    .empty {
      padding: 18px;
      color: var(--muted);
      border: 1px dashed var(--border-strong);
      border-radius: 14px;
      background: var(--panel-soft);
      font-size: 14px;
    }
    @media (max-width: 1400px) {
      .leaderboard-grid {
        grid-template-columns: 1fr;
      }
    }
    @media (max-width: 1180px) {
      .trader-grid {
        grid-template-columns: 1fr;
      }
    }
    @media (max-width: 820px) {
      .wrap {
        width: min(100%, calc(100% - 20px));
        padding-top: 22px;
      }
      .topbar,
      .section-head,
      .panel-head {
        flex-direction: column;
        align-items: start;
      }
      .updated-at,
      .panel-kicker {
        white-space: normal;
      }
      .summary-grid,
      .leaderboard-grid,
      .strategy-grid,
      .trader-meta {
        grid-template-columns: 1fr;
      }
      .card,
      .panel,
      .trader-card,
      .strategy-card {
        border-radius: 16px;
      }
      table {
        min-width: 640px;
      }
      .tooltip {
        left: 0;
        width: min(220px, 78vw);
        transform: translateY(-4px);
      }
      .info-menu:hover .tooltip,
      .info-menu:focus-within .tooltip,
      .info-menu[open] .tooltip {
        transform: translateY(0);
      }
    }
  </style>
</head>
<body>
  <div class="wrap">
    <header class="topbar">
      <div>
        <div class="page-kicker">Solana Strategy Dashboard</div>
        <h1 class="page-title">Trader performance and token flow</h1>
        <p class="page-copy">Compare the strongest and weakest simulated entry ladders, review how each strategy actually works, and inspect which tokens produced the largest combined results.</p>
      </div>
      <div class="updated-at" id="updated">Loading...</div>
    </header>

    <section class="section">
      <div class="summary-grid" id="summary"></div>
    </section>

    <section class="section">
      <div class="section-head">
        <div>
          <h2 class="section-title">Trader leaderboards</h2>
          <div class="section-copy">Net PnL ranks each strategy after combining realized and still-open position performance.</div>
        </div>
      </div>
      <div class="leaderboard-grid">
        <section class="panel">
          <div class="panel-head">
            <div>
              <h3>Top 3 best performers</h3>
              <div class="section-copy">Highest net PnL across all strategy variants.</div>
            </div>
            <div class="panel-kicker">Best net PnL</div>
          </div>
          <div class="trader-grid" id="best-traders"></div>
        </section>
        <section class="panel">
          <div class="panel-head">
            <div>
              <h3>Top 3 weakest performers</h3>
              <div class="section-copy">Lowest net PnL across all strategy variants.</div>
            </div>
            <div class="panel-kicker">Lowest net PnL</div>
          </div>
          <div class="trader-grid" id="worst-traders"></div>
        </section>
      </div>
    </section>

    <section class="section">
      <div class="section-head">
        <div>
          <h2 class="section-title">Strategy guide</h2>
          <div class="section-copy">Two strategy families drive all generated traders. The differences below match the actual simulator rules.</div>
        </div>
      </div>
      <div class="strategy-grid" id="strategies"></div>
    </section>

    <section class="section">
      <div class="leaderboard-grid">
        <section class="panel">
          <div class="panel-head">
            <div>
              <h2>Top 5 performing tokens</h2>
              <div class="section-copy">Tokens ranked by combined realized and unrealized PnL from all traders.</div>
            </div>
          </div>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th style="width: 32%;">Token</th>
                  <th>Positions</th>
                  <th>Total Invested</th>
                  <th>Realized PnL</th>
                  <th>Unrealized PnL</th>
                  <th>Net PnL</th>
                </tr>
              </thead>
              <tbody id="top-tokens"></tbody>
            </table>
          </div>
        </section>

        <section class="panel">
          <div class="panel-head">
            <div>
              <h2>Newest tokens</h2>
              <div class="section-copy">Recently admitted pairs under the current recency filter.</div>
            </div>
          </div>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th style="width: 32%;">Token</th>
                  <th>Market Cap</th>
                  <th>Liquidity</th>
                  <th>Volume 24h</th>
                  <th>Price</th>
                  <th>First Seen</th>
                </tr>
              </thead>
              <tbody id="tokens"></tbody>
            </table>
          </div>
        </section>
      </div>
    </section>
  </div>

  <script>
    function fmtUsd(value, digits = 2) {
      if (value === null || value === undefined) return "-";
      return new Intl.NumberFormat("en-US", {
        style: "currency",
        currency: "USD",
        maximumFractionDigits: digits
      }).format(value);
    }

    function fmtCount(value) {
      if (value === null || value === undefined) return "-";
      return new Intl.NumberFormat("en-US").format(value);
    }

    function fmtDate(value) {
      if (!value) return "-";
      return new Date(value * 1000).toLocaleString();
    }

    function metricCard(label, value, foot = "") {
      return `<div class="card"><div class="metric-label">${label}</div><div class="metric-value">${value}</div>${foot ? `<div class="metric-foot">${foot}</div>` : ""}</div>`;
    }

    function renderTraderCards(rows) {
      if (!rows.length) {
        return `<div class="empty">No trader data yet.</div>`;
      }
      return rows.map((row) => `
        <div class="trader-card">
          <div class="trader-top">
            <div class="trader-heading">
              <div class="trader-name">${row.strategy.label}</div>
              <div class="trader-family">${row.strategy.family}</div>
            </div>
            <div class="trader-actions">
              <details class="info-menu">
                <summary aria-label="Show trader description">?</summary>
                <div class="tooltip">${row.strategy.description}</div>
              </details>
              <div class="trader-pill">${row.open_positions_count} open</div>
            </div>
          </div>
          <div class="trader-net ${row.net_pnl >= 0 ? "pos" : "neg"}">${fmtUsd(row.net_pnl)}</div>
          <div class="trader-meta">
            <div>
              <div class="meta-label">Invested</div>
              <div class="meta-value">${fmtUsd(row.total_invested)}</div>
            </div>
            <div>
              <div class="meta-label">Open Value</div>
              <div class="meta-value">${fmtUsd(row.current_open_value)}</div>
            </div>
            <div>
              <div class="meta-label">Realized</div>
              <div class="meta-value ${row.realized_pnl >= 0 ? "pos" : "neg"}">${fmtUsd(row.realized_pnl)}</div>
            </div>
            <div>
              <div class="meta-label">Unrealized</div>
              <div class="meta-value ${row.unrealized_pnl >= 0 ? "pos" : "neg"}">${fmtUsd(row.unrealized_pnl)}</div>
            </div>
          </div>
          <div class="token-links" style="margin-top: 16px;">
            <a href="/trader/${row.trader_name}">Trader details</a>
          </div>
        </div>
      `).join("");
    }

    async function load() {
      const response = await fetch("/api/dashboard");
      const data = await response.json();

      document.getElementById("updated").textContent = `Updated ${new Date().toLocaleString()}`;

      document.getElementById("summary").innerHTML = [
        metricCard("Strategies", fmtCount(data.summary.strategy_count), "Total generated trader variants currently ranked."),
        metricCard("Families", fmtCount(data.summary.family_count), "Independent entry-rule families in the simulator."),
        metricCard("Closed Trades", fmtCount(data.summary.closed_trades), "Positions that have already been fully exited."),
        metricCard("Profitable Strategies", fmtCount(data.summary.profitable_strategies), "Strategies with positive current net PnL.")
      ].join("");

      document.getElementById("best-traders").innerHTML = renderTraderCards(data.best_traders);
      document.getElementById("worst-traders").innerHTML = renderTraderCards(data.worst_traders);

      document.getElementById("strategies").innerHTML = data.family_guides.map((row) => `
        <div class="strategy-card">
          <div class="strategy-family">${row.family}</div>
          <h3>${row.headline}</h3>
          <p>${row.description}</p>
          <div class="strategy-tags">
            <span class="tag">Entry ${fmtUsd(row.entry_market_cap, 0)}</span>
            <span class="tag">${row.requires_prior_threshold ? `Baseline ${fmtUsd(row.requires_prior_threshold, 0)}` : "No baseline requirement"}</span>
            <span class="tag">Targets ${row.min_sell_multiple.toFixed(1)}x to ${row.max_sell_multiple.toFixed(1)}x</span>
            <span class="tag">${fmtCount(row.trader_count)} variants</span>
          </div>
        </div>
      `).join("");

      document.getElementById("top-tokens").innerHTML = data.top_tokens.length ? data.top_tokens.map((row) => `
        <tr>
          <td>
            <div class="token-primary">${row.symbol || "-"}</div>
            <div class="mono">${row.token_address.slice(0, 14)}...</div>
            <div class="token-links">
              <a href="/token/${row.token_address}">Token detail</a>
              ${row.pair_url ? `<a href="${row.pair_url}" target="_blank" rel="noreferrer">Dexscreener</a>` : ""}
            </div>
          </td>
          <td>${fmtCount(row.total_positions)}</td>
          <td>${fmtUsd(row.total_invested)}</td>
          <td class="${row.realized_pnl >= 0 ? "pos" : "neg"}">${fmtUsd(row.realized_pnl)}</td>
          <td class="${row.unrealized_pnl >= 0 ? "pos" : "neg"}">${fmtUsd(row.unrealized_pnl)}</td>
          <td class="${row.net_pnl >= 0 ? "pos" : "neg"}">${fmtUsd(row.net_pnl)}</td>
        </tr>
      `).join("") : `<tr><td colspan="6">No token performance data yet.</td></tr>`;

      document.getElementById("tokens").innerHTML = data.tokens.length ? data.tokens.map((row) => `
        <tr>
          <td>
            <div class="token-primary">${row.symbol || "-"}</div>
            <div class="mono">${row.token_address.slice(0, 14)}...</div>
            <div class="token-links">
              <a href="/token/${row.token_address}">Details</a>
              ${row.pair_url ? `<a href="${row.pair_url}" target="_blank" rel="noreferrer">Dexscreener</a>` : ""}
            </div>
          </td>
          <td>${fmtUsd(row.latest_market_cap, 0)}</td>
          <td>${fmtUsd(row.latest_liquidity_usd, 0)}</td>
          <td>${fmtUsd(row.latest_volume_h24, 0)}</td>
          <td>${fmtUsd(row.latest_price_usd, 8)}</td>
          <td>${fmtDate(row.first_seen_at)}</td>
        </tr>
      `).join("") : `<tr><td colspan="6">No tokens available yet.</td></tr>`;
    }

    load();
    setInterval(load, 30000);
  </script>
</body>
</html>
"""
def token_detail_html(token_address: str) -> str:
    escaped = html.escape(token_address)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Token Detail</title>
  <style>
    :root {{
      --bg: #0c1117;
      --panel: #131a22;
      --text: #e6edf3;
      --muted: #8aa0b6;
      --accent: #4dd4ac;
      --border: #243140;
      --line: #7bdff6;
      --grid: rgba(255,255,255,0.08);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Georgia, "Times New Roman", serif;
      background:
        radial-gradient(circle at top left, rgba(77, 212, 172, 0.16), transparent 28%),
        linear-gradient(180deg, #0a0f14 0%, var(--bg) 100%);
      color: var(--text);
    }}
    .wrap {{
      width: min(1200px, calc(100% - 32px));
      margin: 24px auto 40px;
    }}
    .top {{
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: end;
      margin-bottom: 16px;
    }}
    h1 {{ margin: 0; font-size: clamp(28px, 5vw, 46px); line-height: 0.96; }}
    .sub, .back {{ color: var(--muted); font-size: 14px; }}
    a {{ color: #9fdcff; text-decoration: none; }}
    .panel {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 18px;
      margin-bottom: 16px;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
      margin-bottom: 16px;
    }}
    .card {{
      background: rgba(255,255,255,0.02);
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 14px;
    }}
    .label {{ color: var(--muted); text-transform: uppercase; letter-spacing: 0.08em; font-size: 12px; }}
    .value {{ margin-top: 8px; font-size: 26px; font-weight: 700; }}
    canvas {{
      width: 100%;
      height: 360px;
      display: block;
      background:
        linear-gradient(180deg, rgba(123,223,246,0.08), transparent 45%),
        rgba(255,255,255,0.01);
      border-radius: 12px;
      border: 1px solid var(--border);
    }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{
      padding: 12px 0;
      border-top: 1px solid var(--border);
      text-align: left;
      font-size: 14px;
    }}
    th {{
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.08em;
      font-size: 12px;
    }}
    .mono {{ font-family: Consolas, monospace; font-size: 12px; }}
    .pos {{ color: var(--accent); }}
    .neg {{ color: #ff6b6b; }}
    @media (max-width: 900px) {{
      .grid {{ grid-template-columns: 1fr 1fr; }}
    }}
    @media (max-width: 640px) {{
      .grid {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="top">
      <div>
        <div class="back"><a href="/">Back to dashboard</a></div>
        <h1 id="title">Token Detail</h1>
        <div class="sub mono">{escaped}</div>
      </div>
      <div class="sub" id="updated">Loading...</div>
    </div>

    <div class="grid" id="summary"></div>

    <section class="panel">
      <h2>Market Cap History</h2>
      <canvas id="chart" width="1120" height="360"></canvas>
      <div class="sub" id="chart-meta" style="margin-top:10px;">Loading history...</div>
    </section>

    <section class="panel">
      <h2>Trader Activity</h2>
      <table>
        <thead>
          <tr>
            <th>Trader</th>
            <th>Status</th>
            <th>Entry Mcap</th>
            <th>Exit Mcap</th>
            <th>PnL</th>
            <th>Reason</th>
          </tr>
        </thead>
        <tbody id="positions"></tbody>
      </table>
    </section>
  </div>

  <script>
    const tokenAddress = {json.dumps(token_address)};

    function fmtUsd(value, digits = 2) {{
      if (value === null || value === undefined) return "-";
      return new Intl.NumberFormat("en-US", {{
        style: "currency",
        currency: "USD",
        maximumFractionDigits: digits
      }}).format(value);
    }}

    function fmtDate(value) {{
      if (!value) return "-";
      return new Date(value * 1000).toLocaleString();
    }}

    function card(label, value) {{
      return `<div class="card"><div class="label">${{label}}</div><div class="value">${{value}}</div></div>`;
    }}

    function drawChart(points) {{
      const canvas = document.getElementById("chart");
      const ctx = canvas.getContext("2d");
      const width = canvas.width;
      const height = canvas.height;
      ctx.clearRect(0, 0, width, height);

      ctx.strokeStyle = "rgba(255,255,255,0.08)";
      ctx.lineWidth = 1;
      for (let i = 0; i < 5; i++) {{
        const y = 20 + ((height - 40) / 4) * i;
        ctx.beginPath();
        ctx.moveTo(50, y);
        ctx.lineTo(width - 20, y);
        ctx.stroke();
      }}

      if (!points.length) {{
        ctx.fillStyle = "#8aa0b6";
        ctx.font = "16px Georgia";
        ctx.fillText("No history yet.", 60, 60);
        return;
      }}

      const values = points.map((p) => p.market_cap).filter((v) => v !== null && v !== undefined);
      if (!values.length) {{
        ctx.fillStyle = "#8aa0b6";
        ctx.font = "16px Georgia";
        ctx.fillText("No market cap values available.", 60, 60);
        return;
      }}

      const min = Math.min(...values);
      const max = Math.max(...values);
      const range = Math.max(1, max - min);

      ctx.strokeStyle = "#7bdff6";
      ctx.lineWidth = 3;
      ctx.beginPath();
      points.forEach((point, index) => {{
        if (point.market_cap === null || point.market_cap === undefined) return;
        const x = 50 + ((width - 70) * index / Math.max(1, points.length - 1));
        const y = height - 20 - (((point.market_cap - min) / range) * (height - 40));
        if (index === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }});
      ctx.stroke();

      ctx.fillStyle = "#8aa0b6";
      ctx.font = "12px Georgia";
      ctx.fillText(fmtUsd(max, 0), 8, 24);
      ctx.fillText(fmtUsd(min, 0), 8, height - 20);
    }}

    async function load() {{
      const response = await fetch(`/api/token/${{encodeURIComponent(tokenAddress)}}`);
      if (!response.ok) {{
        document.getElementById("title").textContent = "Token not found";
        return;
      }}
      const data = await response.json();
      const token = data.token;
      document.getElementById("updated").textContent = `Updated ${{new Date().toLocaleString()}}`;
      document.getElementById("title").textContent = `${{token.symbol || "Unknown"}} token detail`;
      document.getElementById("summary").innerHTML = [
        card("Latest Mcap", fmtUsd(token.latest_market_cap, 0)),
        card("Latest Price", fmtUsd(token.latest_price_usd, 8)),
        card("Liquidity", fmtUsd(token.latest_liquidity_usd, 0)),
        card("Volume 24h", fmtUsd(token.latest_volume_h24, 0))
      ].join("");

      drawChart(data.history);
      document.getElementById("chart-meta").textContent =
        `${{data.history.length}} snapshots from ${{fmtDate(token.first_seen_at)}} to ${{fmtDate(token.last_seen_at)}}`;

      document.getElementById("positions").innerHTML = data.positions.length ? data.positions.map((row) => `
        <tr>
          <td>${{row.trader_name}}</td>
          <td>${{row.status}}</td>
          <td>${{fmtUsd(row.opened_market_cap, 0)}}</td>
          <td>${{fmtUsd(row.closed_market_cap, 0)}}</td>
          <td class="${{(row.pnl_usd || 0) >= 0 ? "pos" : "neg"}}">${{fmtUsd(row.pnl_usd)}}</td>
          <td>${{row.close_reason || "-"}}</td>
        </tr>
      `).join("") : `<tr><td colspan="6">No trader activity for this token yet.</td></tr>`;
    }}

    load();
    setInterval(load, 30000);
  </script>
</body>
</html>"""


def trader_detail_html(trader_name: str) -> str:
    escaped = html.escape(trader_name)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Trader Detail</title>
  <style>
    :root {{
      --bg: #0c1117;
      --panel: #131a22;
      --text: #e6edf3;
      --muted: #8aa0b6;
      --accent: #4dd4ac;
      --danger: #ff6b6b;
      --border: #243140;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Georgia, "Times New Roman", serif;
      background:
        radial-gradient(circle at top right, rgba(244, 185, 66, 0.12), transparent 22%),
        radial-gradient(circle at top left, rgba(77, 212, 172, 0.16), transparent 28%),
        linear-gradient(180deg, #0a0f14 0%, var(--bg) 100%);
      color: var(--text);
    }}
    .wrap {{ width: min(1280px, calc(100% - 32px)); margin: 24px auto 40px; }}
    .top {{ display: flex; justify-content: space-between; gap: 16px; align-items: end; margin-bottom: 16px; }}
    h1 {{ margin: 0; font-size: clamp(28px, 5vw, 46px); line-height: 0.96; }}
    .sub, .back {{ color: var(--muted); font-size: 14px; }}
    a {{ color: #9fdcff; text-decoration: none; }}
    .grid {{ display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); gap: 12px; margin-bottom: 16px; }}
    .card, .panel {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 16px;
      box-shadow: 0 10px 30px rgba(0,0,0,0.2);
    }}
    .card {{ padding: 16px; }}
    .label {{ color: var(--muted); text-transform: uppercase; letter-spacing: 0.08em; font-size: 12px; }}
    .value {{ margin-top: 8px; font-size: 26px; font-weight: 700; }}
    .panel {{ overflow: hidden; margin-bottom: 16px; }}
    .panel h2 {{ margin: 0; padding: 16px 18px 0; font-size: 20px; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ padding: 12px 18px; border-top: 1px solid var(--border); text-align: left; font-size: 14px; }}
    th {{ color: var(--muted); text-transform: uppercase; letter-spacing: 0.08em; font-size: 12px; }}
    .mono {{ font-family: Consolas, monospace; font-size: 12px; }}
    .pos {{ color: var(--accent); }}
    .neg {{ color: var(--danger); }}
    .pill {{
      display: inline-block;
      padding: 3px 8px;
      border-radius: 999px;
      border: 1px solid var(--border);
      background: rgba(255,255,255,0.03);
      font-size: 12px;
    }}
    @media (max-width: 1000px) {{ .grid {{ grid-template-columns: 1fr 1fr; }} }}
    @media (max-width: 640px) {{ .grid {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="top">
      <div>
        <div class="back"><a href="/">Back to dashboard</a></div>
        <h1 id="title">{escaped}</h1>
        <div class="sub" id="strategy-copy">Realized and unrealized performance for this strategy.</div>
      </div>
      <div class="sub" id="updated">Loading...</div>
    </div>

    <div class="grid" id="summary"></div>

    <section class="panel">
      <h2>Open Positions</h2>
      <table>
        <thead>
          <tr>
            <th>Token</th>
            <th>Entry Mcap</th>
            <th>Current Mcap</th>
            <th>Cost</th>
            <th>Current Value</th>
            <th>Unrealized PnL</th>
          </tr>
        </thead>
        <tbody id="open-positions"></tbody>
      </table>
    </section>

    <section class="panel">
      <h2>Closed Positions</h2>
      <table>
        <thead>
          <tr>
            <th>Token</th>
            <th>Opened</th>
            <th>Closed</th>
            <th>Cost</th>
            <th>Proceeds</th>
            <th>PnL</th>
            <th>Reason</th>
          </tr>
        </thead>
        <tbody id="closed-positions"></tbody>
      </table>
    </section>
  </div>

  <script>
    const traderName = {json.dumps(trader_name)};

    function fmtUsd(value, digits = 2) {{
      if (value === null || value === undefined) return "-";
      return new Intl.NumberFormat("en-US", {{
        style: "currency",
        currency: "USD",
        maximumFractionDigits: digits
      }}).format(value);
    }}

    function fmtDate(value) {{
      if (!value) return "-";
      return new Date(value * 1000).toLocaleString();
    }}

    function card(label, value) {{
      return `<div class="card"><div class="label">${{label}}</div><div class="value">${{value}}</div></div>`;
    }}

    async function load() {{
      const response = await fetch(`/api/trader/${{encodeURIComponent(traderName)}}`);
      if (!response.ok) {{
        document.getElementById("title").textContent = "Trader not found";
        return;
      }}
      const data = await response.json();
      document.getElementById("updated").textContent = `Updated ${{new Date().toLocaleString()}}`;
      if (data.strategy) {{
        document.getElementById("strategy-copy").textContent = data.strategy.description;
      }}
      document.getElementById("summary").innerHTML = [
        card("Closed Trades", data.summary.total_trades),
        card("Closed Spend", fmtUsd(data.summary.closed_spent)),
        card("Open Capital", fmtUsd(data.summary.open_spent)),
        card("Total Invested", fmtUsd(data.summary.total_invested)),
        card("Realized PnL", fmtUsd(data.summary.realized_pnl)),
        card("Unrealized PnL", fmtUsd(data.summary.unrealized_pnl)),
        card("Net PnL", fmtUsd(data.summary.net_pnl))
      ].join("");

      document.getElementById("open-positions").innerHTML = data.open_positions.length ? data.open_positions.map((row) => `
        <tr>
          <td>
            <div>${{row.symbol || "-"}}</div>
            <div class="mono">${{row.token_address.slice(0, 14)}}...</div>
            <div><a href="/token/${{row.token_address}}">Token detail</a></div>
          </td>
          <td>${{fmtUsd(row.opened_market_cap, 0)}}</td>
          <td>${{fmtUsd(row.latest_market_cap, 0)}}</td>
          <td>${{fmtUsd(row.amount_usd)}}</td>
          <td>${{fmtUsd(row.current_value)}}</td>
          <td class="${{row.unrealized_pnl >= 0 ? "pos" : "neg"}}">${{fmtUsd(row.unrealized_pnl)}}</td>
        </tr>
      `).join("") : `<tr><td colspan="6">No open positions.</td></tr>`;

      document.getElementById("closed-positions").innerHTML = data.closed_positions.length ? data.closed_positions.map((row) => `
        <tr>
          <td>
            <div>${{row.symbol || "-"}}</div>
            <div class="mono">${{row.token_address.slice(0, 14)}}...</div>
          </td>
          <td>${{fmtDate(row.opened_at)}}</td>
          <td>${{fmtDate(row.closed_at)}}</td>
          <td>${{fmtUsd(row.amount_usd)}}</td>
          <td>${{fmtUsd(row.proceeds_usd)}}</td>
          <td class="${{(row.pnl_usd || 0) >= 0 ? "pos" : "neg"}}">${{fmtUsd(row.pnl_usd)}}</td>
          <td><span class="pill">${{row.close_reason || "-"}}</span></td>
        </tr>
      `).join("") : `<tr><td colspan="7">No closed positions yet.</td></tr>`;
    }}

    load();
    setInterval(load, 30000);
  </script>
</body>
</html>"""


class DashboardServer:
    def __init__(self, db_path: Path, host: str = "127.0.0.1", port: int = 8000) -> None:
        self.db_path = db_path
        self.host = host
        self.port = port

    def serve(self) -> None:
        handler = self._handler()
        server = ThreadingHTTPServer((self.host, self.port), handler)
        print(f"Dashboard running at http://{self.host}:{self.port}")
        server.serve_forever()

    def _handler(self) -> type[BaseHTTPRequestHandler]:
        db_path = self.db_path

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                parsed = urlparse(self.path)
                if parsed.path == "/":
                    self._respond_html(HTML)
                    return
                if parsed.path == "/api/dashboard":
                    limit = _parse_limit(parsed.query)
                    payload = _dashboard_payload(db_path, limit)
                    self._respond_json(payload)
                    return
                if parsed.path.startswith("/trader/"):
                    trader_name = unquote(parsed.path.removeprefix("/trader/"))
                    self._respond_html(trader_detail_html(trader_name))
                    return
                if parsed.path.startswith("/api/trader/"):
                    trader_name = unquote(parsed.path.removeprefix("/api/trader/"))
                    payload = _trader_payload(db_path, trader_name)
                    if payload is None:
                        self.send_error(HTTPStatus.NOT_FOUND, "Trader not found")
                        return
                    self._respond_json(payload)
                    return
                if parsed.path.startswith("/token/"):
                    token_address = unquote(parsed.path.removeprefix("/token/"))
                    self._respond_html(token_detail_html(token_address))
                    return
                if parsed.path.startswith("/api/token/"):
                    token_address = unquote(parsed.path.removeprefix("/api/token/"))
                    payload = _token_payload(db_path, token_address)
                    if payload is None:
                        self.send_error(HTTPStatus.NOT_FOUND, "Token not found")
                        return
                    self._respond_json(payload)
                    return
                self.send_error(HTTPStatus.NOT_FOUND, "Not found")

            def log_message(self, format: str, *args: object) -> None:
                return

            def _respond_html(self, html: str) -> None:
                encoded = html.encode("utf-8")
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

            def _respond_json(self, payload: dict[str, object]) -> None:
                encoded = json.dumps(payload).encode("utf-8")
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

        return Handler


def _parse_limit(query: str) -> int:
    values = parse_qs(query).get("limit", ["50"])
    try:
        return max(1, min(200, int(values[0])))
    except ValueError:
        return 50


def _dashboard_payload(db_path: Path, limit: int) -> dict[str, object]:
    with connect(db_path) as connection:
        repository = Repository(connection)
        tokens = [_row_to_dict(row) for row in repository.latest_tokens(limit=min(limit, 5))]
        traders = []
        for trader_name in repository.trader_names():
            payload = _trader_payload_from_repository(repository, trader_name)
            traders.append(
                {
                    "trader_name": trader_name,
                    "strategy": payload["strategy"],
                    **payload["summary"],
                }
            )
        families = _family_groups(traders)
        top_tokens = []
        for row in repository.top_token_performance(limit=5):
            item = _row_to_dict(row)
            realized = float(item["realized_pnl"] or 0.0)
            unrealized = float(item["unrealized_pnl"] or 0.0)
            item["net_pnl"] = realized + unrealized
            top_tokens.append(item)
        traders_sorted = sorted(traders, key=lambda item: float(item["net_pnl"]), reverse=True)
        best_traders = traders_sorted[:3]
        worst_traders = list(reversed(traders_sorted[-3:])) if traders_sorted else []

        closed_trades = sum(int(row["total_trades"]) for row in traders)
        profitable_strategies = sum(1 for row in traders if float(row["net_pnl"]) > 0)
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "strategy_count": len(traders),
                "family_count": len(families),
                "snapshots": repository.total_snapshot_count(),
                "closed_trades": closed_trades,
                "profitable_strategies": profitable_strategies,
            },
            "traders": traders,
            "families": families,
            "best_traders": best_traders,
            "worst_traders": worst_traders,
            "family_guides": _family_guides(),
            "top_tokens": top_tokens,
            "tokens": tokens,
        }


def _row_to_dict(row: object) -> dict[str, object]:
    return dict(row)


def _token_payload(db_path: Path, token_address: str) -> dict[str, object] | None:
    with connect(db_path) as connection:
        repository = Repository(connection)
        token = repository.token_detail(token_address)
        if token is None:
            return None
        return {
            "token": _row_to_dict(token),
            "history": [_row_to_dict(row) for row in repository.token_history(token_address)],
            "positions": [_row_to_dict(row) for row in repository.positions_for_token(token_address)],
        }


def _trader_payload(db_path: Path, trader_name: str) -> dict[str, object] | None:
    with connect(db_path) as connection:
        repository = Repository(connection)
        trader_names = set(repository.trader_names())
        if trader_name not in trader_names:
            return None
        return _trader_payload_from_repository(repository, trader_name)


def _trader_payload_from_repository(repository: Repository, trader_name: str) -> dict[str, object]:
    config = next((item for item in trader_configs() if item.name == trader_name), None)
    closed_summary = dict(repository.trader_closed_summary(trader_name))
    open_summary = dict(repository.trader_open_summary(trader_name))
    open_rows = []
    unrealized_pnl = 0.0
    current_open_value = 0.0
    for row in repository.trader_open_positions(trader_name):
        item = _position_with_live_values(dict(row))
        unrealized_pnl += float(item["unrealized_pnl"] or 0.0)
        current_open_value += float(item["current_value"] or 0.0)
        open_rows.append(item)

    closed_rows = [_row_to_dict(row) for row in repository.trader_closed_positions(trader_name)]
    realized_pnl = float(closed_summary["total_pnl"] or 0.0)

    return {
        "trader_name": trader_name,
        "strategy": (
            {
                "family": config.family,
                "label": config.label,
                "description": config.description,
                "buy_market_cap": config.buy_market_cap,
                "requires_prior_threshold": config.requires_prior_threshold,
                "sell_multiple": config.sell_multiple,
            }
            if config is not None
            else None
        ),
        "summary": {
            "total_trades": int(closed_summary["total_trades"] or 0),
            "closed_spent": float(closed_summary["total_spent"] or 0.0),
            "open_spent": float(open_summary["open_spent"] or 0.0),
            "total_invested": float(closed_summary["total_spent"] or 0.0) + float(open_summary["open_spent"] or 0.0),
            "total_proceeds": float(closed_summary["total_proceeds"] or 0.0),
            "open_positions_count": int(open_summary["open_trades"] or 0),
            "current_open_value": current_open_value,
            "realized_pnl": realized_pnl,
            "unrealized_pnl": unrealized_pnl,
            "net_pnl": realized_pnl + unrealized_pnl,
        },
        "open_positions": open_rows,
        "closed_positions": closed_rows,
    }


def _position_with_live_values(item: dict[str, object]) -> dict[str, object]:
    latest_market_cap = item.get("latest_market_cap")
    latest_liquidity_usd = item.get("latest_liquidity_usd")
    opened_market_cap = item.get("opened_market_cap")
    amount_usd = float(item.get("amount_usd") or 0.0)
    current_value = amount_usd
    pnl = 0.0
    if latest_market_cap and opened_market_cap:
        multiple = float(latest_market_cap) / float(opened_market_cap)
        current_value = amount_usd * multiple
        if latest_liquidity_usd is not None:
            current_value = min(current_value, max(float(latest_liquidity_usd), 0.0))
        pnl = current_value - amount_usd
    item["current_value"] = current_value
    item["unrealized_pnl"] = pnl
    return item


def _family_groups(traders: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[str, dict[str, object]] = {}
    for trader in traders:
        strategy = trader.get("strategy") or {}
        family = strategy.get("family") or "Other"
        bucket = grouped.setdefault(
            family,
            {
                "family": family,
                "traders": [],
                "total_invested": 0.0,
                "current_open_value": 0.0,
                "realized_pnl": 0.0,
                "unrealized_pnl": 0.0,
                "net_pnl": 0.0,
            },
        )
        bucket["traders"].append(trader)
        bucket["total_invested"] += float(trader.get("total_invested") or 0.0)
        bucket["current_open_value"] += float(trader.get("current_open_value") or 0.0)
        bucket["realized_pnl"] += float(trader.get("realized_pnl") or 0.0)
        bucket["unrealized_pnl"] += float(trader.get("unrealized_pnl") or 0.0)
        bucket["net_pnl"] += float(trader.get("net_pnl") or 0.0)
    families = list(grouped.values())
    for bucket in families:
        bucket["traders"].sort(
            key=lambda item: float(((item.get("strategy") or {}).get("sell_multiple")) or 0.0)
        )
    families.sort(key=lambda item: str(item["family"]))
    return families


def _family_guides() -> list[dict[str, object]]:
    grouped: dict[str, list[object]] = {}
    for config in trader_configs():
        grouped.setdefault(config.family, []).append(config)

    guides = []
    for family, configs in grouped.items():
        configs = sorted(configs, key=lambda item: item.sell_multiple)
        first = configs[0]
        last = configs[-1]
        guides.append(
            {
                "family": family,
                "headline": first.label.split()[0],
                "entry_market_cap": first.buy_market_cap,
                "requires_prior_threshold": first.requires_prior_threshold,
                "min_sell_multiple": first.sell_multiple,
                "max_sell_multiple": last.sell_multiple,
                "trader_count": len(configs),
                "description": (
                    "Enters immediately on the first snapshot at or above 20k market cap, then exits using the selected post-entry multiple."
                    if first.requires_prior_threshold is None
                    else "Uses the first 20k-plus snapshot as a baseline, enters only after a later 2x confirmation, then exits using the selected post-entry multiple."
                ),
            }
        )
    return guides
