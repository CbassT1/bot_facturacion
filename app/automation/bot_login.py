# app/automation/bot_login.py

def ejecutar_login(page, cred, nombre_prov, log_callback, decrypt_password):
    """
    Se encarga exclusivamente de la rutina de inicio de sesión en el portal.
    Retorna True si fue exitoso, lanza Exception si falla.
    """
    log_callback(f"Iniciando sesión en el portal para: {nombre_prov}")

    page.goto("https://auth.facturador.com/partiallogin")

    pwd = decrypt_password(cred.password_encriptado)

    log_callback("Ingresando usuario...")
    caja_usuario = page.get_by_role("textbox", name="Usuario")
    caja_usuario.wait_for(state="visible", timeout=15000)
    caja_usuario.fill(cred.usuario)
    page.get_by_role("button", name="Siguiente").click()

    log_callback("Ingresando contraseña...")
    caja_password = page.get_by_role("textbox", name="Contraseña")
    caja_password.wait_for(state="visible", timeout=10000)
    caja_password.fill(pwd)
    page.get_by_role("button", name="Iniciar").click()

    log_callback("Verificando respuesta del servidor...")

    # ==============================================================
    # ESCUDO PROTECTOR DE CREDENCIALES
    # ==============================================================
    try:
        # LÓGICA: Si el login es correcto, Angular destruye u oculta la caja de
        # contraseña para cargar el panel principal. Le damos 10 segundos.
        caja_password.wait_for(state="hidden", timeout=10000)

        log_callback("¡Acceso concedido! Preparando entorno...")
        page.wait_for_timeout(3000)
        return True

    except Exception:
        # Si pasaron 10 segundos y la caja de contraseña sigue en pantalla, el login falló.
        log_callback("⚠️ El portal rechazó el acceso. Identificando el motivo...")

        mensaje_falla = "Credenciales incorrectas o el servidor de autenticación no responde."

        try:
            # Buscamos la clásica alerta roja (Toast) de Angular para leer qué salió mal
            alerta = page.locator(".toast-message, .alert, [role='alert']").first
            if alerta.is_visible(timeout=2000):
                texto_alerta = alerta.inner_text().strip()
                if texto_alerta:
                    mensaje_falla = f"El portal dice: '{texto_alerta}'"
        except Exception:
            pass

        # Detonamos la excepción. El archivo bot.py la atrapará, marcará la factura
        # como "Error", imprimirá este mensaje en la tabla y saltará a la siguiente empresa.
        raise Exception(f"Fallo de Login -> {mensaje_falla}")
