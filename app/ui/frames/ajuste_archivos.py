# app/ui/frames/ajuste_archivos.py
import os
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading

from app.ui.theme import get_pal
from app.ui.utils import center_toplevel_on_parent

# --- IMPORTAMOS LOS MÓDULOS REPARADORES EXTERNOS ---
from parser.reparadores.vega_ponce import reparar as reparar_vega_ponce
from parser.reparadores.degaz import reparar as reparar_degaz
from parser.reparadores.gasolineras import reparar as reparar_gasolineras
from parser.reparadores.diegza import reparar_diegza


class AjusteArchivosFrame(ttk.Frame):
    def __init__(self, master, controller):
        super().__init__(master)
        self.controller = controller
        self._paths = []
        self._build_ui()

    def _build_ui(self):
        pal = get_pal(self.controller)

        header = ttk.Frame(self)
        header.pack(fill="x", padx=16, pady=(16, 10))

        ttk.Button(header, text="← Menú Principal", command=lambda: self.controller.show("menu")).pack(side="left")
        ttk.Label(header, text="Ajuste de Formatos (Limpiador)", font=("Segoe UI", 16, "bold")).pack(side="left",
                                                                                                     padx=(12, 0))
        ttk.Button(header, text=self.controller.theme_button_label(), command=self._toggle_theme).pack(side="right")

        body = ttk.Frame(self)
        body.pack(fill="both", expand=True, padx=16, pady=10)

        left_panel = ttk.Frame(body)
        left_panel.pack(side="left", fill="both", expand=True, padx=(0, 10))

        actions = ttk.Frame(left_panel)
        actions.pack(fill="x", pady=(0, 12))
        ttk.Button(actions, text="Seleccionar Excel Rebelde", command=self._select_files).pack(side="left")
        ttk.Button(actions, text="Limpiar lista", command=self._clear_files).pack(side="left", padx=(10, 0))

        list_frame = ttk.LabelFrame(left_panel, text="Archivos a reparar")
        list_frame.pack(fill="both", expand=True)

        self.listbox = tk.Listbox(
            list_frame, bg=pal["SURFACE"], fg=pal["TEXT"], selectbackground=pal["LIST_SELECT"],
            selectforeground=pal["TEXT"], highlightbackground=pal["BORDER"], relief="flat", bd=0, font=("Segoe UI", 11)
        )
        self.listbox.configure(selectmode=tk.EXTENDED)
        self.listbox.pack(fill="both", expand=True, padx=12, pady=12)

        def _drag_select(event):
            idx = self.listbox.nearest(event.y)
            if idx >= 0: self.listbox.selection_set(idx)

        self.listbox.bind("<B1-Motion>", _drag_select)
        self.listbox.bind("<Delete>", self._remove_selected)

        right_panel = ttk.LabelFrame(body, text="Opciones de Reparación")
        right_panel.pack(side="right", fill="y")

        inner_right = ttk.Frame(right_panel)
        inner_right.pack(padx=20, pady=20, fill="both")

        ttk.Label(inner_right, text="Perfil de Limpieza:", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(0, 5))

        self.var_perfil = tk.StringVar(value="Vega Ponce (Columnas cruzadas + Obra)")
        opciones_perfil = [
            "Vega Ponce (Columnas cruzadas + Obra)",
            "DEGAZ (Extraer y vaciar en Molde 1)",
            "Gasolinera (Separar y asignar Cliente)",
            "DIEGZA / CLINNSA (Limpiar Conceptos Mezclados)",
            "Limpieza Básica (Próximamente)"
        ]
        self.cmb_perfil = ttk.Combobox(inner_right, textvariable=self.var_perfil, values=opciones_perfil,
                                       state="readonly", width=42)
        self.cmb_perfil.pack(fill="x", pady=(0, 5))
        self.cmb_perfil.bind("<<ComboboxSelected>>", self._on_perfil_change)

        # --- SUB-MENÚ GASOLINERAS ---
        self.frame_gasolinera = ttk.Frame(inner_right)
        ttk.Label(self.frame_gasolinera, text="↳ Selecciona la Sucursal:", font=("Segoe UI", 10, "italic")).pack(
            anchor="w", pady=(5, 2))
        self.var_cliente_gas = tk.StringVar(value="Las Campanas (SAC1212284C7)")
        self.cmb_cliente_gas = ttk.Combobox(self.frame_gasolinera, textvariable=self.var_cliente_gas,
                                            values=["Las Campanas (SAC1212284C7)", "AG Escobedo (SAE2107264V8)",
                                                    "AG Ancira (SAG950408LE8)"], state="readonly", width=40)
        self.cmb_cliente_gas.pack(fill="x")

        # --- SUB-MENÚ DIEGZA / CLINNSA ---
        self.frame_diegza = ttk.Frame(inner_right)
        ttk.Label(self.frame_diegza, text="↳ Selecciona el Cliente:", font=("Segoe UI", 10, "italic")).pack(anchor="w",
                                                                                                            pady=(5, 2))
        self.var_cliente_diegza = tk.StringVar(value="DIEGZA (DIE100730969)")
        self.cmb_cliente_diegza = ttk.Combobox(self.frame_diegza, textvariable=self.var_cliente_diegza,
                                               values=["DIEGZA (DIE100730969)", "CLINNSA (CLI180507CN5)"],
                                               state="readonly", width=40)
        self.cmb_cliente_diegza.pack(fill="x")

        self.lbl_ayuda = ttk.Label(inner_right, text="Asegúrate de elegir el perfil correcto para tu archivo.",
                                   style="Muted.TLabel")
        self.lbl_ayuda.pack(anchor="w", pady=(15, 20))

        self.btn_reparar = ttk.Button(inner_right, text="⚡ Reparar y Enviar al Visor", style="Primary.TButton",
                                      command=self._procesar_reparacion)
        self.btn_reparar.pack(side="bottom", fill="x", ipady=5)

    def _on_perfil_change(self, event=None):
        if "Gasolinera" in self.var_perfil.get():
            self.lbl_ayuda.pack_forget()
            self.frame_diegza.pack_forget()
            self.frame_gasolinera.pack(fill="x", pady=(5, 10))
            self.lbl_ayuda.pack(anchor="w", pady=(5, 20))
        elif "DIEGZA" in self.var_perfil.get():
            self.lbl_ayuda.pack_forget()
            self.frame_gasolinera.pack_forget()
            self.frame_diegza.pack(fill="x", pady=(5, 10))
            self.lbl_ayuda.pack(anchor="w", pady=(5, 20))
        else:
            self.frame_gasolinera.pack_forget()
            self.frame_diegza.pack_forget()
            self.lbl_ayuda.pack(anchor="w", pady=(15, 20))

    def _select_files(self):
        paths = filedialog.askopenfilenames(title="Selecciona archivos Excel dañados", filetypes=[("Excel", "*.xlsx")])
        if paths:
            for p in paths:
                if p not in self._paths:
                    self._paths.append(p)
            self._refresh_list()

    def _clear_files(self):
        self._paths.clear()
        self._refresh_list()

    def _remove_selected(self, event=None):
        sel = self.listbox.curselection()
        if not sel: return
        for idx in reversed(sel):
            self._paths.pop(int(idx))
        self._refresh_list()

    def _refresh_list(self):
        self.listbox.delete(0, tk.END)
        for p in self._paths:
            self.listbox.insert(tk.END, Path(p).name)

    def _procesar_reparacion(self):
        if not self._paths:
            messagebox.showwarning("Sin archivos", "Selecciona al menos un archivo para reparar.")
            return

        perfil = self.var_perfil.get()

        dlg = tk.Toplevel(self)
        dlg.title("Procesando")
        dlg.transient(self.winfo_toplevel())
        dlg.grab_set()
        dlg.resizable(False, False)

        pal = get_pal(self.controller)
        dlg.configure(bg=pal["BG"])

        wrap = ttk.Frame(dlg)
        wrap.pack(padx=20, pady=20)

        ttk.Label(wrap, text="Procesando archivos...", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        self.lbl_progreso = ttk.Label(wrap, text=f"Iniciando...", style="Muted.TLabel")
        self.lbl_progreso.pack(anchor="w", pady=(4, 10))
        pb = ttk.Progressbar(wrap, mode="indeterminate", length=300)
        pb.pack(fill="x")
        pb.start(10)

        dlg.update_idletasks()
        try:
            center_toplevel_on_parent(self.controller, dlg, 380, 140)
        except:
            pass

        def _update_status(texto):
            try:
                self.lbl_progreso.config(text=texto)
            except:
                pass

        def _worker():
            errores_totales = 0
            archivos_totales = []

            # EL CEREBRO: Elige el reparador correcto según el menú
            for i, ruta_str in enumerate(self._paths, start=1):
                self.controller.after(0, _update_status, f"Reparando: {Path(ruta_str).name} ({i}/{len(self._paths)})")

                try:
                    if "Vega Ponce" in perfil:
                        nuevos, errs = reparar_vega_ponce(ruta_str, perfil)
                    elif "DEGAZ" in perfil:
                        nuevos, errs = reparar_degaz(ruta_str, perfil)
                    elif "Gasolinera" in perfil:
                        nuevos, errs = reparar_gasolineras(ruta_str, perfil, self.var_cliente_gas.get())
                    elif "DIEGZA" in perfil:
                        nuevos, errs = reparar_diegza(ruta_str, self.var_cliente_diegza.get())
                    else:
                        continue  # Próximamente limpieza básica

                    archivos_totales.extend(nuevos)
                    errores_totales += errs
                except Exception as e:
                    print(f"Error procesando: {e}")
                    errores_totales += 1

            self.controller.after(0, lambda: self._terminar_reparacion(dlg, archivos_totales, errores_totales))

        threading.Thread(target=_worker, daemon=True).start()

    def _terminar_reparacion(self, dlg, archivos_corregidos, errores):
        try:
            dlg.grab_release()
            dlg.destroy()
        except:
            pass

        generados = len(archivos_corregidos)
        self.controller.set_status(f"Reparación completada: {generados} éxito, {errores} errores.")

        if generados > 0:
            self.controller.show("hacer")
            frame_hacer = self.controller.frames.get("hacer")
            if frame_hacer:
                frame_hacer._add_files(archivos_corregidos)

            messagebox.showinfo(
                "Archivos Nuevos",
                f"Proceso finalizado.\nSe crearon {generados} archivos listos para revisión en la bandeja principal."
            )
            self._clear_files()

        if errores > 0:
            messagebox.showerror("Aviso", f"Hubo problemas reparando {errores} archivos. Revisa la consola.")

    def _toggle_theme(self):
        self.controller.toggle_theme()

    def on_theme_changed(self):
        for widget in self.winfo_children():
            widget.destroy()
        self._build_ui()
