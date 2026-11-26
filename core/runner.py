"""
Dispatcher central. Cada jurisdicción se registra con @register.
El CLI y la GUI llaman únicamente a run_padron().
"""

from __future__ import annotations
from typing import Callable
from core.logger import get_logger

log = get_logger("runner")

# (mensaje, actual, total)
ProgressCallback = Callable[[str, int, int], None]

REGISTRY: dict[str, type] = {}          # tipo -> clase PadronProcessor
TUCUMAN_TIPOS = ("TUCUMAN_CLIENTES", "TUCUMAN_PROVEEDORES")


def register(tipo: str):
    """Decorador: @register('AGIP_CLIENTES')."""
    def decorator(cls):
        REGISTRY[tipo] = cls
        log.debug("Registrado: %s -> %s", tipo, cls.__name__)
        return cls
    return decorator


def run_padron(tipo: str, master: str, padron: str, salida: str,
               progress: ProgressCallback = None, padron2: str = None):
    """
    API pública unificada.
      Normal:   run_padron(tipo, master, padron, salida, progress)
      Tucumán:  run_padron(tipo, master, padron_trim, salida, progress,
                           padron2=padron_mensual)
    """
    if progress is None:
        progress = _noop

    cls = REGISTRY.get(tipo)
    if cls is None:
        raise ValueError(f"Tipo de padrón no soportado: '{tipo}'. "
                         f"Disponibles: {', '.join(sorted(REGISTRY))}")

    log.info("Iniciando %s | master=%s padron=%s salida=%s", tipo, master, padron, salida)

    if tipo in TUCUMAN_TIPOS:
        if not padron2:
            raise ValueError(f"{tipo} requiere padron2 (padrón mensual).")
        processor = cls(master, padron, salida, progress, padron2=padron2)
    else:
        processor = cls(master, padron, salida, progress)

    processor.run()
    log.info("Finalizado %s", tipo)


def _noop(msg: str, cur: int, total: int):
    pass
