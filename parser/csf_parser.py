import re
import pdfplumber

REGIMENES_SAT = {
    "General de Ley Personas Morales": "601",
    "Personas Morales con Fines no Lucrativos": "603",
    "Sueldos y Salarios": "605",
    "Arrendamiento": "606",
    "Demás ingresos": "608",
    "Consolidación": "609",
    "Dividendos": "611",
    "Actividades Empresariales y Profesionales": "612",
    "Ingresos por intereses": "614",
    "Sin obligaciones fiscales": "616",
    "Sociedades Cooperativas de Producción": "620",
    "Incorporación Fiscal": "621",
    "Actividades Agrícolas, Ganaderas, Silvícolas y Pesqueras": "622",
    "Opcional para Grupos de Sociedades": "623",
    "Coordinados": "624",
    "Plataformas Tecnológicas": "625",
    "Simplificado de Confianza": "626"
}


def _limpiar_texto(texto: str) -> str:
    if not texto:
        return ""
    texto = texto.replace("\xa0", " ")
    texto = re.sub(r"[ \t]+", " ", texto)
    texto = re.sub(r"\n+", "\n", texto)
    return texto.strip()


def _extraer_entre(texto: str, etiqueta_inicio: str, siguientes_etiquetas: list[str]) -> str:
    """
    Extrae el texto entre una etiqueta y cualquiera de las etiquetas siguientes.
    Funciona aunque todo esté en una sola línea.
    """
    fin = "|".join(siguientes_etiquetas)
    patron = rf"{etiqueta_inicio}\s*(.*?)(?=\s*(?:{fin})|$)"
    m = re.search(patron, texto, re.IGNORECASE | re.DOTALL)
    if not m:
        return ""
    valor = m.group(1).strip(" :\n\t")
    valor = re.sub(r"\s+", " ", valor).strip()
    return valor


def extraer_datos_csf(ruta_pdf):
    texto_paginas = []

    try:
        with pdfplumber.open(ruta_pdf) as pdf:
            for i in range(min(3, len(pdf.pages))):
                # layout=True suele respetar un poco mejor la estructura
                texto = pdf.pages[i].extract_text(layout=True)
                if texto:
                    texto_paginas.append(texto)

        texto_completo = "\n".join(texto_paginas)
        texto_completo = _limpiar_texto(texto_completo)

        if not texto_completo.strip():
            return {"error": "PDF vacío o es una imagen escaneada."}

        # Versión plana: útil para regex de etiquetas pegadas en una sola línea
        t = re.sub(r"\s+", " ", texto_completo).strip()

        datos = {
            "rfc": "",
            "razon_social": "",
            "curp": "",
            "cp": "",
            "calle": "",
            "num_ext": "",
            "num_int": "",
            "colonia": "",
            "regimen_fiscal": "",
            "error": None
        }

        # =========================
        # 1. RFC
        # =========================
        m_rfc = re.search(r"RFC:\s*([A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3})", t, re.IGNORECASE)
        if not m_rfc:
            m_rfc = re.search(r"\b([A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3})\b", t, re.IGNORECASE)
        if m_rfc:
            datos["rfc"] = m_rfc.group(1).strip().upper()

        # =========================
        # 2. CURP (solo si existe)
        # =========================
        m_curp = re.search(r"CURP:\s*([A-Z0-9]{18})", t, re.IGNORECASE)
        if m_curp:
            datos["curp"] = m_curp.group(1).strip().upper()

        # =========================
        # 3. Razón social / Nombre
        # =========================
        razon = _extraer_entre(
            t,
            r"Denominaci[oó]n\/Raz[oó]n Social:",
            [
                r"R[eé]gimen Capital:",
                r"Nombre Comercial:",
                r"Fecha inicio de operaciones:",
                r"Estatus en el padr[oó]n:"
            ]
        )

        if razon:
            datos["razon_social"] = razon
        else:
            # Plan B: Persona física
            nombre = _extraer_entre(
                t,
                r"Nombre\s*\(s\):",
                [r"Primer Apellido:", r"Segundo Apellido:", r"Fecha inicio", r"Estatus"]
            )
            ap_pat = _extraer_entre(
                t,
                r"Primer Apellido:",
                [r"Segundo Apellido:", r"Fecha inicio", r"Estatus"]
            )
            ap_mat = _extraer_entre(
                t,
                r"Segundo Apellido:",
                [r"Fecha inicio", r"Estatus", r"CURP:"]
            )

            nombre_completo = " ".join(x for x in [nombre, ap_pat, ap_mat] if x).strip()
            datos["razon_social"] = nombre_completo

        # =========================
        # 4. Domicilio
        # =========================
        m_cp = re.search(r"C[oó]digo Postal:\s*(\d{5})", t, re.IGNORECASE)
        if m_cp:
            datos["cp"] = m_cp.group(1).strip()

        datos["calle"] = _extraer_entre(
            t,
            r"Nombre de Vialidad:",
            [
                r"N[uú]mero Exterior:",
                r"Tipo de Vialidad:",
                r"N[uú]mero Interior:",
                r"Nombre de la Colonia:"
            ]
        )

        datos["num_ext"] = _extraer_entre(
            t,
            r"N[uú]mero Exterior:",
            [
                r"N[uú]mero Interior:",
                r"Nombre de la Colonia:",
                r"Nombre de la Localidad:",
                r"Nombre del Municipio"
            ]
        )

        datos["num_int"] = _extraer_entre(
            t,
            r"N[uú]mero Interior:",
            [
                r"Nombre de la Colonia:",
                r"Nombre de la Localidad:",
                r"Nombre del Municipio"
            ]
        )

        datos["colonia"] = _extraer_entre(
            t,
            r"Nombre de la Colonia:",
            [
                r"Nombre de la Localidad:",
                r"Nombre del Municipio",
                r"Nombre de la Entidad Federativa:",
                r"Entre Calle:",
                r"Y Calle:"
            ]
        )

        # Estandarización
        datos["num_ext"] = datos["num_ext"].strip()
        datos["num_int"] = datos["num_int"].strip()

        if datos["num_ext"].upper() in ["", "SN", "S/N", "S. N."]:
            datos["num_ext"] = "SN"

        if datos["num_int"].upper() in ["SN", "S/N", "NONE", "N/A"]:
            datos["num_int"] = ""

        # =========================
        # 5. Régimen fiscal
        # =========================
        # Primero intenta leer la sección de Regímenes
        regimen_encontrado = _extraer_entre(
            t,
            r"Reg[ií]menes:\s*R[eé]gimen Fecha Inicio Fecha Fin",
            [
                r"Obligaciones:",
                r"Sus datos personales",
                r"Cadena Original",
                r"Sello Digital:"
            ]
        )

        if regimen_encontrado:
            for nombre, codigo in REGIMENES_SAT.items():
                if nombre.lower() in regimen_encontrado.lower():
                    datos["regimen_fiscal"] = codigo
                    break

        # Respaldo: búsqueda global
        if not datos["regimen_fiscal"]:
            for nombre, codigo in REGIMENES_SAT.items():
                if nombre.lower() in t.lower():
                    datos["regimen_fiscal"] = codigo
                    break

        return datos

    except Exception as e:
        return {"error": f"Error al procesar: {str(e)}"}
