# app/automation/bot.py
import json
import re
from playwright.sync_api import sync_playwright
from app.database.database import SessionLocal, FacturaGuardada, ProveedorCredencial, decrypt_password


def ejecutar_bot(factura_ids: list[int], log_callback):
    """
    Inicia Playwright y procesa la lista de facturas pendientes.
    log_callback se usa para enviar mensajes de texto a la interfaz gráfica.
    """
    log_callback("Iniciando motor de Playwright...")
    db = SessionLocal()

    try:
        with sync_playwright() as p:
            log_callback("Abriendo navegador Chromium...")
            browser = p.chromium.launch(headless=False, slow_mo=50)
            context = browser.new_context()
            page = context.new_page()

            for f_id in factura_ids:
                # --- ESCUDO ANTIBALAS: Si algo falla aquí adentro, no cierra el navegador ---
                try:
                    factura = db.query(FacturaGuardada).get(f_id)
                    if not factura:
                        continue

                    nombre_prov = (factura.proveedor or "").strip().upper()
                    log_callback(f"Procesando ID {f_id} del proveedor: {nombre_prov}")

                    # --- LOGIN ---
                    page.goto("https://auth.facturador.com/partiallogin")

                    cred = db.query(ProveedorCredencial).filter_by(nombre_proveedor=nombre_prov).first()
                    if not cred or not cred.usuario:
                        log_callback(f"Advertencia: Sin credenciales para {nombre_prov}. Saltando...")
                        page.wait_for_timeout(3000)
                        continue

                    pwd = decrypt_password(cred.password_encriptado)

                    log_callback("Iniciando sesión...")
                    caja_usuario = page.get_by_role("textbox", name="Usuario")
                    caja_usuario.wait_for(state="visible", timeout=15000)
                    caja_usuario.fill(cred.usuario)
                    page.get_by_role("button", name="Siguiente").click()

                    caja_password = page.get_by_role("textbox", name="Contraseña")
                    caja_password.wait_for(state="visible", timeout=10000)
                    caja_password.fill(pwd)
                    page.get_by_role("button", name="Iniciar").click()

                    log_callback("Esperando acceso al portal...")
                    page.wait_for_timeout(5000)

                    # ======================================================
                    # --- AQUÍ COMIENZA EL LLENADO DE LA FACTURA ---
                    # ======================================================

                    # --- PASO 1: NAVEGACIÓN DIRECTA ---
                    log_callback("Navegando directamente a la emisión...")
                    page.goto("https://emision.facturador.com/comprobante/emision40")
                    page.wait_for_timeout(5000)

                    # --- PASO 2: RFC del Cliente ---
                    log_callback("Ingresando RFC del cliente...")
                    rfc_cliente = factura.rfc_cliente or ""

                    caja_rfc = page.get_by_role("textbox", name="Ingresa el RFC de tu cliente")
                    caja_rfc.wait_for(state="visible", timeout=15000)
                    caja_rfc.click(force=True)
                    page.wait_for_timeout(500)

                    caja_rfc.fill(rfc_cliente)
                    caja_rfc.press("Enter")
                    page.wait_for_timeout(3000)

                    # --- PASO 3: Uso de CFDI ---
                    log_callback("Seleccionando Uso de CFDI...")
                    page.get_by_text("Selecciona una opción").nth(1).click()
                    caja_busqueda_cfdi = page.get_by_role("textbox", name="Escribe para buscar...")
                    caja_busqueda_cfdi.click()

                    uso_cfdi_bd = getattr(factura, "uso_cfdi", "G03") or "G03"
                    codigo_uso = uso_cfdi_bd[:3]

                    caja_busqueda_cfdi.type(codigo_uso, delay=100)
                    page.wait_for_timeout(2000)
                    caja_busqueda_cfdi.press("Enter")
                    page.wait_for_timeout(1000)

                    # --- PASO 4: Tipo de Comprobante ---
                    log_callback("Seleccionando Tipo de Comprobante...")
                    page.get_by_text("Selecciona una opción").nth(5).click()
                    page.get_by_role("listitem").filter(has_text="I - Factura").click()
                    page.wait_for_timeout(1500)

                    # --- PASO 5: Moneda y Tipo de Cambio ---
                    es_usd_valor = str(getattr(factura, "es_usd", "")).strip().lower()
                    if es_usd_valor in ["true", "1", "t", "y", "yes"]:
                        log_callback("Cambiando moneda a USD...")
                        page.locator("div").filter(has_text=re.compile(r"^MXN - Peso Mexicano$")).click()
                        page.wait_for_timeout(500)

                        caja_buscar_moneda = page.get_by_role("textbox", name="Escribe para buscar...")
                        caja_buscar_moneda.click()
                        caja_buscar_moneda.type("USD", delay=100)
                        page.wait_for_timeout(2000)
                        caja_buscar_moneda.press("Enter")
                        page.wait_for_timeout(1000)

                        tipo_cambio = getattr(factura, "tipo_cambio", "") or ""
                        if tipo_cambio:
                            log_callback(f"Ingresando tipo de cambio: {tipo_cambio}")
                            caja_tc = page.get_by_role("textbox", name="Ingresa tipo de cambio")
                            caja_tc.click()
                            caja_tc.fill(str(tipo_cambio))
                            page.wait_for_timeout(500)

                    # --- PASO 6: Exportación ---
                    log_callback("Seleccionando Exportación...")
                    caja_vacia_1 = page.locator(
                        ".selectinput.ng-untouched.ng-pristine.ng-invalid > .below > .single > .placeholder").first
                    caja_vacia_1.click()
                    page.get_by_role("listitem").filter(has_text="- No aplica").click()
                    page.wait_for_timeout(1000)

                    # --- PASO 7: Método de Pago ---
                    log_callback("Seleccionando Método de Pago...")
                    metodo_pago = getattr(factura, "metodo_pago", "PUE").upper()
                    caja_vacia_2 = page.locator(
                        ".selectinput.ng-untouched.ng-pristine.ng-invalid > .below > .single > .placeholder").first
                    caja_vacia_2.click()
                    page.wait_for_timeout(500)

                    if "PPD" in metodo_pago:
                        page.get_by_role("listitem").filter(has_text=re.compile("PPD")).first.click()
                    else:
                        page.get_by_role("listitem").filter(has_text=re.compile("PUE")).first.click()

                    page.wait_for_timeout(1500)

                    # --- PASO 8: Forma de Pago (SOLO SI ES PUE) ---
                    if "PUE" in metodo_pago:
                        log_callback("Seleccionando Forma de Pago (PUE detectado)...")
                        forma_pago = getattr(factura, "forma_pago", "03") or "03"
                        codigo_forma = forma_pago[:2]

                        caja_vacia_3 = page.locator(
                            ".selectinput.ng-untouched.ng-pristine.ng-invalid > .below > .single > .placeholder").first
                        caja_vacia_3.click()
                        page.wait_for_timeout(500)

                        caja_buscar_forma = page.get_by_role("textbox", name="Escribe para buscar...")
                        caja_buscar_forma.click()
                        caja_buscar_forma.type(codigo_forma, delay=100)
                        page.wait_for_timeout(2000)
                        caja_buscar_forma.press("Enter")
                        page.wait_for_timeout(1000)
                    else:
                        log_callback("Método PPD detectado. Se omite Forma de Pago.")

                    # --- PASO 9: Información Extra ---
                    notas = getattr(factura, "notas_extra", "") or ""
                    if notas.strip():
                        log_callback("Agregando Información Extra...")
                        # Botón con force=True para ignorar el icono que estorba
                        btn_info = page.locator("text=Información Extra").first
                        btn_info.click(force=True)
                        page.wait_for_timeout(1000)

                        caja_notas = page.get_by_role("textbox", name=re.compile("Te permite un texto libre de",
                                                                                 re.IGNORECASE)).first
                        caja_notas.wait_for(state="visible", timeout=5000)
                        caja_notas.fill(notas)
                        page.wait_for_timeout(500)

                    # ======================================================
                    # --- PASO 10: INYECCIÓN DE CONCEPTOS ---
                    # ======================================================
                    log_callback("Iniciando sección de Conceptos...")

                    json_crudo = getattr(factura, "conceptos_json", "[]")
                    if not json_crudo: json_crudo = "[]"
                    conceptos = json.loads(json_crudo)

                    for i, concepto in enumerate(conceptos):
                        log_callback(f"Inyectando concepto {i + 1} de {len(conceptos)}...")

                        # --- 1. ¿Es Producto o Servicio? ---
                        tipo_ps = concepto.get("tipo_ps", "P")
                        texto_ps = "." if tipo_ps == "P" else ".."

                        caja_ps = page.get_by_role("textbox", name=re.compile("Clave")).first
                        caja_ps.click(force=True)
                        caja_ps.press("Control+A")
                        caja_ps.press("Backspace")
                        caja_ps.type(texto_ps, delay=150)
                        page.wait_for_timeout(2000)
                        caja_ps.press("Enter")
                        page.wait_for_timeout(1000)

                        # --- 2. Clave de Producto / Servicio ---
                        clave_sat = str(concepto.get("clave_prod_serv", ""))
                        caja_clave_sat = page.get_by_role("textbox", name="Busca en el catálogo del SAT").first
                        caja_clave_sat.click(force=True)
                        caja_clave_sat.press("Control+A")
                        caja_clave_sat.press("Backspace")
                        caja_clave_sat.type(clave_sat, delay=150)
                        page.wait_for_timeout(2500)
                        caja_clave_sat.press("Enter")
                        page.wait_for_timeout(1000)

                        # --- 3. Cantidad ---
                        cantidad = str(concepto.get("cantidad", "1"))
                        caja_cant = page.get_by_role("textbox", name="N° de productos o servicios")
                        caja_cant.click()
                        caja_cant.press("Control+A")
                        caja_cant.press("Backspace")
                        caja_cant.fill(cantidad)
                        page.wait_for_timeout(500)

                        # --- 4. Unidad de Medida (FRANCOTIRADOR) ---
                        clave_unidad = str(concepto.get("clave_unidad", ""))

                        # Usamos ^ para indicarle que el texto DEBE empezar con "Unidad de medida"
                        # y agarramos el primero (.first) para evitar la tabla de abajo.
                        caja_unidad = page.locator("div").filter(
                            has_text=re.compile(r"^Unidad de medida", re.IGNORECASE)).locator(".selectinput").first

                        caja_unidad.click(force=True)
                        page.wait_for_timeout(500)

                        caja_buscar_unid = page.get_by_role("textbox", name="Escribe para buscar...")
                        caja_buscar_unid.click()
                        caja_buscar_unid.type(clave_unidad, delay=150)

                        page.wait_for_timeout(2500)
                        caja_buscar_unid.press("Enter")
                        page.wait_for_timeout(1000)

                        # --- 5. Descripción ---
                        descripcion = str(concepto.get("descripcion", ""))
                        caja_desc = page.get_by_role("textbox", name="Describe tu producto o")
                        caja_desc.click()
                        caja_desc.fill(descripcion)
                        page.wait_for_timeout(500)

                        # --- 6. Precio Unitario ---
                        precio = str(concepto.get("precio_unitario", ""))
                        caja_precio = page.get_by_role("textbox", name="Ingresa el valor unitario")
                        caja_precio.click()
                        caja_precio.press("Control+A")
                        caja_precio.press("Backspace")
                        caja_precio.fill(precio)
                        page.wait_for_timeout(500)

                        # --- 7. Agregar Concepto ---
                        log_callback("Guardando concepto...")
                        btn_agregar = page.get_by_role("button", name="Agregar Concepto", exact=True)
                        btn_agregar.click()

                        # Espera inteligente antes de iniciar la inyección del siguiente concepto
                        page.wait_for_timeout(3000)

                    # ======================================================
                    # TERMINA EL CICLO DE CONCEPTOS
                    # ======================================================
                    log_callback("¡Todos los conceptos fueron inyectados!")
                    page.pause()  # Pausa final para que revises

                except Exception as ex_interna:
                    log_callback(f"Error procesando la factura {f_id}: {str(ex_interna)}")
                    log_callback("El bot se pausará para revisar el error.")
                    page.pause()

            browser.close()
            log_callback("Lote completado. Navegador cerrado.")

    except Exception as e:
        log_callback(f"Error crítico en el motor: {str(e)}")
    finally:
        db.close()
