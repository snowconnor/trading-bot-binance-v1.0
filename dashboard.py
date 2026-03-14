from flask import Flask, jsonify, render_template_string
import os
import json

app = Flask(__name__)

LIVE_DATA_FILE  = "live_data.json"
INITIAL_CAPITAL = 10.0

# ─── API ────────────────────────────────────────────────────────────────────

@app.route("/api/data")
def api_data():
    if not os.path.exists(LIVE_DATA_FILE):
        return jsonify({"live": False, "message": "Esperando que main.py inicie..."})
    try:
        with open(LIVE_DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        data["live"] = True
        return jsonify(data)
    except Exception as e:
        return jsonify({"live": False, "message": f"Error leyendo datos: {e}"})

# ─── HTML ────────────────────────────────────────────────────────────────────

HTML = r"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Trading Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#0d1117;--surface:#161b22;--surface2:#1c2128;--border:#30363d;
  --muted:#8b949e;--text:#e6edf3;--blue:#58a6ff;--green:#3fb950;
  --red:#f85149;--yellow:#d29922;--purple:#bc8cff;--orange:#f0883e;
  --radius:10px;--shadow:0 4px 20px rgba(0,0,0,.45)
}
body{font-family:system-ui,-apple-system,"Segoe UI",sans-serif;background:var(--bg);color:var(--text);min-height:100vh;padding:20px 24px 48px}
::-webkit-scrollbar{width:6px;height:6px}
::-webkit-scrollbar-track{background:var(--bg)}
::-webkit-scrollbar-thumb{background:var(--border);border-radius:3px}

/* ── Header ── */
.header{display:flex;align-items:center;justify-content:space-between;margin-bottom:20px;flex-wrap:wrap;gap:10px}
.header h1{font-size:1.45rem;font-weight:700;letter-spacing:-.4px}
.header h1 span{color:var(--blue)}
.badges{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.badge-pill{display:flex;align-items:center;gap:6px;background:var(--surface);border:1px solid var(--border);border-radius:20px;padding:5px 13px;font-size:.8rem;color:var(--muted)}
.pulse{width:8px;height:8px;background:var(--green);border-radius:50%;animation:pulse 1.4s infinite}
.pulse.off{background:var(--red);animation:none}
@keyframes pulse{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.35;transform:scale(1.35)}}
.session-badge{background:rgba(88,166,255,.08);border-color:rgba(88,166,255,.3);color:var(--blue)}
#waiting-msg{text-align:center;padding:60px 20px;color:var(--muted);font-size:1.1rem;display:none}

/* ── Session bar ── */
.session-bar{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:14px 22px;margin-bottom:18px;display:flex;align-items:center;gap:24px;flex-wrap:wrap}
.sb-item{display:flex;flex-direction:column;gap:3px}
.sb-label{font-size:.72rem;text-transform:uppercase;letter-spacing:.8px;color:var(--muted)}
.sb-value{font-size:1.55rem;font-weight:700;font-variant-numeric:tabular-nums;color:var(--blue)}
.sb-sub{font-size:.78rem;color:var(--muted)}
.prog-wrap{flex:1;min-width:160px}
.prog-track{height:6px;background:var(--border);border-radius:3px;overflow:hidden;margin-top:6px}
.prog-fill{height:100%;background:linear-gradient(90deg,var(--blue),var(--purple));border-radius:3px;transition:width .6s ease}

/* ── Stat cards ── */
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(175px,1fr));gap:14px;margin-bottom:18px}
.card{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:16px 18px;box-shadow:var(--shadow)}
.card-label{font-size:.72rem;text-transform:uppercase;letter-spacing:.8px;color:var(--muted);margin-bottom:7px}
.card-val{font-size:1.8rem;font-weight:700;font-variant-numeric:tabular-nums;line-height:1}
.card-sub{font-size:.78rem;color:var(--muted);margin-top:5px}
.green{color:var(--green)}.red{color:var(--red)}.blue{color:var(--blue)}.yellow{color:var(--yellow)}.orange{color:var(--orange)}
.wr-track{height:7px;background:var(--border);border-radius:4px;overflow:hidden;margin-top:9px}
.wr-fill{height:100%;border-radius:4px;background:linear-gradient(90deg,var(--red) 0%,var(--yellow) 50%,var(--green) 100%);transition:width .6s}

