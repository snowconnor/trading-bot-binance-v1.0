from flask import Flask, jsonify, render_template_string, request
import os
import json

app = Flask(__name__)

LIVE_DATA_FILE   = "live_data.json"
BOT_CONTROL_FILE = "bot_control.json"
LOG_FILE         = "trade_log.csv"
INITIAL_CAPITAL  = 10.0

# ─── Helpers ─────────────────────────────────────────────────────────────────

def read_control():
    defaults = {"action": "none", "capital": INITIAL_CAPITAL,
                "interval_secs": 300, "min_confidence": 0.30,
                "session_duration_secs": 3600}
    if not os.path.exists(BOT_CONTROL_FILE):
        return defaults
    try:
        with open(BOT_CONTROL_FILE, "r", encoding="utf-8") as f:
            return {**defaults, **json.load(f)}
    except Exception:
        return defaults

def write_control(ctrl: dict):
    with open(BOT_CONTROL_FILE, "w", encoding="utf-8") as f:
        json.dump(ctrl, f)

# ─── API ─────────────────────────────────────────────────────────────────────

@app.route("/api/data")
def api_data():
    if not os.path.exists(LIVE_DATA_FILE):
        ctrl = read_control()
        return jsonify({"live": False, "message": "Esperando que main.py inicie...",
                        "control": ctrl})
    try:
        with open(LIVE_DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        data["live"]    = True
        data["control"] = read_control()
        return jsonify(data)
    except Exception as e:
        return jsonify({"live": False, "message": f"Error leyendo datos: {e}"})


@app.route("/api/control", methods=["GET", "POST"])
def api_control():
    """GET devuelve bot_control.json; POST recibe acciones/settings."""
    if request.method == "GET":
        return jsonify(read_control())
    body = request.get_json(silent=True) or {}
    ctrl = read_control()

    # Acción puntual; si solo se cambian settings (sin action), limpiar
    # cualquier acción pendiente para evitar que un new_session anterior
    # se ejecute accidentalmente al aplicar capital u otro setting.
    if "action" in body:
        ctrl["action"] = body["action"]
    else:
        ctrl["action"] = "none"

    # Settings persistentes
    if "capital" in body:
        try:
            ctrl["capital"] = max(1.0, float(body["capital"]))
        except ValueError:
            return jsonify({"ok": False, "error": "capital inválido"}), 400

    if "interval_secs" in body:
        allowed = [60, 300, 900, 1800]
        val = int(body["interval_secs"])
        ctrl["interval_secs"] = val if val in allowed else 300

    if "min_confidence" in body:
        try:
            ctrl["min_confidence"] = max(0.0, min(1.0, float(body["min_confidence"])))
        except ValueError:
            return jsonify({"ok": False, "error": "confianza inválida"}), 400

    if "session_duration_secs" in body:
        allowed = [1800, 3600, 7200, 14400, 28800, 86400, 0]
        try:
            val = int(body["session_duration_secs"])
            ctrl["session_duration_secs"] = val if val in allowed else 3600
        except (ValueError, TypeError):
            return jsonify({"ok": False, "error": "duración inválida"}), 400

    write_control(ctrl)
    return jsonify({"ok": True, "control": ctrl})


@app.route("/api/new_session", methods=["POST"])
def api_new_session():
    """Limpia archivos de sesión y envía acción new_session al bot."""
    for f in [LIVE_DATA_FILE, LIVE_DATA_FILE + ".tmp"]:
        if os.path.exists(f):
            os.remove(f)
    if os.path.exists(LOG_FILE):
        os.remove(LOG_FILE)
    ctrl = read_control()
    ctrl["action"] = "new_session"
    write_control(ctrl)
    return jsonify({"ok": True})


# ─── HTML ─────────────────────────────────────────────────────────────────────

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
.header{display:flex;align-items:center;justify-content:space-between;margin-bottom:16px;flex-wrap:wrap;gap:10px}
.header h1{font-size:1.4rem;font-weight:700;letter-spacing:-.4px}
.header h1 span{color:var(--blue)}
.hright{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.badge-pill{display:flex;align-items:center;gap:6px;background:var(--surface);border:1px solid var(--border);border-radius:20px;padding:5px 13px;font-size:.8rem;color:var(--muted)}
.pulse{width:8px;height:8px;border-radius:50%;flex-shrink:0}
.pulse.running{background:var(--green);animation:pulse 1.4s infinite}
.pulse.paused {background:var(--yellow)}
.pulse.stopped{background:var(--red)}
.pulse.off    {background:var(--muted)}
@keyframes pulse{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.35;transform:scale(1.35)}}
.status-text.running{color:var(--green)}
.status-text.paused {color:var(--yellow)}
.status-text.stopped{color:var(--red)}

/* ── Controls panel ── */
.controls-panel{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:16px 20px;margin-bottom:16px;display:flex;flex-wrap:wrap;gap:16px;align-items:flex-end}
.ctrl-group{display:flex;flex-direction:column;gap:5px}
.ctrl-label{font-size:.7rem;text-transform:uppercase;letter-spacing:.7px;color:var(--muted)}
.ctrl-row{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.btn{padding:7px 16px;border-radius:7px;border:1px solid var(--border);font-size:.82rem;font-weight:600;cursor:pointer;transition:all .15s;white-space:nowrap}
.btn:active{transform:scale(.97)}
.btn-pause {background:rgba(210,153,34,.12);border-color:rgba(210,153,34,.4);color:var(--yellow)}
.btn-pause:hover{background:rgba(210,153,34,.22)}
.btn-resume{background:rgba(63,185,80,.12);border-color:rgba(63,185,80,.4);color:var(--green)}
.btn-resume:hover{background:rgba(63,185,80,.22)}
.btn-stop  {background:rgba(248,81,73,.12);border-color:rgba(248,81,73,.4);color:var(--red)}
.btn-stop:hover{background:rgba(248,81,73,.22)}
.btn-apply {background:rgba(88,166,255,.12);border-color:rgba(88,166,255,.4);color:var(--blue)}
.btn-apply:hover{background:rgba(88,166,255,.22)}
.btn-new   {background:rgba(188,140,255,.1);border-color:rgba(188,140,255,.35);color:var(--purple)}
.btn-new:hover{background:rgba(188,140,255,.2)}
.ctrl-input{background:var(--surface2);border:1px solid var(--border);border-radius:6px;color:var(--text);padding:6px 10px;font-size:.84rem;width:90px}
.ctrl-input:focus{outline:none;border-color:var(--blue)}
.ctrl-select{background:var(--surface2);border:1px solid var(--border);border-radius:6px;color:var(--text);padding:6px 10px;font-size:.84rem}
.ctrl-select:focus{outline:none;border-color:var(--blue)}
.ctrl-slider{width:120px;accent-color:var(--blue)}
.ctrl-slider-val{font-size:.82rem;color:var(--blue);font-weight:600;min-width:36px}
.ctrl-divider{width:1px;background:var(--border);align-self:stretch}

/* ── Session bar ── */
.session-bar{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:12px 20px;margin-bottom:16px;display:flex;align-items:center;gap:22px;flex-wrap:wrap}
.sb-item{display:flex;flex-direction:column;gap:3px}
.sb-label{font-size:.7rem;text-transform:uppercase;letter-spacing:.8px;color:var(--muted)}
.sb-val{font-size:1.5rem;font-weight:700;font-variant-numeric:tabular-nums;color:var(--blue)}
.prog-wrap{flex:1;min-width:140px}
.prog-track{height:5px;background:var(--border);border-radius:3px;overflow:hidden;margin-top:5px}
.prog-fill{height:100%;background:linear-gradient(90deg,var(--blue),var(--purple));border-radius:3px;transition:width .6s}

/* ── Stat cards ── */
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin-bottom:16px}
.card{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:15px 17px;box-shadow:var(--shadow)}
.card-label{font-size:.7rem;text-transform:uppercase;letter-spacing:.8px;color:var(--muted);margin-bottom:6px}
.card-val{font-size:1.75rem;font-weight:700;font-variant-numeric:tabular-nums;line-height:1}
.card-sub{font-size:.76rem;color:var(--muted);margin-top:4px}
.green{color:var(--green)}.red{color:var(--red)}.blue{color:var(--blue)}.yellow{color:var(--yellow)}
.wr-track{height:6px;background:var(--border);border-radius:4px;overflow:hidden;margin-top:8px}
.wr-fill{height:100%;border-radius:4px;background:linear-gradient(90deg,var(--red) 0%,var(--yellow) 50%,var(--green) 100%);transition:width .6s}

/* ── Two-col ── */
.two-col{display:grid;grid-template-columns:1fr 310px;gap:14px;margin-bottom:16px}
@media(max-width:840px){.two-col{grid-template-columns:1fr}}
.panel{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:16px 18px;box-shadow:var(--shadow)}
.panel-title{font-size:.72rem;text-transform:uppercase;letter-spacing:.8px;color:var(--muted);margin-bottom:12px}
.chart-wrap{position:relative;height:200px}
.strat-cards{display:flex;flex-direction:column;gap:8px}
.strat-card{border-radius:8px;padding:11px 13px;border:1px solid var(--border)}
.strat-card.best{border-color:rgba(63,185,80,.35);background:rgba(63,185,80,.05)}
.strat-card.worst{border-color:rgba(248,81,73,.35);background:rgba(248,81,73,.05)}
.strat-badge{font-size:.66rem;text-transform:uppercase;letter-spacing:.7px;margin-bottom:2px}
.strat-name{font-size:.92rem;font-weight:600}
.strat-pnl{font-size:.8rem;margin-top:1px}
.strat-bars{margin-top:12px}
.sb-row{display:flex;align-items:center;gap:6px;margin-bottom:6px;font-size:.74rem}
.sb-row-label{width:115px;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.sb-row-track{flex:1;height:5px;background:var(--border);border-radius:3px;overflow:hidden}
.sb-row-fill{height:100%;border-radius:3px;min-width:2px}
.sb-row-val{width:50px;text-align:right;font-variant-numeric:tabular-nums}

/* ── Signals ── */
.section-label{font-size:.72rem;text-transform:uppercase;letter-spacing:.9px;color:var(--muted);margin-bottom:9px;padding-left:2px}
.signals-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:9px;margin-bottom:16px}
.sig-card{background:var(--surface2);border:1px solid var(--border);border-radius:8px;padding:11px 13px}
.sig-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:9px}
.sig-symbol{font-weight:700;font-size:.92rem}
.sig-price{font-size:.78rem;color:var(--muted);font-variant-numeric:tabular-nums}
.sig-rows{display:flex;flex-direction:column;gap:4px}
.sig-row{display:flex;align-items:center;gap:7px;font-size:.76rem}
.sig-strat{width:108px;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.sig-badge{padding:2px 8px;border-radius:10px;font-size:.68rem;font-weight:700;width:40px;text-align:center}
.sig-badge.buy {background:rgba(63,185,80,.15);color:var(--green);border:1px solid rgba(63,185,80,.3)}
.sig-badge.sell{background:rgba(248,81,73,.15);color:var(--red);  border:1px solid rgba(248,81,73,.3)}
.sig-badge.hold{background:rgba(139,148,158,.1);color:var(--muted);border:1px solid var(--border)}
.conf-track{flex:1;height:4px;background:var(--border);border-radius:3px;overflow:hidden}
.conf-fill{height:100%;border-radius:3px;transition:width .4s}
.conf-val{width:32px;text-align:right;color:var(--muted);font-variant-numeric:tabular-nums}

/* ── Symbol grid ── */
.sym-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:9px;margin-bottom:16px}
.sym-card{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:12px 14px;transition:border-color .18s}
.sym-card:hover{border-color:var(--blue)}
.sym-name{font-size:.74rem;color:var(--muted);margin-bottom:2px}
.sym-price{font-size:.98rem;font-weight:600;font-variant-numeric:tabular-nums}

