import pandas as pd

class PaperTrader:
    def __init__(self, initial_balance=10.0):
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.open_trades = []
        self.closed_trades = []
        self.trades = []
        self.pnl_total = 0.0

    def execute_trade(self, symbol, strategy_name, side, price, qty, sl, tp):
        if any(t["symbol"] == symbol for t in self.open_trades):
            print(f"⏸️  [Paper Trading] Ya hay posición abierta en {symbol} — trade rechazado")
            return

        position_value = qty * price
        if position_value > self.balance:
            print(f"⚠️  [Paper Trading] Capital insuficiente para {symbol}: "
                  f"necesario {position_value:.4f} USDT, disponible {self.balance:.4f} USDT — trade rechazado")
            return

        trade = {
            "symbol": symbol,
            "strategy": strategy_name,
            "side": side,
            "entry_price": price,
            "quantity": qty,
            "sl": sl,
            "tp": tp,
            "status": "OPEN",
            "close_at_next": False
        }
        self.open_trades.append(trade)
        self.trades.append(trade)
        print(f"📄 [Paper Trading] {side} {qty:.6f} {symbol} @ {price:.4f} "
              f"| valor={position_value:.4f} USDT | SL={sl:.4f} TP={tp:.4f} (Estrat: {strategy_name})")

    def update_pnl(self, current_prices):
        still_open = []
        for trade in self.open_trades:
            current_price = current_prices.get(trade['symbol'])
            if not current_price:
                still_open.append(trade)
                continue

            closed = False
            pnl = 0.0

            if trade['close_at_next']:
                # PnL=0 en ciclo anterior: cerrar ahora al precio actual de mercado
                if trade['side'] == 'BUY':
                    pnl = (current_price - trade['entry_price']) * trade['quantity']
                else:
                    pnl = (trade['entry_price'] - current_price) * trade['quantity']
                closed = True

            elif current_price != trade['entry_price']:
                if trade['side'] == 'BUY':
                    if current_price >= trade['tp']:
                        # Cierre en TP: PnL máximo es el precio exacto del TP, no el precio de mercado
                        exit_price = trade['tp']
                        pnl = (exit_price - trade['entry_price']) * trade['quantity']
                        closed = True
                    elif current_price <= trade['sl']:
                        # Cierre en SL: pérdida limitada al precio del SL
                        exit_price = trade['sl']
                        pnl = (exit_price - trade['entry_price']) * trade['quantity']
                        closed = True
                else:  # SELL
                    if current_price <= trade['tp']:
                        exit_price = trade['tp']
                        pnl = (trade['entry_price'] - exit_price) * trade['quantity']
                        closed = True
                    elif current_price >= trade['sl']:
                        exit_price = trade['sl']
                        pnl = (trade['entry_price'] - exit_price) * trade['quantity']
                        closed = True

            else:
                # Precio igual al de entrada → PnL=0, marcar para cerrar en la siguiente vela
                trade['close_at_next'] = True

            if closed:
                self.pnl_total += pnl
                self.balance += pnl
                trade.update({'status': 'CLOSED', 'pnl': pnl, 'exit_price': current_price})
                self.closed_trades.append(trade)
            else:
                still_open.append(trade)

        self.open_trades = still_open

    @property
    def win_rate(self):
        if not self.closed_trades:
            return 0.0
        wins = len([t for t in self.closed_trades if t.get('pnl', 0) > 0])
        return (wins / len(self.closed_trades)) * 100

    def get_summary(self):
        return {
            'balance': self.balance,
            'pnl': self.balance - self.initial_balance,
            'trades': len(self.trades),
            'win_rate': self.win_rate
        }

    def generate_report(self):
        if not self.closed_trades:
            return "No se ejecutaron operaciones cerradas."

        df = pd.DataFrame(self.closed_trades)
        win_rate = self.win_rate

        pnl_per_symbol = df.groupby('symbol')['pnl'].sum()
        trades_per_symbol = df.groupby('symbol').size()

        pnl_per_strat = df.groupby('strategy')['pnl'].sum()
        best_strat = pnl_per_strat.idxmax()
        worst_strat = pnl_per_strat.idxmin()

        report = [
            "=== REPORTE FINAL DE SESIÓN ===",
            f"Capital Final: {self.balance:.2f} USDT",
            f"PnL Total: {self.pnl_total:.2f} USDT",
            f"Win Rate Global: {win_rate:.2f}%",
            f"Total Trades: {len(df)}",
            "",
            "--- Rendimiento por Estrategia ---",
            f"Mejor: {best_strat}",
            f"Peor:  {worst_strat}",
            "",
            "--- Detalle por Par ---"
        ]

        for symbol in pnl_per_symbol.index:
            report.append(f"{symbol:10} | Trades: {trades_per_symbol[symbol]:2} | PnL: {pnl_per_symbol[symbol]:.2f}")

        return "\n".join(report)
