# Catálogo de Estrategias

## 1. Cruce SMA

**Lógica:** Media móvil simple rápida cruza a lenta.

| Dirección | Condición |
|-----------|-----------|
| Long | SMA(rapida) cruza ↑ SMA(lenta) |
| Short | SMA(rapida) cruza ↓ SMA(lenta) |

**Parámetros:** `sma_rapida_len = 20`, `sma_lenta_len = 50`

**Cuándo usar:** Tendencias claras. Falla en rangos.

---

## 2. RSI + SMA

**Lógica:** RSI sale de zona extrema + filtro de tendencia por SMA.

| Dirección | Condición |
|-----------|-----------|
| Long | Precio > SMA tendencia Y RSI cruza ↑ 30 |
| Short | Precio < SMA tendencia Y RSI cruza ↓ 70 |

**Parámetros:** `rsi_len = 14`, `rsi_sobrev = 30`, `rsi_sobrec = 70`, `rsi_sma_len = 200`

**Cuándo usar:** Mercados con retrocesos en tendencia.

---

## 3. MACD

**Lógica:** Cruce de línea MACD con señal.

| Dirección | Condición |
|-----------|-----------|
| Long | MACD cruza ↑ Signal |
| Short | MACD cruza ↓ Signal |

**Parámetros:** `fast = 12`, `slow = 26`, `signal = 9`

**Cuándo usar:** Detección temprana de cambios de momentum.

---

## 4. Bollinger Bands

**Lógica:** Reversión a la media en extremos de banda.

| Dirección | Condición |
|-----------|-----------|
| Long | Precio cruza ↑ banda inferior |
| Short | Precio cruza ↓ banda superior |

**Parámetros:** `bb_len = 20`, `bb_mult = 2.0`

**Cuándo usar:** Mercados laterales. Riesgo en tendencias fuertes.

---

## 5. EMA Tendencia

**Lógica:** Igual que Cruce SMA pero con EMA (más reactiva).

| Dirección | Condición |
|-----------|-----------|
| Long | EMA(rapida) cruza ↑ EMA(lenta) |
| Short | EMA(rapida) cruza ↓ EMA(lenta) |

**Parámetros:** `sma_rapida_len = 20`, `sma_lenta_len = 50` (aplicados como EMA)

**Cuándo usar:** Cuando se quiere reacción más rápida que SMA.

---

## 6. Custom (parametrizable)

**Lógica:** Dos condiciones combinadas con Y/O.

**Condiciones disponibles:**
- `RSI < X`
- `RSI > X`
- `Precio > SMA(X)`
- `Precio < SMA(X)`
- `MACD cruza señal`

**Ejemplos de configuración:**

| Objetivo | C1 | Op | C2 |
|----------|-----|-----|-----|
| Sobreventa en tendencia alcista | RSI < 30 | Y | Precio > SMA(200) |
| Sobrecompra en tendencia bajista | RSI > 70 | Y | Precio < SMA(200) |
| Ruptura con momentum | Precio > SMA(50) | Y | MACD cruza señal |
| Cualquier extremo | RSI < 30 | O | RSI > 70 |

---

## Comparativa rápida

| Estrategia | Tipo | Mercado ideal | Señales/año (BTC 4H) |
|------------|------|---------------|---------------------|
| Cruce SMA | Tendencia | Tendencial | ~15–25 |
| RSI + SMA | Reversión | Tendencial con retrocesos | ~10–20 |
| MACD | Momentum | Todos | ~20–30 |
| Bollinger | Reversión | Lateral | ~30–50 |
| EMA Tendencia | Tendencia | Tendencial | ~20–35 |
| Custom | Variable | Según config | Variable |

**Nota:** El número de señales es orientativo. Backtestea cada activo.