/* ── Open trades ── */
.open-list{display:flex;flex-direction:column;gap:6px;margin-bottom:16px}
.open-card{background:var(--surface2);border:1px solid var(--border);border-radius:8px;padding:10px 13px;display:flex;align-items:center;gap:12px;flex-wrap:wrap;font-size:.8rem}
.open-card.buy-card {border-left:3px solid var(--green)}
.open-card.sell-card{border-left:3px solid var(--red)}
.open-symbol{font-weight:700;min-width:76px}
.open-detail{color:var(--muted)}
.open-unr{font-weight:600;margin-left:auto}

/* ── Trades table ── */
.table-wrap{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);overflow:hidden;box-shadow:var(--shadow)}
.table-header{display:flex;align-items:center;justify-content:space-between;padding:12px 16px;border-bottom:1px solid var(--border)}
.table-title{font-size:.72rem;text-transform:uppercase;letter-spacing:.8px;color:var(--muted)}
.count-pill{font-size:.76rem;background:var(--border);border-radius:12px;padding:2px 9px}
.t-scroll{overflow-x:auto}
table{width:100%;border-collapse:collapse;font-size:.8rem}
thead th{padding:8px 13px;text-align:left;font-size:.68rem;text-transform:uppercase;letter-spacing:.6px;color:var(--muted);background:rgba(255,255,255,.02);border-bottom:1px solid var(--border);white-space:nowrap}
tbody tr{border-bottom:1px solid rgba(48,54,61,.5);transition:background .12s}
tbody tr:hover{background:rgba(255,255,255,.03)}
tbody tr:last-child{border-bottom:none}
td{padding:8px 13px;white-space:nowrap}
.tbadge{display:inline-block;padding:2px 8px;border-radius:10px;font-size:.7rem;font-weight:700}
.tbadge-buy {background:rgba(63,185,80,.15);color:var(--green);border:1px solid rgba(63,185,80,.3)}
.tbadge-sell{background:rgba(248,81,73,.15);color:var(--red);  border:1px solid rgba(248,81,73,.3)}
.row-buy{border-left:3px solid var(--green)}.row-sell{border-left:3px solid var(--red)}
.td-m{color:var(--muted);font-size:.74rem}

