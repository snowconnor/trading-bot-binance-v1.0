from binance.client import Client
import os
import json
import pandas as pd
import time
from datetime import datetime
from dotenv import load_dotenv
from strategies import EMAStrategy, RSIMACDStrategy, BreakoutStrategy, ScalpingStrategy, TrendFollowingStrategy
from notifications import notify_signal
from risk_management import RiskManager
from order_executor import OrderExecutor
from logger import TradeLogger
from paper_trading import PaperTrader

load_dotenv()

PAPER_TRADING   = os.getenv("PAPER_TRADING", "True") == "True"
API_KEY         = os.getenv("BINANCE_API_KEY")
API_SECRET      = os.getenv("BINANCE_API_SECRET")
INITIAL_CAPITAL = 10.0
LIVE_DATA_FILE  = "live_data.json"

client       = Client(API_KEY, API_SECRET, testnet=True)
risk_manager = RiskManager(account_balance=INITIAL_CAPITAL)
order_executor = OrderExecutor()
trade_logger   = TradeLogger()
paper_trader   = PaperTrader(initial_balance=INITIAL_CAPITAL)


def get_data(symbol, interval='1h', limit=100):
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


def write_live_data(session_id, end_time, current_prices, cycle_signals,
                    pnl_history):
    """Escribe live_data.json de forma atómica (tmp → rename)."""
    remaining_secs = max(0.0, end_time - time.time())
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
            "symbol":      t["symbol"],
            "strategy":    t["strategy"],
            "side":        t["side"],
            "entry_price": round(entry, 6),
            "current_price": round(price, 6),
            "quantity":    round(t["quantity"], 8),
            "unrealized":  round(unrealized, 6),
            "sl":          round(t["sl"], 6),
            "tp":          round(t["tp"], 6),
        })

    buy_closed  = len([t for t in closed if t["side"] == "BUY"])
    sell_closed = len([t for t in closed if t["side"] == "SELL"])

    data = {
        "session_id":      session_id,
        "end_time":        round(end_time, 3),
        "remaining_secs":  round(remaining_secs, 1),
        "last_update":     datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "initial_capital": INITIAL_CAPITAL,
        "balance":         round(summary["balance"], 6),
        "pnl":             round(summary["pnl"], 6),
        "win_rate":        round(summary["win_rate"], 2),
        "total_trades":    summary["trades"],
        "buy_trades":      buy_closed,
        "sell_trades":     sell_closed,
        "open_count":      len(paper_trader.open_trades),
        "current_prices":  {k: round(v, 6) for k, v in current_prices.items()},
        "signals":         cycle_signals,
        "pnl_history":     pnl_history,
        "open_trades":     open_trades,
        "recent_trades":   recent_trades,
    }

    tmp = LIVE_DATA_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f)
    os.replace(tmp, LIVE_DATA_FILE)


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

    SESSION_ID    = int(time.time())   # único por ejecución
    end_time      = time.time() + 14400
    loop_interval = 5 * 60            # 5 minutos
    pnl_history   = []                # historial en memoria

    print(f"🚀 Iniciando Sesión de Prueba (4 horas reales) | session_id={SESSION_ID}")
    print(f"💰 Capital Inicial: {INITIAL_CAPITAL} USDT")
    print(f"📈 Pares: {len(symbols)} | Modo: PAPER TRADING")

    try:
        while time.time() < end_time:
            try:
                timestamp      = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                remaining_secs = end_time - time.time()
                remaining_h    = round(remaining_secs / 3600, 2)
                print(f"\n--- Ciclo: {timestamp} (Quedan: {remaining_h}h / {int(remaining_secs)}s) ---")

                current_prices = {}
                cycle_signals  = []   # señales de este ciclo para live_data.json

                for symbol in symbols:
                    try:
                        df = get_data(symbol)
                        if df.empty:
                            continue

                        current_price = df['close'].iloc[-1]
                        current_prices[symbol] = current_price

                        # Fase 1: recoger señales de todas las estrategias
                        symbol_signals = []  # [(strategy_name, signal, confidence)]
                        for strategy in strategies:
                            strategy.analyze(df)
                            signal     = strategy.get_signal(df)
                            confidence = strategy.get_confidence(df)
                            print(f"  {symbol} | {strategy.name}: {signal} | Confianza: {confidence:.0%}")

                            cycle_signals.append({
                                "symbol":     symbol,
                                "strategy":   strategy.name,
                                "signal":     signal,
                                "confidence": round(confidence, 4),
                                "price":      round(current_price, 6),
                            })

                            if signal != "HOLD":
                                symbol_signals.append((strategy.name, signal, confidence))

                        # Filtro 1: señales contradictorias → ignorar ambas
                        directions = {sig for _, sig, _ in symbol_signals}
                        if "BUY" in directions and "SELL" in directions:
                            print(f"  ⚠️  {symbol}: BUY+SELL en el mismo ciclo — mercado indeciso, ignorado")
                            continue

                        # Filtro 2: confianza mínima + ejecución
                        for strat_name, signal, confidence in symbol_signals:
                            if confidence < 0.30:
                                print(f"  🔕 {symbol} | {strat_name}: conf={confidence:.0%} < 30% — ignorado")
                                continue

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

                # Actualizar PnL y sincronizar balance
                if PAPER_TRADING:
                    paper_trader.update_pnl(current_prices)
                    sum_stats = paper_trader.get_summary()
                    risk_manager.update_balance(sum_stats['balance'])
                    print(f"📊 Balance={sum_stats['balance']:.4f} | PnL={sum_stats['pnl']:+.4f} | WR={sum_stats['win_rate']:.1f}%")

                    # Snapshot para la gráfica
                    pnl_history.append({
                        "ts":      datetime.now().strftime("%H:%M:%S"),
                        "balance": round(sum_stats["balance"], 6),
                        "pnl":     round(sum_stats["pnl"], 6),
                    })
                    pnl_history = pnl_history[-120:]

                # Escribir datos para el dashboard
                write_live_data(SESSION_ID, end_time, current_prices,
                                cycle_signals, pnl_history)
                print(f"📁 live_data.json actualizado")

                # Dormir sin sobrepasar end_time
                sleep_secs = min(loop_interval, end_time - time.time())
                if sleep_secs > 0:
                    print(f"⏱  Próximo ciclo en {int(sleep_secs)} segundos.")
                    time.sleep(sleep_secs)

            except Exception as e:
                print(f"⚠️  Error en ciclo principal: {e} — continuando en {loop_interval}s")
                time.sleep(loop_interval)

    except KeyboardInterrupt:
        print("\nSesión interrumpida manualmente.")
    finally:
        print("\n⌛ Generando reporte final...")
        report = paper_trader.generate_report()
        with open("reporte_sesion.txt", "w", encoding="utf-8") as f:
            f.write(report)
        print("✅ Reporte guardado.")
