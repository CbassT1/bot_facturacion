# app/ui/frames/clonador.py
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import copy
from pathlib import Path

from app.ui.theme import get_pal
from parser.pdf_parser import parse_pdf_invoice


class ClonadorFacturasFrame(ttk.Frame):
    def __init__(self, master, controller):
        super().__init__(master)
        self.controller = controller
        self.factura_original = None
        self._is_updating = False
        self._build_ui()

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

        # Contenedor central para que no se vea estirado en pantallas grandes
        center_container = ttk.Frame(body)
        center_container.place(relx=0.5, rely=0.4, anchor="center")

        ttk.Label(center_container, text="Importe un documento PDF anterior, ajuste el monto y agregue notas.",
                  style="Muted.TLabel").pack(pady=(0, 20))

        # --- SELECCIÓN DE ARCHIVO ---
        row_file = ttk.Frame(center_container)
        row_file.pack(fill="x", pady=(0, 20))

        self.btn_seleccionar = ttk.Button(row_file, text="📄 Seleccionar PDF Original", command=self._seleccionar_pdf)
        self.btn_seleccionar.pack(side="left")

        self.lbl_archivo = ttk.Label(row_file, text="Ningún archivo seleccionado...", font=("Segoe UI", 10, "italic"))
        self.lbl_archivo.pack(side="left", padx=10)

        # --- PANEL DE CÁLCULO Y DATOS EXTRAS (Oculto al inicio) ---
        self.panel_calculo = ttk.LabelFrame(center_container, text="Nuevos Datos", padding=20)

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

        self.btn_clonar = ttk.Button(self.panel_calculo, text="Crear Copia y Enviar a Bandeja", style="Primary.TButton",
                                     command=self._procesar_clon)

    def _seleccionar_pdf(self):
        ruta = filedialog.askopenfilename(title="Selecciona la Factura Original", filetypes=[("PDF", "*.pdf")])
        if not ruta: return

        self.lbl_archivo.config(text=Path(ruta).name)

        try:
            facturas = parse_pdf_invoice(ruta)
            if not facturas:
                messagebox.showerror("Error", "No se pudo extraer información del PDF.")
                return

            self.factura_original = facturas[0]

            # Mostramos el panel de cálculo
            self.panel_calculo.pack(fill="both", expand=True, pady=10)
            self.btn_clonar.pack(fill="x", side="bottom", pady=(20, 0), ipady=8)

            subtotal_orig = self.factura_original.total / 1.16 if self.factura_original.total else 0.0

            self._is_updating = True
            self.var_subtotal.set(f"{subtotal_orig:.2f}")
            self.var_total.set(f"{self.factura_original.total:.2f}")
            self._is_updating = False

            self.controller.set_status(
                f"Factura leída correctamente. Total Original: ${self.factura_original.total:,.2f}")

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

            clon = copy.deepcopy(self.factura_original)

            subtotal_original = sum(c.importe for c in clon.conceptos)
            factor = nuevo_subtotal / subtotal_original if subtotal_original > 0 else 1.0

            for c in clon.conceptos:
                c.precio_unitario = c.precio_unitario * factor
                c.importe = c.importe * factor

            clon.total = nuevo_total
            clon.id = f"[CLON] {clon.id}"

            texto_extra = self.var_info_extra.get().strip()
            if texto_extra:
                if clon.notas_extra:
                    clon.notas_extra += f" | {texto_extra}"
                else:
                    clon.notas_extra = texto_extra

            # Limpiar la pantalla para el próximo uso
            self.lbl_archivo.config(text="Ningún archivo seleccionado...")
            self.panel_calculo.pack_forget()
            self.var_info_extra.set("")

            # Enviar la factura clonada directamente al visor
            self.controller.open_visor([clon])
            self.controller.set_status("Factura clonada generada correctamente.")

        except Exception as e:
            messagebox.showerror("Error", f"Verifica los números ingresados:\n{e}")

    def _toggle_theme(self):
        self.controller.toggle_theme()

    def on_theme_changed(self):
        for widget in self.winfo_children():
            widget.destroy()
        self._build_ui()
