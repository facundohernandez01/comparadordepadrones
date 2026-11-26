"""
AGIP — Agencia Gubernamental de Ingresos Públicos (CABA)
  - AGIP_CLIENTES   : Percepciones
  - AGIP_PROVEEDORES: Retenciones
"""

from __future__ import annotations
from core.runner import register
from core.master_data import load_cuits_set
from core.fixed_width import count_lines
from jurisdicciones.base import PadronProcessor


_GRUPOS = {
    "0,00": "01", "0,10": "02", "0,20": "03", "0,50": "04", "0,75": "05",
    "0,90": "06", "1,00": "07", "1,25": "08", "1,50": "09", "1,75": "10",
    "2,00": "11", "2,50": "12", "3,00": "14", "3,50": "17",
    "4,00": "15", "4,50": "16",
}


@register("AGIP_CLIENTES")
class AgipClientes(PadronProcessor):
    """Percepciones CABA. Filtra CUIT campo[3], escribe campos[0:11], header J1A2."""

    def process(self):
        clientes = load_cuits_set(self.master_path)
        total = self._count(self.padron_path)
        self.progress("Cargando master data...", 0, 1)
        self.log.info("%d CUITs en master data", len(clientes))
        self.progress(f"Master data: {len(clientes):,} CUITs. Procesando...", 0, total)

        procesados = encontrados = 0
        with open(self.padron_path, "r", encoding="latin1") as fi, \
             open(self.output_path, "w", encoding="latin1") as fo:
            fo.write("J1A2\n")
            for line in fi:
                procesados += 1
                line = line.strip()
                if not line:
                    continue
                campos = line.split(";")
                if len(campos) < 11:
                    continue
                if campos[3].strip() in clientes:
                    encontrados += 1
                    fo.write(";".join(campos[:11]) + "\n")
                if procesados % 50_000 == 0:
                    self.progress(
                        f"Procesados: {procesados:,} | Encontrados: {encontrados:,}",
                        procesados, total)

        self.log.info("Finalizado — procesados=%d encontrados=%d", procesados, encontrados)
        self.progress(
            f"Finalizado — Procesados: {procesados:,} | Encontrados: {encontrados:,}",
            total, total)


@register("AGIP_PROVEEDORES")
class AgipProveedores(PadronProcessor):
    """Retenciones CABA. Filtra CUIT campo[3], reemplaza campo[9] por grupo de alícuota."""

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
                if len(c) < 11:
                    continue
                if c[3].strip() in clientes:
                    encontrados += 1
                    grupo = _GRUPOS.get(c[8], "")
                    fo.write(";".join([c[0], c[1], c[2], c[3], c[4],
                                       c[5], c[6], c[7], c[8], c[10], grupo]) + "\n")
                if procesados % 50_000 == 0:
                    self.progress(
                        f"Procesados: {procesados:,} | Encontrados: {encontrados:,}",
                        procesados, total)

        self.log.info("Finalizado — procesados=%d encontrados=%d", procesados, encontrados)
        self.progress(
            f"Finalizado — Procesados: {procesados:,} | Encontrados: {encontrados:,}",
            total, total)
