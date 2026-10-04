# Manual del Builder Visual Cripto PRO

## 1. Requisitos

- Cuenta de TradingView (gratuita sirve para probar).
- Acceso al Pine Editor (parte inferior de la pantalla).
- Plan gratuito: máximo 1 script por gráfico. Plan Pro+: sin límite.

## 2. Instalación

1. Abre TradingView y pulsa la pestaña **Pine Editor** en la parte inferior.
2. Pega el contenido de `pine/builder_visual.pine`.
3. Pulsa **Guardar** y nómbralo "Builder Visual Cripto PRO".
4. Pulsa **Añadir al gráfico**.

## 3. Uso básico

### 3.1 Elegir el activo (CRÍTICO)

El Builder **opera sobre el activo del gráfico actual**, no sobre un input.

- Para operar BTC → abre `BINANCE:BTCUSDT` en el gráfico.
- Para operar ETH → abre `BINANCE:ETHUSDT`.
- Cambia de activo con el buscador de símbolo (arriba a la izquierda).

**Nunca uses `input.symbol()` para backtest.** TradingView ejecutaría las órdenes sobre el gráfico abierto, no sobre el símbolo del input. Backtest engañoso.

### 3.2 Configurar la estrategia

Pulsa el engranaje ⚙️ junto al nombre del script. Se abren 9 grupos de inputs:

| Grupo | Qué configura |
|-------|---------------|
| 1️⃣ Estrategia | Tipo de estrategia, modo, largos/cortos |
| 2️⃣ Filtro de Tendencia | EMA200 opcional |
| 3️⃣ Cruce SMA / EMA Tendencia | Longitudes de medias |
| 4️⃣ RSI + SMA | RSI, umbrales, SMA de tendencia |
| 5️⃣ MACD | Fast, Slow, Signal |
| 6️⃣ Bollinger Bands | Periodos, desviaciones |
| 7️⃣ Estrategia Custom | 2 condiciones + operador lógico |
| 8️⃣ Gestión de Riesgo | Modo SL/TP, % o ATR |
| 9️⃣ Panel | Visibilidad y posición |

### 3.3 Modos de operación

- **Backtest**: ejecuta órdenes reales en el Strategy Tester.
- **Solo señales**: dibuja flechas y fondo, no opera. Útil para validar.

### 3.4 Gestión de riesgo

Tres modos:

- **Ninguno**: sin SL/TP.
- **Porcentaje**: SL y TP en % respecto al precio de entrada.
- **ATR**: SL = entrada − ATR×mult, TP = entrada + ATR×mult.

## 4. Estrategias incluidas

### Cruce SMA
- Long: SMA rápida cruza al alza SMA lenta.
- Short: cruce a la baja.
- Parámetros: `sma_rapida_len`, `sma_lenta_len`.

### RSI + SMA
- Long: precio > SMA tendencia y RSI sale de sobreventa.
- Short: precio < SMA tendencia y RSI sale de sobrecompra.
- Parámetros: `rsi_len`, `rsi_sobrev`, `rsi_sobrec`, `rsi_sma_len`.

### MACD
- Long: MACD cruza al alza la señal.
- Short: cruce a la baja.

### Bollinger Bands
- Long: precio cruza al alza la banda inferior.
- Short: precio cruza a la baja la banda superior.

### EMA Tendencia
- Long: EMA rápida cruza al alza EMA lenta.
- Short: cruce a la baja.

### Custom
- Condición 1 + Operador (Y/O) + Condición 2.
- Cada condición puede ser: `RSI < X`, `RSI > X`, `Precio > SMA`, `Precio < SMA`, `MACD cruza señal`.
- Ejemplo: `RSI < 30 Y Precio > SMA(200)` → long en sobreventa con tendencia alcista.

## 5. Panel informativo

Muestra en pantalla:

- Estrategia activa
- Modo (Backtest / Solo señales)
- RSI actual (coloreado según zona)
- Tendencia (Alcista/Bajista vs EMA filtro)
- Última señal (LONG/SHORT/—)
- ATR actual
- Estado del filtro (ON/OFF)

## 6. Alertas

Cinco alertas predefinidas:

- Señal LONG
- Señal SHORT
- Cruce SMA alcista
- Cruce SMA bajista
- RSI sale de sobreventa / sobrecompra

Para activarlas: clic derecho en el gráfico → **Añadir alerta** → condición = Builder.

## 7. Limitaciones

- **No puedes seleccionar el activo con un input** para backtest. Debe cambiarse en el gráfico.
- **El plan gratuito de TradingView** solo permite 1 script por gráfico.
- **El backtest no es multi-activo**: cada gráfico es un backtest independiente.
- **Custom** es una plantilla parametrizable, no un editor libre. Pine no permite ejecutar código arbitrario en runtime.

## 8. Buenas prácticas

1. Prueba primero en modo "Solo señales" antes de activar "Backtest".
2. Usa `barstate.isconfirmed` para evitar repintado (ya incluido).
3. Ajusta SL/TP según volatilidad del activo (usa ATR en cripto).
4. Revisa el Strategy Tester: winrate, profit factor, drawdown máximo.
5. No confíes en un backtest con menos de 100 operaciones.

## 9. Solución de problemas

| Problema | Causa | Solución |
|----------|-------|----------|
| No se ejecutan órdenes | Modo "Solo señales" | Cambiar a "Backtest" |
| Señales aparecen y desaparecen | Repintado | Ya evitado con `barstate.isconfirmed` |
| Backtest en activo equivocado | Confusión con input | Verifica el ticker del gráfico |
| Panel no se ve | `mostrar_panel = false` | Activarlo en inputs |