/* ── Two-col layout ── */
.two-col{display:grid;grid-template-columns:1fr 320px;gap:16px;margin-bottom:18px}
@media(max-width:860px){.two-col{grid-template-columns:1fr}}

/* ── Panel ── */
.panel{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:18px 20px;box-shadow:var(--shadow)}
.panel-title{font-size:.75rem;text-transform:uppercase;letter-spacing:.8px;color:var(--muted);margin-bottom:14px}
.chart-wrap{position:relative;height:210px}

/* ── Strategy panel ── */
.strat-cards{display:flex;flex-direction:column;gap:9px}
.strat-card{border-radius:8px;padding:12px 14px;border:1px solid var(--border)}
.strat-card.best{border-color:rgba(63,185,80,.35);background:rgba(63,185,80,.05)}
.strat-card.worst{border-color:rgba(248,81,73,.35);background:rgba(248,81,73,.05)}
.strat-badge{font-size:.68rem;text-transform:uppercase;letter-spacing:.7px;margin-bottom:3px}
.strat-name{font-size:.95rem;font-weight:600}
.strat-pnl{font-size:.82rem;margin-top:2px}
.strat-bars{margin-top:14px}
.sb-row{display:flex;align-items:center;gap:7px;margin-bottom:7px;font-size:.76rem}
.sb-row-label{width:120px;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.sb-row-track{flex:1;height:5px;background:var(--border);border-radius:3px;overflow:hidden}
.sb-row-fill{height:100%;border-radius:3px;min-width:2px}
.sb-row-val{width:52px;text-align:right;font-variant-numeric:tabular-nums}

/* ── Signals section ── */
.signals-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(310px,1fr));gap:10px;margin-bottom:18px}
.sig-card{background:var(--surface2);border:1px solid var(--border);border-radius:8px;padding:12px 14px}
.sig-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:10px}
.sig-symbol{font-weight:700;font-size:.95rem}
.sig-price{font-size:.8rem;color:var(--muted);font-variant-numeric:tabular-nums}
.sig-rows{display:flex;flex-direction:column;gap:5px}
.sig-row{display:flex;align-items:center;gap:8px;font-size:.78rem}
.sig-strat{width:110px;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.sig-badge{padding:2px 8px;border-radius:10px;font-size:.7rem;font-weight:700;letter-spacing:.4px;width:42px;text-align:center}
.sig-badge.buy {background:rgba(63,185,80,.15);color:var(--green);border:1px solid rgba(63,185,80,.3)}
.sig-badge.sell{background:rgba(248,81,73,.15);color:var(--red);  border:1px solid rgba(248,81,73,.3)}
.sig-badge.hold{background:rgba(139,148,158,.1);color:var(--muted);border:1px solid var(--border)}
.conf-track{flex:1;height:5px;background:var(--border);border-radius:3px;overflow:hidden}
.conf-fill{height:100%;border-radius:3px;transition:width .4s}
.conf-val{width:34px;text-align:right;color:var(--muted);font-variant-numeric:tabular-nums}

/* ── Symbol grid ── */
.sym-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(155px,1fr));gap:10px;margin-bottom:18px}
.sym-card{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:13px 15px;transition:border-color .18s}
.sym-card:hover{border-color:var(--blue)}
.sym-name{font-size:.76rem;color:var(--muted);margin-bottom:3px}
.sym-price{font-size:1rem;font-weight:600;font-variant-numeric:tabular-nums}
.sym-open{font-size:.74rem;color:var(--yellow);margin-top:3px}

/* ── Open trades ── */
.open-list{display:flex;flex-direction:column;gap:7px;margin-bottom:18px}
.open-card{background:var(--surface2);border:1px solid var(--border);border-radius:8px;padding:11px 14px;display:flex;align-items:center;gap:14px;flex-wrap:wrap;font-size:.82rem}
.open-card.buy-card {border-left:3px solid var(--green)}
.open-card.sell-card{border-left:3px solid var(--red)}
.open-symbol{font-weight:700;min-width:80px}
.open-detail{color:var(--muted)}
.open-unrealized{font-weight:600;margin-left:auto}