/* ── Toast ── */
.toast{position:fixed;bottom:24px;right:24px;background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:10px 18px;font-size:.84rem;box-shadow:var(--shadow);opacity:0;transform:translateY(10px);transition:all .25s;pointer-events:none;z-index:999}
.toast.show{opacity:1;transform:translateY(0)}
.toast.ok  {border-color:rgba(63,185,80,.5);color:var(--green)}
.toast.err {border-color:rgba(248,81,73,.5);color:var(--red)}

#waiting-msg{text-align:center;padding:60px 20px;color:var(--muted);display:none}
.footer{text-align:center;color:var(--muted);font-size:.72rem;margin-top:28px}
</style>
</head>
<body>

<!-- Toast -->
<div class="toast" id="toast"></div>

<!-- Header -->
<div class="header">
  <h1>Trading <span>Dashboard</span></h1>
  <div class="hright">
    <div class="badge-pill">
      <div class="pulse off" id="status-dot"></div>
      <span class="status-text" id="status-text">Sin datos</span>
    </div>
    <div class="badge-pill">
      <div class="pulse" id="refresh-dot" style="background:var(--blue);animation:pulse 1.4s infinite"></div>
      <span id="refresh-label">Conectando...</span>
    </div>
  </div>
</div>

<!-- Controls panel -->
<div class="controls-panel">

  <!-- Pause / Resume / Stop / New Session -->
  <div class="ctrl-group">
    <div class="ctrl-label">Sesión</div>
    <div class="ctrl-row">
      <button class="btn btn-pause"  id="btn-pause"  onclick="sendAction('pause')">⏸ Pausar</button>
      <button class="btn btn-resume" id="btn-resume" onclick="sendAction('resume')" style="display:none">▶ Reanudar</button>
      <button class="btn btn-stop"   onclick="sendAction('stop')">🛑 Detener</button>
      <button class="btn btn-new"    onclick="newSession()">🔄 Nueva Sesión</button>
    </div>
  </div>

  <div class="ctrl-divider"></div>

  <!-- Capital -->
  <div class="ctrl-group">
    <div class="ctrl-label">Capital inicial (USDT)</div>
    <div class="ctrl-row">
      <input type="number" class="ctrl-input" id="inp-capital" value="10" min="1" step="1">
      <button class="btn btn-apply" onclick="applyCapital()">Aplicar</button>
    </div>
  </div>

  <div class="ctrl-divider"></div>

  <!-- Intervalo -->
  <div class="ctrl-group">
    <div class="ctrl-label">Intervalo de ciclo</div>
    <div class="ctrl-row">
      <select class="ctrl-select" id="sel-interval" onchange="applyInterval()">
        <option value="60">1 min</option>
        <option value="300" selected>5 min</option>
        <option value="900">15 min</option>
        <option value="1800">30 min</option>
      </select>
    </div>
  </div>

  <div class="ctrl-divider"></div>

  <!-- Confianza mínima -->
  <div class="ctrl-group">
    <div class="ctrl-label">Confianza mínima</div>
    <div class="ctrl-row">
      <input type="range" class="ctrl-slider" id="slider-conf" min="0" max="100" value="30"
             oninput="$('slider-conf-val').textContent=this.value+'%'" onchange="applyConfidence()">
      <span class="ctrl-slider-val" id="slider-conf-val">30%</span>
    </div>
  </div>

  <div class="ctrl-divider"></div>

  <!-- Duración de sesión -->
  <div class="ctrl-group">
    <div class="ctrl-label">Duración de sesión</div>
    <div class="ctrl-row">
      <select class="ctrl-select" id="sel-duration">
        <option value="1800">30 minutos</option>
        <option value="3600" selected>1 hora</option>
        <option value="7200">2 horas</option>
        <option value="14400">4 horas</option>
        <option value="28800">8 horas</option>
        <option value="86400">24 horas</option>
        <option value="0">Continuo ∞</option>
      </select>
      <button class="btn btn-apply" onclick="applyDuration()">Aplicar</button>
    </div>
  </div>

