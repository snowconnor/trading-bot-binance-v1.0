# Changelog

Todos los cambios notables de este proyecto están documentados en este archivo.

---

## v1.2.0 — 2026-03-17

### Mejorado
- ScalpingStrategy: filtro de tendencia con EMA9/EMA21 — solo BUY en mercado alcista (EMA9 > EMA21), solo SELL en bajista
- Límite global de 3 posiciones abiertas simultáneas (antes ilimitado)
- RiskManager: cap de capital por operación ajustado a [20%, 70%] del balance (antes [10%, 50%])
- RiskManager: límite máximo SL 3% del precio, TP 9% del precio — evita niveles irreales con ATR alto en 15m
- Filtro de contradictorias mejorado: aplica solo sobre señales que superan min_confidence
- Filtro de tendencia para Scalping: requiere TrendFollowing conf ≥ 50% (ADX ≥ 25) para operar
- Timeframe cambiado de 1h a 15m para mayor frecuencia de señales en mercado lateral
- Controles del dashboard: selector de duración de sesión (30m/1h/2h/4h/8h/24h/Continuo ∞)
- Dashboard: countdown interpolado localmente cada segundo, sin saltos en cada fetch
- Dashboard: controles se sincronizan desde bot_control.json al cargar la página (F5)

### Corregido
- Take Profit negativo en órdenes SELL: ATR × 6 superaba el precio de entrada (ahora cap 9%)
- Sesiones reiniciándose al cambiar duración: end_time se recalculaba desde session_start_time pudiendo quedar en el pasado
- Countdown del dashboard reiniciándose a valores antiguos cada 15s (re-anclaje solo cuando last_update cambia)
- exit_price en trades cerrados guardaba current_price en lugar del precio real de TP/SL
- Acción new_session preservándose accidentalmente al aplicar settings de capital o intervalo
- ScalpingStrategy.get_confidence() retornando 0 en señales SELL (fórmula solo cubría BUY)

### Resultados
- Win Rate mejoró de 40% a 80%
- PnL positivo +0.40% en última sesión de prueba

---

## v1.1.0 — 2026-03-14

### Mejorado
- Filtro de señales contradictorias: si en el mismo ciclo hay BUY y SELL para el mismo par, se ignoran ambas (mercado indeciso)
- Confianza mínima del 30% para ejecutar trades — señales débiles descartadas antes de operar
- Máximo 50% del balance por operación (antes 95%) — protección de capital más conservadora
- Límite de 1 posición abierta por par simultáneamente — evita acumulación de posiciones contradictorias

### Corregido
- Sobreoperación: reducción drástica del número de trades por ciclo gracias a los filtros de calidad
- Posiciones contradictorias BUY+SELL en el mismo par dentro del mismo ciclo
- Capital excesivo en una sola operación cuando la confianza era alta

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
