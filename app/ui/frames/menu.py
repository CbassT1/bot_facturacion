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

        # ==========================================
        # PANEL IZQUIERDO (Dashboard Sidebar)
        # ==========================================
        left_panel = tk.Frame(self, bg=pal["SURFACE2"], width=300)
        left_panel.pack(side="left", fill="y")
        left_panel.pack_propagate(False)

        # Branding
        lbl_title = tk.Label(left_panel, text="FactBot", font=("Segoe UI", 32, "bold"), bg=pal["SURFACE2"],
                             fg=pal["TEXT"])
        lbl_title.pack(pady=(40, 5), anchor="w", padx=30)

        lbl_sub = tk.Label(left_panel, text="Panel de Control", font=("Segoe UI", 12), bg=pal["SURFACE2"],
                           fg=pal["MUTED"])
        lbl_sub.pack(anchor="w", padx=30, pady=(0, 30))

        # Opciones Laterales (Botones arreglados para no verse negros al clic)
        self.btn_theme = tk.Button(
            left_panel,
            text=self.controller.theme_button_label(),
            command=self._toggle_theme,
            bg=pal["BG"],
            fg=pal["TEXT"],
            activebackground=pal["ACCENT"],  # Color al hacer clic
            activeforeground="#FFFFFF",  # Texto al hacer clic
            relief="flat",
            cursor="hand2",
            font=("Segoe UI", 10),
            pady=5
        )
        self.btn_theme.pack(fill="x", padx=30, pady=10)

        # Panel de Estado Inferior
        status_frame = tk.Frame(left_panel, bg=pal["SURFACE2"])
        status_frame.pack(side="bottom", fill="x", padx=30, pady=30)

        tk.Label(status_frame, text="Usuario: Administrador", font=("Segoe UI", 9, "bold"), bg=pal["SURFACE2"],
                 fg=pal["TEXT"], anchor="w").pack(fill="x")
        tk.Label(status_frame, text="Base de Datos: Conectada", font=("Segoe UI", 9), bg=pal["SURFACE2"], fg="#4AF626",
                 anchor="w").pack(fill="x", pady=(2, 10))
        tk.Label(status_frame, text="Version 1.0", font=("Segoe UI", 9), bg=pal["SURFACE2"], fg=pal["MUTED"],
                 anchor="w").pack(fill="x")

        # ==========================================
        # PANEL DERECHO (Cuadricula de tarjetas)
        # ==========================================
        right_panel = tk.Frame(self, bg=pal["BG"])
        right_panel.pack(side="right", fill="both", expand=True)

        lbl_seccion = tk.Label(right_panel, text="Modulos de Operacion", font=("Segoe UI", 16, "bold"), bg=pal["BG"],
                               fg=pal["TEXT"])
        lbl_seccion.pack(anchor="w", padx=40, pady=(40, 20))

        grid_frame = tk.Frame(right_panel, bg=pal["BG"])
        grid_frame.pack(fill="both", expand=True, padx=25)

        def create_modern_card(parent, title, desc, command, row, col):
            # Tarjeta directa (Grosor fijo en 2 para evitar que el diseño brinque)
            card = tk.Frame(parent, bg=pal["SURFACE"], cursor="hand2", highlightbackground=pal["BORDER"],
                            highlightthickness=2)
            card.grid(row=row, column=col, padx=15, pady=15, sticky="nsew")

            lbl_t = tk.Label(card, text=title, font=("Segoe UI", 13, "bold"), bg=pal["SURFACE"], fg=pal["TEXT"],
                             cursor="hand2")
            lbl_t.pack(pady=(20, 5), padx=20, anchor="w")

            lbl_d = tk.Label(card, text=desc, font=("Segoe UI", 10), bg=pal["SURFACE"], fg=pal["MUTED"], cursor="hand2",
                             justify="left", wraplength=220)
            lbl_d.pack(padx=20, pady=(0, 20), anchor="nw", fill="x")

            # Animacion estable: Solo cambiamos el color, no el tamaño fisico
            def on_enter(e):
                card.configure(highlightbackground=pal["ACCENT"])
                lbl_t.configure(fg=pal["ACCENT"])

            def on_leave(e):
                card.configure(highlightbackground=pal["BORDER"])
                lbl_t.configure(fg=pal["TEXT"])

            for w in (card, lbl_t, lbl_d):
                w.bind("<Button-1>", lambda e: command())
                w.bind("<Enter>", on_enter)
                w.bind("<Leave>", on_leave)

        # Fila 0
        create_modern_card(grid_frame, "Nueva Emision", "Leer y aprobar facturas desde Excel o PDF.",
                           lambda: self.controller.show("hacer"), 0, 0)
        create_modern_card(grid_frame, "Centro de Emision", "Fila de trabajo, estatus del bot y registros.",
                           lambda: self.controller.show("pendientes"), 0, 1)

        # Fila 1
        create_modern_card(grid_frame, "Complementos de Pago", "Aplica pagos a folios previos y emite recibos.",
                           lambda: self.controller.show("HacerPagosFrame"), 1, 0)
        create_modern_card(grid_frame, "Clonador de Facturas", "Duplica facturas existentes con nuevos montos.",
                           lambda: self.controller.show("clonador"), 1, 1)

        # Fila 2
        create_modern_card(grid_frame, "Catalogos de Sistema", "Configura Proveedores, Accesos y Sucursales.",
                           lambda: self.controller.show("proveedores"), 2, 0)
        create_modern_card(grid_frame, "Reportes Locales", "Genera y exporta metricas de facturacion.",
                           lambda: self.controller.show("reportes"), 2, 1)

        # Fila 3
        create_modern_card(grid_frame, "Ajuste de Formatos", "Herramienta para reparar Excels con formato dañado.",
                           lambda: self.controller.show("ajustar"), 3, 0)

        # Configuracion simetrica
        grid_frame.columnconfigure(0, minsize=320, weight=1)
        grid_frame.columnconfigure(1, minsize=320, weight=1)

    def _toggle_theme(self):
        self.controller.toggle_theme()

    def on_theme_changed(self):
        for widget in self.winfo_children():
            widget.destroy()
        self._build_ui()
