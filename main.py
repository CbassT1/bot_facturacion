# main.py
from __future__ import annotations

import os
import sys
import traceback
from typing import List, Optional

# --- Base de Datos ---
from app.database.database import init_db

# --- Parsers ---
from parser.excel_parser import parse_excel_files
from parser.pdf_parser import parse_pdf_files

# --- Modelos y App ---
from app.models import Factura, Cliente, DatosFactura
from app.ui.app import App


def _error_factura(filename_only: str, detail: str) -> Factura:
    return Factura(
        id=f"{filename_only}::ERROR",
        cliente=Cliente(proveedor=None, rfc=None),
        datos_factura=DatosFactura(info_extra=f"ERROR: {detail}"),
        conceptos=[],
        total=0.0,
        archivo_origen=filename_only,
        hoja_origen="ERROR",
    )


def parse_files_mixed(paths: List[str], *, use_pdf_ocr: bool = False) -> List[Factura]:
    facturas: List[Factura] = []

    for p in (paths or []):
        p_str = str(p)
        filename_only = p_str.split("\\")[-1].split("/")[-1]

        try:
            if p_str.lower().endswith(".xlsx"):
                facturas.extend(parse_excel_files([p_str]))
            elif p_str.lower().endswith(".pdf"):
                facturas.extend(parse_pdf_files([p_str], use_ocr=use_pdf_ocr))
        except Exception as e:
            detail = "".join(traceback.format_exception_only(type(e), e)).strip()
            facturas.append(_error_factura(filename_only, detail))

    return facturas


if __name__ == "__main__":

    init_db()

    app = App(parse_excel_files=parse_files_mixed)
    app.mainloop()
