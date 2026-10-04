"""
estrategia_custom.py
====================
Sandbox para que el usuario pegue código Python y lo convierta en una
Estrategia compatible con el motor de backtest.

Seguridad:
    - Validación AST: solo permite imports de la whitelist.
    - Prohibidas: os, sys, subprocess, socket, eval, exec, open...
    - Timeout de ejecución con signal.alarm (solo Unix).

Uso:
----
    from src.estrategia_custom import compilar_estrategia_usuario

    codigo = '''
def generar_senales(df):
    import pandas as pd
    from src.indicadores import sma
    rapida = sma(df["close"], 10)
    lenta = sma(df["close"], 30)
    senales = pd.Series(0, index=df.index)
    senales[(rapida > lenta) & (rapida.shift(1) <= lenta.shift(1))] = 1
    senales[(rapida < lenta) & (rapida.shift(1) >= lenta.shift(1))] = -1
    return senales
'''
    est = compilar_estrategia_usuario(codigo)
    senales = est.generar_senales(df)
"""

from __future__ import annotations

import ast
import signal
import textwrap
from typing import Any

import pandas as pd

from src.estrategias import Estrategia


# ============================================================================
# Configuración de seguridad
# ============================================================================
IMPORTS_PERMITIDOS = {
    "pandas", "numpy", "math", "statistics", "random", "datetime",
    "src.indicadores", "src.riesgo", "src.estrategias",
}

FUNCIONES_PROHIBIDAS = {
    "eval", "exec", "compile", "__import__", "open", "input",
    "globals", "locals", "vars", "dir", "getattr", "setattr", "delattr",
    "breakpoint", "exit", "quit",
}

MODULOS_PROHIBIDOS = {
    "os", "sys", "subprocess", "socket", "shutil", "pathlib",
    "requests", "urllib", "http", "ftplib", "telnetlib", "smtplib",
    "pickle", "marshal", "shelve", "dbm", "sqlite3",
    "multiprocessing", "threading", "asyncio",
    "ctypes", "importlib", "builtins",
}

TIMEOUT_SEGUNDOS = 10


# ============================================================================
# Excepciones
# ============================================================================
class ErrorEstrategiaCustom(Exception):
    """Error genérico de la estrategia custom."""
    pass


class ErrorSeguridad(ErrorEstrategiaCustom):
    """El código viola las reglas de seguridad."""
    pass


class ErrorCompilacion(ErrorEstrategiaCustom):
    """El código no compila o no tiene la estructura esperada."""
    pass


class ErrorEjecucion(ErrorEstrategiaCustom):
    """Error durante la ejecución de la estrategia."""
    pass


# ============================================================================
# Validación AST
# ============================================================================
class _ValidadorAST(ast.NodeVisitor):
    """Recorre el AST y valida imports y llamadas."""

    def __init__(self):
        self.errores: list[str] = []

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if alias.name not in IMPORTS_PERMITIDOS:
                self.errores.append(f"Import no permitido: '{alias.name}'")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        modulo = node.module or ""
        # Comprobar que no empiece por un módulo prohibido
        raiz = modulo.split(".")[0]
        if raiz in MODULOS_PROHIBIDOS:
            self.errores.append(f"Módulo prohibido: '{modulo}'")
        elif modulo not in IMPORTS_PERMITIDOS and raiz not in {"src", "pandas", "numpy", "math", "statistics", "random", "datetime"}:
            self.errores.append(f"Import no permitido: 'from {modulo}'")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        # Detectar llamadas a funciones prohibidas
        if isinstance(node.func, ast.Name):
            if node.func.id in FUNCIONES_PROHIBIDAS:
                self.errores.append(f"Función prohibida: '{node.func.id}()'")
        elif isinstance(node.func, ast.Attribute):
            if node.func.attr in FUNCIONES_PROHIBIDAS:
                self.errores.append(f"Método prohibido: '.{node.func.attr}()'")
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        # Detectar acceso a atributos peligrosos
        if node.attr in {"__globals__", "__builtins__", "__subclasses__",
                          "__class__", "__bases__", "__mro__", "__code__"}:
            self.errores.append(f"Atributo prohibido: '{node.attr}'")
        self.generic_visit(node)


