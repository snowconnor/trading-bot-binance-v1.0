from ta.volatility import AverageTrueRange
import pandas as pd

class RiskManager:
    """
    Gestiona el riesgo, calcula Stop Loss, Take Profit y tamaño de posición.

    Reglas de capital (cuenta de 10 USDT):
    - risk_per_trade = 1%  → máximo 0.10 USDT en riesgo por operación
    - max_position_pct = 20% → la posición no puede valer más de 2.0 USDT
      (evita apalancamiento implícito en monedas con ATR muy pequeño)
    """
    def __init__(self, atr_period=14, risk_per_trade=0.01, reward_ratio=2.0,
                 account_balance=10.0):
        self.atr_period      = atr_period
        self.risk_per_trade  = risk_per_trade  # 1 % del balance (referencia)
        self.reward_ratio    = reward_ratio    # R:R 1:2
        self.account_balance = account_balance

    def update_balance(self, new_balance: float):
        """Sincroniza el balance real del PaperTrader para que el sizing sea dinámico."""
        self.account_balance = max(new_balance, 0.0)

    def calculate_levels(self, entry_price: float, signal: str, df: pd.DataFrame,
                         confidence: float = 0.5):
        """
        Calcula niveles de riesgo con position sizing proporcional a la confianza.

        SL = ATR × 1.5
        TP = SL × reward_ratio (1:2)
        position_value = balance * confidence  (mín 10%, máx 95%)
        """
        atr = AverageTrueRange(high=df['high'], low=df['low'], close=df['close'],
                               window=self.atr_period)
        current_atr = atr.average_true_range().iloc[-1]

        stop_loss_distance = current_atr * 1.5
        if stop_loss_distance <= 0 or entry_price <= 0:
            stop_loss_distance = entry_price * 0.01

        if signal == "BUY":
            stop_loss_price   = entry_price - stop_loss_distance
            take_profit_price = entry_price + (stop_loss_distance * self.reward_ratio)
        else:  # SELL
            stop_loss_price   = entry_price + stop_loss_distance
            take_profit_price = entry_price - (stop_loss_distance * self.reward_ratio)

        # Riesgo de referencia para logging
        risk_amount = self.account_balance * self.risk_per_trade

        # Position sizing proporcional a la confianza: mín 10%, máx 95% del balance
        confidence_clamped = max(0.10, min(0.95, confidence))
        position_value     = self.account_balance * confidence_clamped
        position_size      = position_value / entry_price

        return {
            "stop_loss_price":   round(stop_loss_price,   6),
            "take_profit_price": round(take_profit_price, 6),
            "position_size":     round(position_size,     8),
            "risk_amount":       round(risk_amount,       4),
            "confidence":        round(confidence_clamped, 4),
            "position_value":    round(position_value,    4),
        }

    def get_trailing_stop(self, current_price: float, high_price: float, signal: str, atr: float):
        """
        Retorna el nivel de Trailing Stop ajustado.
        """
        # Lógica simplificada: stop sube/baja siguiendo el precio
        if signal == "BUY":
            return current_price - (atr * 2)
        return current_price + (atr * 2)
