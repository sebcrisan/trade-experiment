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
      --bg: #09111a;
      --bg-2: #0e1a27;
      --panel: rgba(11, 19, 30, 0.86);
      --panel-strong: rgba(16, 27, 40, 0.92);
      --border: rgba(120, 165, 210, 0.18);
      --text: #eef4fb;
      --muted: #89a1bb;
      --accent: #3dd6b6;
      --accent-2: #66c7ff;
      --danger: #ff6f7d;
      --glow: rgba(102, 199, 255, 0.12);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Aptos", "Segoe UI Variable", "Segoe UI", sans-serif;
      color: var(--text);
      background:
        radial-gradient(circle at top left, rgba(61, 214, 182, 0.16), transparent 30%),
        radial-gradient(circle at top right, rgba(102, 199, 255, 0.16), transparent 24%),
        linear-gradient(180deg, var(--bg) 0%, #050a10 100%);
    }
    .wrap {
      width: min(1320px, calc(100% - 28px));
      margin: 20px auto 36px;
    }
    .hero {
      display: grid;
      grid-template-columns: 1.2fr 0.8fr;
      gap: 18px;
      margin-bottom: 18px;
    }
    .hero-main, .hero-side, .card, .panel, .trader-card {
      background: linear-gradient(180deg, rgba(255,255,255,0.03), transparent 26%), var(--panel);
      border: 1px solid var(--border);
      border-radius: 22px;
      box-shadow: 0 18px 50px rgba(0,0,0,0.22);
      backdrop-filter: blur(10px);
    }
    .hero-main {
      padding: 22px;
      min-height: 156px;
    }
    .eyebrow {
      color: var(--accent-2);
      text-transform: uppercase;
      letter-spacing: 0.16em;
      font-size: 12px;
    }
    h1 {
      margin: 10px 0 0;
      font-size: clamp(36px, 5.6vw, 64px);
      line-height: 0.96;
      letter-spacing: -0.05em;
    }
    .sub {
      color: var(--muted);
      margin-top: 10px;
      font-size: 13px;
      max-width: 62ch;
    }
    .hero-side {
      padding: 18px;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      gap: 16px;
    }
    .timestamp {
      color: var(--muted);
      font-size: 12px;
      text-align: right;
    }
    .hero-stats {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
    }
    .hero-stat {
      padding: 14px;
      border-radius: 16px;
      background: rgba(255,255,255,0.02);
      border: 1px solid rgba(120, 165, 210, 0.12);
    }
    .hero-stat .label,
    .card .label,
    .trader-meta .label {
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.12em;
      font-size: 11px;
    }
    .hero-stat .value {
      margin-top: 8px;
      font-size: 24px;
      font-weight: 700;
    }
    .summary-grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
      margin-bottom: 14px;
    }
    .card {
      padding: 14px;
    }
    .card .value {
      margin-top: 8px;
      font-size: 24px;
      font-weight: 700;
    }
    .card .foot {
      margin-top: 8px;
      color: var(--muted);
      font-size: 12px;
    }
    .section-head {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      margin-bottom: 12px;
    }
    .section-title {
      margin: 0;
      font-size: 20px;
      line-height: 1;
    }
    .section-copy {
      color: var(--muted);
      font-size: 12px;
    }
    .trader-grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 14px;
      margin-bottom: 18px;
    }
    .leaderboard-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 14px;
      margin-bottom: 16px;
    }
    .leaderboard-panel {
      padding: 16px;
      background: linear-gradient(180deg, rgba(255,255,255,0.03), transparent 26%), var(--panel);
      border: 1px solid var(--border);
      border-radius: 22px;
      box-shadow: 0 18px 50px rgba(0,0,0,0.18);
    }
    .leaderboard-head {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 14px;
      margin-bottom: 12px;
    }
    .leaderboard-title {
      margin: 0;
      font-size: 18px;
    }
    .trader-card {
      padding: 14px;
      color: inherit;
      text-decoration: none;
      transition: transform 140ms ease, border-color 140ms ease, box-shadow 140ms ease;
    }
    .trader-card:hover {
      transform: translateY(-2px);
      border-color: rgba(102, 199, 255, 0.4);
      box-shadow: 0 22px 50px rgba(0,0,0,0.28), 0 0 0 1px var(--glow) inset;
    }
    .trader-top {
      display: flex;
      justify-content: space-between;
      align-items: start;
      gap: 12px;
    }
    .trader-name {
      font-size: 18px;
      line-height: 1;
    }
    .trader-pill {
      border-radius: 999px;
      border: 1px solid var(--border);
      padding: 4px 9px;
      font-size: 11px;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }
    .trader-net {
      margin-top: 12px;
      font-size: 24px;
      font-weight: 700;
    }
    .trader-meta {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px 12px;
      margin-top: 12px;
    }
    .trader-meta .meta-value {
      margin-top: 4px;
      font-size: 13px;
      font-weight: 600;
    }
    .panels {
      display: grid;
      grid-template-columns: 1fr;
      gap: 14px;
    }
    .strategy-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 14px;
      margin-bottom: 14px;
    }
    .strategy-card {
      padding: 14px;
      background: linear-gradient(180deg, rgba(255,255,255,0.03), transparent 26%), var(--panel-strong);
      border: 1px solid var(--border);
      border-radius: 20px;
      box-shadow: 0 18px 50px rgba(0,0,0,0.18);
    }
    .strategy-card h3 {
      margin: 10px 0 8px;
      font-size: 18px;
    }
    .strategy-card p {
      margin: 0;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.5;
    }
    .strategy-tags {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 14px;
    }
    .tag {
      display: inline-block;
      padding: 5px 9px;
      border-radius: 999px;
      border: 1px solid rgba(102, 199, 255, 0.16);
      background: rgba(102, 199, 255, 0.08);
      font-size: 11px;
      color: #b9def7;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }
    .panel {
      overflow: hidden;
    }
    .panel-head {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      padding: 14px 16px 10px;
    }
    .panel-head h2 {
      margin: 0;
      font-size: 18px;
    }
    table {
      width: 100%;
      border-collapse: collapse;
    }
    th, td {
      padding: 11px 16px;
      border-top: 1px solid rgba(120, 165, 210, 0.12);
      text-align: left;
      vertical-align: top;
      font-size: 12px;
    }
    th {
      color: var(--muted);
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.1em;
    }
    tr:hover td {
      background: rgba(255,255,255,0.015);
    }
    .mono {
      font-family: Consolas, monospace;
      font-size: 12px;
    }
    .muted { color: var(--muted); }
    .pos { color: var(--accent); }
    .neg { color: var(--danger); }
    .pill {
      display: inline-block;
      padding: 4px 10px;
      border-radius: 999px;
      background: rgba(102, 199, 255, 0.08);
      border: 1px solid rgba(102, 199, 255, 0.14);
      font-size: 12px;
    }
    .token-name {
      font-size: 13px;
      font-weight: 600;
    }
    .token-links {
      display: flex;
      gap: 8px;
      margin-top: 4px;
      flex-wrap: wrap;
    }
    .token-links a,
    a {
      color: #a7ddff;
      text-decoration: none;
    }
    .footer {
      color: var(--muted);
      font-size: 11px;
      margin-top: 10px;
      text-align: right;
    }
    @media (max-width: 1180px) {
      .hero, .summary-grid, .trader-grid, .strategy-grid, .leaderboard-grid { grid-template-columns: 1fr 1fr; }
    }
    @media (max-width: 820px) {
      .hero, .summary-grid, .trader-grid, .strategy-grid, .hero-stats, .leaderboard-grid { grid-template-columns: 1fr; }
      .timestamp { text-align: left; }
      .wrap { width: min(100%, calc(100% - 20px)); }
    }
  </style>
</head>
<body>
  <div class="wrap">
    <section class="hero">
      <div class="hero-main">
        <div class="eyebrow">Solana Paper-Trading Simulator</div>
        <h1>Crypto Sim</h1>
        <div class="sub">Track newly created Solana pairs and rank competing trader strategies by realized and unrealized performance.</div>
      </div>
      <div class="hero-side">
        <div class="timestamp" id="updated">Loading...</div>
        <div class="hero-stats">
          <div class="hero-stat">
            <div class="label">Best Trader</div>
            <div class="value" id="hero-invested">-</div>
          </div>
          <div class="hero-stat">
            <div class="label">Worst Trader</div>
            <div class="value" id="hero-value">-</div>
          </div>
        </div>
      </div>
    </section>

    <div class="summary-grid" id="summary"></div>

    <section>
      <div class="section-head">
        <div>
          <h2 class="section-title">Trader Leaderboards</h2>
          <div class="section-copy">The goal is to find the strongest individual strategy, not to aggregate the field.</div>
        </div>
      </div>
      <div class="leaderboard-grid">
        <section class="leaderboard-panel">
          <div class="leaderboard-head">
            <h3 class="leaderboard-title">Top 3 Best Performers</h3>
            <div class="section-copy">Highest net PnL</div>
          </div>
          <div class="trader-grid" id="best-traders"></div>
        </section>
        <section class="leaderboard-panel">
          <div class="leaderboard-head">
            <h3 class="leaderboard-title">Top 3 Worst Performers</h3>
            <div class="section-copy">Lowest net PnL</div>
          </div>
          <div class="trader-grid" id="worst-traders"></div>
        </section>
      </div>
    </section>

    <section>
      <div class="section-head">
        <div>
          <h2 class="section-title">Strategy Guide</h2>
          <div class="section-copy">A plain-language summary of how each trader enters and exits positions.</div>
        </div>
      </div>
      <div class="strategy-grid" id="strategies"></div>
    </section>

    <div class="panels">
      <section class="panel">
        <div class="panel-head">
          <h2>Top Performing Tokens</h2>
          <div class="section-copy">Tokens ranked by combined realized and unrealized trader PnL.</div>
        </div>
        <table>
          <thead>
            <tr>
              <th>Token</th>
              <th>Positions</th>
              <th>Total Invested</th>
              <th>Realized PnL</th>
              <th>Unrealized PnL</th>
              <th>Net PnL</th>
            </tr>
          </thead>
          <tbody id="top-tokens"></tbody>
        </table>
      </section>

      <section class="panel">
        <div class="panel-head">
          <h2>Open Positions</h2>
          <div class="section-copy">Live mark-to-market view of every active position.</div>
        </div>
        <table>
          <thead>
            <tr>
              <th>Trader</th>
              <th>Token</th>
              <th>Entry Mcap</th>
              <th>Current Mcap</th>
              <th>Invested</th>
              <th>Current Value</th>
              <th>Unrealized PnL</th>
            </tr>
          </thead>
          <tbody id="positions"></tbody>
        </table>
      </section>

      <section class="panel">
        <div class="panel-head">
          <h2>Newest Tokens</h2>
          <div class="section-copy">Most recently admitted pairs under the current recency filter.</div>
        </div>
        <table>
          <thead>
            <tr>
              <th>Token</th>
              <th>Market Cap</th>
              <th>Liquidity</th>
              <th>Volume 24h</th>
              <th>Price</th>
              <th>First Seen</th>
            </tr>
          </thead>
          <tbody id="tokens"></tbody>
        </table>
      </section>
    </div>

    <div class="footer">Auto-refreshes every 30 seconds.</div>
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

    function fmtDate(value) {
      if (!value) return "-";
      return new Date(value * 1000).toLocaleString();
    }

    function metricCard(label, value, foot = "") {
      return `<div class="card"><div class="label">${label}</div><div class="value">${value}</div>${foot ? `<div class="foot">${foot}</div>` : ""}</div>`;
    }

    async function load() {
      const response = await fetch("/api/dashboard");
      const data = await response.json();

      document.getElementById("updated").textContent = `Updated ${new Date().toLocaleString()}`;
      document.getElementById("hero-invested").textContent = fmtUsd(data.summary.open_capital);
      document.getElementById("hero-value").textContent = fmtUsd(data.summary.current_open_value);

      document.getElementById("summary").innerHTML = [
        metricCard("Tracked Tokens", data.summary.tokens, "Pairs admitted by the current recency filter"),
        metricCard("Snapshots", data.summary.snapshots, "Historical observations stored locally"),
        metricCard("Open Positions", data.summary.open_positions, "Active positions across all traders"),
        metricCard("Top Token", data.summary.top_token_symbol || "-", "Best token by combined trader PnL"),
        metricCard("Best Net PnL", fmtUsd(data.summary.best_trader_net_pnl), "Current leading trader result"),
        metricCard("Worst Net PnL", fmtUsd(data.summary.worst_trader_net_pnl), "Current weakest trader result"),
        metricCard("Top Token PnL", fmtUsd(data.summary.top_token_net_pnl), "Leaderboard token net result"),
        metricCard("Refresh Interval", "30s", "Dashboard polling interval")
      ].join("");

      function renderTraderCards(rows) {
        return rows.length ? rows.map((row) => `
          <a class="trader-card" href="/trader/${row.trader_name}">
            <div class="trader-top">
              <div>
                <div class="trader-name">${row.strategy.label}</div>
                <div class="muted">${row.strategy.family}</div>
              </div>
              <div class="trader-pill">${row.open_positions_count} open</div>
            </div>
            <div class="trader-net ${row.net_pnl >= 0 ? "pos" : "neg"}">${fmtUsd(row.net_pnl)}</div>
            <div class="trader-meta">
              <div>
                <div class="label">Total Invested</div>
                <div class="meta-value">${fmtUsd(row.total_invested)}</div>
              </div>
              <div>
                <div class="label">Current Value</div>
                <div class="meta-value">${fmtUsd(row.current_open_value)}</div>
              </div>
              <div>
                <div class="label">Realized</div>
                <div class="meta-value ${row.realized_pnl >= 0 ? "pos" : "neg"}">${fmtUsd(row.realized_pnl)}</div>
              </div>
              <div>
                <div class="label">Unrealized</div>
                <div class="meta-value ${row.unrealized_pnl >= 0 ? "pos" : "neg"}">${fmtUsd(row.unrealized_pnl)}</div>
              </div>
            </div>
          </a>
        `).join("") : `<div class="card">No trader data yet.</div>`;
      }

      document.getElementById("best-traders").innerHTML = renderTraderCards(data.best_traders);
      document.getElementById("worst-traders").innerHTML = renderTraderCards(data.worst_traders);

      document.getElementById("strategies").innerHTML = data.family_guides.map((row) => `
        <div class="strategy-card">
          <div class="eyebrow">${row.family}</div>
          <h3>${row.headline} Ladder</h3>
          <p>${row.description}</p>
          <div class="strategy-tags">
            <span class="tag">Entry ${fmtUsd(row.entry_market_cap, 0)}</span>
            <span class="tag">${row.requires_prior_threshold ? `Needs prior ${fmtUsd(row.requires_prior_threshold, 0)}` : "No prior threshold"}</span>
            <span class="tag">Targets ${row.min_sell_multiple.toFixed(1)}x to ${row.max_sell_multiple.toFixed(1)}x</span>
            <span class="tag">${row.trader_count} traders</span>
          </div>
        </div>
      `).join("");

      document.getElementById("top-tokens").innerHTML = data.top_tokens.length ? data.top_tokens.map((row) => `
        <tr>
          <td>
            <div class="token-name">${row.symbol || "-"}</div>
            <div class="mono">${row.token_address.slice(0, 14)}...</div>
            <div class="token-links">
              <a href="/token/${row.token_address}">Token detail</a>
              ${row.pair_url ? `<a href="${row.pair_url}" target="_blank" rel="noreferrer">Dexscreener</a>` : ""}
            </div>
          </td>
          <td>${row.total_positions}</td>
          <td>${fmtUsd(row.total_invested)}</td>
          <td class="${row.realized_pnl >= 0 ? "pos" : "neg"}">${fmtUsd(row.realized_pnl)}</td>
          <td class="${row.unrealized_pnl >= 0 ? "pos" : "neg"}">${fmtUsd(row.unrealized_pnl)}</td>
          <td class="${row.net_pnl >= 0 ? "pos" : "neg"}">${fmtUsd(row.net_pnl)}</td>
        </tr>
      `).join("") : `<tr><td colspan="6">No token performance data yet.</td></tr>`;

      document.getElementById("hero-invested").textContent = data.best_traders[0] ? data.best_traders[0].strategy.label : "-";
      document.getElementById("hero-value").textContent = data.worst_traders[0] ? data.worst_traders[0].strategy.label : "-";

      document.getElementById("positions").innerHTML = data.open_positions.length ? data.open_positions.map((row) => `
        <tr>
          <td><a href="/trader/${row.trader_name}"><span class="pill">${row.trader_name}</span></a></td>
          <td>
            <div class="token-name">${row.symbol || "-"}</div>
            <div class="mono">${row.token_address.slice(0, 14)}...</div>
            <div class="token-links">
              <a href="/token/${row.token_address}">Token detail</a>
              ${row.pair_url ? `<a href="${row.pair_url}" target="_blank" rel="noreferrer">Dexscreener</a>` : ""}
            </div>
          </td>
          <td>${fmtUsd(row.opened_market_cap, 0)}</td>
          <td>${fmtUsd(row.latest_market_cap, 0)}</td>
          <td>${fmtUsd(row.amount_usd)}</td>
          <td>${fmtUsd(row.current_value)}</td>
          <td class="${row.unrealized_pnl >= 0 ? "pos" : "neg"}">${fmtUsd(row.unrealized_pnl)}</td>
        </tr>
      `).join("") : `<tr><td colspan="7">No open positions.</td></tr>`;

      document.getElementById("tokens").innerHTML = data.tokens.map((row) => `
        <tr>
          <td>
            <div class="token-name">${row.symbol || "-"}</div>
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
      `).join("");
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
        open_positions = []
        open_capital = 0.0
        current_open_value = 0.0
        for row in repository.open_position_report_rows():
            item = _position_with_live_values(dict(row))
            open_positions.append(item)
            open_capital += float(item["amount_usd"] or 0.0)
            current_open_value += float(item["current_value"] or 0.0)
        tokens = [_row_to_dict(row) for row in repository.latest_tokens(limit=limit)]
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
        for row in repository.top_token_performance(limit=8):
            item = _row_to_dict(row)
            realized = float(item["realized_pnl"] or 0.0)
            unrealized = float(item["unrealized_pnl"] or 0.0)
            item["net_pnl"] = realized + unrealized
            top_tokens.append(item)
        traders_sorted = sorted(traders, key=lambda item: float(item["net_pnl"]), reverse=True)
        best_traders = traders_sorted[:3]
        worst_traders = list(reversed(traders_sorted[-3:])) if traders_sorted else []
        top_token = top_tokens[0] if top_tokens else None

        closed_pnl = sum(float(row["realized_pnl"]) for row in traders)
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "tokens": repository.total_token_count(),
                "snapshots": repository.total_snapshot_count(),
                "open_positions": len(open_positions),
                "closed_pnl": closed_pnl,
                "open_capital": open_capital,
                "current_open_value": current_open_value,
                "net_open_pnl": current_open_value - open_capital,
                "best_trader_net_pnl": float(best_traders[0]["net_pnl"]) if best_traders else 0.0,
                "worst_trader_net_pnl": float(worst_traders[0]["net_pnl"]) if worst_traders else 0.0,
                "top_token_symbol": top_token["symbol"] if top_token else None,
                "top_token_net_pnl": float(top_token["net_pnl"]) if top_token else 0.0,
            },
            "traders": traders,
            "families": families,
            "best_traders": best_traders,
            "worst_traders": worst_traders,
            "family_guides": _family_guides(),
            "open_positions": open_positions,
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
                    "Buys immediately once market cap first reaches the entry threshold."
                    if first.requires_prior_threshold is None
                    else "Waits for a 20k proof point, then only enters after a later 40k confirmation."
                ),
            }
        )
    return guides
