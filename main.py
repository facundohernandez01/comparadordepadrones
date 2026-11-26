"""
Comparador de Padrones Fiscales Argentinos
==========================================
Modos de ejecución:

  GUI interactiva:
    python main.py

  CLI directo (sin GUI):
    python main.py AGIP_CLIENTES master.txt padron.txt salida.prn
    python main.py TUCUMAN_CLIENTES master.txt padron_trim.txt padron_men.txt salida.prn

  Modo automático/RPA (usa config.ini):
    python main.py --auto
    python main.py --auto SIRCIP
    python main.py --auto AGIP_CLIENTES master.txt padron.txt salida.prn
    python main.py --auto TUCUMAN_CLIENTES master.txt trim.txt men.txt salida.prn
"""

import sys
import traceback
import configparser
from pathlib import Path

# Asegurar que el directorio raíz esté en el path para imports relativos
sys.path.insert(0, str(Path(__file__).parent))

# Importar todas las jurisdicciones (activa los @register)
import jurisdicciones  # noqa: F401

from core.runner import run_padron, REGISTRY, TUCUMAN_TIPOS
from core.logger import get_logger

CONFIG_FILE = Path(__file__).parent / "config.ini"
log = get_logger("main")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def run_cli(tipo: str, master: str, padron: str, salida: str, padron2: str = None):
    if tipo not in REGISTRY:
        print(f"ERROR: Tipo '{tipo}' no soportado.\n"
              f"Disponibles: {', '.join(sorted(REGISTRY))}")
        sys.exit(1)

    def progress(msg, cur, total):
        pct = f" [{cur * 100 // total:3d}%]" if total > 0 else ""
        print(f"  {msg}{pct}", flush=True)

    print("=" * 50)
    print(f"  PADRON : {tipo}")
    print(f"  MASTER : {master}")
    print(f"  PADRON : {padron}")
    if tipo in TUCUMAN_TIPOS:
        print(f"  PADRON2: {padron2}")
    print(f"  SALIDA : {salida}")
    print("=" * 50)

    try:
        run_padron(tipo, master, padron, salida, progress,
                   padron2=padron2 if tipo in TUCUMAN_TIPOS else None)
        print("=" * 50)
        print("  OK")
        log.info("CLI finalizado OK: %s", tipo)
    except Exception as e:
        print(f"ERROR: {e}")
        traceback.print_exc()
        log.exception("CLI error: %s", tipo)
        sys.exit(1)


def run_auto(tipo_override: str = None):
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE, encoding="utf-8")

    tipo = tipo_override or config.get("DEFAULT", "padron_auto", fallback=None)
    if not tipo:
        print("ERROR: padron_auto no definido en config.ini.")
        sys.exit(1)
    if tipo not in config:
        print(f"ERROR: Sección [{tipo}] no existe en config.ini")
        sys.exit(1)

    sec = config[tipo]
    master  = sec.get("master_data", "")
    padron  = sec.get("padron", "")
    padron2 = sec.get("padron2", "") if tipo in TUCUMAN_TIPOS else None
    salida  = sec.get("salida", "")

    for label, val in [("master_data", master), ("padron", padron), ("salida", salida)]:
        if not val:
            print(f"ERROR: '{label}' no configurado en [{tipo}]")
            sys.exit(1)

    if tipo in TUCUMAN_TIPOS and not padron2:
        print(f"ERROR: 'padron2' no configurado en [{tipo}]")
        sys.exit(1)

    run_cli(tipo, master, padron, salida, padron2)


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------

def run_gui():
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QIcon
    from gui.app import MainWindow

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    icon_path = Path(__file__).parent / "icon.png"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    win = MainWindow()
    win.show()
    sys.exit(app.exec())


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    args = sys.argv[1:]

    # Modo automático/RPA
    if args and args[0] == "--auto":
        rest = args[1:]
        if len(rest) == 0:
            run_auto()
        elif len(rest) == 1:
            run_auto(rest[0])
        elif len(rest) == 5 and rest[0] in TUCUMAN_TIPOS:
            # --auto TUCUMAN master trim men salida
            run_cli(rest[0], rest[1], rest[2], rest[4], rest[3])
        elif len(rest) == 4:
            # --auto TIPO master padron salida
            run_cli(rest[0], rest[1], rest[2], rest[3])
        else:
            print(__doc__)
            sys.exit(1)
        return

    # CLI directo
    if len(args) == 5 and args[0] in TUCUMAN_TIPOS:
        # TUCUMAN master trim men salida
        run_cli(args[0], args[1], args[2], args[4], args[3])
        return
    if len(args) == 4:
        run_cli(args[0], args[1], args[2], args[3])
        return

    if len(args) > 0:
        print(__doc__)
        sys.exit(1)

    run_gui()


if __name__ == "__main__":
    main()