</div>

<!-- Waiting -->
<div id="waiting-msg">⏳ Esperando que <code>main.py</code> inicie…</div>

<!-- Main content -->
<div id="main-content">

  <!-- Session bar -->
  <div class="session-bar">
    <div class="sb-item">
      <div class="sb-label">Tiempo restante</div>
      <div class="sb-val" id="session-time">--:--:--</div>
    </div>
    <div class="sb-item prog-wrap">
      <div class="sb-label">Progreso (<span id="prog-pct">0</span>%)</div>
      <div class="prog-track"><div class="prog-fill" id="prog-fill" style="width:0%"></div></div>
    </div>
    <div class="sb-item">
      <div class="sb-label">Capital inicial</div>
      <div style="font-weight:700;color:var(--blue)" id="cap-display">10.00 USDT</div>
    </div>
    <div class="sb-item">
      <div class="sb-label">Última actualización</div>
      <div id="last-update" style="font-size:.83rem;color:var(--muted)">—</div>
    </div>
  </div>

  <!-- Stat cards -->
  <div class="cards">
    <div class="card">
      <div class="card-label">Balance</div>
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
          <div class="strat-badge green">Mejor</div>
          <div class="strat-name" id="best-strat">N/A</div>
          <div class="strat-pnl green" id="best-pnl"></div>
        </div>
        <div class="strat-card worst">
          <div class="strat-badge red">Peor</div>
          <div class="strat-name" id="worst-strat">N/A</div>
          <div class="strat-pnl red" id="worst-pnl"></div>
        </div>
      </div>
      <div class="strat-bars" id="strat-bars"></div>
    </div>
  </div>

  <!-- Signals -->
  <div class="section-label">Señales en vivo</div>
  <div class="signals-grid" id="signals-grid"></div>

  <!-- Prices -->
  <div class="section-label">Precios de mercado</div>
  <div class="sym-grid" id="sym-grid"></div>

  <!-- Open trades -->
  <div class="section-label" id="open-label">Posiciones abiertas (0)</div>
  <div class="open-list" id="open-list"></div>

  <!-- Closed trades table -->
  <div class="table-wrap">
    <div class="table-header">
      <div class="table-title">Operaciones cerradas</div>
      <div class="count-pill" id="closed-badge">0 trades</div>
    </div>
    <div class="t-scroll">
      <table>
        <thead>
          <tr><th>Par</th><th>Estrategia</th><th>Lado</th><th>Entrada</th>
              <th>Salida</th><th>Cantidad</th><th>SL</th><th>TP</th><th>PnL</th></tr>
        </thead>
        <tbody id="trades-body">
          <tr><td colspan="9" style="text-align:center;color:var(--muted);padding:26px">Sin operaciones aún</td></tr>
        </tbody>
      </table>
    </div>
  </div>
