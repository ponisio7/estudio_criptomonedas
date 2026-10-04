# Arquitectura del proyecto

## Diagrama del pipeline

┌──────────────────┐

│ Usuario (UI) │

│ Streamlit │

└────────┬─────────┘

│

┌──────────────────┼──────────────────┐

│ │ │

▼ ▼ ▼

┌──────────┐ ┌──────────┐ ┌──────────────┐

│Common │ │Custom │ │Editor │

│Strategy │ │Params │ │Python │

└────┬─────┘ └────┬─────┘ └──────┬───────┘

│ │ │

└────────┬────────┘ │

│ │

▼ ▼

┌──────────────┐ ┌──────────────────┐

│ Estrategia │ │ Sandbox AST │

│ (clase) │ │ (validación) │

└──────┬───────┘ └────────┬─────────┘

│ │

└──────────┬──────────────────┘

│

▼

┌──────────────────┐

│ DataLoader │

│ (ccxt) │

└────────┬─────────┘

│

▼

┌──────────────────┐

│ Indicadores │

│ (pandas) │

└────────┬─────────┘

│

▼

┌──────────────────┐

│ Backtest │

│ (motor vela) │

└────────┬─────────┘

│

▼

┌──────────────────┐

│ Métricas + │

│ Reportes HTML │

└──────────────────┘
texto


## Flujo detallado

### 1. Entrada (UI Streamlit)

El usuario configura en la sidebar:

- **Activo**: exchange + símbolo + timeframe + rango
- **Estrategia**: común (5) o Custom parametrizable (2 condiciones Y/O)
- **Direcciones**: largos / cortos
- **Riesgo**: SL/TP (porcentaje, ATR o ninguno)
- **Costes**: capital, comisión %, slippage %

### 2. Carga de datos (`data_loader.py`)

DataLoader(exchange="binance")

↓ ccxt.fetch_ohlcv (paginado, 1000 velas por llamada)

↓ pd.DataFrame OHLCV + índice UTC

↓ caché parquet en data/raw/
texto


### 3. Estrategia

**Común**: `obtener_estrategia("cruce_sma", sma_rapida=20, ...)` → instancia con `generar_senales(df) -> pd.Series`.

**Custom Python**: `compilar_estrategia_usuario(codigo) -> EstrategiaUsuario`.
- Validación AST (imports y funciones prohibidas)
- Timeout de 10s
- Salida normalizada a `+1/0/-1`

### 4. Backtest (`backtest.py`)

Para cada vela i:

    Ejecutar señal pendiente de vela i-1 (al open)
    Comprobar SL/TP de la posición abierta (con high/low)
    Comprobar cierre por señal contraria
    Registrar nueva señal (para vela i+1)
    Registrar equity

texto


**Sin look-ahead bias**: la señal se evalúa con `close[t]`, la entrada con `open[t+1]`.

### 5. Métricas

- **Retorno total** = (capital_final / capital_inicial − 1) × 100
- **CAGR** = ((capital_final / capital_inicial)^(1/años) − 1) × 100
- **Sharpe** = (mean(retornos) / std(retornos)) × √(velas_por_año)
- **Sortino** = igual pero con downside std
- **Max DD** = min((equity − running_max) / running_max)
- **Winrate** = ganadores / total
- **Profit Factor** = sum(ganancias) / abs(sum(pérdidas))
- **Expectancy** = mean(pnl por trade)

### 6. Reportes (`reportes.py`)

Genera un HTML autocontenido con:
- 12 tarjetas de métricas
- Configuración exacta
- 2 gráficos Plotly (precio+trades, equity+drawdown)
- Tabla completa de trades
- Estilos dark mode inline

## Módulos y responsabilidades

| Módulo | Responsabilidad | Depende de |
|--------|-----------------|------------|
| `data_loader` | Descarga + caché OHLCV | ccxt, pandas |
| `indicadores` | Cálculo técnico | pandas, numpy |
| `estrategias` | 5 comunes + Custom parametrizable | indicadores |
| `estrategia_custom` | Sandbox Python | estrategias |
| `riesgo` | SL/TP, position sizing | indicadores |
| `backtest` | Motor vela a vela | estrategias, riesgo |
| `reportes` | HTML autocontenido | backtest, plotly |
| `ui.app` | Interfaz Streamlit | todo |

## Decisiones de diseño

### ¿Por qué ccxt y no API directa?

ccxt abstrae 100+ exchanges con una API uniforme. Cambiar de Binance a Kraken es cambiar una palabra.

### ¿Por qué caché parquet?

- Binario, comprimido, rápido.
- Persistente entre ejecuciones.
- pandas lo lee nativamente.

### ¿Por qué motor propio y no backtrader/vectorbt?

- Control total del flujo (sin look-ahead).
- Sin dependencias pesadas.
- Fácil de depurar y extender.

*(backtrader y vectorbt se pueden añadir después para validar resultados.)*

### ¿Por qué AST para el sandbox?

`exec()` sin validación es un agujero de seguridad. AST permite:
- Bloquear imports peligrosos
- Bloquear funciones built-in peligrosas
- Bloquear acceso a dunders

### ¿Por qué Plotly y no matplotlib?

Interactividad: zoom, hover, selección. Streamlit renderiza Plotly nativamente.

## Limitaciones actuales

1. **No hay órdenes límite**: solo market al open.
2. **No hay apalancamiento**: solo spot.
3. **No hay funding rate**: solo spot, no futuros.
4. **Un solo timeframe**: no multi-timeframe en la misma estrategia.
5. **Sin walk-forward**: backtest simple, no optimización.

## Roadmap

- [ ] Órdenes límite
- [ ] Walk-forward analysis
- [ ] Optimización de parámetros (grid search)
- [ ] Comparación multi-activo
- [ ] Integración con backtrader para validación cruzada
- [ ] Alertas en tiempo real (Telegram/webhook)