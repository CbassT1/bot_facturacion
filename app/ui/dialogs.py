# app/ui/dialogs.py
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox

from app.ui.theme import get_pal


def _center_toplevel_on_parent(parent: tk.Misc, win: tk.Toplevel, w: int, h: int):
    # Centrado simple y estable (evita depender de utils por ahora)
    try:
        win.update_idletasks()
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        x = px + (pw - w) // 2
        y = py + (ph - h) // 2
        win.geometry(f"{w}x{h}+{x}+{y}")
    except Exception:
        # fallback: solo set size
        try:
            win.geometry(f"{w}x{h}")
        except Exception:
            pass


class ConfirmDialog(tk.Toplevel):
    def __init__(self, parent: tk.Tk, title: str, message: str, checkbox_text: str, *, use_ocr_default: bool = False):
        super().__init__(parent)

        self.title(title)
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)

        self.result_yes = False
        self.var_skip = tk.BooleanVar(value=False)

        # OCR checkbox (si quieres usarlo)
        self.var_use_ocr = tk.BooleanVar(value=bool(use_ocr_default))

        pal = get_pal(parent)
        self.configure(bg=pal["BG"])

        wrap = ttk.Frame(self)
        wrap.pack(padx=18, pady=16)

        ttk.Label(wrap, text=message, font=("Segoe UI", 11, "bold")).pack(anchor="w")
        ttk.Checkbutton(
            wrap,
            text=checkbox_text,
            variable=self.var_skip,
            style="Card.TCheckbutton",
        ).pack(anchor="w", pady=(10, 0))

        btns = ttk.Frame(wrap)
        btns.pack(fill="x", pady=(14, 0))

        ttk.Checkbutton(
            btns,
            text="Usar OCR en PDF (si es escaneado)",
            variable=self.var_use_ocr,
        ).pack(side="right", padx=(6, 0))

        ttk.Button(btns, text="Cancelar", command=self._no).pack(side="right")
        ttk.Button(btns, text="Eliminar", style="Primary.TButton", command=self._yes).pack(side="right", padx=(0, 10))

        self.update_idletasks()
        _center_toplevel_on_parent(parent, self, 520, 190)

        self.bind("<Escape>", lambda _e: self._no())
        self.bind("<Return>", lambda _e: self._yes())

    def _yes(self):
        self.result_yes = True
        self.destroy()

    def _no(self):
        self.result_yes = False
        self.destroy()


class LogDialog(tk.Toplevel):
    def __init__(self, parent, title="Ejecución del Bot"):
        super().__init__(parent)
        self.title(title)
        self.transient(parent)

        pal = get_pal(parent)
        self.configure(bg=pal["BG"])

        # Frame principal
        main_frame = ttk.Frame(self, padding=15)
        main_frame.pack(fill="both", expand=True)

        # Titulo
        ttk.Label(main_frame, text="📡 Consola en Vivo:", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(0, 5))

        # Text Widget para los logs (con estilo de terminal de hacker)
        self.txt_logs = tk.Text(main_frame, wrap="word", font=("Consolas", 10), bg="#1E1E1E", fg="#4AF626", height=20)
        self.txt_logs.pack(fill="both", expand=True, pady=5)

        # Scrollbar integrada
        scrollbar = ttk.Scrollbar(self.txt_logs, orient="vertical", command=self.txt_logs.yview)
        self.txt_logs.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")

        # Botón para ocultar/cerrar la ventana
        self.btn_cerrar = ttk.Button(main_frame, text="Cerrar Consola", command=self.destroy)
        self.btn_cerrar.pack(pady=(10, 0))

        self.update_idletasks()
        _center_toplevel_on_parent(parent, self, 700, 450)

    def add_log(self, mensaje: str):
        """
        Imprime un mensaje en la consola del bot.
        Usa self.after(0, ...) para ser "Thread-Safe" y no congelar la UI de Tkinter.
        """

        def _escribir():
            self.txt_logs.insert(tk.END, f"> {mensaje}\n")
            self.txt_logs.see(tk.END)  # Hace auto-scroll hacia abajo

        self.after(0, _escribir)