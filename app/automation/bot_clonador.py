# app/automation/bot_clonador.py
import json
import re

def rutina_clonar_factura(page, factura, target, log_callback, db):
    """
    Ejecuta el flujo completo para duplicar una factura existente.
    """
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
            log_callback("Totales cuadrados. Emitiendo factura clonada...")
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

            log_callback("Correo enviado con éxito.")
            page.wait_for_timeout(3000)

            factura.estado = "Emitida"
            db.commit()
            log_callback("Clonación y Emisión completada.")

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
