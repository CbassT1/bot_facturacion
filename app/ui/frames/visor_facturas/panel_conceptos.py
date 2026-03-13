from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Callable, Dict, List, Optional, Tuple
import tkinter as tk
from tkinter import ttk
from tkinter import font as tkfont

from app.ui.theme import get_pal
from app.ui.widgets.scrollbars import ModernScrollbar
from app.models import Factura, Concepto
from app.ui.frames.visor_facturas.catalogs import Catalogs

# --- IMPORTAMOS LOS NUEVOS MODALES ---
from app.ui.frames.visor_facturas.dialogs_conceptos import EditCellDialog, SearchKeyDialog


class PanelConceptos(ttk.Frame):
    def __init__(
            self, master: ttk.Frame, *, controller, catalogs: Catalogs,
            get_factura: Callable[[], Optional[Factura]],
            mark_saved: Callable[[str], None],
            default_col_widths: Optional[Dict[str, int]] = None,
    ):
        super().__init__(master)
        self.controller = controller
        self.catalogs = catalogs
        self._get_factura = get_factura
        self._mark_saved = mark_saved

        self._default_col_widths = default_col_widths or {
            "cantidad": 80, "tipo_ps": 50, "clv_unid": 110, "unid_nombre": 260,
            "clv_prod": 150, "prod_nombre": 360, "concepto": 760, "p_unit": 260,
        }

        self.var_search = tk.StringVar(value="")
        self._conceptos_cache: List[Concepto] = []
        self._tree_item_to_concepto: Dict[str, Concepto] = {}

        self._tree_ctx_menu = None
        self._ctx_iid = None
        self._ctx_col = None
        self._concept_clipboard: List[Concepto] = []

        self._build()

    def _infer_ps(self, c: Concepto) -> str:
        if hasattr(c, "tipo_ps") and getattr(c, "tipo_ps"):
            return getattr(c, "tipo_ps")

        clv_unid = (getattr(c, "clave_unidad", "") or "").upper()
        clv_prod = str(getattr(c, "clave_prod_serv", "") or "")

        if clv_unid in ["E48", "ACT"] or clv_prod.startswith(("8", "9")):
            return "S"
        return "P"

    def _build(self):
        head = ttk.Frame(self)
        head.pack(fill="x", pady=(0, 8))

        ttk.Label(head, text="Buscar", style="Muted.TLabel").pack(side="left")
        self.ent_search = ttk.Entry(head, textvariable=self.var_search, width=36)
        self.ent_search.pack(side="left", padx=(10, 10))
        self.ent_search.bind("<KeyRelease>", lambda _e: self._apply_filter())

        ttk.Button(head, text="Reset columnas", command=self._reset_columns).pack(side="right")

        self.frm_conceptos = ttk.Frame(self)
        self.frm_conceptos.pack(fill="both", expand=True)
        self.frm_conceptos.columnconfigure(0, weight=1)
        self.frm_conceptos.rowconfigure(0, weight=1)

        cols = ("cantidad", "tipo_ps", "clv_unid", "unid_nombre", "clv_prod", "prod_nombre", "concepto", "p_unit")
        self.tree = ttk.Treeview(self.frm_conceptos, columns=cols, show="headings", selectmode="browse",
                                 style="Concepts.Treeview")

        self.tree.heading("cantidad", text="Cant.")
        self.tree.heading("tipo_ps", text="P/S")
        self.tree.heading("clv_unid", text="Clave unid.")
        self.tree.heading("unid_nombre", text="Unidad (nombre)")
        self.tree.heading("clv_prod", text="Clave prod/serv")
        self.tree.heading("prod_nombre", text="Prod/serv (nombre)")
        self.tree.heading("concepto", text="Concepto")
        self.tree.heading("p_unit", text="Precio unitario")

        self.tree["displaycolumns"] = cols
        for k, w in [("cantidad", 80), ("tipo_ps", 50), ("clv_unid", 110), ("clv_prod", 150), ("p_unit", 220)]:
            self.tree.column(k, width=w, stretch=False,
                             anchor="center" if "clv" in k or k == "tipo_ps" else ("e" if k == "p_unit" else "w"))

        self.tree.column("unid_nombre", width=240, stretch=False, anchor="w")
        self.tree.column("prod_nombre", width=320, stretch=False, anchor="w")
        self.tree.column("concepto", width=520, minwidth=260, stretch=True, anchor="w")

        try:
            if getattr(self.controller, "_settings", None):
                self.apply_tree_col_widths(self.controller._settings.tree_col_widths)
        except Exception:
            pass

        pal_getter = lambda: get_pal(self.controller)

        self.vsb_conceptos = ModernScrollbar(self.frm_conceptos, orient="vertical", command=self.tree.yview,
                                             pal_getter=pal_getter, thickness=12, pad=6)
        self.hsb_conceptos = ModernScrollbar(self.frm_conceptos, orient="horizontal", command=self.tree.xview,
                                             pal_getter=pal_getter, thickness=12, pad=6)

        self.tree.configure(yscrollcommand=self.vsb_conceptos.set, xscrollcommand=self.hsb_conceptos.set)
        self.tree.grid(row=0, column=0, sticky="nsew", padx=2, pady=(2, 0))
        self.vsb_conceptos.grid(row=0, column=1, sticky="ns", pady=(2, 0))
        self.hsb_conceptos.grid(row=1, column=0, sticky="ew", padx=2, pady=(0, 6))

        detail = ttk.Frame(self.frm_conceptos)
        detail.grid(row=2, column=0, columnspan=2, sticky="ew", padx=8, pady=(2, 6))
        detail.columnconfigure(1, weight=1)

        ttk.Label(detail, text="Concepto (completo):", style="Muted.TLabel").grid(row=0, column=0, sticky="nw",
                                                                                  padx=(0, 8))
        self.lbl_concepto_full = ttk.Label(detail, text="—", wraplength=980, justify="left")
        self.lbl_concepto_full.grid(row=0, column=1, sticky="ew")

        ttk.Label(detail, text="Precio unitario:", style="Muted.TLabel").grid(row=1, column=0, sticky="w", pady=(6, 0),
                                                                              padx=(0, 8))
        self.lbl_precio_full = ttk.Label(detail, text="—", font=("Segoe UI", 11, "bold"))
        self.lbl_precio_full.grid(row=1, column=1, sticky="w", pady=(6, 0))

        footer = ttk.Frame(self.frm_conceptos)
        footer.grid(row=3, column=0, columnspan=2, sticky="ew", padx=8, pady=(0, 6))
        self.lbl_total = ttk.Label(footer, text="TOTAL: —", font=("Segoe UI", 14, "bold"))
        self.lbl_total.pack(side="right")

        self.tree.bind("<Double-1>", self._on_tree_double_click)
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.tree.bind("<Button-3>", self._on_tree_right_click)

        self._apply_tree_tags_theme()

    def clear(self):
        self._conceptos_cache = []
        self.var_search.set("")
        self._tree_item_to_concepto.clear()
        for it in self.tree.get_children(): self.tree.delete(it)
        self._set_detail("—", "—")
        self.lbl_total.config(text="TOTAL: —")

    def set_factura(self, fact: Optional[Factura]):
        if not fact:
            self.clear()
            return
        conceptos = list(getattr(fact, "conceptos", []) or [])
        self._conceptos_cache = conceptos
        self._render_conceptos(conceptos)
        self._recalc_factura_total_from_conceptos()

    def focus_search(self):
        self.ent_search.focus_set()
        self.ent_search.select_range(0, tk.END)

    def on_theme_changed(self):
        self._apply_tree_tags_theme()
        if hasattr(self, "vsb_conceptos"): self.vsb_conceptos.refresh_theme()
        if hasattr(self, "hsb_conceptos"): self.hsb_conceptos.refresh_theme()

    def apply_tree_col_widths(self, widths: Dict[str, int]):
        if not widths: return
        for k, w in widths.items():
            if k in self.tree["columns"]:
                self.tree.column(k, width=int(w))

    def _reset_columns(self):
        for k, w in self._default_col_widths.items():
            self.tree.column(k, width=w)
        self.controller.set_status("Columnas restablecidas.", auto_clear_ms=1500)

    def _render_conceptos(self, conceptos: List[Concepto]):
        for it in self.tree.get_children(): self.tree.delete(it)
        self._tree_item_to_concepto.clear()

        for idx, c in enumerate(conceptos):
            tag = "even" if idx % 2 == 0 else "odd"
            iid = f"c{idx}"
            clv_unid = getattr(c, "clave_unidad", "") or ""
            clv_prod = getattr(c, "clave_prod_serv", "") or ""
            p_unit = getattr(c, "precio_unitario", None)

            values = (
                getattr(c, "cantidad", ""),
                self._infer_ps(c),
                clv_unid,
                self.catalogs.unid_name(clv_unid),
                clv_prod,
                self.catalogs.prod_name(clv_prod),
                getattr(c, "concepto", "") or "",
                self.catalogs.num_to_full_str(p_unit),
            )
            self.tree.insert("", "end", iid=iid, values=values, tags=(tag,))
            self._tree_item_to_concepto[iid] = c

        self._autofit_columns(("unid_nombre", "prod_nombre", "p_unit"), max_px=520, min_px=140)

    def _apply_filter(self):
        q = (self.var_search.get() or "").strip().lower()
        if not q:
            self._render_conceptos(self._conceptos_cache)
            return

        filtered = []
        for c in self._conceptos_cache:
            hay = f"{getattr(c, 'concepto', '')} {getattr(c, 'clave_prod_serv', '')} {getattr(c, 'clave_unidad', '')} {getattr(c, 'precio_unitario', '')}".lower()
            if q in hay:
                filtered.append(c)

        self._render_conceptos(filtered)
        self.controller.set_status(f"Filtro: {len(filtered)} coincidencias.", auto_clear_ms=1500)

    def _apply_tree_tags_theme(self):
        pal = get_pal(self.controller)
        self.tree.tag_configure("odd", background=pal["ROW_ALT"])
        self.tree.tag_configure("even", background=pal["SURFACE"])

    def _autofit_columns(self, col_ids: Tuple[str, ...], *, max_px: int = 520, min_px: int = 90, padding: int = 26):
        try:
            measure = tkfont.nametofont("TkDefaultFont").measure
        except Exception:
            measure = lambda s: len(str(s)) * 8

        for col in col_ids:
            max_w = measure(self.tree.heading(col, option="text")) + padding
            for iid in self.tree.get_children(""):
                vals = self.tree.item(iid, "values") or ()
                idx = self.tree["columns"].index(col)
                if idx < len(vals):
                    w = measure(str(vals[idx])) + padding
                    if w > max_w: max_w = w
            self.tree.column(col, width=max(min_px, min(int(max_w), max_px)))

    def _on_tree_select(self, _event=None):
        sel = self.tree.selection()
        if not sel:
            self._set_detail("—", "—")
            return
        vals = self.tree.item(sel[0], "values") or ()
        cols = list(self.tree["columns"])

        concepto = str(vals[cols.index("concepto")]).strip() if "concepto" in cols else "—"
        precio = str(vals[cols.index("p_unit")]).strip() if "p_unit" in cols else "—"
        self._set_detail(concepto or "—", precio or "—")

    def _set_detail(self, concepto: str, precio: str):
        try:
            self.lbl_concepto_full.configure(wraplength=max(520, self.frm_conceptos.winfo_width() - 160))
        except Exception:
            pass
        self.lbl_concepto_full.configure(text=concepto)
        self.lbl_precio_full.configure(text=precio)

    # -------------- Edit cell (REFACTORIZADO CON DIALOGOS EXTERNOS) --------------
    def _parse_decimal(self, s: str) -> Optional[Decimal]:
        s = (s or "").strip().replace(",", "")
        if not s: return None
        try:
            return Decimal(s)
        except InvalidOperation:
            return None

    def _sanitize_key_alnum(self, s: str, maxlen: int = 18) -> str:
        return re.sub(r"[^A-Z0-9]", "", (s or "").upper().strip())[:maxlen]

    def _on_tree_double_click(self, event):
        region = self.tree.identify("region", event.x, event.y)
        if region != "cell": return

        col = self.tree.identify_column(event.x)
        row_id = self.tree.identify_row(event.y)
        if not row_id: return

        idx = int(col[1:]) - 1
        disp = self.tree["displaycolumns"] if self.tree["displaycolumns"] != ("#all",) else self.tree["columns"]
        col_id = disp[idx]

        if col_id in ("unid_nombre", "prod_nombre"): return

        concepto_obj = self._tree_item_to_concepto.get(str(row_id))
        if not concepto_obj: return

        if col_id == "tipo_ps":
            nuevo_valor = "P" if self._infer_ps(concepto_obj) == "S" else "S"
            concepto_obj.tipo_ps = nuevo_valor
            self._refresh_tree_row_from_model(row_id, concepto_obj)
            self._mark_saved(f"Cambiado a {'Producto' if nuevo_valor == 'P' else 'Servicio'}")
            return

        map_col = {
            "cantidad": ("Cantidad", "cantidad", "qty"),
            "clv_unid": ("Clave unidad (SAT)", "clave_unidad", "key_unid"),
            "clv_prod": ("Clave prod/serv", "clave_prod_serv", "key_prod"),
            "concepto": ("Concepto", "concepto", "text"),
            "p_unit": ("Precio unitario", "precio_unitario", "money"),
        }
        if col_id not in map_col: return

        label, attr, mode = map_col[col_id]
        current = getattr(concepto_obj, attr, "")
        current_str = self.catalogs.num_to_full_str(current) if mode in ("money", "qty") else (
            str(current) if current is not None else "")

        def _save_callback(val: str):
            if mode == "qty" or mode == "money":
                dec = self._parse_decimal(val)
                if dec is None:
                    self.controller.set_status(f"Valor invalido para {label}.", auto_clear_ms=1500)
                    return
                setattr(concepto_obj, attr, float(dec))
            elif mode == "key_unid":
                setattr(concepto_obj, attr, self._sanitize_key_alnum(val, maxlen=6))
            elif mode == "key_prod":
                setattr(concepto_obj, attr, self._sanitize_key_alnum(val, maxlen=18))
            else:
                setattr(concepto_obj, attr, val)

            self._refresh_tree_row_from_model(row_id, concepto_obj)
            self._recalc_factura_total_from_conceptos()
            self._mark_saved("Concepto actualizado")

        EditCellDialog(self, self.controller, label, current_str, mode, self.catalogs, _save_callback)

    def _refresh_tree_row_from_model(self, row_id: str, c: Concepto):
        clv_unid = getattr(c, "clave_unidad", "") or ""
        clv_prod = getattr(c, "clave_prod_serv", "") or ""
        vals = (
            getattr(c, "cantidad", ""), self._infer_ps(c),
            clv_unid, self.catalogs.unid_name(clv_unid),
            clv_prod, self.catalogs.prod_name(clv_prod),
            getattr(c, "concepto", "") or "",
            self.catalogs.num_to_full_str(getattr(c, "precio_unitario", None)),
        )
        self.tree.item(row_id, values=vals)

    def _recalc_factura_total_from_conceptos(self):
        f = self._get_factura()
        if not f: return
        subtotal = sum((float(getattr(c, "cantidad", 0) or 0) * float(
            getattr(c, "precio_unitario", getattr(c, "valor_unitario", 0)) or 0)) for c in
                       getattr(f, "conceptos", []) or [])
        nuevo_total = subtotal * 1.16
        f.total = nuevo_total
        self.lbl_total.config(text=f"TOTAL (+ 16% IVA): ${nuevo_total:,.2f}")

    # -------------- Context menu --------------
    def _build_tree_context_menu(self):
        if self._tree_ctx_menu is not None: return
        self._tree_ctx_menu = tk.Menu(self, tearoff=False)
        self._tree_ctx_menu.add_command(label="Copiar", command=self._ctx_copy_rows)
        self._tree_ctx_menu.add_command(label="Cortar", command=self._ctx_cut_rows)
        self._tree_ctx_menu.add_command(label="Pegar (despues)", command=self._ctx_paste_after)
        self._tree_ctx_menu.add_command(label="Pegar (al final)", command=self._ctx_paste_end)
        self._tree_ctx_menu.add_separator()
        self._tree_ctx_menu.add_command(label="Duplicar fila(s)", command=self._ctx_duplicate_rows)
        self._tree_ctx_menu.add_command(label="Eliminar fila(s)", command=self._ctx_delete_rows)
        self._tree_ctx_menu.add_separator()
        self._tree_ctx_menu.add_command(label="Buscar clave", command=self._ctx_search_key)

    def _on_tree_right_click(self, event):
        self._build_tree_context_menu()
        iid = self.tree.identify_row(event.y)
        col = self.tree.identify_column(event.x)
        self._ctx_col = list(self.tree["columns"])[int(col[1:]) - 1] if col and col.startswith("#") else None

        if iid and iid not in self.tree.selection():
            self.tree.selection_set(iid)
            self.tree.focus(iid)

        self._ctx_iid = iid or None
        has_sel = bool(self.tree.selection())
        can_paste = bool(self._concept_clipboard)
        is_key_col = self._ctx_col in ("clv_unid", "clv_prod")

        for label, cond in [("Copiar", has_sel), ("Cortar", has_sel), ("Duplicar fila(s)", has_sel),
                            ("Eliminar fila(s)", has_sel), ("Pegar (despues)", can_paste and has_sel),
                            ("Pegar (al final)", can_paste), ("Buscar clave", is_key_col and has_sel)]:
            self._tree_ctx_menu.entryconfigure(label, state="normal" if cond else "disabled")

        self._tree_ctx_menu.tk_popup(event.x_root, event.y_root)

    def _clone_concepto(self, c: Concepto) -> Concepto:
        cc = Concepto()
        for k in ("cantidad", "clave_unidad", "clave_prod_serv", "concepto", "precio_unitario", "importe", "tipo_ps"):
            if hasattr(c, k): setattr(cc, k, getattr(c, k))
        return cc

    def _selected_conceptos(self) -> List[Tuple[str, Concepto]]:
        return [(iid, self._tree_item_to_concepto[iid]) for iid in (self.tree.selection() or []) if
                iid in self._tree_item_to_concepto]

    def _refresh_conceptos_view(self, msg: str = "Conceptos actualizados"):
        f = self._get_factura()
        if not f: return
        self._conceptos_cache = list(getattr(f, "conceptos", []) or [])
        self._apply_filter()
        self._recalc_factura_total_from_conceptos()
        self._mark_saved(msg)

    def _ctx_copy_rows(self):
        sel = self._selected_conceptos()
        if not sel: return
        self._concept_clipboard = [self._clone_concepto(c) for _, c in sel]
        self.controller.set_status(f"Copiado: {len(self._concept_clipboard)} fila(s)", auto_clear_ms=1500)

    def _ctx_cut_rows(self):
        self._ctx_copy_rows()
        self._ctx_delete_rows()

    def _ctx_delete_rows(self):
        f = self._get_factura()
        if not f or not (sel := self._selected_conceptos()): return
        to_remove = {id(c) for _, c in sel}
        f.conceptos = [c for c in getattr(f, "conceptos", []) if id(c) not in to_remove]
        self._refresh_conceptos_view("Fila(s) eliminada(s)")

    def _ctx_duplicate_rows(self):
        f = self._get_factura()
        if not f or not (sel := self._selected_conceptos()): return
        conceptos = list(getattr(f, "conceptos", []) or [])
        id_to_idx = {id(c): i for i, c in enumerate(conceptos)}
        idxs = [i for i in sorted(id_to_idx.get(id(c), -1) for _, c in sel) if i >= 0]
        if not idxs: return
        insert_at = max(idxs) + 1
        f.conceptos = conceptos[:insert_at] + [self._clone_concepto(c) for _, c in sel] + conceptos[insert_at:]
        self._refresh_conceptos_view("Fila(s) duplicada(s)")

    def _ctx_paste_after(self):
        f = self._get_factura()
        if not f or not self._concept_clipboard or not (sel := self._selected_conceptos()): return
        anchor = self._tree_item_to_concepto.get(str(self.tree.focus() or sel[0][0]))
        conceptos = list(getattr(f, "conceptos", []) or [])
        insert_at = {id(c): i for i, c in enumerate(conceptos)}.get(id(anchor), len(conceptos)) + 1 if anchor else len(
            conceptos)
        f.conceptos = conceptos[:insert_at] + [self._clone_concepto(c) for c in self._concept_clipboard] + conceptos[
            insert_at:]
        self._refresh_conceptos_view("Pegado")

    def _ctx_paste_end(self):
        f = self._get_factura()
        if not f or not self._concept_clipboard: return
        f.conceptos = list(getattr(f, "conceptos", []) or []) + [self._clone_concepto(c) for c in
                                                                 self._concept_clipboard]
        self._refresh_conceptos_view("Pegado")

    def _ctx_search_key(self):
        sel = self._selected_conceptos()
        if not sel: return
        iid = str(self.tree.focus() or sel[0][0])
        c = self._tree_item_to_concepto.get(iid)

        target = "unidad" if self._ctx_col == "clv_unid" else ("prodserv" if self._ctx_col == "clv_prod" else None)
        if not target or not c: return

        def _on_key_selected(new_key: str):
            if target == "unidad":
                c.clave_unidad = new_key
            else:
                c.clave_prod_serv = new_key
            self._refresh_tree_row_from_model(iid, c)
            self._mark_saved("Clave actualizada")

        current = getattr(c, "clave_unidad" if target == "unidad" else "clave_prod_serv", "") or ""
        SearchKeyDialog(self, self.controller, target, current, self.catalogs, _on_key_selected)
