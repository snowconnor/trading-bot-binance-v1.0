import pandas as pd
from binance.client import Client
from strategies import EMAStrategy, RSIMACDStrategy, BreakoutStrategy, ScalpingStrategy, TrendFollowingStrategy
from risk_management import RiskManager
import os
from dotenv import load_dotenv

load_dotenv()

class Backtester:
    def __init__(self, symbol="BTCUSDT", interval="1h", start_str="1 month ago UTC"):
        self.api_key = os.getenv("BINANCE_API_KEY")
        self.api_secret = os.getenv("BINANCE_API_SECRET")
        self.client = Client(self.api_key, self.api_secret, testnet=True)
        self.symbol = symbol
        self.interval = interval
        self.start_str = start_str
        self.initial_capital = 1000.0

    def get_historical_data(self):
        klines = self.client.get_historical_klines(self.symbol, self.interval, self.start_str)
        df = pd.DataFrame(klines, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume', 
            'close_time', 'quote_asset_volume', 'trades', 'taker_buy_base', 
            'taker_buy_quote', 'ignore'
        ])
        df['close'] = pd.to_numeric(df['close'])
        df['high'] = pd.to_numeric(df['high'])
        df['low'] = pd.to_numeric(df['low'])
        df['volume'] = pd.to_numeric(df['volume'])
        return df

    def run_backtest(self, strategy):
        df = self.get_historical_data()
        rm = RiskManager(account_balance=self.initial_capital)
        
        balance = self.initial_capital
        trades = []
        in_position = False
        position_details = None

        # Preparar indicadores
        strategy.analyze(df)

        for i in range(len(df)):
            if i < 20: continue # Esperar a tener datos suficientes
            
            row = df.iloc[i:i+1]
            signal = strategy.get_signal(df.iloc[:i+1])

            if not in_position and signal == "BUY":
                levels = rm.calculate_levels(row['close'].iloc[0], "BUY", df.iloc[:i+1])
                position_details = levels
                in_position = True
            
            elif in_position and (signal == "SELL" or row['close'].iloc[0] <= position_details['stop_loss_price'] or row['close'].iloc[0] >= position_details['take_profit_price']):
                # Simular salida
                exit_price = row['close'].iloc[0]
                pnl = (exit_price - position_details['stop_loss_price']) * position_details['position_size'] # Simplificación
                balance += pnl
                trades.append(pnl)
                in_position = False

        return self.calculate_metrics(trades)

    def calculate_metrics(self, trades):
        if not trades: return {"total_trades": 0, "win_rate": 0, "total_pnl": 0}
        wins = [t for t in trades if t > 0]
        losses = [t for t in trades if t <= 0]
        return {
            "total_trades": len(trades),
            "win_rate": (len(wins) / len(trades)) * 100,
            "total_pnl": sum(trades),
            "max_win": max(trades) if trades else 0,
            "max_loss": min(trades) if trades else 0
        }

if __name__ == "__main__":
    bt = Backtester()
    strategies = [EMAStrategy(), RSIMACDStrategy(), BreakoutStrategy(), ScalpingStrategy(), TrendFollowingStrategy()]
    
    print(f"{'Estrategia':<20} | {'Trades':<8} | {'WinRate':<8} | {'PnL (USDT)':<12}")
    for strat in strategies:
        metrics = bt.run_backtest(strat)
        print(f"{strat.name:<20} | {metrics['total_trades']:<8} | {metrics['win_rate']:<7.1f}% | {metrics['total_pnl']:<12.2f}")