/* ── Trades table ── */
.table-wrap{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);overflow:hidden;box-shadow:var(--shadow)}
.table-header{display:flex;align-items:center;justify-content:space-between;padding:14px 18px;border-bottom:1px solid var(--border)}
.table-title{font-size:.75rem;text-transform:uppercase;letter-spacing:.8px;color:var(--muted)}
.count-pill{font-size:.78rem;background:var(--border);border-radius:12px;padding:2px 10px}
.t-scroll{overflow-x:auto}
table{width:100%;border-collapse:collapse;font-size:.82rem}
thead th{padding:9px 14px;text-align:left;font-size:.7rem;text-transform:uppercase;letter-spacing:.6px;color:var(--muted);background:rgba(255,255,255,.02);border-bottom:1px solid var(--border);white-space:nowrap}
tbody tr{border-bottom:1px solid rgba(48,54,61,.5);transition:background .12s}
tbody tr:hover{background:rgba(255,255,255,.03)}
tbody tr:last-child{border-bottom:none}
td{padding:9px 14px;white-space:nowrap}
.tbadge{display:inline-block;padding:2px 9px;border-radius:10px;font-size:.72rem;font-weight:700}
.tbadge-buy {background:rgba(63,185,80,.15);color:var(--green);border:1px solid rgba(63,185,80,.3)}
.tbadge-sell{background:rgba(248,81,73,.15);color:var(--red);  border:1px solid rgba(248,81,73,.3)}
.row-buy {border-left:3px solid var(--green)}
.row-sell{border-left:3px solid var(--red)}
.td-m{color:var(--muted);font-size:.76rem}

/* ── Section label ── */
.section-label{font-size:.75rem;text-transform:uppercase;letter-spacing:.9px;color:var(--muted);margin-bottom:10px;padding-left:2px}
.footer{text-align:center;color:var(--muted);font-size:.73rem;margin-top:32px}
</style>
</head>
<body>

<!-- Header -->
<div class="header">
  <h1>Trading <span>Dashboard</span></h1>
  <div class="badges">
    <div class="badge-pill session-badge" id="session-pill">Sesión: —</div>
    <div class="badge-pill">
      <div class="pulse" id="pulse-dot"></div>
      <span id="refresh-label">Conectando...</span>
    </div>
  </div>
</div>

<!-- Mensaje de espera -->
<div id="waiting-msg">⏳ Esperando que <code>main.py</code> inicie y escriba <code>live_data.json</code>…</div>

