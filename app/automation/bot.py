# app/automation/bot.py
import re
from playwright.sync_api import sync_playwright
from app.database.database import SessionLocal, FacturaGuardada, ProveedorCredencial, decrypt_password

# Importamos nuestros "módulos especialistas"
from app.automation.bot_login import ejecutar_login
from app.automation.bot_clonador import rutina_clonar_factura
from app.automation.bot_emision import rutina_emitir_factura


def ejecutar_bot(factura_ids: list[int], log_callback):
    """
    Orquestador principal del Bot.
    Delega el trabajo duro a módulos especializados dependiendo del tipo de factura.
    """
    log_callback("Iniciando motor orquestador de Playwright...")
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
                    log_callback(f"--------------------------------------------------")
                    log_callback(f"Procesando ID {f_id} del proveedor: {nombre_prov}")

                    # ======================================================
                    # CONTROL DE SESIÓN (Delega a bot_login.py)
                    # ======================================================
                    if nombre_prov != proveedor_actual:
                        if context:
                            context.close()

                        context = browser.new_context()
                        page = context.new_page()

                        cred = db.query(ProveedorCredencial).filter_by(nombre_proveedor=nombre_prov).first()
                        if not cred or not cred.usuario:
                            log_callback(f"⚠️ Advertencia: Sin credenciales para {nombre_prov}. Saltando...")
                            continue

                        # Llama al Especialista de Login (lanza excepción si el SAT falla)
                        ejecutar_login(page, cred, nombre_prov, log_callback, decrypt_password)
                        proveedor_actual = nombre_prov
                    else:
                        log_callback(f"Aprovechando sesión activa de {nombre_prov}. Saltando login...")

                    # ======================================================
                    # CONTROL DE TRÁFICO: ¿Factura Normal o Clonación?
                    # ======================================================
                    notas = getattr(factura, "notas_extra", "") or ""
                    match_clon = re.search(r"\[CLONAR_WEB:\s*([^\]]+)\]", notas)

                    if match_clon:
                        folio_target = match_clon.group(1).strip()
                        log_callback(f"MODO CLONACIÓN DETECTADO. Buscando Folio/RFC: {folio_target}")

                        # Llama al Especialista Clonador
                        rutina_clonar_factura(page, factura, folio_target, log_callback, db)
                    else:
                        # Llama al Especialista de Emisión Normal
                        rutina_emitir_factura(page, factura, nombre_prov, log_callback, db)

                except Exception as ex_interna:
                    log_callback(f"❌ Error procesando factura {f_id}: {str(ex_interna)}")
                    factura.estado = "Error"
                    factura.mensaje_error = str(ex_interna)
                    db.commit()
                    log_callback("El bot falló. Abriendo Inspector de Playwright. ¡Revisa la ventana!")
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
        if 'page' in locals() and page: page.pause()
    finally:
        db.close()
