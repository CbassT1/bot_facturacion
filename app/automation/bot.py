# app/automation/bot.py
import json
import re
from playwright.sync_api import sync_playwright
from app.database.database import SessionLocal, FacturaGuardada, ProveedorCredencial, decrypt_password


def ejecutar_bot(factura_ids: list[int], log_callback):
    log_callback("Iniciando motor de Playwright...")
    db = SessionLocal()

    try:
        with sync_playwright() as p:
            log_callback("Abriendo navegador Chromium...")
            browser = p.chromium.launch(headless=False, slow_mo=50)

            context = None
            page = None
            proveedor_actual = None

            for f_id in factura_ids:
                try:
                    factura = db.query(FacturaGuardada).get(f_id)
                    if not factura:
                        continue

                    nombre_prov = (factura.proveedor or "").strip().upper()
                    log_callback(f"Procesando ID {f_id} del proveedor: {nombre_prov}")

                    # ======================================================
                    # CONTROL DE SESIÓN INTELIGENTE
                    # ======================================================
                    if nombre_prov != proveedor_actual:
                        log_callback(f"Iniciando sesión limpia para: {nombre_prov}")

                        if context:
                            context.close()

                        context = browser.new_context()
                        page = context.new_page()

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

                        proveedor_actual = nombre_prov
                    else:
                        log_callback(f"Aprovechando sesión activa de {nombre_prov}. Saltando login...")

                    # ======================================================
                    # DESVÍO DE VÍAS: ¿ES NORMAL O ES CLONACIÓN?
                    # ======================================================
                    notas = getattr(factura, "notas_extra", "") or ""
                    match_clon = re.search(r"\[CLONAR_WEB:\s*([^\]]+)\]", notas)

                    if match_clon:
                        folio_target = match_clon.group(1).strip()
                        log_callback(f"🔀 MODO CLONACIÓN DETECTADO. Buscando Folio/RFC: {folio_target}")

                        _rutina_clonar_factura(page, factura, folio_target, log_callback, db)
                        continue  # Salta todo el código de "Factura Nueva" y pasa a la siguiente

                    # ======================================================
                    # --- AQUÍ COMIENZA EL LLENADO DE LA FACTURA NORMAL ---
                    # ======================================================
                    log_callback("Navegando directamente a la emisión...")
                    page.goto("https://emision.facturador.com/comprobante/emision40")
                    page.wait_for_timeout(5000)

                    log_callback("Ingresando RFC del cliente...")
                    rfc_cliente = factura.rfc_cliente or ""

                    caja_rfc = page.get_by_role("textbox", name="Ingresa el RFC de tu cliente")
                    caja_rfc.wait_for(state="visible", timeout=15000)
                    caja_rfc.click(force=True)
                    page.wait_for_timeout(500)

                    caja_rfc.fill(rfc_cliente)
                    caja_rfc.press("Enter")
                    page.wait_for_timeout(4000)

                    if any(p in nombre_prov for p in ["XISISA", "VIESA", "REKLAMSA", "MARTO"]):
                        log_callback(f"Configurando lugar de expedición para {nombre_prov}...")
                        caja_lugar = page.locator("div").filter(
                            has_text=re.compile(r"^Lugar de Expedición", re.IGNORECASE)).locator(".selectinput").first
                        caja_lugar.click(force=True)
                        page.wait_for_timeout(500)

                        if "XISISA" in nombre_prov:
                            sucursal_bd = getattr(factura, "sucursal", "MONTERREY") or "MONTERREY"
                            texto_suc = "- Matriz" if sucursal_bd.upper() == "MONTERREY" else "- Guadalajara"
                        elif "VIESA" in nombre_prov:
                            sucursal_bd = getattr(factura, "sucursal", "MONTERREY") or "MONTERREY"
                            texto_suc = "- MONTERREY" if sucursal_bd.upper() == "MONTERREY" else "- GUADALAJARA"
                        elif "REKLAMSA" in nombre_prov:
                            texto_suc = "64940 - Monterrey"
                        else:
                            texto_suc = "- MONTERREY"

                        page.get_by_role("listitem").filter(has_text=texto_suc).click()
                        page.wait_for_timeout(1000)

                    log_callback("Seleccionando Uso de CFDI...")
                    caja_uso_cfdi = page.locator("div").filter(
                        has_text=re.compile(r"^Uso de CFDI", re.IGNORECASE)).locator(".selectinput").first
                    caja_uso_cfdi.click(force=True)
                    page.wait_for_timeout(500)

                    caja_busqueda_cfdi = page.get_by_role("textbox", name="Escribe para buscar...")
                    caja_busqueda_cfdi.click()

                    uso_cfdi_bd = getattr(factura, "uso_cfdi", "G03") or "G03"
                    caja_busqueda_cfdi.type(uso_cfdi_bd[:3], delay=100)
                    page.wait_for_timeout(2000)
                    caja_busqueda_cfdi.press("Enter")
                    page.wait_for_timeout(1000)

                    # --- PASO 3.5: ESCUDO DE AUTO-ALTA DE CLIENTES ---
                    log_callback("Verificando registro del cliente...")
                    caja_razon = page.get_by_role("textbox", name=re.compile(r"Ingresa la Razón Social", re.IGNORECASE))
                    razon_social = caja_razon.input_value().strip()

                    if not razon_social:
                        log_callback("⚠️ ALERTA: Cliente NO registrado. Abriendo asistente de Alta...")

                        datos_alta = None
                        import threading
                        evento_modal = threading.Event()

                        def abrir_modal_alta():
                            nonlocal datos_alta
                            from app.ui.frames.alta_cliente_modal import AltaClienteModal
                            import tkinter as tk

                            root = tk._default_root
                            modal = AltaClienteModal(root, rfc_buscado=rfc_cliente)
                            root.wait_window(modal)
                            datos_alta = modal.datos_finales
                            evento_modal.set()

                        import tkinter as tk
                        tk._default_root.after(0, abrir_modal_alta)

                        log_callback("Esperando a que completes el formulario en pantalla...")
                        evento_modal.wait()

                        if not datos_alta:
                            raise Exception("Se canceló el alta de cliente. Bot abortado.")

                        log_callback("Iniciando inyección de Nuevo Cliente en el portal...")

                        page.get_by_role("button", name="Nuevo Receptor").click()
                        page.wait_for_timeout(1500)

                        page.locator("#rfc").click()
                        page.locator("#rfc").fill(datos_alta["rfc"])

                        page.locator("#clienteForm").get_by_role("textbox", name="Ingresa la Razón Social de tu").fill(
                            datos_alta["razon"])

                        if datos_alta["curp"]:
                            page.get_by_role("textbox", name=re.compile("CURP", re.I)).fill(datos_alta["curp"])

                        page.locator(
                            ".panel-body > form > .formRow > div > .inputWrapper > .selectinput > .below > .single > .placeholder").click()
                        page.keyboard.type(datos_alta["regimen"], delay=100)
                        page.wait_for_timeout(500)
                        page.keyboard.press("Enter")
                        page.locator("#collapseRegimenesFiscales").get_by_role("button",
                                                                               name=re.compile("Agregar", re.I)).click()
                        page.wait_for_timeout(500)

                        page.get_by_role("button", name="Agregar dirección").click()
                        page.wait_for_timeout(1000)

                        page.locator(".selectinput.selectClear.w-100 > .below > .single > .placeholder").first.click()
                        page.get_by_role("textbox", name="Escribe para buscar...").fill("MEX")
                        page.wait_for_timeout(500)
                        page.keyboard.press("Enter")

                        page.get_by_role("textbox", name="Código Postal").fill(datos_alta["cp"])
                        page.wait_for_timeout(1500)

                        if datos_alta["colonia"]:
                            log_callback(f"Intentando seleccionar colonia: {datos_alta['colonia']}...")
                            try:
                                page.locator(
                                    "div:nth-child(3) > div:nth-child(3) > .inputWrapper > .selectinput > .below > .single > .placeholder").click(
                                    timeout=5000)
                                page.wait_for_timeout(1000)

                                caja_busqueda = page.get_by_role("textbox", name="Escribe para buscar...")

                                if caja_busqueda.is_visible():
                                    caja_busqueda.fill(datos_alta["colonia"])
                                    page.wait_for_timeout(1500)
                                    caja_busqueda.press("Enter")
                                else:
                                    page.get_by_role("option",
                                                     name=re.compile(datos_alta["colonia"], re.IGNORECASE)).first.click(
                                        timeout=3000)

                                page.wait_for_timeout(500)

                            except Exception as e:
                                log_callback(f"⚠️ Colonia no encontrada. Ignorando...")
                                page.wait_for_timeout(500)

                        # --- CALLE Y NÚMEROS ---
                        page.get_by_role("textbox", name="Calle o Avenida del cliente").click(force=True)
                        page.get_by_role("textbox", name="Calle o Avenida del cliente").fill(datos_alta["calle"])
                        page.get_by_role("textbox", name="Número exterior").fill(datos_alta["num_ext"])

                        if datos_alta["num_int"]:
                            page.get_by_role("textbox", name="Número interior").fill(datos_alta["num_int"])

                        # --- CORREO ELECTRÓNICO ---
                        caja_correo = page.get_by_role("textbox",
                                                       name=re.compile("Correo electrónico", re.IGNORECASE)).first
                        caja_correo.scroll_into_view_if_needed()
                        caja_correo.click(force=True)
                        caja_correo.fill(datos_alta["correo"])
                        page.wait_for_timeout(500)
                        caja_correo.press("Enter")
                        page.wait_for_timeout(1000)

                        # --- GUARDAR DIRECCIÓN ---
                        log_callback("Guardando dirección...")
                        page.locator("#agregarNueva").get_by_role("button", name="Guardar").click(force=True)
                        page.wait_for_timeout(1500)

                        # --- GUARDADO FINAL DEL CLIENTE ---
                        log_callback("Guardando cliente en el portal...")
                        btn_guardar_cliente = page.locator("app-admin-clientes").get_by_role("button", name=re.compile(
                            r"^Guardar$", re.IGNORECASE)).first
                        btn_guardar_cliente.click(force=True)

                        # Damos tiempo a que guarde y regrese a la pantalla de Clientes
                        page.wait_for_timeout(2500)

                        log_callback("Cerrando la ventana del directorio de Clientes...")
                        try:
                            # 1. Intentamos hacer clic en la "X" (Close) del modal gigante
                            btn_x_modal = page.locator("modal-container button.close, button[aria-label='Close']").last
                            if btn_x_modal.is_visible(timeout=3000):
                                btn_x_modal.click(force=True)
                                log_callback("Ventana cerrada con el botón 'X'.")
                        except Exception:
                            log_callback("⚠️ No se vio el botón 'X', intentando forzar cierre...")
                            pass

                        # 2. PLAN DE RESPALDO: Presionamos "Escape" un par de veces para matar cualquier ventana flotante
                        page.keyboard.press("Escape")
                        page.wait_for_timeout(500)
                        page.keyboard.press("Escape")

                        # 3. Esperamos a que la pantalla quede limpia
                        try:
                            page.locator("modal-container").last.wait_for(state="hidden", timeout=4000)
                        except Exception:
                            log_callback("⚠️ El modal principal parece seguir ahí. Cruzando los dedos...")

                        page.wait_for_timeout(1500)

                        # --- RETOMAR LA FACTURA ---
                        log_callback("¡Cliente registrado! Retomando la factura...")

                        caja_rfc_principal = page.get_by_role("textbox", name="Ingresa el RFC de tu cliente").first
                        caja_rfc_principal.click(force=True)
                        caja_rfc_principal.press("Control+A")
                        caja_rfc_principal.press("Backspace")
                        caja_rfc_principal.fill(datos_alta["rfc"])
                        caja_rfc_principal.press("Enter")

                        log_callback("Esperando a que el sistema valide el nuevo RFC...")
                        page.wait_for_timeout(5000)

                        log_callback("Seleccionando Uso de CFDI renovado...")
                        caja_uso_cfdi_renovada = page.locator("div").filter(
                            has_text=re.compile(r"^Uso de CFDI", re.IGNORECASE)).locator(".selectinput").first
                        caja_uso_cfdi_renovada.click(force=True)
                        page.wait_for_timeout(1000)

                        caja_busqueda_renovada = page.get_by_role("textbox", name="Escribe para buscar...").last
                        caja_busqueda_renovada.click(force=True)
                        caja_busqueda_renovada.type(uso_cfdi_bd[:3], delay=100)
                        page.wait_for_timeout(1500)
                        caja_busqueda_renovada.press("Enter")
                        page.wait_for_timeout(1000)
                        
                    log_callback("Seleccionando Tipo de Comprobante...")
                    caja_comprobante = page.locator("div").filter(
                        has_text=re.compile(r"^Tipo de Comprobante", re.IGNORECASE)).locator(".selectinput").first
                    caja_comprobante.click(force=True)
                    page.wait_for_timeout(500)
                    page.get_by_role("listitem").filter(has_text="I - Factura").click()
                    page.wait_for_timeout(1500)

                    if "REKLAMSA" in nombre_prov:
                        log_callback("Configurando Serie para REKLAMSA...")
                        caja_serie = page.locator("div").filter(has_text=re.compile(r"^Serie", re.IGNORECASE)).locator(
                            ".selectinput").first
                        caja_serie.click(force=True)
                        page.wait_for_timeout(500)
                        page.get_by_role("listitem").filter(has_text="Sin Serie").click()
                        page.wait_for_timeout(1000)

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

                    log_callback("Seleccionando Exportación...")
                    caja_vacia_1 = page.locator(
                        ".selectinput.ng-untouched.ng-pristine.ng-invalid > .below > .single > .placeholder").first
                    caja_vacia_1.click()
                    page.get_by_role("listitem").filter(has_text="- No aplica").click()
                    page.wait_for_timeout(1000)

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

                    notas = getattr(factura, "notas_extra", "") or ""
                    if notas.strip():
                        log_callback("Agregando Información Extra...")
                        btn_info = page.locator("text=Información Extra").first
                        btn_info.click(force=True)
                        page.wait_for_timeout(1000)

                        caja_notas = page.get_by_role("textbox", name=re.compile("Te permite un texto libre de",
                                                                                 re.IGNORECASE)).first
                        caja_notas.wait_for(state="visible", timeout=5000)
                        caja_notas.fill(notas)
                        page.wait_for_timeout(500)

                    log_callback("Iniciando sección de Conceptos...")
                    json_crudo = getattr(factura, "conceptos_json", "[]")
                    if not json_crudo: json_crudo = "[]"
                    conceptos = json.loads(json_crudo)

                    for i, concepto in enumerate(conceptos):
                        log_callback(f"Inyectando concepto {i + 1} de {len(conceptos)}...")

                        tipo_ps = concepto.get("tipo_ps", "P")
                        texto_ps = "." if tipo_ps == "P" else ".."

                        caja_ps = page.get_by_role("textbox", name=re.compile("Clave")).first
                        caja_ps.click(force=True)
                        caja_ps.press("Control+A")
                        caja_ps.press("Backspace")
                        caja_ps.type(texto_ps, delay=150)
                        page.wait_for_timeout(2000)
                        caja_ps.press("Enter")

                        log_callback("Esperando a que Angular asigne el foco automático...")
                        page.wait_for_timeout(3500)

                        clave_sat = str(concepto.get("clave_prod_serv", ""))
                        caja_clave_sat = page.get_by_role("textbox", name="Busca en el catálogo del SAT").first

                        caja_clave_sat.click(force=True)
                        caja_clave_sat.focus()
                        page.wait_for_timeout(500)

                        caja_clave_sat.press("Control+A")
                        caja_clave_sat.press("Backspace")
                        caja_clave_sat.type(clave_sat, delay=150)
                        page.wait_for_timeout(3500)
                        caja_clave_sat.press("Enter")
                        page.wait_for_timeout(1000)

                        cantidad = str(concepto.get("cantidad", "1"))
                        caja_cant = page.get_by_role("textbox", name="N° de productos o servicios")
                        caja_cant.click()
                        caja_cant.press("Control+A")
                        caja_cant.press("Backspace")
                        caja_cant.fill(cantidad)
                        page.wait_for_timeout(500)

                        clave_unidad = str(concepto.get("clave_unidad", ""))
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

                        descripcion = str(concepto.get("descripcion", ""))
                        caja_desc = page.get_by_role("textbox", name="Describe tu producto o")
                        caja_desc.click()
                        caja_desc.fill(descripcion)
                        page.wait_for_timeout(500)

                        precio = str(concepto.get("precio_unitario", ""))
                        caja_precio = page.get_by_role("textbox", name="Ingresa el valor unitario")
                        caja_precio.click()
                        caja_precio.press("Control+A")
                        caja_precio.press("Backspace")
                        caja_precio.fill(precio)
                        page.wait_for_timeout(500)

                        log_callback("Guardando concepto...")
                        btn_agregar = page.get_by_role("button", name="Agregar Concepto", exact=True)
                        btn_agregar.click()
                        page.wait_for_timeout(3000)

                    log_callback("¡Todos los conceptos inyectados! Verificando totales...")
                    page.wait_for_timeout(3000)

                    def obtener_total_web():
                        try:
                            fila_total = page.locator("tr").filter(
                                has=page.get_by_role("cell", name="Total", exact=True)).first
                            texto_total = fila_total.locator("td").last.inner_text()
                            texto_limpio = re.sub(r"[^\d.]", "", texto_total)
                            return float(texto_limpio)
                        except Exception:
                            return 0.0

                    total_web = obtener_total_web()
                    total_db = float(getattr(factura, "total", 0.0) or 0.0)
                    margen_error = 1.0

                    if abs(total_web - total_db) > margen_error:
                        log_callback(f"⚠️ Discrepancia detectada. Web: ${total_web} vs BD: ${total_db}")
                        log_callback("Intentando forzar recálculo de impuestos...")
                        try:
                            page.locator(".btn").first.click(force=True)
                            page.wait_for_timeout(1000)
                            page.get_by_text("Editar").click(force=True)
                            page.wait_for_timeout(2500)
                            page.get_by_role("button", name="Guardar Concepto").click(force=True)
                            page.wait_for_timeout(4000)
                            total_web = obtener_total_web()
                        except Exception as e:
                            log_callback(f"No se pudo hacer el recálculo automático: {e}")

                        if abs(total_web - total_db) > margen_error:
                            log_callback(f"❌ El total sigue sin cuadrar (Web: ${total_web} vs BD: ${total_db}).")
                            log_callback("Bot pausado automáticamente. Corrige a mano y presiona 'Resume'.")
                            if page: page.pause()
                            total_web = obtener_total_web()

                    debe_emitir = getattr(factura, "emitir_y_enviar", False)

                    if debe_emitir:
                        log_callback("✅ Totales cuadrados. Emitiendo factura...")
                        page.get_by_role("button", name="Generar").click(force=True)

                        log_callback("Esperando la firma del SAT y cambio de página...")
                        page.wait_for_url(re.compile(r"/comprobante/detalle/"), timeout=45000)
                        page.wait_for_timeout(3000)

                        try:
                            texto_pantalla = page.locator("body").inner_text()
                            match = re.search(r'Folio\s*[:\n]*\s*(\d+)', texto_pantalla, re.IGNORECASE)
                            if match:
                                folio_atrapado = match.group(1)
                                factura.folio_fiscal = folio_atrapado
                                log_callback(f"¡Folio {folio_atrapado} capturado con éxito!")
                        except Exception as e:
                            log_callback(f"Error extrayendo folio: {e}")

                        log_callback("¡Factura timbrada! Abriendo menú de envío...")
                        btn_enviar_menu = page.get_by_role("button", name="Enviar por correo Enviar por")
                        btn_enviar_menu.wait_for(state="visible", timeout=10000)
                        btn_enviar_menu.click(force=True)
                        page.wait_for_timeout(1500)

                        log_callback("Confirmando envío...")
                        btn_confirmar_correo = page.get_by_role("button", name="Enviar Correo")
                        btn_confirmar_correo.click(force=True)

                        log_callback("✅ Correo enviado con éxito.")
                        page.wait_for_timeout(3000)

                        factura.estado = "Emitida"
                        db.commit()
                        log_callback(f"🎉 Factura {f_id} completada.")

                    else:
                        log_callback("⏸️ Casilla 'Emitir' apagada. La factura se quedó en borrador.")
                        log_callback("Presiona el botón azul en la web para avanzar a la siguiente.")
                        factura.estado = "Completada (Borrador)"
                        db.commit()

                        try:
                            page.evaluate("""
                                let btn = document.createElement('button');
                                btn.id = 'btn-espera-bot';
                                btn.innerHTML = '▶ CONTINUAR BOT (SIGUIENTE FACTURA)';
                                btn.style.cssText = 'position:fixed; top:20px; left:50%; transform:translateX(-50%); z-index:99999; padding:20px 40px; font-size:22px; font-weight:bold; background-color:#1976D2; color:white; border:none; border-radius:8px; cursor:pointer; box-shadow: 0px 4px 6px rgba(0,0,0,0.3);';
                                btn.onclick = function() {
                                    this.id = 'btn-continuar-bot'; 
                                    this.innerHTML = 'Continuando...';
                                    this.style.backgroundColor = '#43A047';
                                };
                                document.body.appendChild(btn);
                            """)
                            page.wait_for_selector("#btn-continuar-bot", state="attached", timeout=0)
                            log_callback("Avanzando a la siguiente...")
                        except Exception as e_espera:
                            pass
                        page.wait_for_timeout(1000)

                except Exception as ex_interna:
                    log_callback(f"❌ Error procesando factura {f_id}: {str(ex_interna)}")
                    factura.estado = "Error"
                    factura.mensaje_error = str(ex_interna)
                    db.commit()
                    # === MAGIA APLICADA: Modo Detective ===
                    log_callback("🛑 El bot falló. Abriendo Inspector de Playwright. ¡Revisa la ventana!")
                    if page: page.pause()

            # ======================================================
            # FIN DEL PROGRAMA (CIERRE AUTOMÁTICO SEGURO)
            # ======================================================
            log_callback("=======================================")
            log_callback("Lote finalizado. El navegador se cerrará en 4 segundos...")

            if page:
                page.wait_for_timeout(4000)

            if context:
                context.close()
            browser.close()
            log_callback("Navegador cerrado. Interfaz liberada.")

    except Exception as e:
        log_callback(f"❌ Error crítico general: {str(e)}")
        # Para errores catastróficos, también dejamos un pause si la página existe
        if 'page' in locals() and page: page.pause()
    finally:
        db.close()