<!-- Contenido principal -->
<div id="main-content">

  <!-- Session bar -->
  <div class="session-bar">
    <div class="sb-item">
      <div class="sb-label">Tiempo restante</div>
      <div class="sb-value" id="session-time">--:--:--</div>
    </div>
    <div class="sb-item prog-wrap">
      <div class="sb-label">Progreso de sesión (<span id="prog-pct">0</span>%)</div>
      <div class="prog-track"><div class="prog-fill" id="prog-fill" style="width:0%"></div></div>
    </div>
    <div class="sb-item">
      <div class="sb-label">Capital inicial</div>
      <div style="font-weight:700;color:var(--blue);font-size:1.1rem">10.00 USDT</div>
    </div>
    <div class="sb-item">
      <div class="sb-label">Última actualización</div>
      <div id="last-update" style="font-size:.85rem;color:var(--muted)">—</div>
    </div>
  </div>

  <!-- Stat cards -->
  <div class="cards">
    <div class="card">
      <div class="card-label">Balance actual</div>
      <div class="card-val blue" id="balance">—</div>
      <div class="card-sub" id="balance-sub">+0.0000 desde inicio</div>
    </div>
    <div class="card">
      <div class="card-label">PnL Total</div>
      <div class="card-val" id="pnl">0.0000</div>
      <div class="card-sub" id="pnl-sub">USDT acumulado</div>
    </div>
    <div class="card">
      <div class="card-label">Win Rate</div>
      <div class="card-val green" id="win-rate">0.0%</div>
      <div class="wr-track"><div class="wr-fill" id="wr-bar" style="width:0%"></div></div>
    </div>
    <div class="card">
      <div class="card-label">Operaciones</div>
      <div class="card-val" id="total-trades">0</div>
      <div class="card-sub" id="trades-sub">0 cerradas · 0 abiertas</div>
    </div>
  </div>

  <!-- Chart + Strategies -->
  <div class="two-col">
    <div class="panel">
      <div class="panel-title">PnL en tiempo real</div>
      <div class="chart-wrap"><canvas id="pnl-chart"></canvas></div>
    </div>
    <div class="panel">
      <div class="panel-title">Estrategias</div>
      <div class="strat-cards">
        <div class="strat-card best">
          <div class="strat-badge green">Mejor del día</div>
          <div class="strat-name" id="best-strat">N/A</div>
          <div class="strat-pnl green" id="best-pnl"></div>
        </div>
        <div class="strat-card worst">
          <div class="strat-badge red">Peor del día</div>
          <div class="strat-name" id="worst-strat">N/A</div>
          <div class="strat-pnl red" id="worst-pnl"></div>
        </div>
      </div>
      <div class="strat-bars" id="strat-bars"></div>
    </div>
  </div>

  <!-- Señales en vivo -->
  <div class="section-label">Señales en vivo</div>
  <div class="signals-grid" id="signals-grid"></div>

  <!-- Precios -->
  <div class="section-label">Precios de mercado</div>
  <div class="sym-grid" id="sym-grid"></div>

  <!-- Posiciones abiertas -->
  <div class="section-label" id="open-label">Posiciones abiertas (0)</div>
  <div class="open-list" id="open-list"></div>

  <!-- Tabla de trades -->
  <div class="table-wrap">
    <div class="table-header">
      <div class="table-title">Operaciones cerradas</div>
      <div class="count-pill" id="closed-badge">0 trades</div>
    </div>
    <div class="t-scroll">
      <table>
        <thead>
          <tr>
            <th>Par</th><th>Estrategia</th><th>Lado</th>
            <th>Entrada</th><th>Salida</th><th>Cantidad</th>
            <th>SL</th><th>TP</th><th>PnL</th>
          </tr>
        </thead>
        <tbody id="trades-body">
          <tr><td colspan="9" style="text-align:center;color:var(--muted);padding:28px">Sin operaciones cerradas aún</td></tr>
        </tbody>
      </table>
    </div>
  </div>
</div><!-- /main-content -->

<div class="footer">Trading Bot Dashboard · Capital: 10 USDT · Sesión 4h · live_data.json · refresh 15s</div>

<script>
// ── Chart ────────────────────────────────────────────────────────────────────
const ctx = document.getElementById("pnl-chart").getContext("2d");
const pnlChart = new Chart(ctx, {
  type: "line",
  data: {
    labels: [],
    datasets: [
      { label: "Balance",  data: [], borderColor: "#58a6ff", backgroundColor: "rgba(88,166,255,.07)",
        borderWidth: 2, pointRadius: 2, pointHoverRadius: 5, tension: 0.35, fill: true },
      { label: "PnL", data: [], borderColor: "#3fb950", backgroundColor: "rgba(63,185,80,.05)",
        borderWidth: 1.5, pointRadius: 0, tension: 0.35, fill: true, borderDash: [4,3] }
    ]
  },
  options: {
    responsive: true, maintainAspectRatio: false, animation: { duration: 350 },
    plugins: {
      legend: { labels: { color: "#8b949e", boxWidth: 12, font: { size: 11 } } },
      tooltip: {
        backgroundColor: "#161b22", borderColor: "#30363d", borderWidth: 1,
        titleColor: "#e6edf3", bodyColor: "#8b949e",
        callbacks: { label: c => ` ${c.dataset.label}: ${c.parsed.y.toFixed(6)} USDT` }
      }
    },
    scales: {
      x: { ticks: { color:"#8b949e", maxTicksLimit:8, font:{size:10} }, grid: { color:"rgba(48,54,61,.45)" } },
      y: { ticks: { color:"#8b949e", font:{size:10}, callback: v => v.toFixed(3)+"U" }, grid: { color:"rgba(48,54,61,.45)" } }
    }
  }
});

