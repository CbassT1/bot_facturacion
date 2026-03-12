# app/ui/frames/hacer_pagos.py
import tkinter as tk
from tkinter import ttk, messagebox
import re
import threading
from app.database.database import SessionLocal, PagoGuardado, ProveedorCredencial
from app.automation.bot_pagos import ejecutar_bot_pagos
from app.ui.theme import get_pal


class HacerPagosFrame(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.filas_pagos = []
        self.proveedores_db = self._obtener_proveedores()
        self.placeholder_text = "Pega aqui tus datos desde Excel o correo (Fecha, Cliente, Folio, Monto)..."
        self._build_ui()

    def _obtener_proveedores(self):
        db = SessionLocal()
        try:
            provs = db.query(ProveedorCredencial.nombre_proveedor).all()
            lista = [p[0] for p in provs]
            return lista if lista else ["REKLAMSA", "XISISA", "VIESA", "MARTO"]
        finally:
            db.close()

    def _build_ui(self):
        pal = get_pal(self.controller)

        # --- HEADER ---
        header = ttk.Frame(self)
        header.pack(fill="x", padx=20, pady=20)

        ttk.Button(header, text="Volver al Menu", command=lambda: self.controller.show("menu")).pack(side="left")
        ttk.Label(header, text="Complementos de Pago (REP)", font=("Segoe UI", 16, "bold")).pack(side="left", padx=20)

        self.btn_theme = ttk.Button(header, text=self.controller.theme_button_label(), command=self._toggle_theme)
        self.btn_theme.pack(side="right")

        # --- PEGADO MAGICO ---
        pegado_frame = ttk.LabelFrame(self, text="Pegado Inteligente", padding=10)
        pegado_frame.pack(fill="x", padx=20, pady=5)

        self.txt_pegado = tk.Text(pegado_frame, height=4, width=80, font=("Segoe UI", 10), bg=pal["BG"], fg=pal["TEXT"])
        self.txt_pegado.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self._set_placeholder()
        self.txt_pegado.bind("<FocusIn>", self._clear_placeholder)
        self.txt_pegado.bind("<FocusOut>", self._add_placeholder)

        ttk.Button(pegado_frame, text="Extraer Datos", command=self._interpretar_texto, style="Primary.TButton").pack(
            side="right", ipady=10)

        # --- CONTENEDOR DE FILAS (SCROLLABLE) ---
        filas_container = ttk.LabelFrame(self, text="Pagos Listos para Procesar", padding=10)
        filas_container.pack(fill="both", expand=True, padx=20, pady=10)

        self.canvas = tk.Canvas(filas_container, bg=pal["SURFACE"], highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(filas_container, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)

        self.scrollable_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        # --- LOGICA DEL SCROLL CON EL RATON ---
        def _on_mousewheel(event):
            # Para Windows y Mac
            if event.delta:
                self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def _on_mousewheel_linux_up(event):
            self.canvas.yview_scroll(-1, "units")

        def _on_mousewheel_linux_down(event):
            self.canvas.yview_scroll(1, "units")

        def _bind_mousewheel(event):
            self.canvas.bind_all("<MouseWheel>", _on_mousewheel)
            self.canvas.bind_all("<Button-4>", _on_mousewheel_linux_up)
            self.canvas.bind_all("<Button-5>", _on_mousewheel_linux_down)

        def _unbind_mousewheel(event):
            self.canvas.unbind_all("<MouseWheel>")
            self.canvas.unbind_all("<Button-4>")
            self.canvas.unbind_all("<Button-5>")

        # Activar el scroll solo cuando el raton este sobre el canvas o el frame interior
        self.canvas.bind("<Enter>", _bind_mousewheel)
        self.canvas.bind("<Leave>", _unbind_mousewheel)
        self.scrollable_frame.bind("<Enter>", _bind_mousewheel)
        self.scrollable_frame.bind("<Leave>", _unbind_mousewheel)

        # --- FOOTER ---
        footer = ttk.Frame(self)
        footer.pack(fill="x", padx=20, pady=10)
        ttk.Button(footer, text="Agregar Fila Vacia", command=lambda: self._agregar_fila()).pack(side="left")
        ttk.Button(footer, text="Guardar y Ejecutar Bot", style="Primary.TButton", command=self._ejecutar_bot).pack(
            side="right", ipady=5, ipadx=10)

        self._agregar_fila()

    # ==========================================
    # MANEJO DEL TEMA Y PLACEHOLDER
    # ==========================================
    def _toggle_theme(self):
        self.controller.toggle_theme()

    def on_theme_changed(self):
        for widget in self.winfo_children():
            widget.destroy()
        self.filas_pagos.clear()
        self._build_ui()

    def _set_placeholder(self):
        pal = get_pal(self.controller)
        self.txt_pegado.insert("1.0", self.placeholder_text)
        self.txt_pegado.config(fg=pal["MUTED"])

    def _clear_placeholder(self, event=None):
        if self.txt_pegado.get("1.0", "end-1c") == self.placeholder_text:
            self.txt_pegado.delete("1.0", "end")
            pal = get_pal(self.controller)
            self.txt_pegado.config(fg=pal["TEXT"])

    def _add_placeholder(self, event=None):
        if not self.txt_pegado.get("1.0", "end-1c").strip():
            self._set_placeholder()

    # ==========================================
    # EL INTERPRETE MAGICO
    # ==========================================
    def _interpretar_texto(self):
        texto = self.txt_pegado.get("1.0", tk.END).strip()

        if not texto or texto == self.placeholder_text:
            return

        lineas = [l.strip() for l in texto.split('\n') if l.strip()]

        try:
            if any('\t' in l for l in lineas):
                for l in lineas:
                    if "Fecha" in l or "Folio" in l: continue
                    partes = l.split('\t')
                    if len(partes) >= 5:
                        self._inyectar_fila(partes[0], partes[2], partes[3], partes[4])

            else:
                start_idx = 0
                for i, l in enumerate(lineas):
                    if re.match(r"\d{2}/\d{2}/\d{2,4}", l):
                        start_idx = i
                        break

                datos = lineas[start_idx:]
                for i in range(0, len(datos), 5):
                    chunk = datos[i:i + 5]
                    if len(chunk) >= 5:
                        self._inyectar_fila(chunk[0], chunk[2], chunk[3], chunk[4])

            self.txt_pegado.delete("1.0", tk.END)
            self._add_placeholder()

        except Exception as e:
            messagebox.showerror("Error de lectura", f"No pude entender el formato. \nDetalle: {str(e)}")

    def _inyectar_fila(self, fecha, proveedor, folio, monto):
        if re.match(r"\d{2}/\d{2}/\d{2}$", fecha.strip()):
            p = fecha.split('/')
            fecha = f"{p[0]}/{p[1]}/20{p[2]}"

        monto_limpio = monto.replace('$', '').replace(',', '').strip()

        self._agregar_fila({
            "fecha": fecha.strip(),
            "proveedor": proveedor.strip().upper(),
            "folio": folio.strip(),
            "monto": monto_limpio
        })

    # ==========================================
    # CONSTRUCTOR DE FILAS DE LA UI
    # ==========================================
    def _agregar_fila(self, datos=None):
        if datos is None:
            prov_default = self.proveedores_db[0] if self.proveedores_db else ""
            datos = {"proveedor": prov_default, "folio": "", "fecha": "", "monto": ""}

        fila = ttk.Frame(self.scrollable_frame)
        fila.pack(fill="x", pady=5)

        var_prov = tk.StringVar(value=datos.get("proveedor"))
        var_folio = tk.StringVar(value=datos.get("folio"))
        var_fecha = tk.StringVar(value=datos.get("fecha"))
        var_monto = tk.StringVar(value=datos.get("monto"))
        var_hora = tk.StringVar(value="12:00:00")
        var_forma = tk.StringVar(value="03 - Transferencia")

        ttk.Combobox(fila, textvariable=var_prov, values=self.proveedores_db, width=15).pack(side="left", padx=(0, 5))
        ttk.Label(fila, text="Folio:").pack(side="left")
        ttk.Entry(fila, textvariable=var_folio, width=8).pack(side="left", padx=5)
        ttk.Label(fila, text="Monto: $").pack(side="left")
        ttk.Entry(fila, textvariable=var_monto, width=10).pack(side="left", padx=5)
        ttk.Label(fila, text="Fecha:").pack(side="left")
        ttk.Entry(fila, textvariable=var_fecha, width=10).pack(side="left", padx=5)
        ttk.Label(fila, text="Hora:").pack(side="left")
        ttk.Entry(fila, textvariable=var_hora, width=8).pack(side="left", padx=5)
        ttk.Combobox(fila, textvariable=var_forma, values=["03 - Transferencia", "02 - Cheque"], width=18).pack(
            side="left", padx=5)

        btn_eliminar = ttk.Button(fila, text="X", width=3, command=lambda: fila.destroy())
        btn_eliminar.pack(side="left", padx=10)

        self.filas_pagos.append({
            "frame": fila, "prov": var_prov, "folio": var_folio,
            "monto": var_monto, "fecha": var_fecha, "hora": var_hora, "forma": var_forma
        })

    # ==========================================
    # EJECUTOR DEL BOT
    # ==========================================
    def _ejecutar_bot(self):
        db = SessionLocal()
        ids_pagos = []

        try:
            for f_data in self.filas_pagos:
                if not f_data["frame"].winfo_exists():
                    continue

                p_val = f_data["prov"].get().strip()
                folio_val = f_data["folio"].get().strip()
                monto_val = f_data["monto"].get().strip()
                fecha_val = f_data["fecha"].get().strip()

                if not folio_val or not monto_val:
                    continue

                nuevo_pago = PagoGuardado(
                    proveedor=p_val,
                    folio_factura_origen=folio_val,
                    fecha_pago=fecha_val,
                    hora_pago=f_data["hora"].get().strip(),
                    forma_pago=f_data["forma"].get().strip(),
                    monto=monto_val,
                    estado="Pendiente"
                )
                db.add(nuevo_pago)
                db.flush()
                ids_pagos.append(nuevo_pago.id)

            db.commit()
        finally:
            db.close()

        if not ids_pagos:
            messagebox.showwarning("Atencion", "No hay pagos validos para procesar.")
            return

        from app.ui.dialogs import LogDialog
        log_dialog = LogDialog(self, "Procesando Pagos en el Navegador...")
        threading.Thread(target=ejecutar_bot_pagos, args=(ids_pagos, log_dialog.add_log), daemon=True).start()
