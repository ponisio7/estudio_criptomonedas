# 📈 Estudio de Criptomonedas

Herramienta visual para **backtestear estrategias de trading sobre cualquier criptomoneda**, con datos reales de múltiples exchanges.

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-1.40+-red)
![Tests](https://img.shields.io/badge/tests-88%20passed-brightgreen)
![License](https://img.shields.io/badge/license-MIT-green)

## ✨ Características

- 🌐 **Cualquier criptomoneda**: más de 100 exchanges vía [ccxt](https://github.com/ccxt/ccxt)
- 🎯 **5 estrategias comunes**: Cruce SMA, RSI+SMA, MACD, Bollinger, EMA Tendencia
- 🛠️ **Estrategia Custom**: editor Python con sandbox seguro (AST)
- 📊 **Interfaz visual**: Streamlit + Plotly interactivo
- 💰 **Backtest realista**: comisiones, slippage, SL/TP (% o ATR), riesgo fijo
- 📈 **Métricas completas**: Sharpe, Sortino, Max DD, Profit Factor, Expectancy
- 📥 **Reportes HTML**: exportables con gráficos y trades embebidos
- 📦 **TradingView**: Builder visual en Pine Script incluido

## 🚀 Quickstart

### Instalación

git clone https://github.com/tu-usuario/estudio_criptomonedas.git

cd estudio_criptomonedas

python -m venv .env

source .env/bin/activate # Linux/Mac
o: .env\Scripts\activate # Windows

pip install -e .
texto


### Ejecutar la UI

streamlit run python/ui/app.py
texto


Se abre en http://localhost:8501

### Descargar datos

python scripts/descargar_datos.py \

--simbolos BTC/USDT ETH/USDT \

--timeframe 4h \

--desde 2022-01-01 \

--hasta 2024-12-31
texto


### Backtest desde CLI

python -m src.backtest
texto


### Generar reporte

python scripts/generar_reporte.py \

--simbolo BTC/USDT \

--timeframe 4h \

--estrategia cruce_sma \

--params sma_rapida=20 sma_lenta=50
texto


## 📁 Estructura del proyecto

estudio_criptomonedas/

├── pine/ # Scripts de TradingView

│ ├── builder_visual.pine # Builder visual principal

│ ├── estrategias/ # Estrategias individuales

│ ├── modulos/ # Módulos reutilizables

│ └── ejemplos/ # Scripts listos para probar

│

├── python/ # Motor Python

│ ├── src/

│ │ ├── data_loader.py # ccxt + caché parquet

│ │ ├── indicadores.py # SMA, EMA, RSI, MACD, BB, ATR

│ │ ├── estrategias.py # 5 comunes + Custom parametrizable

│ │ ├── estrategia_custom.py # Sandbox Python (AST)

│ │ ├── riesgo.py # SL/TP y position sizing

│ │ ├── backtest.py # Motor de backtest vela a vela

│ │ └── reportes.py # Generación HTML

│ │

│ ├── ui/ # Interfaz Streamlit

│ │ ├── app.py

│ │ ├── pages/

│ │ └── components/

│ │

│ └── tests/ # 88 tests unitarios

│

├── docs/ # Documentación

├── scripts/ # CLI auxiliares

├── data/ # Datos y resultados (gitignored)

└── assets/ # Recursos
texto


## 🎓 Estrategias incluidas

| Estrategia | Tipo | Descripción |
|-----------|------|-------------|
| **Cruce SMA** | Tendencia | SMA rápida cruza SMA lenta |
| **EMA Tendencia** | Tendencia | Igual pero con EMA (más reactiva) |
| **RSI + SMA** | Reversión | RSI sale de extremo + filtro tendencia |
| **MACD** | Momentum | MACD cruza su línea de señal |
| **Bollinger** | Reversión | Precio toca banda extrema |
| **Custom** | Parametrizable | 2 condiciones Y/O con inputs |
| **Python Custom** | Libre | Editor con sandbox AST |

## 📊 Ejemplo de resultados

Backtest sobre BTC/USDT 4h, 2024-01-01 → 2024-12-31, Cruce SMA 20/50:

Retorno total: +28.48%

Capital final: $12,847.68

Nº trades: 23

Winrate: 56.5%

Max Drawdown: -8.17%

Sharpe: 1.826

Profit Factor: 2.083
texto


## 🧪 Tests

pytest python/tests/ -v
texto


88 tests cubriendo:
- Indicadores técnicos (18)
- Estrategias comunes (14)
- Gestión de riesgo (21)
- Motor de backtest (19)
- Sandbox de seguridad (16)

## 🎨 Screenshots

*(Añadir capturas de la UI)*

## 🔧 Stack técnico

- **Datos**: [ccxt](https://github.com/ccxt/ccxt), pandas, pyarrow
- **Indicadores**: implementación propia (+ opcional pandas-ta)
- **Backtest**: motor vela a vela sin look-ahead bias
- **UI**: [Streamlit](https://streamlit.io) + [Plotly](https://plotly.com)
- **Sandbox**: validación AST para código del usuario
- **TradingView**: Pine Script v5

## 🛡️ Seguridad del editor Python

El editor de estrategias custom usa validación **AST** para bloquear:

- `import os`, `sys`, `subprocess`, `socket`, `requests`...
- `eval()`, `exec()`, `open()`, `__import__()`...
- Acceso a dunders: `__class__`, `__globals__`, `__subclasses__`...
- Timeout de 10 segundos por ejecución

Solo permite imports de: `pandas`, `numpy`, `math`, `statistics`, `random`, `datetime`, `src.*`

## 📖 Documentación

- [Instalación](docs/01_instalacion.md)
- [Manual del Builder Pine](docs/02_uso_builder.md)
- [Catálogo de estrategias](docs/03_estrategias.md)
- [Gestión de riesgo](docs/04_gestion_riesgo.md)
- [Limitaciones de Pine](docs/05_limitaciones_pine.md)

## 🐛 Problemas conocidos

- **Warning de `use_container_width`**: Streamlit lo deprecará en 2025-12-31. Migración a `width="stretch"` en progreso.
- **Primera ejecución lenta**: la descarga de datos tarda; después hay caché parquet.

## 📄 Licencia

MIT — ver [LICENSE](LICENSE)

## 👤 Autor

Christian — [@ponisio7](https://github.com/ponisio7)

---

⭐ Si el proyecto te resulta útil, ¡dale una estrella!