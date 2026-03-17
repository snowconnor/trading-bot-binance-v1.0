import pandas as pd
import numpy as np
from ta.trend import EMAIndicator, ADXIndicator, MACD
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands
from abc import ABC, abstractmethod

class BaseStrategy(ABC):
    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def analyze(self, df: pd.DataFrame):
        pass

    @abstractmethod
    def should_buy(self, df: pd.DataFrame) -> bool:
        pass

    @abstractmethod
    def should_sell(self, df: pd.DataFrame) -> bool:
        pass

    def get_signal(self, df: pd.DataFrame) -> str:
        if self.should_buy(df):
            return "BUY"
        elif self.should_sell(df):
            return "SELL"
        return "HOLD"

    def get_confidence(self, df: pd.DataFrame) -> float:
        """Retorna confianza 0.0–1.0. Subclases sobreescriben este método."""
        return 0.5

class EMAStrategy(BaseStrategy):
    def __init__(self, fast_period=9, slow_period=21):
        super().__init__(f"EMA_{fast_period}_{slow_period}")
        self.fast_period = fast_period
        self.slow_period = slow_period

    def analyze(self, df: pd.DataFrame):
        df['ema_fast'] = EMAIndicator(close=df['close'], window=self.fast_period).ema_indicator()
        df['ema_slow'] = EMAIndicator(close=df['close'], window=self.slow_period).ema_indicator()
        return df

    def should_buy(self, df: pd.DataFrame) -> bool:
        if len(df) < 2: return False
        return (df['ema_fast'].iloc[-1] > df['ema_slow'].iloc[-1]) and (df['ema_fast'].iloc[-2] <= df['ema_slow'].iloc[-2])

    def should_sell(self, df: pd.DataFrame) -> bool:
        if len(df) < 2: return False
        return (df['ema_fast'].iloc[-1] < df['ema_slow'].iloc[-1]) and (df['ema_fast'].iloc[-2] >= df['ema_slow'].iloc[-2])

    def get_confidence(self, df: pd.DataFrame) -> float:
        """Distancia % entre ema_fast y ema_slow normalizada a 2% = confianza 1.0."""
        try:
            fast = df['ema_fast'].iloc[-1]
            slow = df['ema_slow'].iloc[-1]
            if slow == 0 or pd.isna(fast) or pd.isna(slow):
                return 0.5
            pct_gap = abs(fast - slow) / slow  # 0.01 = 1%, 0.02 = 2%
            return min(pct_gap / 0.02, 1.0)
        except Exception:
            return 0.5

class RSIMACDStrategy(BaseStrategy):
    def __init__(self, rsi_period=10, macd_fast=8, macd_slow=17, macd_signal=6):
        super().__init__("RSI_MACD")
        self.rsi_period = rsi_period
        self.macd_fast = macd_fast
        self.macd_slow = macd_slow
        self.macd_signal = macd_signal

    def analyze(self, df: pd.DataFrame):
        df['rsi'] = RSIIndicator(close=df['close'], window=self.rsi_period).rsi()
        macd = MACD(close=df['close'], window_fast=self.macd_fast, window_slow=self.macd_slow, window_sign=self.macd_signal)
        df['macd'] = macd.macd()
        df['macd_signal'] = macd.macd_signal()
        return df

    def should_buy(self, df: pd.DataFrame) -> bool:
        if len(df) < 5: return False
        return (df['rsi'].iloc[-1] < 40) and (df['macd'].iloc[-1] > df['macd_signal'].iloc[-1])

    def should_sell(self, df: pd.DataFrame) -> bool:
        if len(df) < 5: return False
        return (df['rsi'].iloc[-1] > 60) and (df['macd'].iloc[-1] < df['macd_signal'].iloc[-1])

    def get_confidence(self, df: pd.DataFrame) -> float:
        """abs(RSI - 50) / 50 → RSI=20 da 0.6, RSI=10 da 0.8, RSI=50 da 0.0."""
        try:
            rsi = df['rsi'].iloc[-1]
            if pd.isna(rsi):
                return 0.5
            return min(abs(rsi - 50) / 50, 1.0)
        except Exception:
            return 0.5

class BreakoutStrategy(BaseStrategy):
    def __init__(self, length=20, std=2):
        super().__init__("Breakout")
        self.length = length
        self.std = std

    def analyze(self, df: pd.DataFrame):
        bb = BollingerBands(close=df['close'], window=self.length, window_dev=self.std)
        df['bb_high'] = bb.bollinger_hband()
        df['bb_low'] = bb.bollinger_lband()
        return df

    def should_buy(self, df: pd.DataFrame) -> bool:
        return (df['close'].iloc[-1] > df['bb_high'].iloc[-1])

    def should_sell(self, df: pd.DataFrame) -> bool:
        return (df['close'].iloc[-1] < df['bb_low'].iloc[-1])

    def get_confidence(self, df: pd.DataFrame) -> float:
        """Volumen actual / promedio de las últimas 20 velas, cap 1.0."""
        try:
            vol_now = df['volume'].iloc[-1]
            vol_avg = df['volume'].iloc[-20:].mean()
            if vol_avg == 0 or pd.isna(vol_avg):
                return 0.5
            return min(vol_now / vol_avg, 1.0)
        except Exception:
            return 0.5

