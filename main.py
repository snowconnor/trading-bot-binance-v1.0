from binance.client import Client
import os
import json
import pandas as pd
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv
from strategies import EMAStrategy, RSIMACDStrategy, BreakoutStrategy, ScalpingStrategy, TrendFollowingStrategy
from notifications import notify_signal
from risk_management import RiskManager
from order_executor import OrderExecutor
from logger import TradeLogger
from paper_trading import PaperTrader

load_dotenv()

PAPER_TRADING    = os.getenv("PAPER_TRADING", "True") == "True"
API_KEY          = os.getenv("BINANCE_API_KEY")
API_SECRET       = os.getenv("BINANCE_API_SECRET")
INITIAL_CAPITAL  = 10.0
LIVE_DATA_FILE   = "live_data.json"
BOT_CONTROL_FILE = "bot_control.json"
LOG_FILE         = "trade_log.csv"

DURATION_LABELS = {
    1800: "30m", 3600: "1h", 7200: "2h",
    14400: "4h", 28800: "8h", 86400: "24h", 0: "continuo"
}

client         = Client(API_KEY, API_SECRET, testnet=True)
risk_manager   = RiskManager(account_balance=INITIAL_CAPITAL)
order_executor = OrderExecutor()
trade_logger   = TradeLogger()
paper_trader   = PaperTrader(initial_balance=INITIAL_CAPITAL)


def get_data(symbol, interval='15m', limit=100):
    try:
        klines = client.get_klines(symbol=symbol, interval=interval, limit=limit)
        df = pd.DataFrame(klines, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_asset_volume', 'trades', 'taker_buy_base',
            'taker_buy_quote', 'ignore'
        ])
        df['close']  = pd.to_numeric(df['close'])
        df['high']   = pd.to_numeric(df['high'])
        df['low']    = pd.to_numeric(df['low'])
        df['volume'] = pd.to_numeric(df['volume'])
        return df
    except Exception:
        return pd.DataFrame()


# ─── Control ──────────────────────────────────────────────────────────────────

def read_control():
    defaults = {
        "action":                "none",
        "capital":               INITIAL_CAPITAL,
        "interval_secs":         300,
        "min_confidence":        0.30,
        "session_duration_secs": 3600,
    }
    if not os.path.exists(BOT_CONTROL_FILE):
        return defaults
    try:
        with open(BOT_CONTROL_FILE, "r", encoding="utf-8") as f:
            return {**defaults, **json.load(f)}
    except Exception:
        return defaults


def clear_action():
    ctrl = read_control()
    ctrl["action"] = "none"
    with open(BOT_CONTROL_FILE, "w", encoding="utf-8") as f:
        json.dump(ctrl, f)


# ─── Reporte ──────────────────────────────────────────────────────────────────

