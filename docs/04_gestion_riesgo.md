# Gestión de Riesgo

## Modos disponibles

### 1. Ninguno
Sin Stop Loss ni Take Profit.
**Uso:** solo para validar señales. **No recomendado en real.**

### 2. Porcentaje
- SL = entrada × (1 − sl_perc/100) para long
- TP = entrada × (1 + tp_perc/100) para long
- Inverso para short

**Parámetros:** `sl_perc`, `tp_perc`
**Ventaja:** simple, predecible.
**Desventaja:** no se adapta a volatilidad.

### 3. ATR
- SL = entrada − ATR × atr_mult_sl
- TP = entrada + ATR × atr_mult_tp

**Parámetros:** `atr_len = 14`, `atr_mult_sl = 1.5`, `atr_mult_tp = 3.0`
**Ventaja:** se adapta a la volatilidad del activo.
**Desventaja:** en calma extrema, SL muy ceñido.

## Recomendaciones por activo

| Activo | Volatilidad | Modo sugerido | SL | TP |
|--------|-------------|---------------|-----|-----|
| BTC | Alta | ATR | 1.5×ATR | 3×ATR |
| ETH | Alta | ATR | 1.5×ATR | 3×ATR |
| SOL | Muy alta | ATR | 2×ATR | 4×ATR |
| Stablecoins | Baja | Porcentaje | 1% | 2% |

## Reglas de oro

1. **Nunca arriesgues más del 1–2% del capital por operación.**
2. **Ratio Riesgo/Beneficio mínimo 1:2.**
3. **Backtest con y sin SL/TP** para ver el impacto.
4. **El ATR cambia con el timeframe**: en 1H es más pequeño que en 1D.
5. **Un SL demasiado ceñido genera falsos stops** (whipsaw).

## Cálculo del tamaño de posición

Con `default_qty_type = strategy.percent_of_equity` y `default_qty_value = 100`, se arriesga el 100% del equity por operación.

**Recomendación:** cambiar a `strategy.percent_of_equity` con valor 10–20%, o usar `strategy.fixed` con capital concreto.

## Ejemplo de mala gestión

- Capital: 10.000 $
- SL: 0.5% → demasiado ceñido
- Resultado: 20 stops seguidos → −1.000 $ aunque la estrategia sea buena.

## Ejemplo de buena gestión

- Capital: 10.000 $
- SL: 2% (ATR)
- TP: 4% (ATR)
- Ratio 1:2
- Con 40% winrate ya es rentable.