</div>

<div class="footer">Trading Dashboard · live_data.json · bot_control.json · refresh 15s</div>

<script>
// ── Chart ────────────────────────────────────────────────────────────────────
const ctx = document.getElementById("pnl-chart").getContext("2d");
const pnlChart = new Chart(ctx, {
  type: "line",
  data: {
    labels: [],
    datasets: [
      { label:"Balance", data:[], borderColor:"#58a6ff", backgroundColor:"rgba(88,166,255,.07)",
        borderWidth:2, pointRadius:2, tension:0.35, fill:true },
      { label:"PnL", data:[], borderColor:"#3fb950", backgroundColor:"rgba(63,185,80,.05)",
        borderWidth:1.5, pointRadius:0, tension:0.35, fill:true, borderDash:[4,3] }
    ]
  },
  options:{
    responsive:true, maintainAspectRatio:false, animation:{duration:300},
    plugins:{
      legend:{labels:{color:"#8b949e",boxWidth:12,font:{size:11}}},
      tooltip:{backgroundColor:"#161b22",borderColor:"#30363d",borderWidth:1,
               titleColor:"#e6edf3",bodyColor:"#8b949e",
               callbacks:{label:c=>` ${c.dataset.label}: ${c.parsed.y.toFixed(6)} USDT`}}
    },
    scales:{
      x:{ticks:{color:"#8b949e",maxTicksLimit:8,font:{size:10}},grid:{color:"rgba(48,54,61,.4)"}},
      y:{ticks:{color:"#8b949e",font:{size:10},callback:v=>v.toFixed(3)+"U"},grid:{color:"rgba(48,54,61,.4)"}}
    }
  }
});

// ── State ────────────────────────────────────────────────────────────────────
const $ = id => document.getElementById(id);
let knownSessionId   = null;
let remainingAtFetch = 0;
let fetchedAtMs      = Date.now();
let lastUpdateSeen   = null;   // último last_update recibido de main.py
let countdown        = 15;

function resetDashboard(){
  pnlChart.data.labels=[];
  pnlChart.data.datasets[0].data=[];
  pnlChart.data.datasets[1].data=[];
  pnlChart.update("none");
  $("signals-grid").innerHTML="";
  $("open-list").innerHTML="";
  $("trades-body").innerHTML=`<tr><td colspan="9" style="text-align:center;color:var(--muted);padding:26px">Sin operaciones aún</td></tr>`;
  lastUpdateSeen=null;  // forzar re-anclaje en la próxima sesión
}

// ── Toast ────────────────────────────────────────────────────────────────────
let toastTimer;
function toast(msg, type="ok"){
  const el=$("toast"); el.textContent=msg;
  el.className="toast show "+(type==="ok"?"ok":"err");
  clearTimeout(toastTimer);
  toastTimer=setTimeout(()=>el.className="toast",2500);
}

// ── Helpers ──────────────────────────────────────────────────────────────────
const fmtP = v => v!=null ? parseFloat(v).toLocaleString("en-US",{minimumFractionDigits:2,maximumFractionDigits:6}) : "—";
const sign = v => v>=0?"+":"";
const cls  = v => v>0?"green":v<0?"red":"";
function fmtSecs(s){
  if(s<0) return "∞ CONTINUO";
  s=Math.max(0,Math.floor(s));
  const h=Math.floor(s/3600),m=Math.floor((s%3600)/60),sec=s%60;
  return `${String(h).padStart(2,"0")}:${String(m).padStart(2,"0")}:${String(sec).padStart(2,"0")}`;
}
function confColor(c){return c>=0.7?"var(--green)":c>=0.4?"var(--yellow)":"var(--red)";}

