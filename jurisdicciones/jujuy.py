"""
JUJUY_CLIENTES — Dirección Provincial de Rentas de Jujuy.
Padrón CSV: CUIT,PERIODO(YYYYMM),alicuota,num_cliente
MasterData: numCliente (rango <=399999 o >=599999) | CUIT
"""

from __future__ import annotations
from datetime import datetime, timedelta
from core.runner import register
from core.master_data import load_num_cuit_pairs, filter_clientes_rango
from jurisdicciones.base import PadronProcessor


@register("JUJUY_CLIENTES")
class JujuyClientes(PadronProcessor):

    def process(self):
        md, cuit_to_nums = load_num_cuit_pairs(self.master_path, filter_clientes_rango)
        total = self._count(self.padron_path)
        self.progress(f"Master data: {len(cuit_to_nums):,} CUITs. Procesando...", 0, total)

        procesados = encontrados = 0
        with open(self.padron_path, "r", encoding="latin1") as fi, \
             open(self.output_path, "w", encoding="latin1") as fo:
            for line in fi:
                procesados += 1
                line = line.strip()
                if not line:
                    continue
                campos = line.split(",")
                if len(campos) < 3:
                    continue
                cuit = campos[0].strip()
                if cuit not in cuit_to_nums:
                    continue

                periodo = campos[1].strip()   # YYYYMM
                try:
                    alic = float(campos[2].strip().replace(",", "."))
                except ValueError:
                    continue

                exclusion = (1 - alic / 6) * 100
                fecha_desde = f"01.{periodo[4:6]}.{periodo[:4]}"
                dt_desde = datetime.strptime(fecha_desde, "%d.%m.%Y")
                dt_hasta = (dt_desde.replace(day=1) +
                            timedelta(days=32)).replace(day=10)
                fecha_hasta = f"10.{dt_hasta.month:02d}.{dt_hasta.year}"

                for num_cli in cuit_to_nums[cuit]:
                    encontrados += 1
                    excl_fmt = f"{exclusion:.2f}".rjust(6)
                    fo.write(
                        f"{int(num_cli):08d} J2D 01.05.2017 31.12.2999"
                        f"          PADRON {excl_fmt} {fecha_desde} {fecha_hasta}\n"
                    )

                if procesados % 50_000 == 0:
                    self.progress(
                        f"Procesados: {procesados:,} | Encontrados: {encontrados:,}",
                        procesados, total)

        self.log.info("Finalizado — procesados=%d encontrados=%d", procesados, encontrados)
        self.progress(
            f"Finalizado — Procesados: {procesados:,} | Encontrados: {encontrados:,}",
            total, total)
