# app/automation/bot_pagos.py
import json
import re
from playwright.sync_api import sync_playwright
# NOTA: Asegúrate de tener un modelo PagoGuardado en tu database.py
from app.database.database import SessionLocal, ProveedorCredencial, decrypt_password, PagoGuardado


def ejecutar_bot_pagos(pago_ids: list[int], log_callback):
    log_callback("Iniciando motor de Complementos de Pago (REP)...")
    db = SessionLocal()

    try:
        with sync_playwright() as p:
            log_callback("Abriendo navegador Chromium...")
            browser = p.chromium.launch(headless=False, slow_mo=50)

            context = None
            page = None
            proveedor_actual = None

            for p_id in pago_ids:
                try:
                    pago = db.query(PagoGuardado).get(p_id)
                    if not pago:
                        continue

                    nombre_prov = (pago.proveedor or "").strip().upper()
                    log_callback(f"Procesando Pago ID {p_id} del proveedor: {nombre_prov}")

                    # ======================================================
                    # 1. CONTROL DE SESIÓN (Reutilizado del bot de facturas)
                    # ======================================================
                    if nombre_prov != proveedor_actual:
                        log_callback(f"Iniciando sesión limpia para: {nombre_prov}")
                        if context: context.close()
                        context = browser.new_context()
                        page = context.new_page()

                        page.goto("https://auth.facturador.com/partiallogin")

                        cred = db.query(ProveedorCredencial).filter_by(nombre_proveedor=nombre_prov).first()
                        if not cred or not cred.usuario:
                            log_callback(f"⚠️ Sin credenciales para {nombre_prov}. Saltando...")
                            continue

                        pwd = decrypt_password(cred.password_encriptado)

                        log_callback("Iniciando sesión...")
                        page.get_by_role("textbox", name="Usuario").fill(cred.usuario)
                        page.get_by_role("button", name="Siguiente").click()
                        page.get_by_role("textbox", name="Contraseña").wait_for(state="visible", timeout=10000)
                        page.get_by_role("textbox", name="Contraseña").fill(pwd)
                        page.get_by_role("button", name="Iniciar").click()

                        page.wait_for_timeout(5000)
                        proveedor_actual = nombre_prov
                    else:
                        log_callback(f"Aprovechando sesión activa de {nombre_prov}...")

                    # ======================================================
                    # 2. BÚSQUEDA DE LA FACTURA PADRE
                    # ======================================================
                    log_callback("Navegando a la sección de búsqueda...")
                    page.goto("https://emision.facturador.com/comprobante/busqueda")
                    page.wait_for_timeout(4000)

                    log_callback("Configurando calendario a 2017...")
                    page.get_by_role("button", name="ui-btn").first.click(timeout=8000)
                    page.wait_for_timeout(1000)
                    page.get_by_role("combobox").nth(1).select_option("2017")
                    page.wait_for_timeout(500)
                    page.keyboard.press("Escape")
                    page.wait_for_timeout(1000)

                    folio_buscar = str(pago.folio_factura_origen).strip()
                    log_callback(f"Buscando factura origen (Folio: {folio_buscar})...")

                    caja_busqueda = page.get_by_role("textbox", name="Busca por folio")
                    caja_busqueda.click()
                    caja_busqueda.fill(folio_buscar)
                    page.wait_for_timeout(500)
                    page.get_by_role("button", name="Buscar").click()

                    # Esperamos a que cargue la tabla
                    page.get_by_role("cell").filter(has_text=re.compile(r"Ver Detalle", re.IGNORECASE)).first.wait_for(
                        state="visible", timeout=15000)
                    page.wait_for_timeout(1500)

                    # ======================================================
                    # 3. ABRIR MODAL DE PAGOS
                    # ======================================================
                    log_callback("Abriendo el Administrador de Pagos...")
                    celda_acciones = page.get_by_role("cell").filter(
                        has_text=re.compile(r"Ver Detalle", re.IGNORECASE)).first
                    btn_opciones = celda_acciones.locator(".btn").first
                    btn_opciones.click(force=True)
                    page.wait_for_timeout(1000)

                    page.get_by_text("Administrar Pagos").click(force=True)
                    page.wait_for_timeout(3000)

                    log_callback("Iniciando Nuevo Pago...")
                    page.get_by_role("button", name="Nuevo Pago").click(force=True)
                    page.wait_for_timeout(2000)

                    # ======================================================
                    # 4. LLENADO DEL COMPLEMENTO DE PAGO
                    # ======================================================
                    if any(p in nombre_prov for p in ["XISISA", "VIESA", "REKLAMSA", "MARTO"]):
                        log_callback(f"Configurando lugar de expedición para {nombre_prov}...")
                        page.locator("app-info-pago").get_by_text("Selecciona una opción").click(force=True)
                        page.wait_for_timeout(500)

                        if "XISISA" in nombre_prov:
                            texto_suc = "- Matriz" if getattr(pago, "sucursal",
                                                              "MONTERREY").upper() == "MONTERREY" else "- Guadalajara"
                        elif "VIESA" in nombre_prov:
                            texto_suc = "- MONTERREY" if getattr(pago, "sucursal",
                                                                 "MONTERREY").upper() == "MONTERREY" else "- GUADALAJARA"
                        elif "REKLAMSA" in nombre_prov:
                            texto_suc = "64940 - Monterrey"
                        else:
                            texto_suc = "- MONTERREY"

                        page.get_by_role("listitem").filter(has_text=texto_suc).click(force=True)
                        page.wait_for_timeout(1000)

                    # --- FECHA ---
                    # TRUCO: En lugar de usar el calendario, Angular suele permitir forzar el texto directamente.
                    log_callback("Ingresando Fecha y Hora del depósito...")
                    fecha_pago = getattr(pago, "fecha_pago", "12/03/2026")  # Formato esperado: DD/MM/YYYY
                    caja_fecha = page.locator("#fecha").locator("input").first
                    if caja_fecha.is_visible():
                        caja_fecha.click(force=True)
                        caja_fecha.fill(fecha_pago)
                        caja_fecha.press("Enter")
                    else:
                        page.locator("#fecha").click(force=True)
                        page.keyboard.type(fecha_pago, delay=100)
                        page.keyboard.press("Enter")
                    page.wait_for_timeout(1000)

                    # --- HORA ---
                    # TRUCO: Escribimos la hora directo en la caja de texto en lugar de dar clics infinitos en las flechitas.
                    hora_pago = getattr(pago, "hora_pago", "12:00:00")
                    caja_hora = page.get_by_role("textbox", name="HH:mm:ss")
                    caja_hora.click(force=True)
                    caja_hora.press("Control+A")
                    caja_hora.press("Backspace")
                    caja_hora.type(hora_pago, delay=100)
                    page.keyboard.press("Escape")  # Cerramos el cuadrito de las flechas
                    page.wait_for_timeout(1000)

                    # --- FORMA DE PAGO ---
                    log_callback("Seleccionando Forma de Pago...")
                    forma_pago_bd = getattr(pago, "forma_pago", "03").upper()  # "03" o "TRANSFERENCIA"

                    caja_forma_pago = page.locator("app-complemento-pago div").filter(
                        has_text=re.compile(r"^Forma de Pago", re.IGNORECASE)).locator(".selectinput").first
                    caja_forma_pago.click(force=True)
                    page.wait_for_timeout(1000)

                    if "03" in forma_pago_bd or "TRANS" in forma_pago_bd:
                        page.get_by_role("listitem").filter(
                            has_text=re.compile(r"03 - Transferencia", re.IGNORECASE)).click(force=True)
                        es_transferencia = True
                    elif "02" in forma_pago_bd or "CHEQ" in forma_pago_bd:
                        page.get_by_role("listitem").filter(has_text=re.compile(r"02 - Cheque", re.IGNORECASE)).click(
                            force=True)
                        es_transferencia = False
                    else:
                        page.get_by_role("listitem").first.click()  # Por defecto
                        es_transferencia = False
                    page.wait_for_timeout(1500)

                    # --- MONTO ---
                    log_callback("Ingresando Monto...")
                    monto = str(getattr(pago, "monto", "0.00"))
                    caja_monto = page.get_by_role("textbox", name="Ingresa el monto a pagar")
                    caja_monto.click(force=True)
                    caja_monto.press("Control+A")
                    caja_monto.press("Backspace")
                    caja_monto.fill(monto)
                    page.wait_for_timeout(1000)

                    # --- CADENA DE PAGO (Solo si es Transferencia) ---
                    if es_transferencia:
                        log_callback("Configurando cadena de pago (SPEI)...")
                        caja_cadena = page.locator("div").filter(
                            has_text=re.compile(r"^Tipo cadena de pago", re.IGNORECASE)).locator(".selectinput").first
                        if caja_cadena.is_visible():
                            caja_cadena.click(force=True)
                            page.wait_for_timeout(1000)
                            page.get_by_role("listitem").filter(has_text="- SPEI").click(force=True)
                            page.wait_for_timeout(1000)

                    # ======================================================
                    # 5. GENERAR Y ENVIAR POR CORREO
                    # ======================================================
                    log_callback("Emitiendo Complemento de Pago...")
                    page.get_by_role("button", name="Generar").click(force=True)

                    # Esperamos a que el portal procese el pago y regrese a la tabla
                    log_callback("Esperando a que se timbre el recibo...")
                    page.wait_for_timeout(8000)

                    debe_enviar = getattr(pago, "enviar_correo", True)
                    if debe_enviar:
                        log_callback("Enviando recibo por correo...")
                        # Buscamos la tuerca del pago recién hecho (normalmente es el primero de la lista de pagos)
                        btn_tuerca_pago = page.locator(
                            ".btn.btn-default.btn-sm.dropdown-toggle.noborder.ng-star-inserted").first
                        btn_tuerca_pago.click(force=True)
                        page.wait_for_timeout(1000)

                        # nth(1) según tu instrucción para "Enviar por correo" de los pagos
                        page.get_by_text("Enviar por correo").nth(1).click(force=True)
                        page.wait_for_timeout(2000)  # Esperamos el modal de correo

                        page.get_by_role("button", name="Enviar Correo").click(force=True)
                        page.wait_for_timeout(3000)
                        log_callback("✅ Correo enviado.")

                    # Cerramos la ventana de Administrar Pagos para dejar la pantalla limpia para el siguiente
                    page.keyboard.press("Escape")
                    page.wait_for_timeout(1000)
                    page.keyboard.press("Escape")

                    pago.estado = "Emitido"
                    db.commit()
                    log_callback(f"🎉 Complemento de Pago {p_id} completado con éxito.")

                except Exception as ex_interna:
                    log_callback(f"❌ Error procesando Pago {p_id}: {str(ex_interna)}")
                    pago.estado = "Error"
                    pago.mensaje_error = str(ex_interna)
                    db.commit()

                    log_callback("🛑 MODO DETECTIVE: Abriendo Inspector para revisar el error del pago.")
                    if page: page.pause()

            log_callback("=======================================")
            log_callback("Lote de pagos finalizado. Cerrando en 4 segundos...")
            if page: page.wait_for_timeout(4000)
            if context: context.close()
            browser.close()

    except Exception as e:
        log_callback(f"❌ Error crítico general en Pagos: {str(e)}")
        if 'page' in locals() and page: page.pause()
    finally:
        db.close()