// ── State ────────────────────────────────────────────────────────────────────
const $ = id => document.getElementById(id);
let knownSessionId    = null;
let remainingAtFetch  = 0;
let fetchedAtMs       = Date.now();
let endTimeFromServer = 0;
let countdown         = 15;

function resetDashboard() {
  pnlChart.data.labels = [];
  pnlChart.data.datasets[0].data = [];
  pnlChart.data.datasets[1].data = [];
  pnlChart.update("none");
  $("signals-grid").innerHTML = "";
  $("open-list").innerHTML    = "";
  $("trades-body").innerHTML  = `<tr><td colspan="9" style="text-align:center;color:var(--muted);padding:28px">Sin operaciones cerradas aún</td></tr>`;
  console.log("🔄 Nueva sesión detectada — dashboard reiniciado");
}

// ── Helpers ───────────────────────────────────────────────────────────────────
const fmtP  = v => v != null ? parseFloat(v).toLocaleString("en-US",{minimumFractionDigits:2,maximumFractionDigits:6}) : "—";
const sign  = v => v >= 0 ? "+" : "";
const cls   = v => v > 0 ? "green" : v < 0 ? "red" : "";

function fmtSecs(s) {
  s = Math.max(0, Math.floor(s));
  const h = Math.floor(s/3600), m = Math.floor((s%3600)/60), sec = s%60;
  return `${String(h).padStart(2,"0")}:${String(m).padStart(2,"0")}:${String(sec).padStart(2,"0")}`;
}

function confColor(c) {
  if (c >= 0.7) return "var(--green)";
  if (c >= 0.4) return "var(--yellow)";
  return "var(--red)";
}

// ── Render functions ──────────────────────────────────────────────────────────
function renderSession(d) {
  const elapsed  = (endTimeFromServer - d.remaining_secs) > 0
    ? 14400 - d.remaining_secs : 0;
  const progPct  = Math.min(100, Math.round((elapsed / 14400) * 100));
  $("prog-pct").textContent  = progPct;
  $("prog-fill").style.width = progPct + "%";
  $("last-update").textContent = d.last_update || "—";
  $("session-pill").textContent = "Session ID: " + d.session_id;
}

function renderStats(d) {
  const pnl = d.pnl, bal = d.balance;
  $("balance").textContent    = bal.toFixed(6) + " USDT";
  $("balance-sub").textContent = sign(pnl) + pnl.toFixed(6) + " desde inicio";
  $("pnl").textContent        = sign(pnl) + pnl.toFixed(6);
  $("pnl").className          = "card-val " + cls(pnl);
  $("pnl-sub").textContent    = pnl >= 0 ? "Ganancia acumulada" : "Pérdida acumulada";
  $("win-rate").textContent   = d.win_rate.toFixed(1) + "%";
  $("wr-bar").style.width     = d.win_rate + "%";
  $("total-trades").textContent = d.total_trades;
  $("trades-sub").textContent = `${d.buy_trades + d.sell_trades} cerradas · ${d.open_count || 0} abiertas`;
}

function renderChart(history) {
  if (!history || !history.length) return;
  pnlChart.data.labels            = history.map(h => h.ts);
  pnlChart.data.datasets[0].data  = history.map(h => h.balance);
  pnlChart.data.datasets[1].data  = history.map(h => h.pnl);
  pnlChart.update("none");
}

