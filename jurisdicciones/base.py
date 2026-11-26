"""
Clase base para todos los procesadores de padrón.
Cada jurisdicción hereda de PadronProcessor e implementa process().
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from core.runner import ProgressCallback, _noop
from core.fixed_width import count_lines
from core.logger import get_logger


class PadronProcessor(ABC):
    """
    Contrato común para todas las jurisdicciones.

    Subclases deben implementar process().
    run() se encarga del try/except y logging.
    """

    def __init__(self, master_path: str, padron_path: str, output_path: str,
                 progress: ProgressCallback = _noop, **kwargs):
        self.master_path = master_path
        self.padron_path = padron_path
        self.output_path = output_path
        self.progress = progress
        self.log = get_logger(self.__class__.__name__)

    def _count(self, path: str) -> int:
        return count_lines(path)

    def run(self):
        """Entry point llamado por el dispatcher. No sobreescribir."""
        try:
            self.process()
        except Exception as e:
            self.log.exception("Error en %s: %s", self.__class__.__name__, e)
            raise

    @abstractmethod
    def process(self):
        """Lógica principal de la jurisdicción."""
        ...
