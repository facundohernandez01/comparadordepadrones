"""
Worker QThread para ejecutar procesamiento en background sin bloquear la GUI.
Las señales son atributos de clase (no de instancia) — requisito de PySide6.
"""

from __future__ import annotations
import traceback
from PySide6.QtCore import QThread, Signal
from core.runner import run_padron, TUCUMAN_TIPOS


class Worker(QThread):
    progress = Signal(str, int, int)
    finished = Signal()
    error = Signal(str)

    def __init__(self, tipo: str, master: str, padron: str,
                 salida: str, padron2: str = None):
        super().__init__()
        self.tipo = tipo
        self.master = master
        self.padron = padron
        self.salida = salida
        self.padron2 = padron2

    def run(self):
        try:
            run_padron(
                self.tipo, self.master, self.padron, self.salida,
                self.progress.emit,
                padron2=self.padron2 if self.tipo in TUCUMAN_TIPOS else None,
            )
            self.finished.emit()
        except Exception as e:
            msg = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"
            self.error.emit(msg)
