# app/ui/frames/menu.py
import tkinter as tk
from tkinter import ttk
from app.ui.theme import get_pal


class MenuPrincipalFrame(ttk.Frame):
    def __init__(self, master, controller):
        super().__init__(master)
        self.controller = controller
        self._build_ui()

    def _build_ui(self):
        pal = get_pal(self.controller)

        # --- TOP BAR (Botón de Tema en la esquina superior derecha) ---
        top_bar = ttk.Frame(self)
        top_bar.pack(side="top", fill="x", padx=20, pady=15)

        self.btn_theme = ttk.Button(top_bar, text=self.controller.theme_button_label(), command=self._toggle_theme)
        self.btn_theme.pack(side="right")

        # --- FOOTER (Versión en la esquina inferior derecha) ---
        footer_frame = ttk.Frame(self)
        footer_frame.pack(side="bottom", fill="x", padx=20, pady=15)

        ttk.Label(footer_frame, text="Versión 1.0 Beta", style="Muted.TLabel").pack(side="right")

        # --- CONTENEDOR CENTRAL MAESTRO ---
        # Usamos 'place' para que este bloque siempre flote exactamente en el centro de la ventana
        master_container = ttk.Frame(self)
        master_container.place(relx=0.5, rely=0.5, anchor="center")

        # Cabecera Central (Título)
        header_frame = ttk.Frame(master_container)
        header_frame.pack(fill="x", pady=(0, 45))  # Mayor separación hacia las tarjetas

        ttk.Label(header_frame, text="FactBot", font=("Segoe UI", 36, "bold")).pack(anchor="center")
        ttk.Label(header_frame, text="Panel de Control Principal", font=("Segoe UI", 13), style="Muted.TLabel").pack(
            anchor="center", pady=(5, 0))

        # --- CUADRÍCULA DE MÓDULOS (Tarjetas separadas) ---
        grid_frame = ttk.Frame(master_container)
        grid_frame.pack(expand=True)

        def create_module_card(parent, title, desc, command, row, col):
            # highlightthickness=2 hace que el borde se note más
            card = tk.Frame(parent, bg=pal["SURFACE"], cursor="hand2", highlightbackground=pal["BORDER"],
                            highlightthickness=2)

            # Aumentamos padx y pady para separar más las tarjetas entre sí
            card.grid(row=row, column=col, padx=20, pady=20, sticky="nsew")

            inner = tk.Frame(card, bg=pal["SURFACE"], cursor="hand2")
            inner.place(relx=0.5, rely=0.5, anchor="center")

            lbl_title = tk.Label(inner, text=title, font=("Segoe UI", 15, "bold"), bg=pal["SURFACE"], fg=pal["TEXT"],
                                 cursor="hand2")
            lbl_title.pack(pady=(0, 6))

            lbl_desc = tk.Label(inner, text=desc, font=("Segoe UI", 10), bg=pal["SURFACE"], fg=pal["MUTED"],
                                cursor="hand2")
            lbl_desc.pack()

            # Efecto Hover con el Borde Iluminado (ACCENT)
            def on_enter(e):
                card.configure(bg=pal["SURFACE2"], highlightbackground=pal["ACCENT"])
                inner.configure(bg=pal["SURFACE2"])
                lbl_title.configure(bg=pal["SURFACE2"])
                lbl_desc.configure(bg=pal["SURFACE2"])

            def on_leave(e):
                card.configure(bg=pal["SURFACE"], highlightbackground=pal["BORDER"])
                inner.configure(bg=pal["SURFACE"])
                lbl_title.configure(bg=pal["SURFACE"])
                lbl_desc.configure(bg=pal["SURFACE"])

            for w in (card, inner, lbl_title, lbl_desc):
                w.bind("<Button-1>", lambda e: command())
                w.bind("<Enter>", on_enter)
                w.bind("<Leave>", on_leave)

        # Generamos las tarjetas
        create_module_card(grid_frame, "Nueva Emisión", "Leer y aprobar archivos Excel o PDF",
                           lambda: self.controller.show("hacer"), 0, 0)
        create_module_card(grid_frame, "Centro de Emisión", "Fila de trabajo, bot y registros",
                           lambda: self.controller.show("pendientes"), 0, 1)
        create_module_card(grid_frame, "Catálogos", "Proveedores, Credenciales y Sucursales",
                           lambda: self.controller.show("proveedores"), 1, 0)
        create_module_card(grid_frame, "Reportes Locales", "Generar y exportar métricas",
                           lambda: self.controller.show("reportes"), 1, 1)
        create_module_card(grid_frame, "Ajuste de Formatos", "Reparar Excels con formato dañado",
                           lambda: self.controller.show("ajustar"), 2, 0)

        grid_frame.columnconfigure(0, minsize=340)
        grid_frame.columnconfigure(1, minsize=340)
        grid_frame.rowconfigure(0, minsize=160)
        grid_frame.rowconfigure(1, minsize=160)
        grid_frame.rowconfigure(2, minsize=160)

    def _toggle_theme(self):
        self.controller.toggle_theme()

    def on_theme_changed(self):
        for widget in self.winfo_children():
            widget.destroy()
        self._build_ui()
