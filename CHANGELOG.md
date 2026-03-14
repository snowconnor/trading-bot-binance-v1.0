# Changelog

Todos los cambios notables de este proyecto están documentados en este archivo.

---

## v1.0.0 — 2026-03-14

### Agregado

#### Estrategias (`strategies.py`)
- **EMAStrategy**: cruce de EMA rápida (9) y lenta (21); confianza = distancia % entre EMAs normalizada a 2%
- **RSIMACDStrategy**: señal cuando RSI < 40 (BUY) o > 60 (SELL) con confirmación de MACD; confianza = `abs(RSI - 50) / 50`
- **BreakoutStrategy**: ruptura de Bandas de Bollinger (20, 2σ); confianza = volumen actual / promedio 20 velas
- **ScalpingStrategy**: precio en banda inferior de Bollinger con filtro RSI; confianza = cercanía al borde de la banda
- **TrendFollowingStrategy**: ADX > 15 con precio sobre/bajo EMA 200; confianza = `ADX / 50`
- Método `get_confidence(df)` en `BaseStrategy` con fallback 0.5 para todas las subclases

#### Gestión de riesgo (`risk_management.py`)
- Stop Loss dinámico basado en ATR × 1.5
- Take Profit con ratio riesgo/recompensa 1:2 (ATR × 3.0)
- Position sizing proporcional a la confianza: `position_value = balance × confidence` (mín 10%, máx 95%)
- Método `update_balance()` para sincronización dinámica con el balance real del PaperTrader
- Fallback de SL al 1% del precio de entrada si ATR = 0

#### Paper Trading (`paper_trading.py`)
- `execute_trade()`: verificación de capital suficiente antes de abrir posición
- `update_pnl()`: cierre exacto al precio de TP o SL (no al precio de mercado), evitando ganancias irreales
- Cierre en siguiente vela para posiciones con PnL = 0 (precio igual al de entrada) via flag `close_at_next`
- `get_summary()`: balance, PnL, total de trades y win rate
- `generate_report()`: reporte final con rendimiento por par y por estrategia

#### Bot principal (`main.py`)
- Loop continuo de 4 horas (`end_time = time.time() + 14400`)
- 12 pares: BTCUSDT, ETHUSDT, BNBUSDT, SOLUSDT, XRPUSDT, ADAUSDT, DOGEUSDT, AVAXUSDT, DOTUSDT, POLUSDT, LINKUSDT, LTCUSDT
- Intervalo de 5 minutos entre ciclos con `sleep = min(300, end_time - now)` para no sobrepasar la sesión
- `SESSION_ID` único por ejecución (timestamp Unix)
- Escritura atómica de `live_data.json` (`.tmp` + `os.replace`) al final de cada ciclo
- `cycle_signals[]`: todas las señales del ciclo (incluido HOLD) con confianza y precio para el dashboard
- Historial de PnL en memoria (`pnl_history[]`, máx 120 puntos) para la gráfica
- Sincronización de balance entre `PaperTrader` y `RiskManager` en cada ciclo
- Reporte final guardado en `reporte_sesion.txt` al terminar la sesión
- Doble `try/except`: interno por símbolo y externo por ciclo completo, para que errores puntuales no rompan el loop

#### Dashboard web (`dashboard.py`)
- Servidor Flask con endpoint `/api/data` que lee `live_data.json` directamente
- Sin dependencia de Binance API: todos los datos vienen de `main.py` vía archivo compartido
- Detección automática de nueva sesión por cambio de `session_id` → limpia gráfica y contadores
- Countdown interpolado en tiempo real (tick cada segundo en JS, calibrado con `remaining_secs` del servidor)
- Sección **Señales en vivo**: cards por símbolo con barra de confianza color-coded por estrategia
- Gráfica de PnL con Chart.js (Balance + PnL, dos datasets)
- Tarjetas de estado: balance, PnL, win rate con barra de progreso, total de operaciones
- Posiciones abiertas con PnL no realizado calculado en vivo
- Tabla de operaciones cerradas con colores (verde BUY, rojo SELL)
- Tarjetas de precios de mercado para los 12 pares
- Mejor y peor estrategia del día con mini bar-chart
- Panel de sesión con barra de progreso y tiempo restante
- Auto-refresh cada 15 segundos sin recarga de página (fetch + DOM update)
- Pantalla de espera cuando `live_data.json` no existe aún
- Diseño oscuro moderno (`#0d1117`) con variables CSS

#### Logger (`logger.py`)
- Registro de trades en CSV (`trade_log.csv`) con cabecera automática
- Reporte diario en Excel (`reporte_diario.xlsx`) con una hoja por fecha

#### Otros módulos
- `order_executor.py`: ejecución de órdenes Market y OCO en Binance Testnet
- `notifications.py`: notificaciones de señales
- `backtest.py`: backtesting con datos históricos de Binance

### Infraestructura
- `.env` para credenciales (no incluido en el repo)
- `.gitignore` excluye datos sensibles y archivos de sesión
