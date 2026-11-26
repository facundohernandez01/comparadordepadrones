"""
RG615 — AFIP RG 615 (retenciones IVA).
RG17  — AFIP RG 17 (certificados de no retención IVA).
EMBARGOS — Embargos AFIP.
SIRCIP — Sistema de Recaudación y Control de Ingresos Públicos (consolidador nacional).
"""

from __future__ import annotations
from datetime import datetime
from collections import defaultdict

from core.runner import register
from core.master_data import load_num_cuit_pairs, filter_clientes_rango
from core.fixed_width import split_fixed, count_lines
from jurisdicciones.base import PadronProcessor


# ---------------------------------------------------------------------------
# RG615
# ---------------------------------------------------------------------------

_DUMMY_CUITS = {"22222222222", "20219999991"}


@register("RG615")
class Rg615(PadronProcessor):
    """
    Filtra CUIT (col 2 del master, col 1 del padrón CSV).
    Rango: 199_999_999 <= CUIT <= 35_000_000_000, excluye dummies.
    Skipea primeras 5 líneas del master.
    """

    def process(self):
        cuits: set[str] = set()
        with open(self.master_path, "r", encoding="latin1") as f:
            for _ in range(5):
                f.readline()
            for line in f:
                parts = line.strip().split("|")
                if len(parts) < 3:
                    continue
                cuit = parts[2].strip()
                if not cuit or not cuit.isdigit():
                    continue
                val = int(cuit)
                if 199_999_999 <= val <= 35_000_000_000 and cuit not in _DUMMY_CUITS:
                    cuits.add(cuit)

        total = self._count(self.padron_path)
        self.progress(f"Master data: {len(cuits):,} CUITs. Procesando...", 0, total)

        procesados = encontrados = 0
        with open(self.padron_path, "r", encoding="latin1") as fi, \
             open(self.output_path, "w", encoding="latin1") as fo:
            for line in fi:
                procesados += 1
                line = line.strip()
                if not line:
                    continue
                parts = line.split(",")
                if len(parts) < 2:
                    continue
                if parts[1].strip() in cuits:
                    encontrados += 1
                    fo.write(line + "\n")
                if procesados % 50_000 == 0:
                    self.progress(
                        f"Procesados: {procesados:,} | Encontrados: {encontrados:,}",
                        procesados, total)

        self.log.info("Finalizado — procesados=%d encontrados=%d", procesados, encontrados)
        self.progress(
            f"Finalizado — Procesados: {procesados:,} | Encontrados: {encontrados:,}",
            total, total)


# ---------------------------------------------------------------------------
# RG17
# ---------------------------------------------------------------------------

_RG17_WIDTHS = [12, 60, 10, 10, 12, 6, 20]


@register("RG17")
class Rg17(PadronProcessor):
    """
    Padrón ancho fijo [12,60,10,10,12,6,20].
    Agrupa por CUIT, calcula fechaDesde/Hasta mín/máx.
    MasterData: numCliente|CUIT, rango clientes.
    """

    def process(self):
        _, cuit_to_nums = load_num_cuit_pairs(self.master_path, filter_clientes_rango)
        total = self._count(self.padron_path)
        self.progress(f"Cargando padrón RG17 ({total:,} líneas)...", 0, total)

        by_cuit: dict[str, list] = defaultdict(list)
        with open(self.padron_path, "r", encoding="latin1") as f:
            for line in f:
                campos = [c.strip() for c in split_fixed(line.rstrip("\n"), _RG17_WIDTHS, True)]
                if len(campos) < 7 or campos[6] != "CNR_IVA":
                    continue
                cuit = campos[0]
                if len(cuit) != 11 or not cuit.isdigit():
                    continue
                by_cuit[cuit].append((campos[2], campos[3], campos[4]))

        self.progress(f"Cruzando {len(by_cuit):,} CUITs...", 0, 1)
        encontrados = 0
        with open(self.output_path, "w", encoding="latin1") as fo:
            for cuit, registros in by_cuit.items():
                if cuit not in cuit_to_nums:
                    continue
                try:
                    fecha_desde = min(registros,
                                      key=lambda r: datetime.strptime(r[0], "%d/%m/%Y"))[0]
                    fecha_hasta = max(registros,
                                      key=lambda r: datetime.strptime(r[1], "%d/%m/%Y"))[1]
                    num_cert = registros[0][2]
                except Exception:
                    continue
                for num_cli in cuit_to_nums[cuit]:
                    encontrados += 1
                    fd = fecha_desde.replace("/", ".")
                    fh = fecha_hasta.replace("/", ".")
                    fo.write(
                        f"{int(num_cli):08d} PIV 01.01.2015 31.12.2999"
                        f"     CERTIFICADO    {num_cert.rjust(3)} {fd} {fh}\n"
                    )

        self.log.info("Finalizado — encontrados=%d", encontrados)
        self.progress(f"Finalizado — Encontrados: {encontrados:,}", 1, 1)