// ── Control actions ──────────────────────────────────────────────────────────
async function sendAction(action){
  try{
    const r=await fetch("/api/control",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({action})});
    const d=await r.json();
    if(d.ok){
      toast(action==="pause"?"Bot pausado ⏸":"Bot "+action+" ✓");
      if(action==="pause"){ $("btn-pause").style.display="none"; $("btn-resume").style.display=""; }
      if(action==="resume"){ $("btn-resume").style.display="none"; $("btn-pause").style.display=""; }
    } else toast("Error: "+d.error,"err");
  } catch(e){ toast("Sin conexión","err"); }
}

async function applyCapital(){
  const val=parseFloat($("inp-capital").value);
  if(isNaN(val)||val<1){toast("Capital inválido","err");return;}
  const r=await fetch("/api/control",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({capital:val})});
  const d=await r.json();
  if(d.ok) toast(`Capital → ${val} USDT ✓`); else toast("Error","err");
}

async function applyInterval(){
  const val=parseInt($("sel-interval").value);
  const r=await fetch("/api/control",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({interval_secs:val})});
  const d=await r.json();
  if(d.ok) toast(`Intervalo → ${val/60} min ✓`); else toast("Error","err");
}

async function applyConfidence(){
  const val=parseInt($("slider-conf").value)/100;
  const r=await fetch("/api/control",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({min_confidence:val})});
  const d=await r.json();
  if(d.ok) toast(`Conf. mínima → ${(val*100).toFixed(0)}% ✓`); else toast("Error","err");
}

async function applyDuration(){
  const val=parseInt($("sel-duration").value);
  const r=await fetch("/api/control",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({session_duration_secs:val})});
  const d=await r.json();
  const labels={1800:"30 min",3600:"1 hora",7200:"2 horas",14400:"4 horas",28800:"8 horas",86400:"24 horas",0:"Continuo ∞"};
  if(d.ok) toast(`Duración → ${labels[val]||val} ✓`); else toast("Error","err");
}

async function newSession(){
  if(!confirm("¿Nueva sesión? Se limpiarán los datos actuales.")) return;
  const r=await fetch("/api/new_session",{method:"POST"});
  const d=await r.json();
  if(d.ok){ resetDashboard(); toast("Nueva sesión iniciada 🔄"); }
  else toast("Error","err");
}

// ── Sync controls from live_data ─────────────────────────────────────────────
function syncControls(data){
  // Intervalo
  const iv=data.loop_interval||300;
  const sel=$("sel-interval");
  for(let o of sel.options) if(parseInt(o.value)===iv){ sel.value=o.value; break; }

  // Confianza
  const mc=Math.round((data.min_confidence||0.30)*100);
  $("slider-conf").value=mc;
  $("slider-conf-val").textContent=mc+"%";

  // Capital — leer desde control (valor configurado) para reflejar cambios inmediatos
  const capVal=(data.control&&data.control.capital)||data.initial_capital||10;
  $("cap-display").textContent=parseFloat(capVal).toFixed(2)+" USDT";
  $("inp-capital").value=parseFloat(capVal).toFixed(2);

  // Duración — leer desde control (bot_control.json), no desde live_data
  const ctrl=data.control||{};
  const dur=ctrl.session_duration_secs!=null?ctrl.session_duration_secs:3600;
  const selDur=$("sel-duration");
  for(let o of selDur.options) if(parseInt(o.value)===dur){ selDur.value=o.value; break; }

  // Status buttons
  const status=data.status||"running";
  if(status==="paused"){ $("btn-pause").style.display="none"; $("btn-resume").style.display=""; }
  else { $("btn-pause").style.display=""; $("btn-resume").style.display="none"; }
}

// ── Render ───────────────────────────────────────────────────────────────────
function renderStatus(status){
  const dot=$("status-dot"), txt=$("status-text");
  const map={running:["running","🟢 CORRIENDO"],paused:["paused","🟡 PAUSADO"],stopped:["stopped","🔴 DETENIDO"]};
  const [cls,label]=map[status]||["off","Sin datos"];
  dot.className="pulse "+cls; txt.className="status-text "+cls; txt.textContent=label;
}

function renderSession(d){
  if(d.remaining_secs<0){
    // Modo continuo
    $("session-time").textContent="∞ CONTINUO";
    $("prog-pct").textContent="∞";
    $("prog-fill").style.width="100%";
    $("prog-fill").style.background="linear-gradient(90deg,var(--purple),var(--blue))";
  } else {
    const durSecs=d.session_duration_secs||3600;
    // Usar remaining interpolado localmente para evitar saltos en cada fetch
    const localElapsed=(Date.now()-fetchedAtMs)/1000;
    const currentRemaining=Math.max(0,remainingAtFetch-localElapsed);
    const elapsedSecs=Math.max(0,durSecs-currentRemaining);
    const pct=Math.min(100,Math.round((elapsedSecs/durSecs)*100));
    $("prog-pct").textContent=pct;
    $("prog-fill").style.width=pct+"%";
    $("prog-fill").style.background="";
  }
  $("last-update").textContent=d.last_update||"—";
}

