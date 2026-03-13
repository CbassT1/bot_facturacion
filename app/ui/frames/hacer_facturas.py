# app/ui/frames/hacer_facturas.py
from __future__ import annotations
import threading
from typing import TYPE_CHECKING
import tkinter as tk
from tkinter import ttk, messagebox

from app.ui.utils import center_toplevel_on_parent
from app.ui.theme import get_pal

# Importamos nuestro componente especialista
from app.ui.frames.file_manager_panel import FileManagerPanel

if TYPE_CHECKING:
    from app.ui.app import App


class HacerFacturasFrame(ttk.Frame):
    """
    Controlador principal de la pantalla de Nueva Emisión.
    Delega el UI a FileManagerPanel y maneja el Hilo de Procesamiento (Parser).
    """

    def __init__(self, master: ttk.Frame, controller: "App"):
        super().__init__(master)
        self.controller = controller

        # --- Cabecera ---
        header = ttk.Frame(self)
        header.pack(fill="x", padx=16, pady=(16, 10))

        ttk.Button(header, text="← Volver", command=lambda: controller.show("menu")).pack(side="left")
        ttk.Label(header, text="Nueva Emisión", font=("Segoe UI", 16, "bold")).pack(side="left", padx=(12, 0))
        ttk.Button(header, text=self.controller.theme_button_label(), command=self._toggle_theme).pack(side="right")

        # --- Cuerpo Central (Delegado al Componente) ---
        body = ttk.Frame(self)
        body.pack(fill="both", expand=True, padx=16, pady=10)

        self.file_manager = FileManagerPanel(body, controller)
        self.file_manager.pack(fill="both", expand=True)

        # --- Pie de página ---
        footer = ttk.Frame(body)
        footer.pack(fill="x", pady=(12, 0))
        ttk.Button(footer, text="Continuar", style="Primary.TButton", command=self._procesar_archivos).pack(
            side="right")

    # --- Lógica de Procesamiento ---
    def _procesar_archivos(self):
        paths_list = self.file_manager.get_paths()

        if not paths_list:
            messagebox.showwarning("Sin archivos", "Agrega al menos un archivo .xlsx para continuar.", parent=self)
            return

        # Modal de Carga
        dlg = tk.Toplevel(self)
        dlg.title("Procesando")
        dlg.transient(self.winfo_toplevel())
        dlg.grab_set()
        dlg.resizable(False, False)
        dlg.configure(bg=get_pal(self.controller)["BG"])

        wrap = ttk.Frame(dlg)
        wrap.pack(padx=18, pady=16)
        ttk.Label(wrap, text="Procesando archivos...", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        ttk.Label(wrap, text=f"Archivos a parsear: {len(paths_list)}", style="Muted.TLabel").pack(anchor="w",
                                                                                                  pady=(4, 10))

        pb = ttk.Progressbar(wrap, mode="indeterminate", length=360)
        pb.pack(fill="x")
        pb.start(12)

        dlg.update_idletasks()
        center_toplevel_on_parent(self.controller, dlg, 440, 150)
        self.controller.set_status(f"Procesando {len(paths_list)} archivo(s)...")

        self.controller._last_input_paths = list(paths_list)

        # El Trabajo Pesado (Thread)
        def _worker():
            try:
                facturas = self.controller.parse_excel_files(paths_list)
                err = None
            except Exception as e:
                facturas = []
                err = e

            def _on_finish():
                try:
                    pb.stop()
                except:
                    pass
                try:
                    dlg.destroy()
                except:
                    pass

                if err is not None:
                    self.controller.set_status("Error crítico al procesar archivos.")
                    messagebox.showerror("Error al parsear", f"No se pudieron leer los archivos.\n\nDetalle:\n{err}",
                                         parent=self)
                    return
                if not facturas:
                    self.controller.set_status("Sin facturas detectadas.", auto_clear_ms=2500)
                    messagebox.showwarning("Sin facturas", "No se detectaron facturas/hojas válidas en los archivos.",
                                           parent=self)
                    return

                self.file_manager.clear_files()
                self.controller.open_visor(facturas)

            self.controller.after(0, _on_finish)

        threading.Thread(target=_worker, daemon=True).start()

    # --- Delegación de UI y Atajos ---
    def _toggle_theme(self):
        self.controller.toggle_theme()

    def on_theme_changed(self):
        header = self.winfo_children()[0]
        for w in header.winfo_children():
            if isinstance(w, ttk.Button) and w.cget("text") in ("Modo claro", "Modo oscuro"):
                w.configure(text=self.controller.theme_button_label())

        # Le avisamos al componente que el tema cambió
        self.file_manager.on_theme_changed()

    def _select_files(self):
        """Este método es llamado por el atajo Ctrl+O definido en app.py"""
        self.file_manager.trigger_select_files()
