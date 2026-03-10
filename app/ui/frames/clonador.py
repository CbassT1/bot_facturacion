# app/ui/frames/clonador.py
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import re
from pathlib import Path

from app.ui.theme import get_pal
from app.models import Factura, Cliente, DatosFactura, Concepto
from parser.pdf_parser import extract_clone_data
from app.database.database import SessionLocal, ProveedorCredencial


class ClonadorFacturasFrame(ttk.Frame):
    def __init__(self, master, controller):
        super().__init__(master)
        self.controller = controller
        self.ruta_actual = None
        self._is_updating = False
        self._build_ui()
        self._cargar_emisores()

    def _cargar_emisores(self):
        """Carga los emisores que tienen credenciales en la BD para el Combobox."""
        db = SessionLocal()
        try:
            creds = db.query(ProveedorCredencial).all()
            nombres = [c.nombre_proveedor for c in creds]
            if nombres:
                self.cb_emisor['values'] = nombres
        finally:
            db.close()

    def _build_ui(self):
        pal = get_pal(self.controller)

        # --- HEADER ---
        header = ttk.Frame(self)
        header.pack(fill="x", padx=16, pady=(16, 10))

        ttk.Button(header, text="← Volver", command=lambda: self.controller.show("menu")).pack(side="left")
        ttk.Label(header, text="Clonador de Facturas", font=("Segoe UI", 16, "bold")).pack(side="left", padx=(12, 0))
        ttk.Button(header, text=self.controller.theme_button_label(), command=self._toggle_theme).pack(side="right")

        # --- BODY ---
        body = ttk.Frame(self)
        body.pack(fill="both", expand=True, padx=16, pady=10)

        center_container = ttk.Frame(body)
        center_container.place(relx=0.5, rely=0.45, anchor="center")

        ttk.Label(center_container, text="Duplique una factura ingresando su Folio/RFC o cargando el PDF original.",
                  style="Muted.TLabel").pack(pady=(0, 20))

        # --- SECCIÓN ORIGEN DE DATOS ---
        row_file = ttk.Frame(center_container)
        row_file.pack(fill="x", pady=(0, 15))

        self.btn_seleccionar = ttk.Button(row_file, text="📄 Autocompletar desde PDF", command=self._seleccionar_pdf)
        self.btn_seleccionar.pack(side="left")

        self.lbl_archivo = ttk.Label(row_file, text="(Opcional) Cargar PDF", font=("Segoe UI", 10, "italic"))
        self.lbl_archivo.pack(side="left", padx=10)

        # --- PANEL DE DATOS ---
        self.panel_datos = ttk.LabelFrame(center_container, text="Parámetros de Clonación", padding=20)
        self.panel_datos.pack(fill="both", expand=True)

        grid_datos = ttk.Frame(self.panel_datos)
        grid_datos.pack(fill="x")

        # Variables
        self.var_emisor = tk.StringVar()
        self.var_llave = tk.StringVar()
        self.var_subtotal = tk.StringVar(value="0.00")
        self.var_total = tk.StringVar(value="0.00")
        self.var_info_extra = tk.StringVar(value="")
        self.var_emitir = tk.BooleanVar(value=True)  # Checkbox Emitir

        self.var_subtotal.trace_add("write", lambda *args: self._on_subtotal_change())
        self.var_total.trace_add("write", lambda *args: self._on_total_change())

        # Fila 1: Emisor y Llave
        ttk.Label(grid_datos, text="Empresa Emisora:", font=("Segoe UI", 11)).grid(row=0, column=0, pady=10, sticky="e")
        self.cb_emisor = ttk.Combobox(grid_datos, textvariable=self.var_emisor, font=("Segoe UI", 11), state="readonly",
                                      width=25)
        self.cb_emisor.grid(row=0, column=1, pady=10, padx=(5, 15))

        ttk.Label(grid_datos, text="Folio o RFC a duplicar:", font=("Segoe UI", 11)).grid(row=0, column=2, pady=10,
                                                                                          sticky="e")
        self.ent_llave = ttk.Entry(grid_datos, textvariable=self.var_llave, font=("Segoe UI", 11, "bold"), width=18)
        self.ent_llave.grid(row=0, column=3, pady=10, padx=5)

        # Fila 2: Montos (Con enlace al evento FocusOut)
        ttk.Label(grid_datos, text="Nuevo Subtotal: $", font=("Segoe UI", 11)).grid(row=1, column=0, pady=10,
                                                                                    sticky="e")
        self.ent_subtotal = ttk.Entry(grid_datos, textvariable=self.var_subtotal, font=("Segoe UI", 11, "bold"),
                                      width=27)
        self.ent_subtotal.grid(row=1, column=1, pady=10, padx=(5, 15))
        self.ent_subtotal.bind("<FocusOut>", self._format_subtotal_on_leave)

        ttk.Label(grid_datos, text="Total (IVA inc): $", font=("Segoe UI", 11)).grid(row=1, column=2, pady=10,
                                                                                     sticky="e")
        self.ent_total = ttk.Entry(grid_datos, textvariable=self.var_total, font=("Segoe UI", 11, "bold"), width=18)
        self.ent_total.grid(row=1, column=3, pady=10, padx=5)
        self.ent_total.bind("<FocusOut>", self._format_total_on_leave)

        # Fila 3: Información Extra
        ttk.Label(grid_datos, text="Información Extra:", font=("Segoe UI", 11)).grid(row=2, column=0, pady=10,
                                                                                     sticky="e")
        self.ent_info = ttk.Entry(grid_datos, textvariable=self.var_info_extra, font=("Segoe UI", 11), width=65)
        self.ent_info.grid(row=2, column=1, columnspan=3, pady=10, padx=5, sticky="w")

        # Fila 4: Checkbox Emitir
        self.chk_emitir = ttk.Checkbutton(grid_datos, text="Emitir y enviar al correo del cliente inmediatamente",
                                          variable=self.var_emitir)
        self.chk_emitir.grid(row=3, column=1, columnspan=3, pady=15, sticky="w")

        # Botón Enviar
        self.btn_clonar = ttk.Button(self.panel_datos, text="Preparar Clonación y Enviar a Bandeja",
                                     style="Primary.TButton", command=self._procesar_clon)
        self.btn_clonar.pack(fill="x", side="bottom", pady=(15, 0), ipady=8)

    def _seleccionar_pdf(self):
        ruta = filedialog.askopenfilename(title="Selecciona la Factura Original", filetypes=[("PDF", "*.pdf")])
        if not ruta: return

        self.ruta_actual = ruta
        self.lbl_archivo.config(text=Path(ruta).name)

        try:
            datos = extract_clone_data(ruta)
            if datos["folio"] == "No detectado":
                messagebox.showerror("Error", "No se encontró el Folio en el PDF.")
                return

            # Autocompletar campos
            self.var_emisor.set(datos["proveedor"])
            self.var_llave.set(datos["folio"])

            subtotal_orig = datos["total"] / 1.16 if datos["total"] else 0.0
            self._is_updating = True
            # Formato de miles al extraer
            self.var_subtotal.set(f"{subtotal_orig:,.2f}")
            self.var_total.set(f"{datos['total']:,.2f}")
            self._is_updating = False

            self.controller.set_status(f"Datos extraídos correctamente de {datos['proveedor']}.")
        except Exception as e:
            messagebox.showerror("Error de lectura", f"Ocurrió un problema:\n{e}")

    def _on_subtotal_change(self):
        if self._is_updating: return
        try:
            sub = float(self.var_subtotal.get().replace(",", ""))
            tot = sub * 1.16
            self._is_updating = True
            self.var_total.set(f"{tot:,.2f}")
            self._is_updating = False
        except ValueError:
            pass

    def _on_total_change(self):
        if self._is_updating: return
        try:
            tot = float(self.var_total.get().replace(",", ""))
            sub = tot / 1.16
            self._is_updating = True
            self.var_subtotal.set(f"{sub:,.2f}")
            self._is_updating = False
        except ValueError:
            pass

    def _format_subtotal_on_leave(self, event=None):
        """Aplica formato de miles al perder el foco de la caja Subtotal."""
        if self._is_updating: return
        try:
            val = float(self.var_subtotal.get().replace(",", ""))
            self._is_updating = True
            self.var_subtotal.set(f"{val:,.2f}")
            self._is_updating = False
        except ValueError:
            pass

    def _format_total_on_leave(self, event=None):
        """Aplica formato de miles al perder el foco de la caja Total."""
        if self._is_updating: return
        try:
            val = float(self.var_total.get().replace(",", ""))
            self._is_updating = True
            self.var_total.set(f"{val:,.2f}")
            self._is_updating = False
        except ValueError:
            pass

    def _procesar_clon(self):
        emisor = self.var_emisor.get().strip()
        llave_target = self.var_llave.get().strip()

        if not emisor:
            messagebox.showwarning("Aviso", "Seleccione la Empresa Emisora.")
            return
        if not llave_target:
            messagebox.showwarning("Aviso", "Ingrese el Folio o RFC a duplicar.")
            return

        try:
            nuevo_total = float(self.var_total.get().replace(",", ""))
            nuevo_subtotal = float(self.var_subtotal.get().replace(",", ""))

            if nuevo_total <= 0:
                messagebox.showwarning("Aviso", "El total debe ser mayor a 0.")
                return

            info_usuario = self.var_info_extra.get().strip()
            instruccion_bot = f"[CLONAR_WEB:{llave_target}]"
            notas_finales = f"{instruccion_bot} | {info_usuario}" if info_usuario else instruccion_bot

            # Se crea la "Factura Fantasma"
            factura_clon = Factura(
                id=f"CLON-{llave_target}",
                cliente=Cliente(proveedor=emisor, rfc="EXTRACCIÓN WEB"),
                datos_factura=DatosFactura(
                    uso_cfdi="G03",
                    metodo_pago="PPD",
                    forma_pago="99",
                    info_extra=notas_finales,
                    emitir_y_enviar=self.var_emitir.get()
                ),
                conceptos=[
                    Concepto(
                        cantidad=1.0,
                        clave_unidad="ACT",
                        clave_prod_serv="01010101",
                        concepto="[CLONACIÓN WEB]",
                        precio_unitario=nuevo_subtotal,
                        importe=nuevo_subtotal
                    )
                ],
                total=nuevo_total,
                archivo_origen="Ingreso Manual" if not self.ruta_actual else Path(self.ruta_actual).name,
                hoja_origen="BOT_PORTAL"
            )

            # Limpieza tras envío
            self.lbl_archivo.config(text="(Opcional) Cargar PDF")
            self.ruta_actual = None
            self.var_llave.set("")
            self.var_info_extra.set("")
            self.var_subtotal.set("0.00")
            self.var_total.set("0.00")

            self.controller.open_visor([factura_clon])
            self.controller.set_status("Instrucción de clonación lista para la Fila de Trabajo.")

        except Exception as e:
            messagebox.showerror("Error", f"Verifique los montos ingresados:\n{e}")

    def _toggle_theme(self):
        self.controller.toggle_theme()

    def on_theme_changed(self):
        for widget in self.winfo_children():
            widget.destroy()
        self._build_ui()
