from __future__ import annotations

import openpyxl
from pathlib import Path
from typing import List

from app.models import Factura as UIFactura, Cliente, DatosFactura, Concepto
from parser.legacy_excel_parser import ExcelFacturaParser, load_catalogs

_CATALOGS_LOADED = False


def _ensure_catalogs_loaded():
    global _CATALOGS_LOADED
    if not _CATALOGS_LOADED:
        load_catalogs()
        _CATALOGS_LOADED = True


def _split_origen(origen: str):
    origen = (origen or "").strip()
    if "::" in origen:
        a, h = origen.split("::", 1)
        return a.strip(), h.strip()
    return origen, ""


def parse_excel_files(paths: List[str]) -> List[UIFactura]:
    _ensure_catalogs_loaded()
    parser = ExcelFacturaParser()
    out: List[UIFactura] = []

    for p in (paths or []):
        ruta = Path(str(p))

        if ruta.name.startswith("~$"):
            continue

        # --- ESCÁNER PROFUNDO CON OPENPYXL (A PRUEBA DE BALAS) ---
        totales_por_hoja = {}
        try:
            # data_only=True asegura que leamos los valores reales y no las fórmulas
            wb = openpyxl.load_workbook(ruta, data_only=True)
            for sheet_name in wb.sheetnames:
                ws = wb[sheet_name]
                total_encontrado = None

                # Convertimos las filas a una lista para poder leerlas de abajo hacia arriba
                rows = list(ws.iter_rows(values_only=True))

                for row in reversed(rows):
                    # Filtramos las celdas que están completamente vacías
                    row_vals = [val for val in row if val is not None and str(val).strip() != ""]
                    if not row_vals:
                        continue

                    # Convertimos la fila a un solo texto en mayúsculas
                    row_str = " ".join(str(v).upper() for v in row_vals)

                    # Si es un subtotal, lo ignoramos y seguimos buscando hacia arriba
                    if any(bad in row_str for bad in ["SUBTOTAL", "SUB TOTAL", "SUB-TOTAL", "LETRA"]):
                        continue

                    # Si encontramos la palabra TOTAL, extraemos el último número de esa fila
                    if "TOTAL" in row_str:
                        nums = []
                        for val in row_vals:
                            try:
                                clean_val = str(val).replace("$", "").replace(",", "").strip()
                                nums.append(float(clean_val))
                            except ValueError:
                                pass

                        if nums:
                            total_encontrado = nums[-1]
                            break

                if total_encontrado is not None:
                    totales_por_hoja[sheet_name] = total_encontrado
            wb.close()
        except Exception as e:
            print(f"Error escaneando totales en {ruta.name}: {e}")
        # --------------------------------------------------------

        legacy_facturas = parser.parse_file(ruta)

        for lf in legacy_facturas:
            origen_str = getattr(lf.archivo, "name", ruta.name) if lf.archivo else ruta.name
            archivo_origen, hoja_origen = _split_origen(origen_str)

            cliente = Cliente(
                rfc=(lf.rfc or None),
                proveedor=(lf.proveedor or None),
            )

            datos = DatosFactura(
                uso_cfdi=(lf.uso_cfdi or None),
                metodo_pago=(lf.metodo_pago or None),
                forma_pago=(lf.forma_pago or None),
                es_usd=bool(getattr(lf, "es_usd", False)),
                tipo_cambio="",
                info_extra="",
            )

            conceptos_ui: List[Concepto] = []
            for c in (lf.conceptos or []):
                cantidad = float(c.cantidad or 0.0) if c.cantidad is not None else 0.0
                precio_unit = float(c.precio_unitario or 0.0) if c.precio_unitario is not None else 0.0
                importe = float(c.importe) if c.importe is not None else None

                conceptos_ui.append(
                    Concepto(
                        cantidad=cantidad,
                        clave_unidad=str(c.clave_unidad or ""),
                        clave_prod_serv=str(c.clave_prod_serv or ""),
                        concepto=str(c.descripcion or ""),
                        precio_unitario=precio_unit,
                        importe=importe,
                    )
                )

            # ASIGNAR EL TOTAL ENCONTRADO POR EL ESCÁNER
            total_inteligente = None
            if hoja_origen and hoja_origen in totales_por_hoja:
                total_inteligente = totales_por_hoja[hoja_origen]
            elif totales_por_hoja:
                # Si por alguna razón el nombre de la hoja no coincide, toma el valor más alto encontrado
                total_inteligente = max(totales_por_hoja.values())

            if total_inteligente is not None and total_inteligente > 0:
                total_val = float(total_inteligente)
            else:
                total_val = float(lf.total or 0.0) if lf.total is not None else 0.0

            factura_id = f"{archivo_origen}::{hoja_origen}" if hoja_origen else archivo_origen

            out.append(
                UIFactura(
                    id=factura_id,
                    cliente=cliente,
                    datos_factura=datos,
                    conceptos=conceptos_ui,
                    total=total_val,
                    archivo_origen=archivo_origen,
                    hoja_origen=hoja_origen,
                )
            )

    return out
