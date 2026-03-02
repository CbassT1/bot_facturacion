# app/ui/frames/visor_facturas/panel_datos.py
from __future__ import annotations

import re
import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional

from app.models import Factura, Cliente, DatosFactura
from app.ui.theme import get_pal
from app.ui.constants import PROVEEDORES_OPCIONES, USO_CFDI_OPCIONES, FORMA_PAGO_OPCIONES


class PanelDatos(ttk.Frame):
    def __init__(
            self,
            master: ttk.Frame,
            *,
            controller,
            get_factura: Callable[[], Optional[Factura]],
            mark_saved: Callable[[str], None],
    ):
        super().__init__(master)
        self.controller = controller
        self.get_factura = get_factura
        self._mark_saved_cb = mark_saved

        self._build_ui()

    def _build_ui(self):
        card = ttk.Frame(self, style="Card.TFrame")
        card.pack(fill="x", padx=0, pady=0)

        inner = ttk.Frame(card, style="CardInner.TFrame")
        inner.pack(fill="x", padx=14, pady=14)
        pal = get_pal(self.controller)

        # Variables
        self.var_manual_user = tk.StringVar(value="")
        self.var_manual_pass = tk.StringVar(value="")
        self.var_usd = tk.BooleanVar(value=False)
        self.var_fx = tk.StringVar(value="")
        self.var_extra = tk.BooleanVar(value=False)
        self.var_saved = tk.StringVar(value="")
        self.var_rfc_msg = tk.StringVar(value="")
        self.var_fx_msg = tk.StringVar(value="")
        self.var_emitir_enviar = tk.BooleanVar(value=False)

        # Fila 0: Proveedor / RFC
        ttk.Label(inner, text="Proveedor", style="Muted.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 10),
                                                                      pady=(0, 8))
        self.var_proveedor = tk.StringVar(value="")
        self.cmb_proveedor = ttk.Combobox(inner, textvariable=self.var_proveedor, values=PROVEEDORES_OPCIONES,
                                          state="readonly", width=22)
        self.cmb_proveedor.grid(row=0, column=1, sticky="w", pady=(0, 8))
        self.cmb_proveedor.bind("<<ComboboxSelected>>", self._on_proveedor_change)
        self._hook_combobox(self.cmb_proveedor)

        ttk.Label(inner, text="RFC", style="Muted.TLabel").grid(row=0, column=2, sticky="w", padx=(24, 10), pady=(0, 8))
        self.var_rfc = tk.StringVar(value="")
        self.ent_rfc = ttk.Entry(inner, textvariable=self.var_rfc, width=22)
        self.ent_rfc.grid(row=0, column=3, sticky="w", pady=(0, 8))
        self.ent_rfc.bind("<KeyRelease>", self._on_rfc_live)
        self.ent_rfc.bind("<FocusOut>", self._on_rfc_change)

        self.lbl_rfc_msg = ttk.Label(inner, textvariable=self.var_rfc_msg, style="Muted.TLabel")
        self.lbl_rfc_msg.grid(row=0, column=4, sticky="w", padx=(10, 0), pady=(0, 8))

        # Fila 1: Uso CFDI / Metodo / Sucursal
        ttk.Label(inner, text="Uso CFDI", style="Muted.TLabel").grid(row=1, column=0, sticky="w", padx=(0, 10),
                                                                     pady=(0, 8))
        self.var_uso = tk.StringVar(value="")
        self.cmb_uso = ttk.Combobox(inner, textvariable=self.var_uso, values=USO_CFDI_OPCIONES, state="readonly",
                                    width=8)
        self.cmb_uso.grid(row=1, column=1, sticky="w", pady=(0, 8))
        self.cmb_uso.bind("<<ComboboxSelected>>", self._on_uso_change)
        self._hook_combobox(self.cmb_uso)

        self.var_sucursal = tk.StringVar(value="")
        self.lbl_sucursal = ttk.Label(inner, text="Sucursal", style="Muted.TLabel")
        self.cmb_sucursal = ttk.Combobox(inner, textvariable=self.var_sucursal, values=("Monterrey", "Guadalajara"),
                                         state="readonly", width=12)
        self.lbl_sucursal.grid(row=1, column=4, sticky="w", padx=(24, 10), pady=(0, 8))
        self.cmb_sucursal.grid(row=1, column=5, sticky="w", pady=(0, 8))
        self.cmb_sucursal.bind("<<ComboboxSelected>>", self._on_sucursal_change)
        self._hook_combobox(self.cmb_sucursal)

        ttk.Label(inner, text="Método", style="Muted.TLabel").grid(row=1, column=2, sticky="w", padx=(24, 10),
                                                                   pady=(0, 8))
        self.var_metodo = tk.StringVar(value="PUE")
        self.method_frame = ttk.Frame(inner, style="CardInner.TFrame")
        self.method_frame.grid(row=1, column=3, sticky="w", pady=(0, 8))

        # AQUI SE APLICA EL ESTILO ILUMINADO Tab/TabSel a PUE y PPD
        btn_pue = ttk.Button(self.method_frame, text="PUE", style="Tab.TButton",
                             command=lambda: self._set_metodo("PUE"))
        btn_ppd = ttk.Button(self.method_frame, text="PPD", style="Tab.TButton",
                             command=lambda: self._set_metodo("PPD"))
        btn_pue.pack(side="left", padx=(0, 8))
        btn_ppd.pack(side="left")
        self._method_buttons = {"PUE": btn_pue, "PPD": btn_ppd}

        # Fila 2: Forma de pago
        ttk.Label(inner, text="Forma de pago", style="Muted.TLabel").grid(row=2, column=0, sticky="w", padx=(0, 10),
                                                                          pady=(0, 8))
        self.var_forma = tk.StringVar(value="")
        self.cmb_forma = ttk.Combobox(inner, textvariable=self.var_forma, values=FORMA_PAGO_OPCIONES, state="readonly",
                                      width=44)
        self.cmb_forma.grid(row=2, column=1, columnspan=3, sticky="w", pady=(0, 8))
        self.cmb_forma.bind("<<ComboboxSelected>>", self._on_forma_change)
        self._hook_combobox(self.cmb_forma)

        # Fila 3: USD y Tipo de cambio
        self.chk_usd = tk.Checkbutton(
            inner, text="Factura en dólares (USD)", variable=self.var_usd, command=self._update_usd_fields,
            font=("Segoe UI", 10, "bold"), bg=pal["BG"], fg=pal["MUTED"],
            activebackground=pal["BG"], activeforeground=pal["TEXT"], selectcolor=pal["BG"], highlightthickness=1, bd=0,
        )
        self.chk_usd.grid(row=3, column=0, sticky="w", pady=(4, 8))

        self.fx_wrap = ttk.Frame(inner, style="CardInner.TFrame")
        self.fx_wrap.grid(row=3, column=1, sticky="w", pady=(4, 8))
        ttk.Label(self.fx_wrap, text="Tipo de cambio", style="Muted.TLabel").pack(side="left", padx=(0, 10))
        self.ent_fx = ttk.Entry(self.fx_wrap, textvariable=self.var_fx, width=12)
        self.ent_fx.pack(side="left")
        self.ent_fx.bind("<KeyRelease>", self._on_fx_live)
        self.ent_fx.bind("<FocusOut>", self._on_fx_change)
        self.lbl_fx_msg = ttk.Label(self.fx_wrap, textvariable=self.var_fx_msg, style="Muted.TLabel")
        self.lbl_fx_msg.pack(side="left", padx=(10, 0))

        # Fila 4: Extra info y Emitir/Enviar
        self.chk_extra = tk.Checkbutton(
            inner, text="Agregar información extra", variable=self.var_extra, command=self._update_extra_fields,
            font=("Segoe UI", 10, "bold"), bg=pal["BG"], fg=pal["MUTED"],
            activebackground=pal["BG"], activeforeground=pal["TEXT"], selectcolor=pal["BG"], highlightthickness=1, bd=0,
        )
        self.chk_extra.grid(row=4, column=0, sticky="w", pady=(0, 8))

        self.chk_emitir_enviar = tk.Checkbutton(
            inner, text="Emitir y enviar esta factura", variable=self.var_emitir_enviar,
            command=self._on_emitir_enviar_change,
            font=("Segoe UI", 11, "bold"), bg=pal["BG"], fg=pal["TEXT"],
            activebackground=pal["BG"], activeforeground=pal["TEXT"], selectcolor=pal["BG"], highlightthickness=1, bd=0,
        )
        self.chk_emitir_enviar.grid(row=4, column=3, columnspan=3, sticky="e", padx=(40, 0), pady=(0, 8))

        # Extra info
        self.extra_wrap = ttk.Frame(inner, style="CardInner.TFrame")
        self.extra_wrap.grid(row=5, column=0, columnspan=4, sticky="ew", pady=(0, 8))
        ttk.Label(self.extra_wrap, text="Notas", style="Muted.TLabel").pack(anchor="w")
        self.txt_extra = tk.Text(self.extra_wrap, height=4, wrap="word", font=("Segoe UI", 11), bd=0,
                                 highlightthickness=1)
        self.txt_extra.pack(fill="x", expand=True, pady=(6, 0))
        self.txt_extra.bind("<FocusOut>", lambda _e: self._mark_saved("Notas actualizadas"))

        # Manual wrap
        self.manual_wrap = ttk.Frame(inner, style="CardInner.TFrame")
        self.manual_wrap.grid(row=6, column=0, columnspan=4, sticky="ew", pady=(6, 0))
        ttk.Label(self.manual_wrap, text="Usuario", style="Muted.TLabel").grid(row=1, column=0, sticky="w",
                                                                               padx=(0, 10), pady=(0, 8))
        self.ent_manual_user = ttk.Entry(self.manual_wrap, textvariable=self.var_manual_user, width=22)
        self.ent_manual_user.grid(row=1, column=1, sticky="w", pady=(0, 8))
        self.ent_manual_user.bind("<FocusOut>", lambda _e: self._mark_saved("Usuario actualizado"))

        ttk.Label(self.manual_wrap, text="Contraseña", style="Muted.TLabel").grid(row=1, column=2, sticky="w",
                                                                                  padx=(24, 10), pady=(0, 8))
        self.ent_manual_pass = ttk.Entry(self.manual_wrap, textvariable=self.var_manual_pass, width=22, show="•")
        self.ent_manual_pass.grid(row=1, column=3, sticky="w", pady=(0, 8))
        self.ent_manual_pass.bind("<FocusOut>", lambda _e: self._mark_saved("Contraseña actualizada"))

        self.lbl_saved = ttk.Label(inner, textvariable=self.var_saved, style="Muted.TLabel")
        self.lbl_saved.grid(row=0, column=5, sticky="e", padx=(18, 0), pady=(0, 8))

        inner.columnconfigure(3, weight=1)
        inner.columnconfigure(4, weight=1)
        inner.columnconfigure(5, weight=1)

        self._refresh_method_styles()
        self._update_provider_manual_fields()
        self._update_usd_fields()
        self._update_extra_fields()
        self._apply_text_theme()
        self._on_rfc_live()
        self._on_fx_live()
        self._refresh_toggle_colors()

    # ====== LÓGICA DE CONTROL ======
    def _mark_saved(self, msg: str = "Guardado"):
        self.var_saved.set("Guardado")
        if self._mark_saved_cb:
            self._mark_saved_cb(msg)
        self.after(1200, lambda: self.var_saved.set(""))

    def _ensure_cliente(self, fact):
        if getattr(fact, "cliente", None) is None:
            fact.cliente = Cliente()

    def _ensure_datos(self, fact):
        if getattr(fact, "datos_factura", None) is None:
            fact.datos_factura = DatosFactura()

    def _apply_text_theme(self):
        pal = get_pal(self.controller)
        try:
            self.txt_extra.configure(
                bg=pal["SURFACE2"], fg=pal["TEXT"], insertbackground=pal["TEXT"],
                selectbackground=pal["ACCENT2"], selectforeground=pal["TEXT"],
                highlightbackground=pal["BORDER"], highlightcolor=pal["ACCENT"],
            )
        except Exception:
            pass
        self._refresh_toggle_colors()

    def _refresh_toggle_colors(self):
        pal = get_pal(self.controller)

        def _style_chk(chk, var, is_primary=False):
            if chk is None: return
            selected = bool(var.get())
            fg = pal["SUCCESS"] if is_primary and selected else (pal["ACCENT"] if selected else pal["MUTED"])
            border = pal["ACCENT"] if selected else pal["BG"]
            chk.configure(bg=pal["BG"], fg=fg, activebackground=pal["BG"], activeforeground=fg, highlightthickness=1,
                          highlightbackground=border, highlightcolor=border)

        _style_chk(self.chk_usd, self.var_usd, is_primary=False)
        _style_chk(self.chk_extra, self.var_extra, is_primary=False)
        _style_chk(self.chk_emitir_enviar, self.var_emitir_enviar, is_primary=True)

    def _tint_combobox_popdown_for(self, combo: ttk.Combobox):
        pal = get_pal(self.controller)
        try:
            pop = combo.tk.eval(f"ttk::combobox::PopdownWindow {str(combo)}")
            lb_path = f"{pop}.f.l"
            lb = self.controller.nametowidget(lb_path)
            lb.configure(bg=pal["SURFACE"], fg=pal["TEXT"], selectbackground=pal["ACCENT2"],
                         selectforeground=pal["TEXT"], highlightbackground=pal["BORDER"], highlightthickness=1,
                         relief="flat", bd=0)
        except Exception:
            pass

    def _hook_combobox(self, combo: ttk.Combobox):
        combo.bind("<Button-1>", lambda _e: self.controller.after(20, lambda: self._tint_combobox_popdown_for(combo)),
                   add="+")
        combo.bind("<KeyRelease-Down>",
                   lambda _e: self.controller.after(20, lambda: self._tint_combobox_popdown_for(combo)), add="+")
        combo.bind("<KeyRelease-Return>",
                   lambda _e: self.controller.after(20, lambda: self._tint_combobox_popdown_for(combo)), add="+")

    def _refresh_method_styles(self):
        active = (self.var_metodo.get().strip() or "PUE")
        for k, btn in self._method_buttons.items():
            btn.configure(style="TabSel.TButton" if k == active else "Tab.TButton")

    def _set_metodo(self, metodo: str):
        self.var_metodo.set(metodo)
        self._refresh_method_styles()
        self._on_metodo_change()
        self._mark_saved("Método actualizado")

    # ====== VALIDACIONES ======
    def _sanitize_rfc_alnum(self, s: str) -> str:
        s = (s or "").upper()
        s = re.sub(r"[^A-Z0-9]", "", s)
        return s[:13]

    def _is_rfc_len_ok(self, s: str) -> bool:
        n = len(s)
        return (n == 0) or (n == 12) or (n == 13)

    def _sanitize_fx_numeric(self, s: str) -> str:
        s = (s or "").replace(",", "").strip()
        out = []
        dot_used = False
        for ch in s:
            if ch.isdigit():
                out.append(ch)
            elif ch == "." and not dot_used:
                out.append(ch); dot_used = True
        return "".join(out)

    def _fx_format_ok(self, s: str) -> bool:
        if not s: return False
        return re.match(r"^\d+(\.\d+)?$", s) is not None

    # ====== EVENTOS UI ======
    def _update_provider_manual_fields(self):
        sel = (self.var_proveedor.get() or "").strip().lower()
        if sel == "otro":
            self.manual_wrap.grid()
        else:
            self.manual_wrap.grid_remove()

    def _update_usd_fields(self):
        if self.var_usd.get():
            self.fx_wrap.grid()
            self._on_fx_live()
            self._mark_saved("Marcado: Factura en dólares")
        else:
            self.fx_wrap.grid_remove()
            self.var_fx.set("")
            self.var_fx_msg.set("")
            try:
                self.ent_fx.configure(style="TEntry")
            except Exception:
                pass
            self._mark_saved("Desmarcado: Factura en dólares")
        self._refresh_toggle_colors()

    def _update_sucursal_visibility(self):
        prov = (self.var_proveedor.get() or "").strip().lower()
        if prov in ("xisisa", "viesa"):
            self.lbl_sucursal.grid()
            self.cmb_sucursal.grid()
            if not (self.var_sucursal.get() or "").strip(): self.var_sucursal.set("Monterrey")
        else:
            self.lbl_sucursal.grid_remove()
            self.cmb_sucursal.grid_remove()
            self.var_sucursal.set("")
            fact = self.get_factura()
            if fact and getattr(fact, "datos_factura", None) is not None:
                fact.datos_factura.sucursal = None

    def _update_extra_fields(self):
        if self.var_extra.get():
            self.extra_wrap.grid()
            self._mark_saved("Marcado: Información extra")
        else:
            self.extra_wrap.grid_remove()
            try:
                self.txt_extra.delete("1.0", "end")
            except Exception:
                pass
            self._mark_saved("Desmarcado: Información extra")
        self._refresh_toggle_colors()

    def _on_rfc_live(self, _evt=None):
        raw = self.var_rfc.get()
        clean = self._sanitize_rfc_alnum(raw)
        if clean != raw: self.var_rfc.set(clean)
        ok = self._is_rfc_len_ok(clean)
        try:
            self.ent_rfc.configure(style="TEntry" if ok else "Error.TEntry")
        except Exception:
            pass
        self.var_rfc_msg.set("RFC debe tener 12 o 13." if clean and not ok else "")

    def _on_fx_live(self, _evt=None):
        if not self.var_usd.get():
            self.var_fx_msg.set("")
            try:
                self.ent_fx.configure(style="TEntry")
            except Exception:
                pass
            return
        raw = self.var_fx.get()
        clean = self._sanitize_fx_numeric(raw)
        if clean != raw: self.var_fx.set(clean)
        if not clean:
            self.var_fx_msg.set("")
            try:
                self.ent_fx.configure(style="TEntry")
            except Exception:
                pass
            return
        ok = self._fx_format_ok(clean)
        try:
            self.ent_fx.configure(style="TEntry" if ok else "Warn.TEntry")
        except Exception:
            pass
        self.var_fx_msg.set("" if ok else "Solo números y decimales.")

    # ====== CAMBIOS EN MODELO ======
    def _on_rfc_change(self, _evt=None):
        fact = self.get_factura()
        if not fact: return
        rfc = (self.var_rfc.get() or "").strip()
        ok = self._is_rfc_len_ok(rfc)
        try:
            self.ent_rfc.configure(style="TEntry" if ok else "Error.TEntry")
        except Exception:
            pass
        self._ensure_cliente(fact)
        fact.cliente.rfc = rfc
        self._mark_saved("RFC actualizado" if ok else "RFC inválido")

    def _on_fx_change(self, _evt=None):
        if not self.var_usd.get():
            return

        val = (self.var_fx.get() or "").strip()
        ok = self._fx_format_ok(val)

        if ok:
            try:
                self.ent_fx.configure(style="TEntry")
            except Exception:
                pass

            # Actualizamos el modelo
            fact = self.get_factura()
            if fact:
                self._ensure_datos(fact)
                fact.datos_factura.tipo_cambio = val

            self._mark_saved("Tipo de cambio actualizado")
        else:
            try:
                self.ent_fx.configure(style="Warn.TEntry")
            except Exception:
                pass
            self.controller.set_status("Tipo de cambio inválido (solo números y decimales).", auto_clear_ms=3500)

    def _on_proveedor_change(self, _evt=None):
        self._update_provider_manual_fields()
        self._update_sucursal_visibility()
        fact = self.get_factura()
        if not fact: return
        self._ensure_cliente(fact)
        fact.cliente.proveedor = self.var_proveedor.get().strip()
        self._mark_saved("Proveedor actualizado")

    def _on_uso_change(self, _evt=None):
        fact = self.get_factura()
        if not fact: return
        self._ensure_datos(fact)
        fact.datos_factura.uso_cfdi = self.var_uso.get().strip()
        self._mark_saved("Uso CFDI actualizado")

    def _on_metodo_change(self):
        fact = self.get_factura()
        if not fact: return
        self._ensure_datos(fact)
        fact.datos_factura.metodo_pago = self.var_metodo.get().strip()

    def _on_forma_change(self, _evt=None):
        fact = self.get_factura()
        if not fact: return
        self._ensure_datos(fact)
        fact.datos_factura.forma_pago = self.var_forma.get().strip()
        self._mark_saved("Forma de pago actualizada")

    def _on_emitir_enviar_change(self, _evt=None):
        fact = self.get_factura()
        if not fact: return
        self._ensure_datos(fact)
        fact.datos_factura.emitir_y_enviar = bool(self.var_emitir_enviar.get())
        self._mark_saved("Opción 'emitir y enviar' actualizada")
        self._refresh_toggle_colors()

    def _on_sucursal_change(self, _evt=None):
        fact = self.get_factura()
        if not fact: return
        self._ensure_datos(fact)
        fact.datos_factura.sucursal = (self.var_sucursal.get() or "").strip() or None
        self._mark_saved("Sucursal actualizada")

    # ====== CARGA Y LIMPIEZA ======
    def cargar_datos(self, fact: Factura):
        cli = getattr(fact, "cliente", None)
        dat = getattr(fact, "datos_factura", None)

        self.var_proveedor.set((getattr(cli, "proveedor", "") or "").strip())
        self.var_rfc.set((getattr(cli, "rfc", "") or "").strip())
        self.var_uso.set((getattr(dat, "uso_cfdi", "") or "").strip())
        self.var_metodo.set((getattr(dat, "metodo_pago", "PUE") or "PUE").strip() or "PUE")
        self.var_forma.set((getattr(dat, "forma_pago", "") or "").strip())

        try:
            self.var_sucursal.set((getattr(dat, "sucursal", "") or "").strip())
        except Exception:
            pass

        try:
            self.var_emitir_enviar.set(bool(getattr(dat, "emitir_y_enviar", False)))
        except Exception:
            self.var_emitir_enviar.set(False)

        try:
            is_usd = bool(getattr(dat, "usd", False))
        except Exception:
            is_usd = False
        self.var_usd.set(is_usd)

        try:
            fx_val = getattr(dat, "tipo_cambio", "") or ""
        except Exception:
            fx_val = ""
        self.var_fx.set("" if fx_val is None else str(fx_val).strip())

        try:
            extra_txt = getattr(dat, "info_extra", "") or ""
            extra_on = bool(extra_txt.strip())
        except Exception:
            extra_txt = ""
            extra_on = False

        self.var_extra.set(extra_on)
        try:
            self.txt_extra.delete("1.0", "end")
            if extra_txt: self.txt_extra.insert("1.0", extra_txt)
        except Exception:
            pass

        self._refresh_method_styles()
        self._update_provider_manual_fields()
        self._update_sucursal_visibility()
        self._update_usd_fields()
        self._update_extra_fields()
        self._on_rfc_live()
        self._on_fx_live()

    def clear(self):
        self.var_proveedor.set("")
        self.var_rfc.set("")
        self.var_uso.set("")
        self.var_metodo.set("PUE")
        self._refresh_method_styles()
        self.var_forma.set("")
        self.var_sucursal.set("")
        self.var_manual_user.set("")
        self.var_manual_pass.set("")
        self.var_emitir_enviar.set(False)
        self.var_usd.set(False)
        self.var_fx.set("")
        self.var_fx_msg.set("")
        self.var_extra.set(False)
        try:
            self.txt_extra.delete("1.0", "end")
        except Exception:
            pass

        self._update_provider_manual_fields()
        self._update_sucursal_visibility()
        self._update_usd_fields()
        self._update_extra_fields()
        self._on_rfc_live()
        self._on_fx_live()