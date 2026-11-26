"""
TUCUMAN — Dirección General de Rentas de Tucumán.
  - TUCUMAN_CLIENTES   : RG 176/10 (acreditación inscripción)
  - TUCUMAN_PROVEEDORES: Coeficiente RG 116/10

Flujo:
  1. Cargar master data
  2. Cargar padrón TRIMESTRAL completo (sin saltear headers)
  3. Construir mdNoEstanTrimestral = clientes cuyo CUIT no aparece en el trim
  4. Recorrer trimestral → E/CL: escribir; CM: acumular
  5. Cargar padrón MENSUAL (widths distintos)
  6. Cruzar mensual con CM del trim y con mdNoEstanTrimestral
  7. Reprocesar CM no encontrados en mensual con datos del trimestral
"""

from __future__ import annotations
from datetime import datetime as _dt

from core.runner import register
from core.master_data import load_num_cuit_pairs, filter_clientes_rango, filter_proveedores_cuit
from core.fixed_width import split_fixed, count_lines, fmt_left, fmt_right, safe_float
from jurisdicciones.base import PadronProcessor

# Widths padrón TRIMESTRAL: [11,3,2,10,8,151,6] space=True
_TW = [11, 3, 2, 10, 8, 151, 6]
# Widths padrón MENSUAL:    [11,3,6,8,151,6]   space=True
_MW = [11, 3, 6, 8, 151, 6]

_MONTHS = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
    "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
    "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}


# ---------------------------------------------------------------------------
# Helpers de fecha (equivalentes a GetFromDate/GetToDate/ParseDatetime del VB)
# ---------------------------------------------------------------------------

def _parse_dt(s: str) -> str:
    """'d.m.yyyy' -> 'dd.mm.yyyy'"""
    parts = s.split(".")
    if len(parts) != 3:
        return s
    return f"{parts[0].zfill(2)}.{parts[1].zfill(2)}.{parts[2][:4]}"


def _get_from(state: dict) -> str:
    m = state.get("month") or _dt.now().month
    y = state.get("year") or _dt.now().year
    return _parse_dt(f"1.{m}.{y}")


def _get_to(state: dict) -> str:
    m = state.get("month") or _dt.now().month
    y = state.get("year") or _dt.now().year
    m2, y2 = (1, y + 1) if m == 12 else (m + 1, y)
    return _parse_dt(f"10.{m2}.{y2}")


def _to_from_yyyymmdd(hasta: str) -> str:
    """Convierte YYYYMMDD al día 10 del mes siguiente."""
    try:
        y, m = int(hasta[:4]), int(hasta[4:6])
        m2, y2 = (1, y + 1) if m == 12 else (m + 1, y)
        return _parse_dt(f"10.{m2}.{y2}")
    except Exception:
        return hasta


def _extract_date(line: str, state: dict):
    """ExtractFileDate del VB: extrae mes/año del encabezado del padrón."""
    if "PERIODO" not in line.upper():
        return
    ll = line.lower()
    for name, num in _MONTHS.items():
        if name in ll:
            state["month"] = num
            tail = line.strip()
            try:
                state["year"] = int(tail[-4:])
            except ValueError:
                pass
            break


# ---------------------------------------------------------------------------
# Carga de padrones
# ---------------------------------------------------------------------------

def _load_quarterly(path: str, progress) -> tuple[list, list, dict]:
    state: dict = {"month": 0, "year": 0}
    padron, padron_cuit = [], []
    total = count_lines(path)
    progress("Cargando padrón trimestral...", 0, total)
    with open(path, "r", encoding="latin1") as f:
        for i, raw in enumerate(f):
            s = raw.rstrip("\r\n")
            padron.append(s)
            cuit = s[:11].strip() if len(s) >= 11 else f"FILA_{i}"
            padron_cuit.append(cuit)
            if i < 10:
                _extract_date(s, state)
            if i % 50_000 == 0 and i:
                progress(f"Trimestral: {i:,}", i, total)
    progress(f"Trimestral: {len(padron):,} líneas", total, total)
    return padron, padron_cuit, state


def _load_monthly(path: str, progress) -> list:
    padron = []
    total = count_lines(path)
    progress("Cargando padrón mensual...", 0, total)
    with open(path, "r", encoding="latin1") as f:
        for i, raw in enumerate(f):
            padron.append(raw.rstrip("\r\n"))
            if i % 50_000 == 0 and i:
                progress(f"Mensual: {i:,}", i, total)
    progress(f"Mensual: {len(padron):,} líneas", total, total)
    return padron


