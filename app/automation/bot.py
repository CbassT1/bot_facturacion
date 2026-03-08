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

            # --- VARIABLES GLOBALES DEL NAVEGADOR ---
            context = None
            page = None
            proveedor_actual = None  # Rastreador de sesión activa

            for f_id in factura_ids:
                # --- ESCUDO ANTIBALAS ---
                try:
                    factura = db.query(FacturaGuardada).get(f_id)
                    if not factura:
                        continue

                    nombre_prov = (factura.proveedor or "").strip().upper()
                    log_callback(f"Procesando ID {f_id} del proveedor: {nombre_prov}")

                    # ======================================================
                    # CONTROL DE SESIÓN SÚPER INTELIGENTE
                    # ======================================================
                    if nombre_prov != proveedor_actual:
                        log_callback(f"Iniciando sesión limpia para: {nombre_prov}")

                        # Si ya había una sesión de otro proveedor, la destruimos
                        if context:
                            context.close()

                        # Creamos una sesión "incógnito" nueva
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

                        proveedor_actual = nombre_prov  # Actualizamos nuestra memoria
                    else:
                        log_callback(f"Aprovechando sesión activa de {nombre_prov}. Saltando login...")

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
                    page.wait_for_timeout(4000)  # Esperamos a que el sistema procese el RFC

                    # --- PASO 2.5: LUGAR DE EXPEDICIÓN (Xisisa, Viesa, Reklamsa, Marto) ---
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
                        else:  # MARTO
                            texto_suc = "- MONTERREY"

                        page.get_by_role("listitem").filter(has_text=texto_suc).click()
                        page.wait_for_timeout(1000)

                    # --- PASO 3: Uso de CFDI ---
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

                    # --- PASO 3.5: ESCUDO PARA ALTA DE CLIENTES ---
                    log_callback("Verificando registro del cliente...")
                    caja_razon = page.get_by_role("textbox", name=re.compile(r"Ingresa la Razón Social", re.IGNORECASE))
                    razon_social = caja_razon.input_value().strip()

                    if not razon_social:
                        log_callback("⚠️ ALERTA: Cliente NO registrado.")
                        log_callback("Inyectando botón de pausa en el navegador...")

                        page.evaluate("""
                            window.botContinuar = false;
                            let btn = document.createElement('button');
                            btn.innerHTML = '▶ TERMINÉ EL ALTA - CONTINUAR BOT';
                            btn.style.cssText = 'position:fixed; top:20px; left:50%; transform:translateX(-50%); z-index:99999; padding:20px 40px; font-size:22px; font-weight:bold; background-color:#E53935; color:white; border:none; border-radius:8px; cursor:pointer; box-shadow: 0px 4px 6px rgba(0,0,0,0.3);';
                            btn.onclick = function() {
                                window.botContinuar = true;
                                this.innerHTML = 'Continuando...';
                                this.style.backgroundColor = '#43A047';
                            };
                            document.body.appendChild(btn);
                        """)

                        page.wait_for_function("window.botContinuar === true", timeout=0)
                        log_callback("Bot reanudado. Continuando con la factura...")
                        page.wait_for_timeout(3000)

                    # --- PASO 4: Tipo de Comprobante ---
                    log_callback("Seleccionando Tipo de Comprobante...")
                    caja_comprobante = page.locator("div").filter(
                        has_text=re.compile(r"^Tipo de Comprobante", re.IGNORECASE)).locator(".selectinput").first
                    caja_comprobante.click(force=True)
                    page.wait_for_timeout(500)
                    page.get_by_role("listitem").filter(has_text="I - Factura").click()
                    page.wait_for_timeout(1500)

                    # --- PASO 4.5: SERIE (Solo Reklamsa) ---
                    if "REKLAMSA" in nombre_prov:
                        log_callback("Configurando Serie para REKLAMSA...")
                        caja_serie = page.locator("div").filter(has_text=re.compile(r"^Serie", re.IGNORECASE)).locator(
                            ".selectinput").first
                        caja_serie.click(force=True)
                        page.wait_for_timeout(500)
                        page.get_by_role("listitem").filter(has_text="Sin Serie").click()
                        page.wait_for_timeout(1000)

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

                        # --- EL ANTÍDOTO CONTRA EL ROBO DE FOCO ---
                        log_callback("Esperando a que Angular asigne el foco automático...")
                        page.wait_for_timeout(3500)  # Dejamos que el SAT mueva el foco a Cantidad si quiere

                        # --- 2. Clave de Producto / Servicio ---
                        clave_sat = str(concepto.get("clave_prod_serv", ""))
                        caja_clave_sat = page.get_by_role("textbox", name="Busca en el catálogo del SAT").first

                        # Le robamos el foco de vuelta explícitamente
                        caja_clave_sat.click(force=True)
                        caja_clave_sat.focus()
                        page.wait_for_timeout(500)

                        caja_clave_sat.press("Control+A")
                        caja_clave_sat.press("Backspace")
                        caja_clave_sat.type(clave_sat, delay=150)
                        page.wait_for_timeout(3500)
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

                        page.wait_for_timeout(3000)

                    # ======================================================
                    # TERMINA EL CICLO DE CONCEPTOS
                    # ======================================================
                    log_callback("¡Todos los conceptos inyectados! Verificando totales...")
                    page.wait_for_timeout(3000)  # Dar tiempo a que Angular sume todo

                    # --- VERIFICACIÓN DE TOTALES ---
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
                        log_callback("Intentando forzar recálculo de impuestos (Truco del engranaje)...")

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
                            log_callback("Bot pausado. Revisa la factura a mano, ajusta y dale a 'Resume'.")
                            if page:
                                page.pause()
                            total_web = obtener_total_web()

                    # ======================================================
                    # --- GENERAR Y ENVIAR (CONDICIONAL) ---
                    # ======================================================
                    debe_emitir = getattr(factura, "emitir_y_enviar", False)

                    if debe_emitir:
                        log_callback("✅ Totales cuadrados. Emitiendo factura...")
                        page.get_by_role("button", name="Generar").click(force=True)

                        log_callback("Esperando la firma del SAT y cambio de página (Esto puede tardar)...")
                        page.wait_for_url(re.compile(r"/comprobante/detalle/"), timeout=45000)
                        page.wait_for_timeout(3000)

                        log_callback("Extrayendo Folio Interno...")
                        try:
                            # Extraemos todo el texto visible de la pantalla
                            texto_pantalla = page.locator("body").inner_text()
                            # Buscamos la palabra Folio, ignoramos saltos de línea/espacios, y atrapamos los números siguientes
                            match = re.search(r'Folio\s*[:\n]*\s*(\d+)', texto_pantalla, re.IGNORECASE)
                            if match:
                                folio_atrapado = match.group(1)
                                factura.folio_fiscal = folio_atrapado
                                log_callback(f"¡Folio {folio_atrapado} capturado con éxito!")
                            else:
                                log_callback("No se encontró el Folio en la pantalla.")
                        except Exception as e:
                            log_callback(f"Error extrayendo folio: {e}")

                        log_callback("¡Factura timbrada! Abriendo menú de envío...")
                        btn_enviar_menu = page.get_by_role("button", name="Enviar por correo Enviar por")
                        btn_enviar_menu.wait_for(state="visible", timeout=10000)
                        btn_enviar_menu.click(force=True)
                        page.wait_for_timeout(1500)

                        log_callback("Confirmando envío del correo...")
                        btn_confirmar_correo = page.get_by_role("button", name="Enviar Correo")
                        btn_confirmar_correo.click(force=True)

                        log_callback("✅ Correo enviado con éxito.")
                        page.wait_for_timeout(3000)

                        factura.estado = "Emitida"
                        db.commit()
                        log_callback(f"🎉 Factura {f_id} completada y marcada como Emitida.")

                    else:
                        log_callback("⏸️ Casilla 'Emitir' apagada. La factura se quedó en borrador.")
                        log_callback("El bot te esperará. Emite manualmente o presiona el botón azul para seguir.")
                        factura.estado = "Completada (Borrador)"
                        db.commit()

                        try:
                            # Inyectamos el botón azul flotante con un ID inicial
                            page.evaluate("""
                                let btn = document.createElement('button');
                                btn.id = 'btn-espera-bot';
                                btn.innerHTML = '▶ CONTINUAR BOT (SIGUIENTE FACTURA)';
                                btn.style.cssText = 'position:fixed; top:20px; left:50%; transform:translateX(-50%); z-index:99999; padding:20px 40px; font-size:22px; font-weight:bold; background-color:#1976D2; color:white; border:none; border-radius:8px; cursor:pointer; box-shadow: 0px 4px 6px rgba(0,0,0,0.3);';
                                btn.onclick = function() {
                                    this.id = 'btn-continuar-bot'; // Al darle clic, le cambiamos el ID
                                    this.innerHTML = 'Continuando...';
                                    this.style.backgroundColor = '#43A047';
                                };
                                document.body.appendChild(btn);
                            """)

                            # Playwright se quedará congelado aquí buscando el nuevo ID por tiempo infinito
                            page.wait_for_selector("#btn-continuar-bot", state="attached", timeout=0)
                            log_callback("Botón presionado. Avanzando a la siguiente...")

                        except Exception as e_espera:
                            log_callback(f"Pausa terminada (Emisión manual o interrupción). Avanzando...")

                        page.wait_for_timeout(1000)

                except Exception as ex_interna:
                    log_callback(f"Error procesando la factura {f_id}: {str(ex_interna)}")
                    log_callback("El bot se pausará para revisar el error.")
                    if page:
                        page.pause()

            # ======================================================
            # FIN DEL CICLO FOR
            # ======================================================

            log_callback("=======================================")
            log_callback("Lote completado. El navegador permanecerá abierto.")
            log_callback("Ciérralo tú mismo (con la X) cuando hayas terminado todo.")

            try:
                # Playwright se queda esperando infinitamente a que cierres la ventana
                if page:
                    page.wait_for_event("close", timeout=0)
            except Exception:
                pass

            if context:
                context.close()
            browser.close()
            log_callback("Navegador cerrado. Motor apagado.")

    except Exception as e:
        log_callback(f"Error crítico en el motor: {str(e)}")
    finally:
        db.close()