function renderStrategies(recent_trades) {
  // Calcular PnL por estrategia desde recent_trades
  const byStrat = {};
  (recent_trades || []).forEach(t => {
    if (!byStrat[t.strategy]) byStrat[t.strategy] = 0;
    byStrat[t.strategy] += t.pnl || 0;
  });
  const entries = Object.entries(byStrat).sort((a,b) => b[1]-a[1]);
  if (!entries.length) return;

  const best  = entries[0],  worst = entries[entries.length-1];
  $("best-strat").textContent = best[0];
  $("best-pnl").textContent   = sign(best[1])  + best[1].toFixed(6)  + " USDT";
  $("worst-strat").textContent = worst[0];
  $("worst-pnl").textContent  = sign(worst[1]) + worst[1].toFixed(6) + " USDT";

  const bars = $("strat-bars");
  bars.innerHTML = "";
  const maxAbs = Math.max(...entries.map(([,v]) => Math.abs(v)), 0.0001);
  entries.forEach(([name, val]) => {
    const pct = (Math.abs(val) / maxAbs * 100).toFixed(1);
    const col = val >= 0 ? "var(--green)" : "var(--red)";
    const row = document.createElement("div");
    row.className = "sb-row";
    row.innerHTML = `
      <div class="sb-row-label" title="${name}">${name}</div>
      <div class="sb-row-track"><div class="sb-row-fill" style="width:${pct}%;background:${col}"></div></div>
      <div class="sb-row-val ${cls(val)}">${sign(val)}${val.toFixed(4)}</div>`;
    bars.appendChild(row);
  });
}

function renderSignals(signals, prices) {
  const grid = $("signals-grid");
  if (!signals || !signals.length) {
    grid.innerHTML = `<div style="color:var(--muted);font-size:.85rem;padding:10px">Sin señales en este ciclo aún.</div>`;
    return;
  }

  // Agrupar por símbolo
  const bySym = {};
  signals.forEach(s => {
    if (!bySym[s.symbol]) bySym[s.symbol] = [];
    bySym[s.symbol].push(s);
  });

  grid.innerHTML = "";
  Object.entries(bySym).forEach(([sym, rows]) => {
    const price = prices && prices[sym] != null ? fmtP(prices[sym]) : "—";
    const card  = document.createElement("div");
    card.className = "sig-card";

    const rowsHtml = rows.map(r => {
      const badgeCls = r.signal === "BUY" ? "buy" : r.signal === "SELL" ? "sell" : "hold";
      const confPct  = (r.confidence * 100).toFixed(0);
      const confCol  = confColor(r.confidence);
      return `<div class="sig-row">
        <div class="sig-strat" title="${r.strategy}">${r.strategy}</div>
        <span class="sig-badge ${badgeCls}">${r.signal}</span>
        <div class="conf-track"><div class="conf-fill" style="width:${confPct}%;background:${confCol}"></div></div>
        <div class="conf-val">${confPct}%</div>
      </div>`;
    }).join("");

    card.innerHTML = `
      <div class="sig-header">
        <div class="sig-symbol">${sym.replace("USDT","")}<span style="color:var(--border)">/USDT</span></div>
        <div class="sig-price">${price}</div>
      </div>
      <div class="sig-rows">${rowsHtml}</div>`;
    grid.appendChild(card);
  });
}

function renderPrices(prices) {
  const grid = $("sym-grid");
  grid.innerHTML = "";
  const syms = ["BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","XRPUSDT","ADAUSDT",
                 "DOGEUSDT","AVAXUSDT","DOTUSDT","POLUSDT","LINKUSDT","LTCUSDT"];
  syms.forEach(sym => {
    const price = prices && prices[sym] != null ? fmtP(prices[sym]) : "—";
    const card  = document.createElement("div");
    card.className = "sym-card";
    card.innerHTML = `
      <div class="sym-name">${sym.replace("USDT","")}<span style="color:var(--border)"> /USDT</span></div>
      <div class="sym-price">${price}</div>`;
    grid.appendChild(card);
  });
}