def generate_full_report(session_id, session_start_time, session_duration_secs, initial_capital):
    """Genera reporte completo con toda la información de la sesión."""
    now       = datetime.now()
    start_dt  = datetime.fromtimestamp(session_start_time)
    real_dur  = timedelta(seconds=int(now.timestamp() - session_start_time))
    dur_label = DURATION_LABELS.get(session_duration_secs,
                                    f"{session_duration_secs}s" if session_duration_secs else "Continuo")

    closed  = paper_trader.closed_trades
    summary = paper_trader.get_summary()
    pnl_pct = (summary['pnl'] / initial_capital * 100) if initial_capital > 0 else 0.0

    sep = "=" * 54
    lines = [
        sep,
        "  REPORTE DE SESIÓN — TRADING BOT BINANCE",
        sep,
        f"  Session ID       : {session_id}",
        f"  Duración config  : {dur_label}",
        f"  Inicio           : {start_dt.strftime('%Y-%m-%d %H:%M:%S')}",
        f"  Fin              : {now.strftime('%Y-%m-%d %H:%M:%S')}",
        f"  Duración real    : {real_dur}",
        sep,
        "  CAPITAL",
        f"  Inicial          : {initial_capital:.4f} USDT",
        f"  Final            : {summary['balance']:.4f} USDT",
        f"  PnL Total        : {summary['pnl']:+.4f} USDT  ({pnl_pct:+.2f}%)",
        sep,
        "  OPERACIONES",
        f"  Total trades     : {len(closed)}",
        f"  Win Rate         : {summary['win_rate']:.2f}%",
        f"  BUY cerradas     : {len([t for t in closed if t['side']=='BUY'])}",
        f"  SELL cerradas    : {len([t for t in closed if t['side']=='SELL'])}",
        f"  Abiertas (fin)   : {len(paper_trader.open_trades)}",
        "",
    ]

    if closed:
        df = pd.DataFrame(closed)

        lines.append("  PnL POR ESTRATEGIA")
        strat_pnl = df.groupby('strategy')['pnl'].sum().sort_values(ascending=False)
        for strat, pnl in strat_pnl.items():
            lines.append(f"    {strat:<32} {pnl:+.6f} USDT")
        lines.append("")

        lines.append("  PnL POR PAR")
        sym_pnl   = df.groupby('symbol')['pnl'].sum().sort_values(ascending=False)
        sym_count = df.groupby('symbol').size()
        for sym, pnl in sym_pnl.items():
            lines.append(f"    {sym:<12}  Trades: {sym_count[sym]:>3}  PnL: {pnl:+.6f} USDT")
        lines.append("")

        best_sym  = sym_pnl.idxmax()
        worst_sym = sym_pnl.idxmin()
        lines.append(f"  Mejor par  : {best_sym}  ({sym_pnl[best_sym]:+.6f} USDT)")
        lines.append(f"  Peor par   : {worst_sym}  ({sym_pnl[worst_sym]:+.6f} USDT)")
    else:
        lines.append("  Sin operaciones cerradas en esta sesión.")

    lines += ["", sep]
    return "\n".join(lines)


def save_report(session_id, session_start_time, session_duration_secs, initial_capital):
    """Guarda el reporte con nombre único basado en timestamp y duración."""
    report    = generate_full_report(session_id, session_start_time,
                                     session_duration_secs, initial_capital)
    dur_label = DURATION_LABELS.get(session_duration_secs,
                                    f"{session_duration_secs}s" if session_duration_secs else "continuo")
    filename  = f"reporte_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{dur_label}.txt"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"✅ Reporte guardado: {filename}")
    return filename


# ─── Live data ────────────────────────────────────────────────────────────────

def write_live_data(session_id, session_start_time, end_time, current_prices,
                    cycle_signals, pnl_history, status,
                    loop_interval, min_confidence, session_duration_secs):
    continuous     = (session_duration_secs == 0)
    remaining_secs = -1 if continuous else round(max(0.0, end_time - time.time()), 1)
    summary        = paper_trader.get_summary()

    closed = paper_trader.closed_trades
    recent_trades = []
    for t in list(reversed(closed))[:25]:
        recent_trades.append({
            "symbol":      t["symbol"],
            "strategy":    t["strategy"],
            "side":        t["side"],
            "entry_price": round(t["entry_price"], 6),
            "exit_price":  round(t.get("exit_price", 0), 6),
            "quantity":    round(t["quantity"], 8),
            "pnl":         round(t.get("pnl", 0.0), 6),
            "sl":          round(t["sl"], 6),
            "tp":          round(t["tp"], 6),
        })

    open_trades = []
    for t in paper_trader.open_trades:
        entry = t["entry_price"]
        price = current_prices.get(t["symbol"], entry)
        unrealized = (price - entry) * t["quantity"] if t["side"] == "BUY" \
                     else (entry - price) * t["quantity"]
        open_trades.append({
            "symbol":        t["symbol"],
            "strategy":      t["strategy"],
            "side":          t["side"],
            "entry_price":   round(entry, 6),
            "current_price": round(price, 6),
            "quantity":      round(t["quantity"], 8),
            "unrealized":    round(unrealized, 6),
            "sl":            round(t["sl"], 6),
            "tp":            round(t["tp"], 6),
        })

    buy_closed  = len([t for t in closed if t["side"] == "BUY"])
    sell_closed = len([t for t in closed if t["side"] == "SELL"])

    data = {
        "session_id":            session_id,
        "session_start_time":    datetime.fromtimestamp(session_start_time).strftime("%Y-%m-%d %H:%M:%S"),
        "session_duration_secs": session_duration_secs,
        "session_duration_label": DURATION_LABELS.get(session_duration_secs,
                                    f"{session_duration_secs}s" if session_duration_secs else "Continuo"),
        "end_time":              round(end_time, 3),
        "remaining_secs":        remaining_secs,
        "last_update":           datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "status":                status,
        "loop_interval":         loop_interval,
        "min_confidence":        min_confidence,
        "initial_capital":       INITIAL_CAPITAL,
        "balance":               round(summary["balance"], 6),
        "pnl":                   round(summary["pnl"], 6),
        "win_rate":              round(summary["win_rate"], 2),
        "total_trades":          summary["trades"],
        "buy_trades":            buy_closed,
        "sell_trades":           sell_closed,
        "open_count":            len(paper_trader.open_trades),
        "current_prices":        {k: round(v, 6) for k, v in current_prices.items()},
        "signals":               cycle_signals,
        "pnl_history":           pnl_history,
        "open_trades":           open_trades,
        "recent_trades":         recent_trades,
    }

    tmp = LIVE_DATA_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f)
    os.replace(tmp, LIVE_DATA_FILE)