def _not_in_quarterly(md: list, padron_cuit: list) -> tuple[list, dict]:
    """Clientes cuyo CUIT no aparece en el trimestral. O(n) con set."""
    cuit_set = set(padron_cuit)
    result = [item for item in md
              if item.split("|")[1].strip()
              and item.split("|")[1].strip() not in cuit_set]
    # índice rápido
    idx: dict = {}
    for item in result:
        num, cuit = item.split("|", 1)
        idx.setdefault(cuit, set()).add(num)
    return result, idx


def _parse_trim(item: str) -> list:
    return [x.strip() for x in split_fixed(item, _TW, space=True)]


def _parse_men(item: str) -> list:
    return [x.strip() for x in split_fixed(item, _MW, space=True)]


# ---------------------------------------------------------------------------
# TUCUMAN_CLIENTES
# ---------------------------------------------------------------------------

@register("TUCUMAN_CLIENTES")
class TucumanClientes(PadronProcessor):

    def __init__(self, master_path, padron_path, output_path, progress, **kwargs):
        super().__init__(master_path, padron_path, output_path, progress)
        self.padron2 = kwargs["padron2"]   # padrón mensual

    def process(self):
        self.progress("Cargando master data clientes...", 0, 1)
        md, cuit_to_nums = load_num_cuit_pairs(self.master_path, filter_clientes_rango)
        self.progress(
            f"Master data: {len(md):,} registros | {len(cuit_to_nums):,} CUITs", 0, 1)

        padron_trim, padron_cuit, state = _load_quarterly(self.padron_path, self.progress)
        _, no_trim_idx = _not_in_quarterly(md, padron_cuit)

        fd_periodo = _get_from(state)
        fh_periodo = _get_to(state)

        registros_cm: list[str] = []
        cm_procesados: list[str] = []

        with open(self.output_path, "w", encoding="latin1") as fo:

            # ---- FASE 1: trimestral ----
            total_t = len(padron_trim)
            self.progress(f"Fase 1: trimestral ({total_t:,} líneas)...", 0, total_t)
            for i, item in enumerate(padron_trim):
                f = _parse_trim(item)
                if len(f) < 7 or not f[0] or not f[0].isdigit():
                    continue
                cuit, tipo_e, cat = f[0], f[1], f[2]
                desde, hasta, porc = f[3], f[4], f[6]
                if cuit not in cuit_to_nums:
                    continue

                fd = f"{desde[6:8]}.{desde[4:6]}.{desde[:4]}"
                fh = _to_from_yyyymmdd(hasta)

                for num_cli in cuit_to_nums[cuit]:
                    nc = f"{int(num_cli):08d}"
                    if tipo_e == "E":
                        fo.write(f"{nc} IB5 01.01.2015 31.12.2999          E trim    100 {fd} {fh}\n")
                    elif cat == "CL":
                        if porc.strip() == "5":
                            fo.write(f"{nc} IB5 01.01.2015 31.12.2999\n")
                        else:
                            excl = (1.0 - safe_float(porc) / 5.0) * 100.0
                            fo.write(f"{nc} IB5 01.01.2015 31.12.2999        padron T {fmt_left(excl)} {fd} {fh}\n")
                    elif cat == "CM":
                        registros_cm.append(item)

                if i % 50_000 == 0 and i:
                    self.progress(f"Fase 1: {i:,}/{total_t:,}", i, total_t)

            # ---- FASE 2: mensual ----
            padron_men = _load_monthly(self.padron2, self.progress)
            cm_cuits = {_parse_trim(l)[0].strip() for l in registros_cm}

            total_m = len(padron_men)
            self.progress(f"Fase 2: mensual ({total_m:,} líneas)...", 0, total_m)
            encontrado = False

            for i, item4 in enumerate(padron_men):
                f = _parse_men(item4)
                if len(f) < 6 or not f[0] or not f[0].isdigit():
                    continue
                cuit, tipo_e = f[0], f[1]
                alic_men = f[2]
                porc = f[5] if len(f) > 5 else ""
                encontrado = False

                # Sub-caso A: CM del trimestral
                if cuit in cm_cuits and cuit in cuit_to_nums:
                    for num_cli in cuit_to_nums[cuit]:
                        nc = f"{int(num_cli):08d}"
                        if tipo_e == "E":
                            fo.write(f"{nc} IB5 01.01.2015 31.12.2999          E trim    100 {fd_periodo} {fh_periodo}\n")
                        else:
                            alq = fmt_left(96.5) if alic_men in ("0.0000", "-.----", "") \
                                else fmt_left((1.0 - safe_float(porc) / 2.0 * safe_float(alic_men) / 5.0) * 100.0)
                            fo.write(f"{nc} IB5 01.01.2015 31.12.2999          PADRON {alq} {fd_periodo} {fh_periodo}\n")
                        encontrado = True

                # Sub-caso B: no estaban en trimestral
                if cuit in no_trim_idx:
                    for num_cli in no_trim_idx[cuit]:
                        nc = f"{int(num_cli):08d}"
                        if tipo_e == "E":
                            fo.write(f"{nc} IB5 01.01.2015 31.12.2999          E trim    100 {fd_periodo} {fh_periodo}\n")
                            encontrado = True
                        else:
                            alq_val = 96.5 if alic_men in ("0.0000", "-.----", "") \
                                else (1.0 - safe_float(porc) * safe_float(alic_men) / 5.0) * 100.0
                            if round(alq_val, 2) == 0:
                                fo.write(f"{nc} IB5 01.01.2015 31.12.2999\n")
                            else:
                                fo.write(f"{nc} IB5 01.01.2015 31.12.2999          PADRON {fmt_left(alq_val)} {fd_periodo} {fh_periodo}\n")
                            encontrado = True

                if encontrado:
                    cm_procesados.append(cuit)

                if i % 50_000 == 0 and i:
                    self.progress(f"Fase 2: {i:,}/{total_m:,}", i, total_m)

            # ---- FASE 3: CM no encontrados en mensual ----
            cm_procesados_set = set(cm_procesados)
            self.progress(f"Fase 3: CM sin mensual ({len(registros_cm):,})...", 0, len(registros_cm))

            for item7 in registros_cm:
                f = _parse_trim(item7)
                if len(f) < 7 or not f[0]:
                    continue
                cuit, tipo_e, cat = f[0], f[1], f[2]
                desde, hasta, porc = f[3], f[4], f[6]
                if cuit in cm_procesados_set or cuit not in cuit_to_nums:
                    continue

                fd = f"{desde[6:8]}.{desde[4:6]}.{desde[:4]}"
                fh = _to_from_yyyymmdd(hasta)

                for num_cli in cuit_to_nums[cuit]:
                    nc = f"{int(num_cli):08d}"
                    if tipo_e == "E":
                        fo.write(f"{nc} IB5 01.01.2015 31.12.2999          E trim    100 {fd} {fh}\n")
                    elif cat == "CL":
                        if porc.strip() == "5":
                            fo.write(f"{nc} IB5 01.01.2015 31.12.2999\n")
                        else:
                            excl = (1.0 - safe_float(porc) / 5.0) * 100.0
                            fo.write(f"{nc} IB5 01.01.2015 31.12.2999        padron T {fmt_left(excl)} {fd} {fh}\n")
                    elif cat == "CM":
                        excl = 100.0 - safe_float(porc) * 10.0
                        fo.write(f"{nc} IB5 01.01.2015 31.12.2999          E trim {fmt_left(excl)} {fd} {fh}\n")

        self.log.info("Finalizado TUCUMAN_CLIENTES")
        self.progress("Finalizado TUCUMAN_CLIENTES.", 1, 1)


