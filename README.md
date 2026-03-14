# Trading Bot Binance v1.0

Bot de trading automatizado para Binance (Testnet y producción) con paper trading, dashboard web en tiempo real y gestión de riesgo dinámica.

---

## Descripción general

Sistema completo de trading algorítmico que analiza 12 pares USDT cada 5 minutos usando 5 estrategias independientes. Cada estrategia calcula una señal (BUY / SELL / HOLD) y un nivel de confianza (0–100%) que determina el tamaño de la posición. El dashboard web muestra el estado de la sesión en tiempo real vía `live_data.json`.

---

## Características principales

- **5 estrategias de trading**: EMA Crossover, RSI+MACD, Breakout (Bollinger), Scalping, Trend Following (ADX)
- **Sistema de confianza proporcional**: el capital invertido escala con la confianza de cada estrategia (10%–95% del balance)
- **Gestión de riesgo dinámica**: Stop Loss y Take Profit calculados con ATR (Average True Range), ratio R:R 1:2
- **Paper Trading realista**: simulación con SL/TP exactos, rechazo por capital insuficiente, cierre en siguiente vela si PnL=0
- **Dashboard web en tiempo real**: Flask + Chart.js, señales en vivo, gráfica de PnL, auto-refresh cada 15 segundos
- **Loop continuo multi-par**: 12 pares (BTC, ETH, BNB, SOL, XRP, ADA, DOGE, AVAX, DOT, POL, LINK, LTC)
- **Sesiones de 4 horas** con timer preciso y reporte final automático
- **Logger CSV + Excel**: registro de cada operación con fecha, par, estrategia, SL, TP, cantidad y riesgo
- **Backtesting** con datos históricos de Binance
- **Comunicación main↔dashboard** vía `live_data.json` (escritura atómica)

---

## Requisitos

- Python 3.9+
- Cuenta en [Binance Testnet](https://testnet.binance.vision/) (gratuita)
- Dependencias:

```
pip install python-binance pandas ta flask python-dotenv openpyxl
```

---

## Instalación

```bash
git clone https://github.com/snowconnor/trading-bot-binance-v1.0.git
cd trading-bot-binance-v1.0
pip install python-binance pandas ta flask python-dotenv openpyxl
```

Crear archivo `.env` en la raíz del proyecto:

```env
BINANCE_API_KEY=tu_api_key_de_testnet
BINANCE_API_SECRET=tu_api_secret_de_testnet
PAPER_TRADING=True
```

---

## Cómo usar

**1. Iniciar el bot de trading:**
```bash
python main.py
```
Inicia una sesión de 4 horas, analiza los 12 pares cada 5 minutos y ejecuta operaciones en paper trading.

**2. Iniciar el dashboard web** (en otra terminal):
```bash
python dashboard.py
```
Abre [http://localhost:5000](http://localhost:5000) en el navegador.

**3. Ejecutar backtesting:**
```bash
python backtest.py
```

---

## Estructura de archivos

```
trading_bot/
├── main.py              # Loop principal, sesión de 4 horas, escritura de live_data.json
├── strategies.py        # 5 estrategias con señal y confianza (get_signal / get_confidence)
├── risk_management.py   # SL/TP con ATR, position sizing por confianza, ratio 1:2
├── paper_trading.py     # Simulador: execute_trade, update_pnl, generate_report
├── dashboard.py         # Servidor Flask + HTML dashboard con Chart.js
├── logger.py            # Registro de trades en CSV y Excel
├── order_executor.py    # Ejecución de órdenes reales en Binance (Market + OCO)
├── notifications.py     # Notificaciones de señales
├── backtest.py          # Backtesting con datos históricos
├── .env                 # API keys (no incluido en el repo)
└── .gitignore
```

---

## Variables de entorno

| Variable | Descripción | Default |
|---|---|---|
| `BINANCE_API_KEY` | API Key de Binance Testnet | — |
| `BINANCE_API_SECRET` | API Secret de Binance Testnet | — |
| `PAPER_TRADING` | Activar modo paper trading | `True` |

---

## Advertencia

Este bot es un proyecto educativo. **No usar con dinero real** sin entender completamente el riesgo. El trading algorítmico puede resultar en pérdida total del capital invertido.
