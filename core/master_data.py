"""
Carga de master data en distintas variantes según la jurisdicción.
Todos los loaders deduplicán y retornan estructuras O(1) para lookup.
"""

from __future__ import annotations
from core.logger import get_logger

log = get_logger("master_data")


def load_cuits_set(master_path: str) -> set[str]:
    """
    Carga CUITs desde master data pipe-delimited.
    Columna 2 (índice 2) = CUIT.
    Usado por: AGIP, ARBA, RG615, SIRCIP.
    """
    cuits: set[str] = set()
    with open(master_path, "r", encoding="latin1") as f:
        for line in f:
            parts = line.strip().split("|")
            if len(parts) > 2:
                cuit = parts[2].strip()
                if cuit:
                    cuits.add(cuit)
    log.debug("load_cuits_set: %d CUITs cargados desde %s", len(cuits), master_path)
    return cuits


def load_num_cuit_pairs(master_path: str,
                         filter_fn=None) -> tuple[list[str], dict[str, list[str]]]:
    """
    Carga pares num|CUIT, aplica filtro opcional, deduplica por numCliente.
    Retorna (md_list, cuit_to_nums_dict).
    Usado por: JUJUY, RG17, EMBARGOS, TUCUMAN.

    filter_fn(num_str, cuit_str) -> bool
    """
    seen: dict[str, str] = {}  # num -> cuit, deduplicado
    with open(master_path, "r", encoding="latin1") as f:
        for line in f:
            cols = line.replace(" ", "").strip().split("|")
            if len(cols) < 3:
                continue
            num = cols[1].strip()
            cuit = cols[2].strip()
            if not num or not cuit:
                continue
            if filter_fn and not filter_fn(num, cuit):
                continue
            seen[num] = cuit

    md = sorted({f"{n}|{c}" for n, c in seen.items()})
    idx = _build_index(md)
    log.debug("load_num_cuit_pairs: %d registros, %d CUITs únicos desde %s",
              len(md), len(idx), master_path)
    return md, idx


def _build_index(md: list[str]) -> dict[str, list[str]]:
    """["num|cuit",...] -> {cuit: [num1,num2]} deduplicado y ordenado."""
    result: dict[str, set] = {}
    for item in md:
        num, cuit = item.split("|", 1)
        result.setdefault(cuit, set()).add(num)
    return {cuit: sorted(nums, key=lambda x: int(x) if x.isdigit() else 0)
            for cuit, nums in result.items()}


# ---------------------------------------------------------------------------
# Filtros reutilizables
# ---------------------------------------------------------------------------

def filter_clientes_rango(num: str, cuit: str) -> bool:
    """Filtra numCliente fuera del rango 400000-599999 y que sea numérico."""
    if not num.isdigit():
        return False
    val = int(num)
    return val <= 399999 or val >= 599999


def filter_proveedores_cuit(num: str, cuit: str) -> bool:
    """Filtra proveedores con CUIT > 20000000000."""
    if not cuit.isdigit():
        return False
    return int(cuit) > 20_000_000_000
