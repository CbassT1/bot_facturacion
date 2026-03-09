# app/ui/frames/clonador.py
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path

from app.ui.theme import get_pal
from app.models import Factura, Cliente, DatosFactura, Concepto
from parser.pdf_parser import extract_clone_data


class ClonadorFacturasFrame(ttk.Frame):
    def __init__(self, master, controller):
        super().__init__(master)
        self.controller = controller
        self.datos_extraidos = None
        self.ruta_actual = None
        self._is_updating = False
        self._build_ui()

    def _build_ui(self):
        pal = get_pal(self.controller)

        # --- HEADER ---
        header = ttk.Frame(self)
        header.pack(fill="x", padx=16, pady=(16, 10))

        ttk.Button(header, text="← Volver", command=lambda: self.controller.show("menu")).pack(side="left")
        ttk.Label(header, text="Clonador de Facturas (Portal Web)", font=("Segoe UI", 16, "bold")).pack(side="left",
                                                                                                        padx=(12, 0))
        ttk.Button(header, text=self.controller.theme_button_label(), command=self._toggle_theme).pack(side="right")

        # --- BODY ---
        body = ttk.Frame(self)
        body.pack(fill="both", expand=True, padx=16, pady=10)

        center_container = ttk.Frame(body)
        center_container.place(relx=0.5, rely=0.4, anchor="center")

        ttk.Label(center_container,
                  text="Extrae el folio de una factura anterior para duplicarla automáticamente en el portal.",
                  style="Muted.TLabel").pack(pady=(0, 20))

        # --- SELECCIÓN DE ARCHIVO ---
        row_file = ttk.Frame(center_container)
        row_file.pack(fill="x", pady=(0, 20))

        self.btn_seleccionar = ttk.Button(row_file, text="📄 Seleccionar PDF Original", command=self._seleccionar_pdf)
        self.btn_seleccionar.pack(side="left")

        self.lbl_archivo = ttk.Label(row_file, text="Ningún archivo seleccionado...", font=("Segoe UI", 10, "italic"))
        self.lbl_archivo.pack(side="left", padx=10)

        # --- PANEL DE DATOS DETECTADOS ---
        self.panel_detectado = ttk.LabelFrame(center_container, text="Llave Maestra Detectada", padding=15)
        self.lbl_proveedor = ttk.Label(self.panel_detectado, text="Emisor: -", font=("Segoe UI", 11, "bold"))
        self.lbl_proveedor.pack(anchor="w")
        self.lbl_folio = ttk.Label(self.panel_detectado, text="Folio a Duplicar: -", font=("Segoe UI", 11, "bold"),
                                   foreground=pal["ACCENT"])
        self.lbl_folio.pack(anchor="w", pady=5)

        # --- PANEL DE CÁLCULO Y DATOS EXTRAS ---
        self.panel_calculo = ttk.LabelFrame(center_container, text="Nuevos Valores", padding=20)

        self.var_subtotal = tk.StringVar(value="0.00")
        self.var_total = tk.StringVar(value="0.00")
        self.var_info_extra = tk.StringVar(value="")

        self.var_subtotal.trace_add("write", lambda *args: self._on_subtotal_change())
        self.var_total.trace_add("write", lambda *args: self._on_total_change())

        grid_montos = ttk.Frame(self.panel_calculo)
        grid_montos.pack(fill="x")

        ttk.Label(grid_montos, text="Nuevo Subtotal: $", font=("Segoe UI", 12)).grid(row=0, column=0, pady=10,
                                                                                     sticky="e")
        self.ent_subtotal = ttk.Entry(grid_montos, textvariable=self.var_subtotal, font=("Segoe UI", 12, "bold"),
                                      width=20)
        self.ent_subtotal.grid(row=0, column=1, pady=10, padx=10)

        ttk.Label(grid_montos, text="Nuevo Total (IVA incl): $", font=("Segoe UI", 12)).grid(row=1, column=0, pady=10,
                                                                                             sticky="e")
        self.ent_total = ttk.Entry(grid_montos, textvariable=self.var_total, font=("Segoe UI", 12, "bold"), width=20)
        self.ent_total.grid(row=1, column=1, pady=10, padx=10)

        ttk.Label(grid_montos, text="Información Extra:", font=("Segoe UI", 12)).grid(row=2, column=0, pady=15,
                                                                                      sticky="e")
        self.ent_info = ttk.Entry(grid_montos, textvariable=self.var_info_extra, font=("Segoe UI", 12), width=28)
        self.ent_info.grid(row=2, column=1, pady=15, padx=10)

        self.btn_clonar = ttk.Button(self.panel_calculo, text="⚙️ Preparar Clonación Bot y Enviar",
                                     style="Primary.TButton", command=self._procesar_clon)

    def _seleccionar_pdf(self):
        ruta = filedialog.askopenfilename(title="Selecciona la Factura Original", filetypes=[("PDF", "*.pdf")])
        if not ruta: return

        self.ruta_actual = ruta
        self.lbl_archivo.config(text=Path(ruta).name)

        try:
            self.datos_extraidos = extract_clone_data(ruta)

            if self.datos_extraidos["folio"] == "No detectado":
                messagebox.showerror("Error",
                                     "No se encontró el Folio en el PDF.\nEl bot necesita el folio para duplicar en la web.")
                return

            # Mostrar UI
            self.panel_detectado.pack(fill="x", pady=10)
            self.lbl_proveedor.config(text=f"Emisor: {self.datos_extraidos['proveedor']}")
            self.lbl_folio.config(text=f"Folio a Duplicar: {self.datos_extraidos['folio']}")

            self.panel_calculo.pack(fill="both", expand=True, pady=10)
            self.btn_clonar.pack(fill="x", side="bottom", pady=(20, 0), ipady=8)

            subtotal_orig = self.datos_extraidos["total"] / 1.16 if self.datos_extraidos["total"] else 0.0

            self._is_updating = True
            self.var_subtotal.set(f"{subtotal_orig:.2f}")
            self.var_total.set(f"{self.datos_extraidos['total']:.2f}")
            self._is_updating = False

            self.controller.set_status("Llave Maestra extraída correctamente.")

        except Exception as e:
            messagebox.showerror("Error de lectura", f"Ocurrió un problema:\n{e}")

    def _on_subtotal_change(self):
        if self._is_updating: return
        try:
            sub = float(self.var_subtotal.get().replace(",", ""))
            tot = sub * 1.16
            self._is_updating = True
            self.var_total.set(f"{tot:.2f}")
            self._is_updating = False
        except ValueError:
            pass

    def _on_total_change(self):
        if self._is_updating: return
        try:
            tot = float(self.var_total.get().replace(",", ""))
            sub = tot / 1.16
            self._is_updating = True
            self.var_subtotal.set(f"{sub:.2f}")
            self._is_updating = False
        except ValueError:
            pass

    def _procesar_clon(self):
        try:
            nuevo_total = float(self.var_total.get().replace(",", ""))
            nuevo_subtotal = float(self.var_subtotal.get().replace(",", ""))

            if nuevo_total <= 0:
                messagebox.showwarning("Aviso", "El total debe ser mayor a 0.")
                return

            folio_target = self.datos_extraidos["folio"]
            prov = self.datos_extraidos["proveedor"]
            rfc = self.datos_extraidos["rfc_cliente"]
            info_usuario = self.var_info_extra.get().strip()

            # MAGIA: Ocultamos las instrucciones para Playwright en las Notas Extra
            instruccion_bot = f"[CLONAR_WEB:{folio_target}]"
            notas_finales = f"{instruccion_bot} | {info_usuario}" if info_usuario else instruccion_bot

            # Creamos una factura fantasma con 1 solo concepto de referencia
            factura_clon = Factura(
                id=f"CLON-{folio_target}",
                cliente=Cliente(proveedor=prov, rfc=rfc),
                datos_factura=DatosFactura(uso_cfdi="G03", metodo_pago="PPD", forma_pago="99",
                                           info_extra=notas_finales),
                conceptos=[
                    Concepto(
                        cantidad=1.0,
                        clave_unidad="ACT",
                        clave_prod_serv="01010101",
                        concepto="[CLONACIÓN WEB] - El Bot editará el concepto original del portal.",
                        precio_unitario=nuevo_subtotal,
                        importe=nuevo_subtotal
                    )
                ],
                total=nuevo_total,
                archivo_origen=Path(self.ruta_actual).name,
                hoja_origen="BOT_PORTAL"
            )

            # Limpiar pantalla
            self.lbl_archivo.config(text="Ningún archivo seleccionado...")
            self.panel_detectado.pack_forget()
            self.panel_calculo.pack_forget()
            self.var_info_extra.set("")

            # Enviar a bandeja
            self.controller.open_visor([factura_clon])
            self.controller.set_status("Instrucción de clonación lista para emitir.")

        except Exception as e:
            messagebox.showerror("Error", f"Verifica los números ingresados:\n{e}")

    def _toggle_theme(self):
        self.controller.toggle_theme()

    def on_theme_changed(self):
        for widget in self.winfo_children():
            widget.destroy()
        self._build_ui()
