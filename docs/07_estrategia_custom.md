# Guía del editor de estrategias custom

## Introducción

El editor Python permite escribir tu propia estrategia **sin modificar el código del proyecto**. El código se valida con AST y se ejecuta en un sandbox.

## Estructura mínima

Toda estrategia debe definir una función `generar_senales(df)`:

def generar_senales(df):

"""

df: pd.DataFrame con columnas open, high, low, close, volume.

Devuelve: pd.Series con +1 (long), 0 (nada), -1 (short).

"""

import pandas as pd

senales = pd.Series(0, index=df.index)

# tu lógica aquí

return senales
texto


## API disponible

### Datos

| Columna | Descripción |
|---------|-------------|
| `df["open"]` | Precio de apertura |
| `df["high"]` | Precio máximo |
| `df["low"]` | Precio mínimo |
| `df["close"]` | Precio de cierre |
| `df["volume"]` | Volumen |
| `df.index` | Timestamps UTC |

### Indicadores

from src.indicadores import sma, ema, rsi, macd, bollinger, atr
texto


| Función | Devuelve |
|---------|----------|
| `sma(serie, longitud)` | `pd.Series` |
| `ema(serie, longitud)` | `pd.Series` |
| `rsi(serie, longitud)` | `pd.Series` (0–100) |
| `macd(serie, fast, slow, signal)` | DataFrame `{macd, macd_signal, macd_hist}` |
| `bollinger(serie, longitud, desv)` | DataFrame `{bb_upper, bb_middle, bb_lower}` |
| `atr(high, low, close, longitud)` | `pd.Series` |

## Ejemplos

### Ejemplo 1: Cruce SMA

def generar_senales(df):

import pandas as pd

from src.indicadores import sma

rapida = sma(df["close"], 20)

lenta = sma(df["close"], 50)

senales = pd.Series(0, index=df.index)

senales[(rapida > lenta) & (rapida.shift(1) <= lenta.shift(1))] = 1

senales[(rapida < lenta) & (rapida.shift(1) >= lenta.shift(1))] = -1

return senales
texto


### Ejemplo 2: RSI reversión

def generar_senales(df):

import pandas as pd

from src.indicadores import rsi

r = rsi(df["close"], 14)

senales = pd.Series(0, index=df.index)

senales[r < 30] = 1

senales[r > 70] = -1

return senales
texto


### Ejemplo 3: Tres velas alcistas seguidas

def generar_senales(df):

import pandas as pd

subida = (df["close"] > df["close"].shift(1)) & \

(df["close"].shift(1) > df["close"].shift(2)) & \

(df["close"].shift(2) > df["close"].shift(3))

bajada = (df["close"] < df["close"].shift(1)) & \

(df["close"].shift(1) < df["close"].shift(2)) & \

(df["close"].shift(2) < df["close"].shift(3))

senales = pd.Series(0, index=df.index)

senales[subida] = 1

senales[bajada] = -1

return senales
texto


### Ejemplo 4: Bollinger + ATR como filtro

def generar_senales(df):

import pandas as pd

from src.indicadores import bollinger, atr

bb = bollinger(df["close"], 20, 2.0)

volatilidad = atr(df["high"], df["low"], df["close"], 14)

# Solo operar cuando ATR > media de ATR (mercado activo)

atr_medio = volatilidad.rolling(50).mean()

activo = volatilidad > atr_medio

senales = pd.Series(0, index=df.index)

long_cond = (df["close"] > bb["bb_lower"]) & \

(df["close"].shift(1) <= bb["bb_lower"].shift(1))

short_cond = (df["close"] < bb["bb_upper"]) & \

(df["close"].shift(1) >= bb["bb_upper"].shift(1))

senales[long_cond & activo] = 1

senales[short_cond & activo] = -1

return senales
texto


## Reglas de seguridad

### ❌ Prohibido

import os # Import no permitido

import subprocess # Import no permitido

eval("...") # Función prohibida

exec("...") # Función prohibida

open("archivo") # Función prohibida

().class # Acceso a dunder prohibido
texto


### ✅ Permitido

import pandas as pd

import numpy as np

import math

import statistics

from src.indicadores import sma, rsi
texto


## Depuración

Si tu estrategia no genera señales:

1. **Comprueba el número de señales** en la pestaña "🎯 Señales crudas"
2. **Verifica los indicadores**: imprime valores intermedios con `st.write` (no, no puedes usar st; usa prints que se ven en la terminal)
3. **Simplifica**: empieza con `senales[df["close"] > df["close"].shift(1)] = 1` y añade complejidad

### Ejemplo de debug

def generar_senales(df):

import pandas as pd

from src.indicadores import rsi

r = rsi(df["close"], 14)

print(f"RSI min={r.min():.2f}, max={r.max():.2f}, media={r.mean():.2f}")

senales = pd.Series(0, index=df.index)

senales[r < 30] = 1

senales[r > 70] = -1

print(f"Señales long: {(senales == 1).sum()}, short: {(senales == -1).sum()}")

return senales
texto


Los `print` aparecen en la terminal donde corre Streamlit.

## Cómo funciona por dentro

1. **Validación AST** (`ast.parse` + visitor):
   - Se recorren imports, llamadas y atributos
   - Si algo no está en la whitelist → error

2. **Compilación** (`compile` + `exec`):
   - Se ejecuta en un namespace aislado
   - Se extrae `generar_senales`

3. **Ejecución** (con timeout de 10s):
   - Se llama `generar_senales(df)`
   - Se normaliza la salida a `pd.Series` de `int` en `{-1, 0, +1}`

4. **Backtest**:
   - El motor de `backtest.py` procesa las señales como cualquier otra estrategia

## Casos de uso

### Prototipado rápido

Antes de implementar una estrategia nueva en `estrategias.py`, pruébala en el editor. Si funciona bien, la promocionas a clase.

### Investigación personal

Prueba hipótesis concretas: "¿Qué pasa si compro cuando el RSI cae por debajo de 25 durante una tendencia alcista?"

### Educación

El editor es una forma ideal de aprender cómo funcionan las señales y el backtest, porque puedes modificar el código y ver el efecto inmediato.

## Limitaciones

- **No puedes importar sklearn/tensorflow**: solo la whitelist.
- **No hay persistencia**: si cierras Streamlit, el código se pierde (guárdalo aparte).
- **Timeout 10s**: estrategias muy pesadas fallarán.

## Integración con estrategias comunes

Si tu código custom funciona bien, puedes **migrarlo a `estrategias.py`**:

class EstrategiaMiPropia(Estrategia):

nombre = "mi_propia"

descripcion = "..."

def init(self, param1=10, param2=20, **kwargs):

super().init(param1=param1, param2=param2, **kwargs)

self.param1 = param1

self.param2 = param2

def generar_senales(self, df):

# ... tu lógica ...

return senales
texto


Y registrarla:

_REGISTRO = {

# ...

"mi_propia": EstrategiaMiPropia,

}
texto


Ahora aparece en el selector de la sidebar como cualquier otra.