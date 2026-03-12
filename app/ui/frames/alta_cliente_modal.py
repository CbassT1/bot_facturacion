# app/ui/frames/alta_cliente_modal.py
import tkinter as tk
from tkinter import ttk, messagebox


class AltaClienteModal(tk.Toplevel):
    def __init__(self, parent, rfc_buscado=""):
        super().__init__(parent)
        self.title("⚡ Acción Requerida: Alta de Nuevo Cliente")

        # --- FIX VISUAL: Ajustado para ingreso manual ---
        self.geometry("700x700")
        self.minsize(600, 650)
        self.resizable(True, True)

        bg_color = ttk.Style().lookup('TFrame', 'background')
        self.configure(bg=bg_color)

        self.grab_set()

        # Forzar al frente y emitir sonido
        self.bell()
        self.lift()
        self.attributes('-topmost', True)
        self.focus_force()
        self.after(1000, lambda: self.attributes('-topmost', False))

        self.datos_finales = None

        self.var_rfc = tk.StringVar(value=rfc_buscado)
        self.var_razon = tk.StringVar()
        self.var_curp = tk.StringVar()
        self.var_regimen = tk.StringVar()
        self.var_cp = tk.StringVar()
        self.var_colonia = tk.StringVar()
        self.var_calle = tk.StringVar()
        self.var_num_ext = tk.StringVar()
        self.var_num_int = tk.StringVar()
        self.var_correo = tk.StringVar()

        self._build_ui()

    def _build_ui(self):
        # Cabecera
        header = ttk.Frame(self)
        header.pack(fill="x", padx=20, pady=(20, 10))
        ttk.Label(header, text="⚠️ Cliente no encontrado", font=("Segoe UI", 14, "bold"), foreground="#E53935").pack(
            anchor="w")
        ttk.Label(header, text="El bot se ha pausado. Ingresa los datos fiscales para que el bot lo registre.").pack(
            anchor="w", pady=(5, 0))

        # Formulario
        form = ttk.LabelFrame(self, text="Datos del Cliente", padding=20)
        form.pack(fill="both", expand=True, padx=20, pady=5)

        def add_row(parent, label_text, var, row, col_span=1, width=30):
            ttk.Label(parent, text=label_text, font=("Segoe UI", 10)).grid(row=row, column=0, sticky="w", pady=5)
            ttk.Entry(parent, textvariable=var, width=width, font=("Segoe UI", 10)).grid(row=row, column=1,
                                                                                         columnspan=col_span,
                                                                                         sticky="we", pady=5, padx=10)

        form.columnconfigure(1, weight=1)

        add_row(form, "* RFC:", self.var_rfc, 0)
        add_row(form, "  CURP (Opcional):", self.var_curp, 1)
        add_row(form, "* Razón Social:", self.var_razon, 2, col_span=3, width=60)
        add_row(form, "* Régimen (Código ej. 601):", self.var_regimen, 3)
        add_row(form, "* Código Postal:", self.var_cp, 4)
        add_row(form, "  Colonia:", self.var_colonia, 5, col_span=3, width=60)
        add_row(form, "* Calle:", self.var_calle, 6, col_span=3, width=60)

        fila_nums = ttk.Frame(form)
        fila_nums.grid(row=7, column=0, columnspan=4, sticky="w", pady=5)
        ttk.Label(fila_nums, text="* Num Ext:", font=("Segoe UI", 10)).pack(side="left")
        ttk.Entry(fila_nums, textvariable=self.var_num_ext, width=15, font=("Segoe UI", 10)).pack(side="left",
                                                                                                  padx=(10, 20))
        ttk.Label(fila_nums, text="Num Int:", font=("Segoe UI", 10)).pack(side="left")
        ttk.Entry(fila_nums, textvariable=self.var_num_int, width=15, font=("Segoe UI", 10)).pack(side="left", padx=10)

        add_row(form, "* Correo Electrónico:", self.var_correo, 8, col_span=3, width=60)

        # Botones de Acción
        footer = ttk.Frame(self)
        footer.pack(fill="x", padx=20, pady=(10, 20))
        ttk.Button(footer, text="Cancelar Alta (Pausar Bot)", command=self.destroy).pack(side="left")
        ttk.Button(footer, text="Guardar y Ejecutar Alta en Web", style="Primary.TButton", command=self._guardar).pack(
            side="right", ipady=5, ipadx=10)

    def _guardar(self):
        if not self.var_razon.get() or not self.var_cp.get() or not self.var_correo.get():
            messagebox.showwarning("Atención", "Los campos marcados con (*) son obligatorios.")
            return

        self.datos_finales = {
            "rfc": self.var_rfc.get().strip(),
            "razon": self.var_razon.get().strip(),
            "curp": self.var_curp.get().strip(),
            "regimen": self.var_regimen.get().strip(),
            "cp": self.var_cp.get().strip(),
            "colonia": self.var_colonia.get().strip(),
            "calle": self.var_calle.get().strip(),
            "num_ext": self.var_num_ext.get().strip(),
            "num_int": self.var_num_int.get().strip(),
            "correo": self.var_correo.get().strip()
        }
        self.destroy()
