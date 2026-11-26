"""
Logging centralizado.
- Archivo rotativo: comparador.log (5 MB x 3 backups)
- Consola: solo WARNING+
- La GUI puede adjuntar su propio handler en tiempo de ejecución.
"""

import logging
import logging.handlers
from pathlib import Path

_LOG_FILE = Path(__file__).parent.parent / "comparador.log"
_FMT = "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s"
_DATE = "%Y-%m-%d %H:%M:%S"

logging.basicConfig(handlers=[], level=logging.DEBUG)  # raíz sin handlers

_root = logging.getLogger("comparador")
_root.setLevel(logging.DEBUG)
_root.propagate = False

# --- archivo rotativo ---
_fh = logging.handlers.RotatingFileHandler(
    _LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
)
_fh.setLevel(logging.DEBUG)
_fh.setFormatter(logging.Formatter(_FMT, _DATE))
_root.addHandler(_fh)

# --- consola ---
_ch = logging.StreamHandler()
_ch.setLevel(logging.WARNING)
_ch.setFormatter(logging.Formatter(_FMT, _DATE))
_root.addHandler(_ch)


def get_logger(name: str) -> logging.Logger:
    """Devuelve un logger hijo del root 'comparador'."""
    return _root.getChild(name)


def add_gui_handler(handler: logging.Handler):
    """Adjunta un handler extra (ej: emitir a QTextEdit)."""
    handler.setFormatter(logging.Formatter(_FMT, _DATE))
    _root.addHandler(handler)


def remove_gui_handler(handler: logging.Handler):
    _root.removeHandler(handler)