# =====================================================================
# EL CEREBRO DE CLONACIÓN AUTOMÁTICA (BÚSQUEDA INTELIGENTE)
# =====================================================================
def _rutina_clonar_factura(page, factura, target, log_callback, db):
    try:
        nuevo_total = float(getattr(factura, "total", 0.0) or 0.0)

        json_crudo = getattr(factura, "conceptos_json", "[]")
        conceptos_lista = json.loads(json_crudo) if json_crudo else []
        nuevo_subtotal = float(conceptos_lista[0].get("precio_unitario", 0.0)) if conceptos_lista else 0.0

        # --- PASO 1: NAVEGACIÓN ---
        log_callback("Dejando que el portal cargue tras el login...")
        page.wait_for_timeout(4000)

        log_callback("Haciendo clic en el menú lateral de Emisión...")
        try:
            page.locator("facturador-menu-fijo #mdo-emision").click(timeout=10000)
            page.wait_for_timeout(3000)

            if "busqueda" not in page.url.lower():
                log_callback("Ajustando URL a la pestaña de búsqueda...")
                page.goto("https://emision.facturador.com/comprobante/busqueda")
                page.wait_for_timeout(3000)
        except Exception as e:
            raise Exception(f"No se pudo interactuar con el menú. Detalle: {e}")

        # --- PASO 2: ABRIR CALENDARIO Y CAMBIAR A 2017 ---
        log_callback("Configurando año del calendario a 2017...")
        try:
            page.get_by_role("button", name="ui-btn").first.click(timeout=8000)
            page.wait_for_timeout(1500)
            page.get_by_role("combobox").nth(1).select_option("2017")
            page.wait_for_timeout(1000)
            page.keyboard.press("Escape")
            page.wait_for_timeout(1000)
            log_callback("Calendario configurado exitosamente.")
        except Exception as e:
            log_callback(f"⚠️ Falló el clic en el calendario. Detalle: {e}")

        # --- PASO 3: BÚSQUEDA ---
        target_limpio = target.upper()
        es_rfc = bool(re.fullmatch(r"[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}", target_limpio))

        if es_rfc:
            log_callback(f"Escribiendo RFC en el buscador: {target_limpio}")
            caja_busqueda = page.get_by_role("textbox", name="Busca por RFC de tu cliente")
        else:
            log_callback(f"Escribiendo Folio en el buscador: {target_limpio}")
            caja_busqueda = page.get_by_role("textbox", name="Busca por folio")

        caja_busqueda.click(timeout=8000)
        caja_busqueda.fill(target_limpio)
        page.wait_for_timeout(500)

        log_callback("Dando clic en el botón de Buscar...")
        page.get_by_role("button", name="Buscar").click()
        log_callback("Esperando a que la tabla cargue los resultados...")

        # --- ESPERA SENSORIAL (A prueba de borradores) ---
        try:
            page.get_by_role("cell").filter(has_text=re.compile(r"Ver Detalle", re.IGNORECASE)).first.wait_for(
                state="visible", timeout=15000)
        except Exception:
            raise Exception(f"La tabla se quedó vacía o solo hay borradores para: {target_limpio}")

        page.wait_for_timeout(2000)

        # --- PASO 4: SELECCIONAR LA FACTURA ---
        log_callback("Identificando la celda de opciones de la factura...")

        celda_acciones = page.get_by_role("cell").filter(has_text=re.compile(r"Ver Detalle", re.IGNORECASE)).first

        try:
            celda_acciones.click(force=True)
        except:
            pass
        page.wait_for_timeout(500)

        btn_opciones = celda_acciones.locator(".btn").first

        # --- PASO 5: DUPLICAR ---
        log_callback("Abriendo opciones y haciendo clic en Duplicar...")
        btn_opciones.evaluate("node => node.click()")
        page.wait_for_timeout(1500)

        page.get_by_text("Duplicar").first.click(force=True)
        log_callback("Cargando entorno de nueva factura...")
        page.wait_for_timeout(8000)

        # --- PASO 6: EDITAR CONCEPTO ---
        log_callback("Buscando el botón para editar el concepto...")
        btn_opciones_concepto = page.locator("td .btn").first
        btn_opciones_concepto.wait_for(state="attached", timeout=10000)
        btn_opciones_concepto.evaluate("node => node.click()")
        page.wait_for_timeout(1000)

        log_callback("Haciendo clic en Editar...")
        page.get_by_text("Editar").click(force=True)
        page.wait_for_timeout(2500)

        log_callback("Cambiando el valor unitario...")
        caja_precio = page.get_by_role("textbox", name="Ingresa el valor unitario")
        caja_precio.click()
        caja_precio.press("Control+A")
        caja_precio.press("Backspace")
        caja_precio.fill(str(nuevo_subtotal))
        page.wait_for_timeout(1000)

        log_callback("Guardando el nuevo concepto...")
        page.get_by_role("button", name="Guardar Concepto").click()
        page.wait_for_timeout(4000)

        # --- PASO 7: VERIFICACIÓN DE TOTALES ---
        log_callback("Verificando totales...")

        def obtener_total_web():
            try:
                fila_total = page.locator("tr").filter(has=page.get_by_role("cell", name="Total", exact=True)).first
                texto_total = fila_total.locator("td").last.inner_text()
                texto_limpio = re.sub(r"[^\d.]", "", texto_total)
                return float(texto_limpio)
            except Exception:
                return 0.0

        total_web = obtener_total_web()
        margen_error = 1.0

        if abs(total_web - nuevo_total) > margen_error:
            log_callback(f"⚠️ Discrepancia detectada. Web: ${total_web} vs BD: ${nuevo_total}")
            log_callback("Bot pausado automáticamente. Corrige a mano en la web y presiona 'Resume'.")
            page.pause()
            total_web = obtener_total_web()

        # --- PASO 8: EMITIR Y ENVIAR ---
        debe_emitir = getattr(factura, "emitir_y_enviar", False)

        if debe_emitir:
            log_callback("✅ Totales cuadrados. Emitiendo factura clonada...")
            page.get_by_role("button", name="Generar").click(force=True)

            log_callback("Esperando la firma del SAT y cambio de página...")
            page.wait_for_url(re.compile(r"/comprobante/detalle/"), timeout=45000)
            page.wait_for_timeout(3000)

            try:
                texto_pantalla = page.locator("body").inner_text()
                match = re.search(r'Folio\s*[:\n]*\s*(\d+)', texto_pantalla, re.IGNORECASE)
                if match:
                    folio_atrapado = match.group(1)
                    factura.folio_fiscal = folio_atrapado
                    log_callback(f"¡Folio {folio_atrapado} capturado con éxito!")
            except Exception as e:
                log_callback(f"Error extrayendo folio nuevo: {e}")

            log_callback("¡Factura timbrada! Abriendo menú de envío...")
            btn_enviar_menu = page.get_by_role("button", name="Enviar por correo Enviar por")
            btn_enviar_menu.wait_for(state="visible", timeout=10000)
            btn_enviar_menu.click(force=True)
            page.wait_for_timeout(1500)

            log_callback("Confirmando envío...")
            btn_confirmar_correo = page.get_by_role("button", name="Enviar Correo")
            btn_confirmar_correo.click(force=True)

            log_callback("✅ Correo enviado con éxito.")
            page.wait_for_timeout(3000)

            factura.estado = "Emitida"
            db.commit()
            log_callback("🎉 Clonación y Emisión completada.")

        else:
            log_callback("⏸️ Casilla 'Emitir' apagada. El clon se guardó como borrador.")
            log_callback("El bot te esperará. Emite manualmente o presiona el botón azul para seguir.")
            factura.estado = "Completada (Borrador)"
            db.commit()

            try:
                page.evaluate("""
                        let btn = document.createElement('button');
                        btn.id = 'btn-espera-bot';
                        btn.innerHTML = '▶ CONTINUAR BOT (SIGUIENTE FACTURA)';
                        btn.style.cssText = 'position:fixed; top:20px; left:50%; transform:translateX(-50%); z-index:99999; padding:20px 40px; font-size:22px; font-weight:bold; background-color:#1976D2; color:white; border:none; border-radius:8px; cursor:pointer; box-shadow: 0px 4px 6px rgba(0,0,0,0.3);';
                        btn.onclick = function() {
                            this.id = 'btn-continuar-bot'; 
                            this.innerHTML = 'Continuando...';
                            this.style.backgroundColor = '#43A047';
                        };
                        document.body.appendChild(btn);
                    """)
                page.wait_for_selector("#btn-continuar-bot", state="attached", timeout=0)
                log_callback("Avanzando a la siguiente...")
            except Exception as e_espera:
                pass
            page.wait_for_timeout(1000)

    except Exception as e:
        log_callback(f"❌ Error durante la clonación: {e}")
        factura.estado = "Error en Clonación"
        factura.mensaje_error = str(e)
        db.commit()

        log_callback("MODO DETECTIVE: El navegador se pausó para que revises qué salió mal.")
        page.pause()
