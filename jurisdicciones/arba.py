"""
ARBA — Agencia de Recaudación de Buenos Aires (PBA)
  - ARBA_CLIENTES   : Percepciones
  - ARBA_PROVEEDORES: Retenciones
"""

from __future__ import annotations
from core.runner import register
from core.master_data import load_cuits_set
from jurisdicciones.base import PadronProcessor


@register("ARBA_CLIENTES")
class ArbaClientes(PadronProcessor):
    """Percepciones PBA. CUIT en campo[4]. Reordena columnas, agrega 0,00 y 00. Header J1A1."""

    def process(self):
        clientes = load_cuits_set(self.master_path)
        total = self._count(self.padron_path)
        self.progress(f"Master data: {len(clientes):,} CUITs. Procesando...", 0, total)

        procesados = encontrados = 0
        with open(self.padron_path, "r", encoding="latin1") as fi, \
             open(self.output_path, "w", encoding="latin1") as fo:
            fo.write("J1A1\n")
            for line in fi:
                procesados += 1
                line = line.strip()
                if not line:
                    continue
                c = line.split(";")
                if len(c) < 10:
                    continue
                if c[4].strip() in clientes:
                    encontrados += 1
                    fo.write(";".join([c[1], c[2], c[3], c[4], c[5],
                                       c[6], c[7], c[8], "0,00", c[9], "00"]) + "\n")
                if procesados % 50_000 == 0:
                    self.progress(
                        f"Procesados: {procesados:,} | Encontrados: {encontrados:,}",
                        procesados, total)

        self.log.info("Finalizado — procesados=%d encontrados=%d", procesados, encontrados)
        self.progress(
            f"Finalizado — Procesados: {procesados:,} | Encontrados: {encontrados:,}",
            total, total)


@register("ARBA_PROVEEDORES")
class ArbaProveedores(PadronProcessor):
    """Retenciones PBA. CUIT en campo[4]. Reordena columnas, agrega 0,00 y 00."""

    def process(self):
        clientes = load_cuits_set(self.master_path)
        total = self._count(self.padron_path)
        self.progress(f"Master data: {len(clientes):,} CUITs. Procesando...", 0, total)

        procesados = encontrados = 0
        with open(self.padron_path, "r", encoding="latin1") as fi, \
             open(self.output_path, "w", encoding="latin1") as fo:
            for line in fi:
                procesados += 1
                line = line.strip()
                if not line:
                    continue
                c = line.split(";")
                if len(c) < 10:
                    continue
                if c[4].strip() in clientes:
                    encontrados += 1
                    fo.write(";".join([c[1], c[2], c[3], c[4], c[5],
                                       c[6], c[7], "0,00", c[8], "00", c[9]]) + "\n")
                if procesados % 50_000 == 0:
                    self.progress(
                        f"Procesados: {procesados:,} | Encontrados: {encontrados:,}",
                        procesados, total)

        self.log.info("Finalizado — procesados=%d encontrados=%d", procesados, encontrados)
        self.progress(
            f"Finalizado — Procesados: {procesados:,} | Encontrados: {encontrados:,}",
            total, total)
