# app/automation/bot.py
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

                caja_busqueda_cfdi.type(codigo_uso, delay=150)
                page.wait_for_timeout(2000)
                # Volvemos al ENTER obligatorio
                caja_busqueda_cfdi.press("Enter")
                page.wait_for_timeout(1000)

                # --- PASO 4: Tipo de Comprobante ---
                log_callback("Seleccionando Tipo de Comprobante...")
                page.get_by_text("Selecciona una opción").nth(5).click()
                page.get_by_role("listitem").filter(has_text="I - Factura").click()
                page.wait_for_timeout(1500)

                # --- PASO 5: Moneda y Tipo de Cambio (Condicional USD) ---
                # Cast a string/bool en caso de que SQLite lo guarde como 1 o "True"
                es_usd = getattr(factura, "es_usd", False)
                if str(es_usd).lower() in ["true", "1"]:
                    log_callback("Cambiando moneda a USD...")

                    # El selector que sacaste para la caja de MXN
                    page.locator("div").filter(has_text=re.compile(r"^MXN - Peso Mexicano$")).click()

                    caja_buscar_moneda = page.get_by_role("textbox", name="Escribe para buscar...")
                    caja_buscar_moneda.click()

                    caja_buscar_moneda.type("USD", delay=150)
                    page.wait_for_timeout(2000)

                    # ENTER para elegir USD
                    caja_buscar_moneda.press("Enter")
                    page.wait_for_timeout(1500)

                    # Tipo de cambio
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
                page.wait_for_timeout(1500)

                # --- PASO 7: Método de Pago ---
                log_callback("Seleccionando Método de Pago...")
                metodo_pago = getattr(factura, "metodo_pago", "PUE").upper()
                caja_vacia_2 = page.locator(
                    ".selectinput.ng-untouched.ng-pristine.ng-invalid > .below > .single > .placeholder").first
                caja_vacia_2.click()

                if "PPD" in metodo_pago:
                    page.get_by_role("listitem").filter(has_text="PPD - Pago en parcialidades o").click()
                else:
                    # Corrección: Ahora usa el listitem con re.compile para encontrar PUE de manera segura
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

                    caja_buscar_forma = page.get_by_role("textbox", name="Escribe para buscar...")
                    caja_buscar_forma.click()

                    caja_buscar_forma.type(codigo_forma, delay=150)
                    page.wait_for_timeout(2000)

                    # ENTER para elegir Forma de Pago
                    caja_buscar_forma.press("Enter")
                    page.wait_for_timeout(1000)
                else:
                    log_callback("Método PPD detectado. Se omite Forma de Pago.")

                # ======================================================
                log_callback("Datos generales listos. Bot pausado para sección de Conceptos...")
                page.pause()

            browser.close()
            log_callback("Lote completado. Navegador cerrado.")

    except Exception as e:
        log_callback(f"Error crítico en el bot: {str(e)}")
    finally:
        db.close()