def validar_codigo(codigo: str) -> None:
    """
    Valida el código del usuario. Lanza ErrorSeguridad si algo no está permitido.
    """
    try:
        arbol = ast.parse(codigo)
    except SyntaxError as e:
        raise ErrorCompilacion(f"Error de sintaxis: {e}") from e

    validador = _ValidadorAST()
    validador.visit(arbol)

    if validador.errores:
        raise ErrorSeguridad(
            "Código rechazado por seguridad:\n" +
            "\n".join(f"  - {err}" for err in validador.errores)
        )

    # Comprobar que existe la función generar_senales
    funciones = [n.name for n in ast.walk(arbol)
                 if isinstance(n, ast.FunctionDef)]
    if "generar_senales" not in funciones:
        raise ErrorCompilacion(
            "El código debe definir una función 'generar_senales(df)'"
        )


# ============================================================================
# Timeout (solo Unix)
# ============================================================================
class _Timeout:
    """Context manager que lanza TimeoutError tras N segundos."""

    def __init__(self, segundos: int):
        self.segundos = segundos

    def _handler(self, signum, frame):
        raise TimeoutError(f"Timeout de {self.segundos}s excedido")

    def __enter__(self):
        try:
            self.anterior = signal.signal(signal.SIGALRM, self._handler)
            signal.alarm(self.segundos)
        except (AttributeError, ValueError):
            # Windows o fuera del hilo principal: sin timeout
            self.anterior = None
        return self

    def __exit__(self, *args):
        if self.anterior is not None:
            try:
                signal.alarm(0)
                signal.signal(signal.SIGALRM, self.anterior)
            except (AttributeError, ValueError):
                pass


# ============================================================================
# Clase EstrategiaUsuario
# ============================================================================
class EstrategiaUsuario(Estrategia):
    """
    Estrategia creada a partir de código Python del usuario.
    El usuario define una función `generar_senales(df) -> pd.Series`.
    """

    nombre = "usuario"
    descripcion = "Estrategia definida por el usuario"

    def __init__(self, codigo: str):
        super().__init__(codigo=codigo)
        self.codigo = textwrap.dedent(codigo)
        validar_codigo(self.codigo)

        # Compilar en un namespace aislado
        self._namespace: dict[str, Any] = {}
        try:
            exec(compile(self.codigo, "<usuario>", "exec"), self._namespace)
        except Exception as e:
            raise ErrorCompilacion(f"Error compilando: {e}") from e

        if "generar_senales" not in self._namespace:
            raise ErrorCompilacion("No se encontró la función 'generar_senales'")

        self._func = self._namespace["generar_senales"]

    # ------------------------------------------------------------------
    def generar_senales(self, df: pd.DataFrame) -> pd.Series:
        """Ejecuta la función del usuario con timeout."""
        try:
            with _Timeout(TIMEOUT_SEGUNDOS):
                señales = self._func(df)
        except TimeoutError as e:
            raise ErrorEjecucion(str(e)) from e
        except Exception as e:
            raise ErrorEjecucion(f"Error en generar_senales: {e}") from e

        # Normalizar: convertir a int (+1/0/-1)
        if not isinstance(señales, pd.Series):
            señales = pd.Series(señales, index=df.index)

        señales = señales.reindex(df.index).fillna(0).astype(int)

        # Clamp: solo -1, 0, +1
        señales = señales.clip(-1, 1)
        return señales


# ============================================================================
# API pública
# ============================================================================
def compilar_estrategia_usuario(codigo: str) -> EstrategiaUsuario:
    """
    Compila el código del usuario y devuelve una Estrategia lista para usar.

    Lanza:
        - ErrorSeguridad si el código viola las reglas.
        - ErrorCompilacion si no compila o falta `generar_senales`.
    """
    return EstrategiaUsuario(codigo)


# ============================================================================
# Plantillas
# ============================================================================
PLANTILLA_VACIA = '''def generar_senales(df):
    """
    df: pd.DataFrame con columnas open, high, low, close, volume.
    Devuelve: pd.Series con valores +1 (long), 0 (nada), -1 (short).
    """
    import pandas as pd
    from src.indicadores import sma

    senales = pd.Series(0, index=df.index)
    # Tu lógica aquí
    return senales
'''


PLANTILLA_CRUCE_SMA = '''def generar_senales(df):
    """Ejemplo: cruce SMA 20/50."""
    import pandas as pd
    from src.indicadores import sma

    rapida = sma(df["close"], 20)
    lenta = sma(df["close"], 50)

    senales = pd.Series(0, index=df.index)
    senales[(rapida > lenta) & (rapida.shift(1) <= lenta.shift(1))] = 1
    senales[(rapida < lenta) & (rapida.shift(1) >= lenta.shift(1))] = -1
    return senales
'''


