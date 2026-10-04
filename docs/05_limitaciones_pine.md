# Limitaciones de Pine Script

## 1. No se puede seleccionar el activo con `input.symbol()` para backtest

**El error más común.** Ver código así:

```pine
simbolo = input.symbol("BINANCE:BTCUSDT")
precio  = request.security(simbolo, timeframe.period, close)
if ta.crossover(ta.sma(precio, 20), ta.sma(precio, 50))
    strategy.entry("Long", strategy.long)  // ❌ NO opera sobre el símbolo del input
```

**Qué pasa realmente:** TradingView ejecuta las órdenes sobre el gráfico abierto, no sobre `simbolo`. El backtest es engañoso.

**Solución:** el usuario cambia el ticker del gráfico. `input.symbol` solo sirve para **mostrar** datos de otro activo (comparativas, correlaciones), nunca para backtest.

## 2. `request.security()` puede repintar

Sin control de `lookahead` ni `barstate.isconfirmed`, las señales pueden aparecer y desaparecer.

**Solución:**
```pine
precio = request.security(simbolo, timeframe.period, close, lookahead = barmerge.lookahead_off)
```

## 3. No hay ejecución de código arbitrario

Pine no permite que el usuario escriba lógica propia en runtime. Las "estrategias custom" son **plantillas parametrizables**, no editores libres.

## 4. Límite de `request.*()`

- Plan básico: 40 llamadas únicas.
- Plan Profesional: 64.

## 5. Un solo script por gráfico (plan gratuito)

El plan gratuito de TradingView solo permite 1 indicador/estrategia por gráfico.

## 6. No hay multi-activo en un backtest

Cada gráfico = un backtest. Para comparar BTC vs ETH, hay que ejecutar el script dos veces.

## 7. No hay órdenes reales

Pine ejecuta órdenes simuladas en el Strategy Tester. Para órdenes reales:
- Alertas + webhooks + servicio externo.
- O usar la API del exchange directamente (Python + ccxt).

## 8. Timeframe limitado

`request.security()` puede acceder a otros timeframes, pero con retraso y posibles repintes.

## 9. No hay programación orientada a objetos real

Pine v5 tiene `type` y `method`, pero no es un lenguaje OOP completo.

## 10. La estrategia se recalcula en cada vela

El script se ejecuta completo en cada barra. No hay estado persistente entre barras excepto con `var`.

---

## Resumen: qué SÍ y qué NO se puede hacer en Pine

| Quiero... | ¿Pine? | Alternativa |
|-----------|--------|-------------|
| Seleccionar activo con input para backtest | ❌ | Cambiar ticker del gráfico |
| Seleccionar activo con input para ver datos | ✅ | `request.security` |
| Estrategia custom con código libre | ❌ | Python + backtrader |
| 5+ estrategias en un script | ✅ | `input.string` |
| Órdenes reales | ❌ | Alertas + webhook o ccxt |
| Backtest multi-activo | ❌ | Python + vectorbt |
| Panel visual | ✅ | `table.new` |
| Alertas | ✅ | `alertcondition` |