# ---------------------------------------------------------------------------
# TUCUMAN_PROVEEDORES
# ---------------------------------------------------------------------------

@register("TUCUMAN_PROVEEDORES")
class TucumanProveedores(PadronProcessor):

    def __init__(self, master_path, padron_path, output_path, progress, **kwargs):
        super().__init__(master_path, padron_path, output_path, progress)
        self.padron2 = kwargs["padron2"]

    def process(self):
        self.progress("Cargando master data proveedores...", 0, 1)
        md, cuit_to_nums = load_num_cuit_pairs(self.master_path, filter_proveedores_cuit)
        md = sorted(set(md))
        self.progress(
            f"Master data: {len(md):,} registros | {len(cuit_to_nums):,} CUITs", 0, 1)

        padron_trim, padron_cuit, state = _load_quarterly(self.padron_path, self.progress)
        _, no_trim_idx = _not_in_quarterly(md, padron_cuit)

        fd_periodo = _get_from(state)
        fh_periodo = _get_to(state)

        registros_cm: list[str] = []
        cm_procesados: list[str] = []

        with open(self.output_path, "w", encoding="latin1") as fo:

            # ---- FASE 1: trimestral ----
            total_t = len(padron_trim)
            self.progress(f"Fase 1: trimestral ({total_t:,} líneas)...", 0, total_t)
            for i, item in enumerate(padron_trim):
                f = _parse_trim(item)
                if len(f) < 7 or not f[0] or not f[0].isdigit():
                    continue
                cuit, tipo_e, cat = f[0], f[1], f[2]
                desde, hasta, porc = f[3], f[4], f[6]
                if cuit not in cuit_to_nums:
                    continue

                fd = f"{desde[6:8]}.{desde[4:6]}.{desde[:4]}"
                fh = _to_from_yyyymmdd(hasta)

                if tipo_e == "E":
                    fo.write(f"{cuit}\t100   \t{fd}\t{fh}\tE trim\t\tI5\n")
                elif cat == "CL":
                    if porc.strip() == "5":
                        fo.write(f"{cuit}\t0\t{fd}\t{fh}\tE trim\t\tI5\n")
                    else:
                        excl = (1.0 - safe_float(porc) / 5.0) * 100.0
                        fo.write(f"{cuit}\t{fmt_right(excl)}\t{fd}\t{fh}\tE trim\t\tI5\n")
                elif cat == "CM":
                    registros_cm.append(item)

                if i % 50_000 == 0 and i:
                    self.progress(f"Fase 1: {i:,}/{total_t:,}", i, total_t)

            # ---- FASE 2: mensual ----
            padron_men = _load_monthly(self.padron2, self.progress)
            cm_cuits = {_parse_trim(l)[0].strip() for l in registros_cm}

            total_m = len(padron_men)
            self.progress(f"Fase 2: mensual ({total_m:,} líneas)...", 0, total_m)

            for i, item3 in enumerate(padron_men):
                f = _parse_men(item3)
                if len(f) < 6 or not f[0] or not f[0].isdigit():
                    continue
                cuit, tipo_e = f[0], f[1]
                alic_men = f[2]
                porc = f[5] if len(f) > 5 else ""

                encontrado = False
                procesado = False

                # Sub-caso A: CM del trimestral
                if cuit in cm_cuits and cuit in cuit_to_nums:
                    if tipo_e == "E":
                        fo.write(f"{cuit}\t100   \t{fd_periodo}\t{fh_periodo}\tE trim\t\tI5\n")
                    else:
                        alq = fmt_right(96.5) if alic_men in ("0.0000", "-.----", "") \
                            else fmt_right((1.0 - safe_float(porc) / 2.0 * safe_float(alic_men) / 5.0) * 100.0)
                        fo.write(f"{cuit}\t{alq}\t{fd_periodo}\t{fh_periodo}\tpadron\t\tI5\n")
                    encontrado = True
                    procesado = True

                # Sub-caso B: no estaban en trimestral
                if not procesado and cuit in no_trim_idx:
                    if tipo_e == "E":
                        fo.write(f"{cuit}\t100   \t{fd_periodo}\t{fh_periodo}\tpadron\t\tI5\n")
                    else:
                        alq = fmt_right(96.5) if alic_men in ("0.0000", "-.----", "") \
                            else fmt_right((1.0 - safe_float(porc) * safe_float(alic_men) / 5.0) * 100.0)
                        fo.write(f"{cuit}\t{alq}\t{fd_periodo}\t{fh_periodo}\tpadron\t\tI5\n")
                    encontrado = True

                if encontrado:
                    cm_procesados.append(cuit)

                if i % 50_000 == 0 and i:
                    self.progress(f"Fase 2: {i:,}/{total_m:,}", i, total_m)

            # ---- FASE 3: CM no encontrados en mensual ----
            cm_procesados_set = set(cm_procesados)
            seen_cuits: set[str] = set()
            self.progress(f"Fase 3: CM sin mensual ({len(registros_cm):,})...", 0, len(registros_cm))

            for item5 in registros_cm:
                f = _parse_trim(item5)
                if len(f) < 7 or not f[0]:
                    continue
                cuit, tipo_e, cat = f[0], f[1], f[2]
                desde, hasta, porc = f[3], f[4], f[6]

                if cuit in cm_procesados_set or cuit not in cuit_to_nums or cuit in seen_cuits:
                    continue
                seen_cuits.add(cuit)

                fd = f"{desde[6:8]}.{desde[4:6]}.{desde[:4]}"
                fh = _to_from_yyyymmdd(hasta)

                if tipo_e == "E":
                    fo.write(f"{cuit}\t100   \t{fd}\t{fh}\tE trim\t\tI5\n")
                elif cat == "CL":
                    if porc.strip() == "5":
                        fo.write(f"{cuit}\t0\t{fd}\t{fh}\tE trim\t\tI5\n")
                    else:
                        excl = (1.0 - safe_float(porc) / 5.0) * 100.0
                        fo.write(f"{cuit}\t{fmt_right(excl)}\t{fd}\t{fh}\tE trim\t\tI5\n")
                elif cat == "CM":
                    excl = 100.0 - safe_float(porc) * 10.0
                    fo.write(f"{cuit}\t{fmt_right(excl)}\t{fd}\t{fh}\tE trim\t\tI5\n")

        self.log.info("Finalizado TUCUMAN_PROVEEDORES")
        self.progress("Finalizado TUCUMAN_PROVEEDORES.", 1, 1)