function renderStats(d){
  const pnl=d.pnl,bal=d.balance;
  $("balance").textContent=bal.toFixed(6)+" USDT";
  $("balance-sub").textContent=sign(pnl)+pnl.toFixed(6)+" desde inicio";
  $("pnl").textContent=sign(pnl)+pnl.toFixed(6); $("pnl").className="card-val "+cls(pnl);
  $("pnl-sub").textContent=pnl>=0?"Ganancia acumulada":"Pérdida acumulada";
  $("win-rate").textContent=d.win_rate.toFixed(1)+"%"; $("wr-bar").style.width=d.win_rate+"%";
  $("total-trades").textContent=d.total_trades;
  $("trades-sub").textContent=`${d.buy_trades+d.sell_trades} cerradas · ${d.open_count||0} abiertas`;
}

function renderChart(h){
  if(!h||!h.length) return;
  pnlChart.data.labels=h.map(x=>x.ts);
  pnlChart.data.datasets[0].data=h.map(x=>x.balance);
  pnlChart.data.datasets[1].data=h.map(x=>x.pnl);
  pnlChart.update("none");
}

function renderStrategies(trades){
  const byS={};
  (trades||[]).forEach(t=>{if(!byS[t.strategy])byS[t.strategy]=0;byS[t.strategy]+=t.pnl||0;});
  const e=Object.entries(byS).sort((a,b)=>b[1]-a[1]);
  if(!e.length) return;
  $("best-strat").textContent=e[0][0]; $("best-pnl").textContent=sign(e[0][1])+e[0][1].toFixed(6)+" USDT";
  const w=e[e.length-1];
  $("worst-strat").textContent=w[0]; $("worst-pnl").textContent=sign(w[1])+w[1].toFixed(6)+" USDT";
  const bars=$("strat-bars"); bars.innerHTML="";
  const maxA=Math.max(...e.map(([,v])=>Math.abs(v)),0.0001);
  e.forEach(([n,v])=>{
    const pct=(Math.abs(v)/maxA*100).toFixed(1),col=v>=0?"var(--green)":"var(--red)";
    const r=document.createElement("div"); r.className="sb-row";
    r.innerHTML=`<div class="sb-row-label" title="${n}">${n}</div>
      <div class="sb-row-track"><div class="sb-row-fill" style="width:${pct}%;background:${col}"></div></div>
      <div class="sb-row-val ${cls(v)}">${sign(v)}${v.toFixed(4)}</div>`;
    bars.appendChild(r);
  });
}

function renderSignals(signals,prices){
  const grid=$("signals-grid");
  if(!signals||!signals.length){grid.innerHTML=`<div style="color:var(--muted);font-size:.83rem;padding:8px">Sin señales aún.</div>`;return;}
  const bySym={};
  signals.forEach(s=>{if(!bySym[s.symbol])bySym[s.symbol]=[];bySym[s.symbol].push(s);});
  grid.innerHTML="";
  Object.entries(bySym).forEach(([sym,rows])=>{
    const price=prices&&prices[sym]!=null?fmtP(prices[sym]):"—";
    const card=document.createElement("div"); card.className="sig-card";
    const rowsHtml=rows.map(r=>{
      const bc=r.signal==="BUY"?"buy":r.signal==="SELL"?"sell":"hold";
      const cp=(r.confidence*100).toFixed(0),cc=confColor(r.confidence);
      return `<div class="sig-row"><div class="sig-strat" title="${r.strategy}">${r.strategy}</div>
        <span class="sig-badge ${bc}">${r.signal}</span>
        <div class="conf-track"><div class="conf-fill" style="width:${cp}%;background:${cc}"></div></div>
        <div class="conf-val">${cp}%</div></div>`;
    }).join("");
    card.innerHTML=`<div class="sig-header"><div class="sig-symbol">${sym.replace("USDT","")}<span style="color:var(--border)">/USDT</span></div><div class="sig-price">${price}</div></div><div class="sig-rows">${rowsHtml}</div>`;
    grid.appendChild(card);
  });
}

function renderPrices(prices){
  const grid=$("sym-grid"); grid.innerHTML="";
  ["BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","XRPUSDT","ADAUSDT",
   "DOGEUSDT","AVAXUSDT","DOTUSDT","POLUSDT","LINKUSDT","LTCUSDT"].forEach(sym=>{
    const p=prices&&prices[sym]!=null?fmtP(prices[sym]):"—";
    const c=document.createElement("div"); c.className="sym-card";
    c.innerHTML=`<div class="sym-name">${sym.replace("USDT","")}<span style="color:var(--border)"> /USDT</span></div><div class="sym-price">${p}</div>`;
    grid.appendChild(c);
  });
}