PLANTILLA_RSI_REVERSION = '''def generar_senales(df):
    """Ejemplo: RSI < 30 compra, RSI > 70 vende."""
    import pandas as pd
    from src.indicadores import rsi

    r = rsi(df["close"], 14)
    senales = pd.Series(0, index=df.index)
    senales[r < 30] = 1
    senales[r > 70] = -1
    return senales
'''


PLANTILLA_BOLLINGER = '''def generar_senales(df):
    """Ejemplo: rebote en bandas de Bollinger."""
    import pandas as pd
    from src.indicadores import bollinger

    bb = bollinger(df["close"], 20, 2.0)
    senales = pd.Series(0, index=df.index)

    # Long: precio cruza al alza banda inferior
    senales[(df["close"] > bb["bb_lower"]) &
            (df["close"].shift(1) <= bb["bb_lower"].shift(1))] = 1

    # Short: precio cruza a la baja banda superior
    senales[(df["close"] < bb["bb_upper"]) &
            (df["close"].shift(1) >= bb["bb_upper"].shift(1))] = -1
    return senales
'''


PLANTILLA_MACD = '''def generar_senales(df):
    """Ejemplo: cruce MACD con señal."""
    import pandas as pd
    from src.indicadores import macd

    sub = macd(df["close"], 12, 26, 9)
    linea = sub["macd"]
    sig = sub["macd_signal"]

    senales = pd.Series(0, index=df.index)
    senales[(linea > sig) & (linea.shift(1) <= sig.shift(1))] = 1
    senales[(linea < sig) & (linea.shift(1) >= sig.shift(1))] = -1
    return senales
'''


PLANTILLAS = {
    "Vacía": PLANTILLA_VACIA,
    "Cruce SMA": PLANTILLA_CRUCE_SMA,
    "RSI Reversión": PLANTILLA_RSI_REVERSION,
    "Bollinger": PLANTILLA_BOLLINGER,
    "MACD": PLANTILLA_MACD,
}


# ============================================================================
# CLI de prueba
# ============================================================================
if __name__ == "__main__":
    from pathlib import Path
    from rich.console import Console
    from rich.syntax import Syntax

    console = Console()

    console.rule("[bold]Test de seguridad[/bold]")

    # 1) Código válido
    console.print("\n[green]Test 1: código válido[/green]")
    try:
        est = compilar_estrategia_usuario(PLANTILLA_CRUCE_SMA)
        console.print("  ✓ Compilado OK")
    except Exception as e:
        console.print(f"  ✗ {e}")

    # 2) Import prohibido
    console.print("\n[yellow]Test 2: import prohibido[/yellow]")
    codigo_malo = """
import os
def generar_senales(df):
    return df["close"] * 0
"""
    try:
        compilar_estrategia_usuario(codigo_malo)
        console.print("  ✗ No detectó el import prohibido")
    except ErrorSeguridad as e:
        console.print(f"  ✓ Detectado: {e}")

    # 3) Función prohibida
    console.print("\n[yellow]Test 3: eval() prohibido[/yellow]")
    codigo_malo = """
def generar_senales(df):
    return eval("1+1")
"""
    try:
        compilar_estrategia_usuario(codigo_malo)
        console.print("  ✗ No detectó eval()")
    except ErrorSeguridad as e:
        console.print(f"  ✓ Detectado: {e}")

    # 4) Falta generar_senales
    console.print("\n[yellow]Test 4: falta generar_senales[/yellow]")
    codigo_malo = "x = 1"
    try:
        compilar_estrategia_usuario(codigo_malo)
        console.print("  ✗ No detectó la ausencia")
    except ErrorCompilacion as e:
        console.print(f"  ✓ Detectado: {e}")

    # 5) Ejecución real
    console.print("\n[green]Test 5: ejecución real[/green]")
    raiz = Path(__file__).resolve().parents[2]
    parquets = list((raiz / "data" / "raw").glob("*.parquet"))
    if parquets:
        import pandas as pd
        df = pd.read_parquet(parquets[0])
        est = compilar_estrategia_usuario(PLANTILLA_CRUCE_SMA)
        señales = est.generar_senales(df)
        longs = (señales == 1).sum()
        shorts = (señales == -1).sum()
        console.print(f"  ✓ Longs: {longs}, Shorts: {shorts}")