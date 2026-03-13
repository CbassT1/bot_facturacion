# app/ui/frames/proveedores.py
import tkinter as tk
from tkinter import ttk
from app.ui.theme import get_pal

# Importamos nuestros nuevos componentes (Pestañas)
from app.ui.frames.tab_proveedores import TabProveedores
from app.ui.frames.tab_sucursales import TabSucursales

class ProveedoresFrame(ttk.Frame):
    def __init__(self, master, controller):
        super().__init__(master)
        self.controller = controller
        self._build_ui()

    def _build_ui(self):
        # --- Cabecera ---
        header = ttk.Frame(self)
        header.pack(fill="x", padx=12, pady=(12, 6))

        ttk.Button(header, text="← Menú Principal", command=lambda: self.controller.show("menu")).pack(side="left")
        ttk.Label(header, text="Gestión de Catálogos", font=("Segoe UI", 16, "bold")).pack(side="left", padx=(12, 0))

        self.btn_theme = ttk.Button(header, text=self.controller.theme_button_label(), command=self._toggle_theme)
        self.btn_theme.pack(side="right")

        # --- Notebook (Contenedor de pestañas) ---
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=12, pady=(10, 15))

        # --- INYECCIÓN DE LOS COMPONENTES ---
        # Le pasamos "self.refresh_data" para que si guardas un proveedor en la Pestaña 1,
        # la Pestaña 2 actualice su lista desplegable al instante.
        self.tab_provs = TabProveedores(self.notebook, self.controller, on_data_changed=self.refresh_data)
        self.notebook.add(self.tab_provs, text="Proveedores y Credenciales")

        self.tab_sucs = TabSucursales(self.notebook, self.controller, on_data_changed=self.refresh_data)
        self.notebook.add(self.tab_sucs, text="Sucursales")

    def refresh_data(self):
        """Llama al refresh de las sub-pestañas"""
        self.tab_provs.refresh_data()
        self.tab_sucs.refresh_data()

    def _toggle_theme(self):
        self.controller.toggle_theme()

    def on_theme_changed(self):
        self.btn_theme.configure(text=self.controller.theme_button_label())
        # Propaga el cambio de tema a los componentes hijos
        self.tab_provs.on_theme_changed()
        self.tab_sucs.on_theme_changed()