function renderOpen(open){
  const list=$("open-list"),label=$("open-label"),n=(open||[]).length;
  label.textContent=`Posiciones abiertas (${n})`;
  if(!n){list.innerHTML=`<div style="color:var(--muted);font-size:.8rem;padding:6px 2px">Sin posiciones abiertas.</div>`;return;}
  list.innerHTML=open.map(t=>{
    const side=t.side==="BUY"?"buy":"sell",u=t.unrealized||0;
    return `<div class="open-card ${side}-card"><div class="open-symbol">${t.symbol}</div>
      <div class="open-detail">${t.strategy}·${t.side}</div>
      <div class="open-detail">Entrada:${fmtP(t.entry_price)}→${fmtP(t.current_price)}</div>
      <div class="open-detail">Qty:${t.quantity}</div>
      <div class="open-unr ${cls(u)}">${sign(u)}${u.toFixed(6)} USDT</div></div>`;
  }).join("");
}

function renderTrades(trades){
  const body=$("trades-body"),badge=$("closed-badge");
  const t=(trades||[]).filter(x=>x.exit_price>0);
  badge.textContent=t.length+" trades";
  if(!t.length){body.innerHTML=`<tr><td colspan="9" style="text-align:center;color:var(--muted);padding:26px">Sin operaciones cerradas aún</td></tr>`;return;}
  body.innerHTML=t.map(tr=>{
    const b=tr.side==="BUY";
    return `<tr class="${b?"row-buy":"row-sell"}">
      <td><strong>${tr.symbol}</strong></td><td class="td-m">${tr.strategy}</td>
      <td><span class="tbadge ${b?"tbadge-buy":"tbadge-sell"}">${tr.side}</span></td>
      <td>${fmtP(tr.entry_price)}</td><td>${fmtP(tr.exit_price)}</td>
      <td class="td-m">${tr.quantity}</td><td class="red">${fmtP(tr.sl)}</td>
      <td class="green">${fmtP(tr.tp)}</td>
      <td class="${cls(tr.pnl)}">${sign(tr.pnl)}${parseFloat(tr.pnl).toFixed(6)}</td></tr>`;
  }).join("");
}

// ── Fetch ────────────────────────────────────────────────────────────────────
async function fetchData(){
  try{
    const res=await fetch("/api/data"),data=await res.json();
    if(!data.live){
      $("waiting-msg").style.display="block";
      $("main-content").style.display="none";
      $("refresh-label").textContent=data.message||"Sin datos";
      renderStatus("stopped");
      return;
    }
    $("waiting-msg").style.display="none";
    $("main-content").style.display="block";

    if(knownSessionId!==null&&knownSessionId!==data.session_id) resetDashboard();
    knownSessionId=data.session_id;

    // Solo re-anclar el countdown cuando main.py escribió datos nuevos.
    // Si last_update no cambió, live_data.json es un snapshot antiguo y
    // el valor de remaining_secs ya está desactualizado — la interpolación
    // local es más precisa que sobrescribirla.
    if(data.last_update !== lastUpdateSeen){
      remainingAtFetch = data.remaining_secs;
      fetchedAtMs      = Date.now();
      lastUpdateSeen   = data.last_update;
    }

    renderStatus(data.status||"running");
    syncControls(data);
    renderSession(data);
    renderStats(data);
    renderChart(data.pnl_history);
    renderStrategies(data.recent_trades);
    renderSignals(data.signals,data.current_prices);
    renderPrices(data.current_prices);
    renderOpen(data.open_trades);
    renderTrades(data.recent_trades);
  } catch(e){
    $("refresh-label").textContent="Error de conexión";
  }
}

// ── Tick ─────────────────────────────────────────────────────────────────────
function tick(){
  const elapsed=(Date.now()-fetchedAtMs)/1000;
  if(remainingAtFetch<0){
    $("session-time").textContent="∞ CONTINUO";
  } else {
    $("session-time").textContent=fmtSecs(Math.max(0,remainingAtFetch-elapsed));
  }
  countdown--;
  $("refresh-label").textContent=countdown>0?`Actualizando en ${countdown}s`:"Actualizando...";
  if(countdown<=0){countdown=15;fetchData();}
}

// ── Init controls from bot_control.json on page load ─────────────────────────
async function initControls(){
  try{
    const r=await fetch("/api/control");
    const ctrl=await r.json();
    // Intervalo
    const sel=$("sel-interval");
    const iv=ctrl.interval_secs||300;
    for(let o of sel.options) if(parseInt(o.value)===iv){ sel.value=o.value; break; }
    // Confianza
    const mc=Math.round((ctrl.min_confidence||0.30)*100);
    $("slider-conf").value=mc; $("slider-conf-val").textContent=mc+"%";
    // Capital
    const cap=ctrl.capital||10;
    $("inp-capital").value=cap;
    // Duración
    const dur=ctrl.session_duration_secs!=null?ctrl.session_duration_secs:3600;
    const selDur=$("sel-duration");
    for(let o of selDur.options) if(parseInt(o.value)===dur){ selDur.value=o.value; break; }
  } catch(e){}
}

initControls();
fetchData();
setInterval(tick,1000);
</script>
</body>
</html>"""

@app.route("/")
def index():
    return render_template_string(HTML)

if __name__ == "__main__":
    app.run(port=5000, debug=True)