function renderOpenTrades(open_trades) {
  const list  = $("open-list");
  const label = $("open-label");
  const count = (open_trades || []).length;
  label.textContent = `Posiciones abiertas (${count})`;
  if (!count) { list.innerHTML = `<div style="color:var(--muted);font-size:.82rem;padding:8px 2px">Sin posiciones abiertas.</div>`; return; }
  list.innerHTML = open_trades.map(t => {
    const side    = t.side === "BUY" ? "buy" : "sell";
    const unr     = t.unrealized || 0;
    const unrCls  = cls(unr);
    return `<div class="open-card ${side}-card">
      <div class="open-symbol">${t.symbol}</div>
      <div class="open-detail">${t.strategy} · ${t.side}</div>
      <div class="open-detail">Entrada: ${fmtP(t.entry_price)} → ${fmtP(t.current_price)}</div>
      <div class="open-detail">Qty: ${t.quantity}</div>
      <div class="open-unrealized ${unrCls}">${sign(unr)}${unr.toFixed(6)} USDT</div>
    </div>`;
  }).join("");
}

function renderTrades(recent_trades) {
  const body  = $("trades-body");
  const badge = $("closed-badge");
  const trades = (recent_trades || []).filter(t => t.exit_price > 0);
  badge.textContent = trades.length + " trades";
  if (!trades.length) {
    body.innerHTML = `<tr><td colspan="9" style="text-align:center;color:var(--muted);padding:28px">Sin operaciones cerradas aún</td></tr>`;
    return;
  }
  body.innerHTML = trades.map(t => {
    const isBuy = t.side === "BUY";
    return `<tr class="${isBuy ? "row-buy" : "row-sell"}">
      <td><strong>${t.symbol}</strong></td>
      <td class="td-m">${t.strategy}</td>
      <td><span class="tbadge ${isBuy ? "tbadge-buy" : "tbadge-sell"}">${t.side}</span></td>
      <td>${fmtP(t.entry_price)}</td>
      <td>${fmtP(t.exit_price)}</td>
      <td class="td-m">${t.quantity}</td>
      <td class="red">${fmtP(t.sl)}</td>
      <td class="green">${fmtP(t.tp)}</td>
      <td class="${cls(t.pnl)}">${sign(t.pnl)}${parseFloat(t.pnl).toFixed(6)}</td>
    </tr>`;
  }).join("");
}

// ── Fetch & dispatch ──────────────────────────────────────────────────────────
async function fetchData() {
  try {
    const res  = await fetch("/api/data");
    const data = await res.json();

    $("pulse-dot").className = data.live ? "pulse" : "pulse off";

    if (!data.live) {
      $("waiting-msg").style.display    = "block";
      $("main-content").style.display   = "none";
      $("refresh-label").textContent    = data.message || "Sin datos";
      return;
    }

    $("waiting-msg").style.display  = "none";
    $("main-content").style.display = "block";

    // Detectar nueva sesión → resetear dashboard
    if (knownSessionId !== null && knownSessionId !== data.session_id) {
      resetDashboard();
    }
    knownSessionId = data.session_id;

    // Calibrar countdown local
    remainingAtFetch  = data.remaining_secs;
    fetchedAtMs       = Date.now();
    endTimeFromServer = data.end_time;

    renderSession(data);
    renderStats(data);
    renderChart(data.pnl_history);
    renderStrategies(data.recent_trades);
    renderSignals(data.signals, data.current_prices);
    renderPrices(data.current_prices);
    renderOpenTrades(data.open_trades);
    renderTrades(data.recent_trades);

  } catch(e) {
    console.error("Error fetch:", e);
    $("refresh-label").textContent = "Error de conexión";
  }
}

// ── Tick (cada segundo) ───────────────────────────────────────────────────────
function tick() {
  // Countdown del dashboard (interpolado desde último fetch)
  const elapsed = (Date.now() - fetchedAtMs) / 1000;
  const current = Math.max(0, remainingAtFetch - elapsed);
  $("session-time").textContent = fmtSecs(current);

  // Countdown hacia el próximo fetch
  countdown--;
  $("refresh-label").textContent = countdown > 0 ? `Actualizando en ${countdown}s` : "Actualizando...";
  if (countdown <= 0) {
    countdown = 15;
    fetchData();
  }
}

fetchData();
setInterval(tick, 1000);
</script>
</body>
</html>"""

@app.route("/")
def index():
    return render_template_string(HTML)

if __name__ == "__main__":
    app.run(port=5000, debug=True)