# ─── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    symbols = [
        "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT",
        "DOGEUSDT", "AVAXUSDT", "DOTUSDT", "POLUSDT", "LINKUSDT", "LTCUSDT"
    ]
    strategies = [
        EMAStrategy(),
        RSIMACDStrategy(),
        BreakoutStrategy(),
        ScalpingStrategy(),
        TrendFollowingStrategy()
    ]

    # ── Configuración inicial ─────────────────────────────────────────────────
    _ctrl                = read_control()
    loop_interval        = int(_ctrl.get("interval_secs", 300))
    min_confidence       = float(_ctrl.get("min_confidence", 0.30))
    session_duration_secs = int(_ctrl.get("session_duration_secs", 3600))

    SESSION_ID         = int(time.time())
    session_start_time = time.time()
    continuous         = (session_duration_secs == 0)
    end_time           = session_start_time + (session_duration_secs if not continuous
                                               else 365 * 24 * 3600)
    pnl_history        = []
    paused             = False
    bot_status         = "running"
    last_report_date   = datetime.now().date()   # para reporte diario en modo continuo

    dur_label = DURATION_LABELS.get(session_duration_secs,
                                    f"{session_duration_secs}s" if session_duration_secs else "Continuo")
    print(f"🚀 Iniciando Sesión | session_id={SESSION_ID} | duración={dur_label}")
    print(f"💰 Capital: {INITIAL_CAPITAL} USDT | Intervalo: {loop_interval}s | Conf.mín: {min_confidence:.0%}")

    try:
        while continuous or time.time() < end_time:
            try:
                # ── Leer control ──────────────────────────────────────────────
                ctrl   = read_control()
                action = ctrl.get("action", "none")

                if action == "stop":
                    clear_action()
                    bot_status = "stopped"
                    print("🛑 Stop recibido — terminando sesión.")
                    write_live_data(SESSION_ID, session_start_time, end_time,
                                    {}, [], pnl_history, bot_status,
                                    loop_interval, min_confidence, session_duration_secs)
                    break

                if action == "pause":
                    clear_action()
                    paused = True; bot_status = "paused"
                    print("⏸️  Bot pausado.")

                if action == "resume":
                    clear_action()
                    paused = False; bot_status = "running"
                    print("▶️  Bot reanudado.")

                if action == "new_session":
                    clear_action()
                    # Guardar reporte de sesión anterior
                    save_report(SESSION_ID, session_start_time,
                                session_duration_secs, INITIAL_CAPITAL)
                    # Reiniciar todo
                    SESSION_ID          = int(time.time())
                    session_start_time  = time.time()
                    pnl_history         = []
                    paper_trader.__init__(initial_balance=INITIAL_CAPITAL)
                    risk_manager.update_balance(INITIAL_CAPITAL)
                    if os.path.exists(LOG_FILE):
                        os.remove(LOG_FILE)
                    continuous = (session_duration_secs == 0)
                    end_time   = session_start_time + (session_duration_secs if not continuous
                                                       else 365 * 24 * 3600)
                    paused = False; bot_status = "running"
                    print(f"🔄 Nueva sesión | session_id={SESSION_ID}")

                # ── Aplicar settings ──────────────────────────────────────────
                loop_interval        = int(ctrl.get("interval_secs",         300))
                min_confidence       = float(ctrl.get("min_confidence",       0.30))
                new_dur              = int(ctrl.get("session_duration_secs",  3600))
                new_capital          = float(ctrl.get("capital", INITIAL_CAPITAL))

                # Actualizar duración si cambió — end_time desde ahora, no desde session_start_time,
                # para que nunca quede en el pasado y el loop no salga accidentalmente.
                if new_dur != session_duration_secs:
                    session_duration_secs = new_dur
                    continuous = (session_duration_secs == 0)
                    end_time   = time.time() + (session_duration_secs if not continuous
                                                else 365 * 24 * 3600)
                    print(f"⏱  Duración actualizada: {DURATION_LABELS.get(new_dur, str(new_dur)+'s')}")

                if new_capital != INITIAL_CAPITAL:
                    INITIAL_CAPITAL = new_capital
                    risk_manager.update_balance(new_capital)
                    print(f"💰 Capital actualizado: {new_capital} USDT")

                # ── Modo pausado ──────────────────────────────────────────────
                if paused:
                    write_live_data(SESSION_ID, session_start_time, end_time,
                                    {}, [], pnl_history, bot_status,
                                    loop_interval, min_confidence, session_duration_secs)
                    time.sleep(5)
                    continue

                # ── Ciclo normal ──────────────────────────────────────────────
                remaining_secs = -1 if continuous else (end_time - time.time())
                remaining_str  = "∞" if continuous else f"{round(remaining_secs/3600, 2)}h"
                timestamp      = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print(f"\n--- Ciclo: {timestamp} (Quedan: {remaining_str}) | "
                      f"Intervalo: {loop_interval}s | Conf.mín: {min_confidence:.0%} ---")

                current_prices = {}
                cycle_signals  = []

                for symbol in symbols:
                    try:
                        df = get_data(symbol)
                        if df.empty:
                            continue

                        current_price = df['close'].iloc[-1]
                        current_prices[symbol] = current_price

                        symbol_signals    = []
                        trend_conf        = 0.0   # confianza de TrendFollowing para filtro Scalping
                        for strategy in strategies:
                            strategy.analyze(df)
                            signal     = strategy.get_signal(df)
                            confidence = strategy.get_confidence(df)
                            print(f"  {symbol} | {strategy.name}: {signal} | conf={confidence:.0%}")

                            cycle_signals.append({
                                "symbol":     symbol,
                                "strategy":   strategy.name,
                                "signal":     signal,
                                "confidence": round(confidence, 4),
                                "price":      round(current_price, 6),
                            })
                            if strategy.name == "TrendFollowing":
                                trend_conf = confidence
                            if signal != "HOLD":
                                symbol_signals.append((strategy.name, signal, confidence))

                        # Filtrar por confianza y tendencia ANTES de detectar contradictorias
                        # Scalping requiere TrendFollowing conf >= 50% como confirmación de tendencia
                        weak_trend = (trend_conf < 0.50)
                        qualified = []
                        for s, sig, c in symbol_signals:
                            if c < min_confidence:
                                print(f"  🔕 {symbol} | {s}: conf={c:.0%} < {min_confidence:.0%} — ignorado")
                                continue
                            if s == "Scalping" and weak_trend:
                                print(f"  🔕 {symbol} | Scalping: TrendFollowing conf={trend_conf:.0%} < 50% — ignorado")
                                continue
                            qualified.append((s, sig, c))

                        directions = {sig for _, sig, _ in qualified}
                        if "BUY" in directions and "SELL" in directions:
                            print(f"  ⚠️  {symbol}: BUY+SELL cualificadas mismo ciclo — ignorado")
                            continue

                        for strat_name, signal, confidence in qualified:
                            if len(paper_trader.open_trades) >= 3:
                                print(f"  🚫 Límite de 3 posiciones abiertas alcanzado — ignorando {symbol} | {strat_name}")
                                break
                            risk_data = risk_manager.calculate_levels(
                                current_price, signal, df, confidence)
                            if PAPER_TRADING:
                                paper_trader.execute_trade(
                                    symbol, strat_name, signal, current_price,
                                    risk_data['position_size'],
                                    risk_data['stop_loss_price'],
                                    risk_data['take_profit_price']
                                )
                                trade_logger.log_trade(
                                    symbol, strat_name, signal, current_price,
                                    risk_data['stop_loss_price'], risk_data['take_profit_price'],
                                    risk_data['position_size'], risk_data['risk_amount'], "PAPER"
                                )
                    except Exception as e:
                        print(f"Error en {symbol}: {e}")

                if PAPER_TRADING:
                    paper_trader.update_pnl(current_prices)
                    sum_stats = paper_trader.get_summary()
                    risk_manager.update_balance(sum_stats['balance'])
                    print(f"📊 Balance={sum_stats['balance']:.4f} | PnL={sum_stats['pnl']:+.4f} | WR={sum_stats['win_rate']:.1f}%")
                    pnl_history.append({
                        "ts":      datetime.now().strftime("%H:%M:%S"),
                        "balance": round(sum_stats["balance"], 6),
                        "pnl":     round(sum_stats["pnl"], 6),
                    })
                    pnl_history = pnl_history[-120:]

                write_live_data(SESSION_ID, session_start_time, end_time,
                                current_prices, cycle_signals, pnl_history,
                                bot_status, loop_interval, min_confidence,
                                session_duration_secs)
                print("📁 live_data.json actualizado")

                # ── Reporte diario automático (modo continuo) ─────────────────
                if continuous:
                    today = datetime.now().date()
                    if today != last_report_date:
                        print(f"🌙 Medianoche — guardando reporte diario...")
                        save_report(SESSION_ID, session_start_time,
                                    session_duration_secs, INITIAL_CAPITAL)
                        last_report_date = today

                sleep_secs = min(loop_interval, max(0, end_time - time.time()))
                if sleep_secs > 0:
                    print(f"⏱  Próximo ciclo en {int(sleep_secs)}s.")
                    sleep_end = time.time() + sleep_secs
                    while time.time() < sleep_end:
                        time.sleep(min(5, max(0, sleep_end - time.time())))
                        # Leer control cada 5s para aplicar cambios sin esperar al próximo ciclo
                        _c = read_control()
                        changed = False

                        _new_dur = int(_c.get("session_duration_secs", session_duration_secs))
                        if _new_dur != session_duration_secs:
                            session_duration_secs = _new_dur
                            continuous = (session_duration_secs == 0)
                            end_time   = time.time() + (session_duration_secs if not continuous
                                                        else 365 * 24 * 3600)
                            sleep_end  = min(sleep_end, time.time() + loop_interval)
                            changed = True
                            print(f"⏱  Duración actualizada: {DURATION_LABELS.get(_new_dur, str(_new_dur)+'s')}")

                        _new_cap = float(_c.get("capital", INITIAL_CAPITAL))
                        if _new_cap != INITIAL_CAPITAL:
                            INITIAL_CAPITAL = _new_cap
                            risk_manager.update_balance(_new_cap)
                            changed = True
                            print(f"💰 Capital actualizado: {_new_cap} USDT")

                        _new_iv = int(_c.get("interval_secs", loop_interval))
                        if _new_iv != loop_interval:
                            loop_interval = _new_iv
                            sleep_end = min(sleep_end, time.time() + loop_interval)
                            changed = True

                        _new_mc = float(_c.get("min_confidence", min_confidence))
                        if _new_mc != min_confidence:
                            min_confidence = _new_mc
                            changed = True

                        if changed:
                            write_live_data(SESSION_ID, session_start_time, end_time,
                                            current_prices, cycle_signals, pnl_history,
                                            bot_status, loop_interval, min_confidence,
                                            session_duration_secs)

                        # Salir del sleep si hay una acción pendiente
                        if _c.get("action", "none") != "none":
                            break

            except Exception as e:
                print(f"⚠️  Error en ciclo: {e} — continuando en {loop_interval}s")
                time.sleep(loop_interval)

    except KeyboardInterrupt:
        print("\nSesión interrumpida manualmente.")
    finally:
        bot_status = "stopped"
        write_live_data(SESSION_ID, session_start_time, end_time,
                        {}, [], pnl_history, bot_status,
                        loop_interval, min_confidence, session_duration_secs)
        save_report(SESSION_ID, session_start_time, session_duration_secs, INITIAL_CAPITAL)
