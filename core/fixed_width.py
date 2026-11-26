"""
Utilidades de parsing de archivos de ancho fijo y conteo de líneas.
"""

from __future__ import annotations


def split_fixed(line: str, widths: list[int], space: bool) -> list[str]:
    """
    Equivalente a SplitFixedWidth del VB.NET original.
    space=True: hay un carácter separador entre cada campo.
    """
    result: list[str] = []
    pos = 0
    gap = 1 if space else 0
    for w in widths:
        result.append(line[pos:pos + w] if pos < len(line) else "")
        pos += w + gap
    return result


def count_lines(path: str) -> int:
    """Cuenta líneas eficientemente leyendo en bloques binarios."""
    count = 0
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            count += chunk.count(b"\n")
    return count


def safe_float(s: str, default: float = 0.0) -> float:
    try:
        return float(s.strip().replace(",", "."))
    except Exception:
        return default


def fmt_vb(val: float) -> str:
    """
    Replica {0:#0.##} de VB.NET:
    - Sin ceros finales tras el decimal
    - Separador decimal coma
    - Mínimo un dígito entero
    Ejemplos: 96.5->'96,5'  100.0->'100'  30.0->'30'  99.9->'99,9'
    """
    rounded = round(val, 2)
    if rounded == int(rounded):
        return str(int(rounded))
    s = f"{rounded:.2f}".rstrip("0").rstrip(".")
    return s.replace(".", ",")


def fmt_left(val: float, width: int = 6) -> str:
    """fmt_vb con PadLeft (clientes)."""
    return fmt_vb(val).rjust(width)


def fmt_right(val: float, width: int = 6) -> str:
    """fmt_vb con PadRight (proveedores)."""
    return fmt_vb(val).ljust(width)