# ---------------------------------------------------------------------------
# EMBARGOS
# ---------------------------------------------------------------------------

_EMB_WIDTHS = [8, 11, 13, 120]


@register("EMBARGOS")
class Embargos(PadronProcessor):
    """Padrón ancho fijo [8,11,13,120] sin separador. CUIT en campo[1]."""

    def process(self):
        _, cuit_to_nums = load_num_cuit_pairs(self.master_path)
        total = self._count(self.padron_path)
        self.progress(f"Master data: {len(cuit_to_nums):,} CUITs. Procesando...", 0, total)

        procesados = encontrados = 0
        with open(self.padron_path, "r", encoding="latin1") as fi, \
             open(self.output_path, "w", encoding="latin1") as fo:
            for line in fi:
                procesados += 1
                if not line.strip():
                    continue
                campos = split_fixed(line.rstrip("\n"), _EMB_WIDTHS, False)
                cuit = campos[1].strip()
                if cuit not in cuit_to_nums:
                    continue
                descripcion = campos[3].strip() if len(campos) > 3 else ""
                for num_prov in cuit_to_nums[cuit]:
                    encontrados += 1
                    fo.write(f"{num_prov},{cuit},{descripcion}\n")
                if procesados % 50_000 == 0:
                    self.progress(
                        f"Procesados: {procesados:,} | Encontrados: {encontrados:,}",
                        procesados, total)

        self.log.info("Finalizado — procesados=%d encontrados=%d", procesados, encontrados)
        self.progress(
            f"Finalizado — Procesados: {procesados:,} | Encontrados: {encontrados:,}",
            total, total)


# ---------------------------------------------------------------------------
# SIRCIP
# ---------------------------------------------------------------------------

_ALICUOTAS = {
    "A": 0.00, "B": 0.01, "C": 0.05, "D": 0.10, "E": 0.20, "F": 0.30,
    "G": 0.40, "H": 0.50, "I": 0.60, "J": 0.70, "K": 0.80, "L": 1.00,
    "M": 1.20, "N": 1.40, "O": 1.50, "P": 1.60, "Q": 1.80, "R": 2.00,
    "S": 2.50, "T": 3.00, "U": 3.50, "V": 4.00, "W": 4.50, "X": 5.00,
}


@register("SIRCIP")
class Sircip(PadronProcessor):
    """
    SIRCIP — consolidador nacional (reemplazará otras jurisdicciones gradualmente).
    CSV: periodo,CUIT,razon_social,num_cert,CRC,alicuota_letra,hash
    Agrega columna alicuota_pct resolviendo la letra.
    """

    def process(self):
        from core.master_data import load_cuits_set
        clientes = load_cuits_set(self.master_path)
        total = self._count(self.padron_path)
        self.progress(f"Master data: {len(clientes):,} CUITs. Procesando SIRCIP...", 0, total)

        procesados = encontrados = 0
        with open(self.padron_path, "r", encoding="latin1") as fi, \
             open(self.output_path, "w", encoding="latin1") as fo:
            fo.write("periodo,CUIT,razon_social,num_cert,CRC,alicuota_letra,alicuota_pct\n")
            for line in fi:
                procesados += 1
                line = line.strip()
                if not line:
                    continue
                campos = line.split(",")
                if len(campos) < 6:
                    continue
                cuit = campos[1].strip()
                if cuit in clientes:
                    encontrados += 1
                    letra = campos[5].strip()
                    alicuota = _ALICUOTAS.get(letra, 0.0)
                    fo.write(f"{line},{alicuota:.2f}\n")
                if procesados % 50_000 == 0:
                    self.progress(
                        f"Procesados: {procesados:,} | Encontrados: {encontrados:,}",
                        procesados, total)

        self.log.info("Finalizado — procesados=%d encontrados=%d", procesados, encontrados)
        self.progress(
            f"Finalizado — Procesados: {procesados:,} | Encontrados: {encontrados:,}",
            total, total)