class ScalpingStrategy(BaseStrategy):
    def __init__(self, length=20, std=2):
        super().__init__("Scalping")
        self.length = length
        self.std = std

    def analyze(self, df: pd.DataFrame):
        bb = BollingerBands(close=df['close'], window=self.length, window_dev=self.std)
        df['bb_low']  = bb.bollinger_lband()
        df['bb_mid']  = bb.bollinger_mavg()
        df['bb_high'] = bb.bollinger_hband()
        df['rsi']     = RSIIndicator(close=df['close'], window=14).rsi()
        df['sc_ema9']  = EMAIndicator(close=df['close'], window=9).ema_indicator()
        df['sc_ema21'] = EMAIndicator(close=df['close'], window=21).ema_indicator()
        return df

    def should_buy(self, df: pd.DataFrame) -> bool:
        rsi_filter  = (df['rsi'].iloc[-1] > 20) and (df['rsi'].iloc[-1] < 80)
        band_width  = df['bb_high'].iloc[-1] - df['bb_low'].iloc[-1]
        lower_20pct = df['bb_low'].iloc[-1] + 0.20 * band_width
        uptrend     = df['sc_ema9'].iloc[-1] > df['sc_ema21'].iloc[-1]
        return (df['close'].iloc[-1] <= lower_20pct) and rsi_filter and uptrend

    def should_sell(self, df: pd.DataFrame) -> bool:
        rsi_filter  = (df['rsi'].iloc[-1] > 20) and (df['rsi'].iloc[-1] < 80)
        band_width  = df['bb_high'].iloc[-1] - df['bb_low'].iloc[-1]
        upper_80pct = df['bb_high'].iloc[-1] - 0.20 * band_width
        downtrend   = df['sc_ema9'].iloc[-1] < df['sc_ema21'].iloc[-1]
        return (df['close'].iloc[-1] >= upper_80pct) and rsi_filter and downtrend

    def get_confidence(self, df: pd.DataFrame) -> float:
        """Distancia normalizada al borde de la banda según dirección de la señal.
        BUY : (bb_mid - price) / (bb_mid - bb_low)  → 1.0 cuando price == bb_low
        SELL: (price - bb_mid) / (bb_high - bb_mid) → 1.0 cuando price == bb_high"""
        try:
            price   = df['close'].iloc[-1]
            bb_mid  = df['bb_mid'].iloc[-1]
            bb_low  = df['bb_low'].iloc[-1]
            bb_high = df['bb_high'].iloc[-1]
            if any(pd.isna(v) for v in (price, bb_mid, bb_low, bb_high)):
                return 0.5
            if price <= bb_mid:
                band_width = bb_mid - bb_low
                if band_width == 0:
                    return 0.5
                return min(max((bb_mid - price) / band_width, 0.0), 1.0)
            else:
                band_width = bb_high - bb_mid
                if band_width == 0:
                    return 0.5
                return min(max((price - bb_mid) / band_width, 0.0), 1.0)
        except Exception:
            return 0.5

class TrendFollowingStrategy(BaseStrategy):
    def __init__(self, adx_period=7):
        super().__init__("TrendFollowing")
        self.adx_period = adx_period

    def analyze(self, df: pd.DataFrame):
        adx_ind = ADXIndicator(high=df['high'], low=df['low'], close=df['close'], window=self.adx_period)
        df['adx'] = adx_ind.adx()
        df['ema_200'] = EMAIndicator(close=df['close'], window=200).ema_indicator()
        return df

    def should_buy(self, df: pd.DataFrame) -> bool:
        if len(df) < 200: return False
        return (df['adx'].iloc[-1] > 15) and (df['close'].iloc[-1] > df['ema_200'].iloc[-1])

    def should_sell(self, df: pd.DataFrame) -> bool:
        if len(df) < 200: return False
        return (df['close'].iloc[-1] < df['ema_200'].iloc[-1])

    def get_confidence(self, df: pd.DataFrame) -> float:
        """ADX / 50, cap 1.0. ADX=25 da 0.5, ADX=50 da 1.0."""
        try:
            adx = df['adx'].iloc[-1]
            if pd.isna(adx):
                return 0.5
            return min(adx / 50.0, 1.0)
        except Exception:
            return 0.5
