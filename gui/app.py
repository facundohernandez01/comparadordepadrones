"""
Ventana principal del Comparador de Padrones.
Lee/escribe config.ini automáticamente.
Soporta Tucumán con campo extra para padrón mensual.
"""

from __future__ import annotations
import logging
from pathlib import Path
import configparser

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QProgressBar,
    QTextEdit, QFileDialog, QGroupBox, QFormLayout,
    QMessageBox,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from core.runner import REGISTRY, TUCUMAN_TIPOS
from core.logger import add_gui_handler, remove_gui_handler, get_logger
from gui.worker import Worker

CONFIG_FILE = Path(__file__).parent.parent / "config.ini"
log = get_logger("gui")


class _LogHandler(logging.Handler):
    """Redirige logs al QTextEdit."""
    def __init__(self, widget: QTextEdit):
        super().__init__()
        self._w = widget

    def emit(self, record):
        try:
            self._w.append(self.format(record))
            sb = self._w.verticalScrollBar()
            sb.setValue(sb.maximum())
        except Exception:
            pass


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Comparador de Padrones Fiscales")
        self.setMinimumWidth(820)
        self._worker: Worker | None = None
        self._config = configparser.ConfigParser()
        self._config.read(CONFIG_FILE, encoding="utf-8")
        self._log_handler: _LogHandler | None = None
        self._build_ui()
        self._load_config_to_ui()

    # ------------------------------------------------------------------
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(8)
        root.setContentsMargins(12, 12, 12, 12)

        # ---- Jurisdicción ----
        jur_box = QGroupBox("Jurisdicción")
        jur_lay = QHBoxLayout(jur_box)
        self.cb_tipo = QComboBox()
        self.cb_tipo.addItems(sorted(REGISTRY.keys()))
        self.cb_tipo.currentTextChanged.connect(self._on_tipo_changed)
        lbl_auto = QLabel("Auto por defecto:")
        self.cb_auto = QComboBox()
        self.cb_auto.addItems(sorted(REGISTRY.keys()))
        btn_save_auto = QPushButton("💾 Guardar")
        btn_save_auto.setFixedWidth(90)
        btn_save_auto.clicked.connect(self._save_auto_default)
        jur_lay.addWidget(QLabel("Padrón:"))
        jur_lay.addWidget(self.cb_tipo, 1)
        jur_lay.addWidget(lbl_auto)
        jur_lay.addWidget(self.cb_auto, 1)
        jur_lay.addWidget(btn_save_auto)
        root.addWidget(jur_box)

        # ---- Archivos ----
        arch_box = QGroupBox("Archivos")
        self._form = QFormLayout(arch_box)
        self.le_master = self._file_row("Master Data:", False)
        self.le_padron = self._file_row("Padrón:", False)
        # Fila extra para Tucumán (padrón mensual)
        self._row_padron2 = QHBoxLayout()
        self.le_padron2 = QLineEdit()
        btn2 = QPushButton("...")
        btn2.setFixedWidth(32)
        btn2.clicked.connect(lambda: self._browse_open(self.le_padron2))
        self._row_padron2.addWidget(self.le_padron2)
        self._row_padron2.addWidget(btn2)
        self._lbl_padron2 = QLabel("Padrón Mensual:")
        self._form.addRow(self._lbl_padron2, self._row_padron2)
        self.le_salida = self._file_row("Salida:", True)
        root.addWidget(arch_box)

        # ---- Progreso ----
        prog_box = QGroupBox("Progreso")
        prog_lay = QVBoxLayout(prog_box)
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.lbl_estado = QLabel("Listo.")
        self.lbl_estado.setWordWrap(True)
        prog_lay.addWidget(self.progress_bar)
        prog_lay.addWidget(self.lbl_estado)
        root.addWidget(prog_box)

        # ---- Log ----
        log_box = QGroupBox("Log")
        log_lay = QVBoxLayout(log_box)
        self.log_widget = QTextEdit()
        self.log_widget.setReadOnly(True)
        self.log_widget.setMaximumHeight(200)
        self.log_widget.setFont(QFont("Consolas", 9))
        log_lay.addWidget(self.log_widget)
        root.addWidget(log_box)

        # ---- Botones ----
        btn_row = QHBoxLayout()
        self.btn_start = QPushButton("▶ INICIAR")
        self.btn_start.setFixedHeight(40)
        self.btn_start.setStyleSheet(
            "QPushButton{background:#2d7d3f;color:white;font-weight:bold;"
            "font-size:14px;border-radius:4px}"
            "QPushButton:hover{background:#3aaa55}"
            "QPushButton:disabled{background:#555;color:#999}"
        )
        self.btn_start.clicked.connect(self._on_start)
        btn_save = QPushButton("💾 Guardar config")
        btn_save.clicked.connect(self._save_current_config)
        btn_clear = QPushButton("🗑 Limpiar log")
        btn_clear.clicked.connect(self.log_widget.clear)
        btn_row.addWidget(self.btn_start, 2)
        btn_row.addWidget(btn_save)
        btn_row.addWidget(btn_clear)
        root.addLayout(btn_row)

    def _file_row(self, label: str, save: bool) -> QLineEdit:
        row = QHBoxLayout()
        le = QLineEdit()
        btn = QPushButton("...")
        btn.setFixedWidth(32)
        if save:
            btn.clicked.connect(lambda: self._browse_save(le))
        else:
            btn.clicked.connect(lambda: self._browse_open(le))
        row.addWidget(le)
        row.addWidget(btn)
        self._form.addRow(label, row)
        return le

    def _browse_open(self, le: QLineEdit):
        path, _ = QFileDialog.getOpenFileName(self, "Seleccionar archivo", le.text())
        if path:
            le.setText(path)
            self._save_current_config()

    def _browse_save(self, le: QLineEdit):
        path, _ = QFileDialog.getSaveFileName(self, "Archivo de salida", le.text())
        if path:
            le.setText(path)
            self._save_current_config()

    # ------------------------------------------------------------------
    def _on_tipo_changed(self, tipo: str):
        es_tucuman = tipo in TUCUMAN_TIPOS
        self._lbl_padron2.setVisible(es_tucuman)
        self.le_padron2.setVisible(es_tucuman)
        # botón ... del padron2
        self._row_padron2.itemAt(1).widget().setVisible(es_tucuman)

        if tipo in self._config:
            sec = self._config[tipo]
            self.le_master.setText(sec.get("master_data", ""))
            self.le_padron.setText(sec.get("padron", ""))
            self.le_padron2.setText(sec.get("padron2", ""))
            self.le_salida.setText(sec.get("salida", ""))

    def _load_config_to_ui(self):
        auto = self._config.get("DEFAULT", "padron_auto", fallback="AGIP_CLIENTES")
        idx = self.cb_auto.findText(auto)
        if idx >= 0:
            self.cb_auto.setCurrentIndex(idx)
        self._on_tipo_changed(self.cb_tipo.currentText())

    def _save_auto_default(self):
        self._config["DEFAULT"]["padron_auto"] = self.cb_auto.currentText()
        self._write_config()
        self._log_ui("✔ Jurisdicción automática guardada.")

    def _save_current_config(self):
        tipo = self.cb_tipo.currentText()
        if tipo not in self._config:
            self._config[tipo] = {}
        self._config[tipo]["master_data"] = self.le_master.text()
        self._config[tipo]["padron"] = self.le_padron.text()
        self._config[tipo]["padron2"] = self.le_padron2.text()
        self._config[tipo]["salida"] = self.le_salida.text()
        self._write_config()

    def _write_config(self):
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            self._config.write(f)

    # ------------------------------------------------------------------
    def _on_start(self):
        tipo = self.cb_tipo.currentText()
        master = self.le_master.text().strip()
        padron = self.le_padron.text().strip()
        padron2 = self.le_padron2.text().strip()
        salida = self.le_salida.text().strip()

        errors = []
        if not Path(master).exists():
            errors.append(f"Master data no encontrado: {master}")
        if not Path(padron).exists():
            errors.append(f"Padrón no encontrado: {padron}")
        if tipo in TUCUMAN_TIPOS and not Path(padron2).exists():
            errors.append(f"Padrón mensual no encontrado: {padron2}")
        if not salida:
            errors.append("Debe especificar archivo de salida.")
        if errors:
            QMessageBox.warning(self, "Error de validación", "\n".join(errors))
            return

        self._save_current_config()
        self.btn_start.setEnabled(False)
        self.progress_bar.setValue(0)
        self.progress_bar.setMaximum(100)

        # Adjuntar log handler
        if self._log_handler:
            remove_gui_handler(self._log_handler)
        self._log_handler = _LogHandler(self.log_widget)
        add_gui_handler(self._log_handler)

        self._log_ui(f"[INICIO] {tipo} | {Path(padron).name} → {Path(salida).name}")
        if tipo in TUCUMAN_TIPOS:
            self._log_ui(f"Padrón 2: {Path(padron2).name}")

        self._worker = Worker(tipo, master, padron, salida,
                              padron2=padron2 if tipo in TUCUMAN_TIPOS else None)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_progress(self, msg: str, cur: int, total: int):
        self.lbl_estado.setText(msg)
        if total > 0:
            self.progress_bar.setMaximum(total)
            self.progress_bar.setValue(cur)

    def _on_finished(self):
        self.progress_bar.setValue(self.progress_bar.maximum())
        self.lbl_estado.setText("✔ Finalizado correctamente.")
        self._log_ui("✔ Proceso finalizado.")
        self.btn_start.setEnabled(True)
        self._cleanup_worker()

    def _on_error(self, msg: str):
        self.lbl_estado.setText("✘ ERROR")
        self._log_ui(f"ERROR:\n{msg}")
        QMessageBox.critical(self, "Error", msg[:600])
        self.btn_start.setEnabled(True)
        self._cleanup_worker()

    def _cleanup_worker(self):
        if self._worker:
            self._worker.quit()
            self._worker.wait()
            self._worker = None
        if self._log_handler:
            remove_gui_handler(self._log_handler)
            self._log_handler = None

    def _log_ui(self, msg: str):
        self.log_widget.append(msg)
        sb = self.log_widget.verticalScrollBar()
        sb.setValue(sb.maximum())

    def closeEvent(self, event):
        self._cleanup_worker()
        super().closeEvent(event)
