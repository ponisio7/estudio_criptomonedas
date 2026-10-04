# Instalación

## Requisitos

- **TradingView**: cuenta gratuita o de pago.
- **Navegador**: Chrome, Firefox, Edge.
- **Opcional (Fase Python)**: Python 3.10+, pip, entorno virtual.

## Instalación del Builder en TradingView

1. Abre [tradingview.com](https://tradingview.com) e inicia sesión.
2. Abre cualquier gráfico (ej. `BINANCE:BTCUSDT`).
3. En la parte inferior, pulsa **Pine Editor**.
4. Borra el contenido por defecto.
5. Copia el contenido de `pine/builder_visual.pine`.
6. Pega en el editor.
7. Pulsa **Guardar** → nombre: "Builder Visual Cripto PRO".
8. Pulsa **Añadir al gráfico**.

## Estructura del proyecto

```
estudio_criptomonedas/
├── pine/           # Scripts de TradingView
├── python/         # Fase 2: app con ccxt + Streamlit
├── docs/           # Documentación
├── data/           # Datos descargados
└── scripts/        # Utilidades
```

## Verificación

Si el script carga correctamente, verás:

- Medias móviles dibujadas según la estrategia activa.
- Panel informativo arriba a la derecha.
- Flechas verdes/rojas cuando hay señal.
- Strategy Tester con métricas (si modo = Backtest).

## Problemas comunes

| Error | Causa | Solución |
|-------|-------|----------|
| "Script could not be translated" | Copia incompleta | Verifica que pegaste todo |
| "Cannot use 'strategy' with 'indicator'" | Directiva mal | Debe empezar con `//@version=5` |
| No aparece el panel | `mostrar_panel = false` | Activarlo en inputs |
| No hay órdenes | Modo "Solo señales" | Cambiar a "Backtest" |