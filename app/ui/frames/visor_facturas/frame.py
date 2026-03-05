from __future__ import annotations

# --- stdlib ---
import re
import json
from collections import defaultdict
from typing import List, Dict, Optional

# --- tkinter / ttk ---
import tkinter as tk
from tkinter import ttk, messagebox

# --- base de datos ---
from app.database.database import SessionLocal, FacturaGuardada, ProveedorCredencial, encrypt_password

# --- modelos ---
from app.models import Factura, Cliente, DatosFactura, Concepto

# --- app core ---
from typing import TYPE_CHECKING

# --- theme / ui helpers ---
from app.ui.theme import get_pal, restyle_listbox

# --- dialogs ---
from app.ui.dialogs import ConfirmDialog

# --- Catalogs ---
from app.ui.frames.visor_facturas.catalogs import Catalogs

# --- Panels ---
from .panel_left import PanelLeft
from .panel_sheets import PanelSheets
from .panel_conceptos import PanelConceptos
from .panel_datos import PanelDatos

if TYPE_CHECKING:
    from app.ui.app import App


class VisorFacturasFrame(ttk.Frame):
    def __init__(self, master: ttk.Frame, controller: App, facturas: List[Factura]):
        super().__init__(master)
        self.controller = controller

        self._facturas: List[Factura] = []
        self._by_file: Dict[str, List[Factura]] = defaultdict(list)
        self._factura_sel: Optional[Factura] = None
        self._accordion_active: str = "conceptos"
        self._is_duplicate: bool = False

        # NUEVO: Rastreador para saber si estamos editando una factura que ya estaba en BD
        self._current_db_id = None

        self.catalogs = Catalogs()
        self.catalogs.load()

        self._default_col_widths = {
            "cantidad": 80, "clv_unid": 110, "unid_nombre": 260,
            "clv_prod": 150, "prod_nombre": 360, "concepto": 760, "p_unit": 260,
        }

        header = ttk.Frame(self)
        header.pack(fill="x", padx=12, pady=(12, 6))

        ttk.Button(header, text="☰", command=self._toggle_left_panel, width=3).pack(side="left")
        ttk.Button(header, text="← Volver", command=self._back).pack(side="left", padx=(8, 0))

        ttk.Button(header, text="Ir a Pendientes ➔", command=lambda: self.controller.show("pendientes")).pack(
            side="left", padx=(8, 0))

        ttk.Label(header, text="Visor de facturas", font=("Segoe UI", 14, "bold")).pack(side="left", padx=(12, 0))

        self.btn_theme = ttk.Button(header, text=self.controller.theme_button_label(), command=self._toggle_theme)
        self.btn_theme.pack(side="right")

        self.paned = ttk.Panedwindow(self, orient="horizontal")
        self.paned.pack(fill="both", expand=True, padx=12, pady=(6, 12))

        self.left = ttk.Frame(self.paned)
        self.right = ttk.Frame(self.paned)

        self.paned.add(self.left, weight=3)
        self.paned.add(self.right, weight=7)
        try:
            self.paned.paneconfigure(self.left, minsize=0)
            self.paned.paneconfigure(self.right, minsize=0)
        except Exception:
            pass

        self._left_visible = True
        self._left_last_sash = 420

        self._build_left()
        self._build_right()

        self.controller.after(50, self._collapse_left_on_start)
        self.set_facturas(facturas)

    def _collapse_left_on_start(self):
        try:
            self._left_visible = True
            self._toggle_left_panel(force_collapse=True)
        except Exception:
            pass

    def _toggle_left_panel(self, force_collapse: bool = False):
        try:
            self.controller.update_idletasks()
            if force_collapse or self._left_visible:
                try:
                    self._left_last_sash = int(self.paned.sashpos(0))
                except Exception:
                    self._left_last_sash = 520
                self.paned.sashpos(0, 1)
                self._left_visible = False
                self.controller.set_status("Panel de archivos oculto.", auto_clear_ms=1200)
            else:
                try:
                    total_w = max(1, int(self.paned.winfo_width()))
                except Exception:
                    total_w = 1200
                preferred = max(520, int(total_w * 0.35))
                target = int(self._left_last_sash or preferred)
                self.paned.sashpos(0, max(target, preferred))
                self._left_visible = True
                self.controller.set_status("Panel de archivos visible.", auto_clear_ms=1200)
        except Exception:
            pass

    def _back(self):
        self.controller.show("hacer")

    def _toggle_theme(self):
        self.controller.toggle_theme()

    def on_theme_changed(self):
        self.btn_theme.configure(text=self.controller.theme_button_label())
        restyle_listbox(self.controller, self.lst_archivos)

        try:
            if hasattr(self, "panel_sheets") and self.panel_sheets:
                self.panel_sheets.on_theme_changed()
            if hasattr(self, "panel_conceptos") and self.panel_conceptos:
                self.panel_conceptos.on_theme_changed()
        except Exception:
            pass

        self._refresh_accordion_styles()

        if hasattr(self, "panel_datos"):
            self.panel_datos._apply_text_theme()
            self.panel_datos._refresh_method_styles()

    def set_facturas(self, facturas: List[Factura]):
        self._facturas = list(facturas or [])
        self._by_file = defaultdict(list)
        for f in self._facturas:
            self._by_file[getattr(f, "archivo_origen", None) or "SIN_ARCHIVO"].append(f)

        if hasattr(self, "panel_left") and self.panel_left:
            self.panel_left.set_files(self._by_file)
            self.panel_left.autoselect_first()

    def _build_left(self):
        self.panel_left = PanelLeft(
            self.left,
            controller=self.controller,
            pal_getter=lambda: get_pal(self.controller),
            on_select=self._on_archivo_select,
        )
        self.panel_left.pack(fill="both", expand=True)
        self.lst_archivos = self.panel_left.lst_archivos

    def _build_right(self):
        top = ttk.Frame(self.right)
        top.pack(fill="x", padx=12, pady=(10, 6))

        self.lbl_header = ttk.Label(top, text="Archivo: —", font=("Segoe UI", 12, "bold"))
        self.lbl_header.pack(side="left")

        self.lbl_warn = ttk.Label(top, text="", font=("Segoe UI", 10, "bold"))
        self.lbl_warn.pack(side="left", padx=(10, 0))

        # --- BOTÓN APROBAR ---
        self.btn_aprobar = ttk.Button(
            top,
            text="Aprobar",
            style="Primary.TButton",
            command=self._aprobar_factura
        )
        self.btn_aprobar.pack(side="right")

        row = ttk.Frame(self.right)
        row.pack(fill="x", padx=12, pady=(0, 8))

        self.panel_sheets = PanelSheets(
            row, controller=self.controller, on_select_sheet=self._set_factura,
            get_by_file=lambda: self._by_file, get_facturas_list=lambda: self._facturas,
            refresh_left_panel=lambda: self.panel_left.set_files(self._by_file),
            autoselect_first_file=self.panel_left.autoselect_first,
        )
        self.panel_sheets.pack(side="left", fill="x", expand=True)

        ttk.Separator(self.right, orient="horizontal").pack(fill="x", padx=12, pady=(4, 12))

        self.acc = ttk.Frame(self.right)
        self.acc.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        hdr_row = ttk.Frame(self.acc)
        hdr_row.pack(fill="x", pady=(0, 10))

        self.btn_acc_datos = ttk.Button(
            hdr_row, text="Datos de factura", style="Tab.TButton", command=lambda: self._set_accordion("datos")
        )
        self.btn_acc_datos.pack(side="left", fill="x", expand=True)

        self.btn_acc_conc = ttk.Button(
            hdr_row, text="Conceptos", style="Tab.TButton", command=lambda: self._set_accordion("conceptos")
        )
        self.btn_acc_conc.pack(side="left", fill="x", expand=True, padx=(10, 0))

        self.panel_datos = PanelDatos(
            self.acc, controller=self.controller,
            get_factura=lambda: self._factura_sel, mark_saved=self._mark_saved
        )

        self.panel_conceptos = PanelConceptos(
            self.acc, controller=self.controller, catalogs=self.catalogs,
            get_factura=lambda: self._factura_sel, mark_saved=self._mark_saved,
            default_col_widths=self._default_col_widths,
        )

        self._set_accordion("conceptos", init=True)

    def _refresh_accordion_styles(self):
        self.btn_acc_datos.configure(style="TabSel.TButton" if self._accordion_active == "datos" else "Tab.TButton")
        self.btn_acc_conc.configure(style="TabSel.TButton" if self._accordion_active == "conceptos" else "Tab.TButton")

    def _pulse_active_header(self):
        active = self._accordion_active
        btn = self.btn_acc_datos if active == "datos" else self.btn_acc_conc
        normal_style = "TabSel.TButton"
        alt_style = "Tab.TButton"
        btn.configure(style=alt_style)
        self.after(60, lambda: btn.configure(style=normal_style))
        self.after(120, lambda: btn.configure(style=alt_style))
        self.after(180, lambda: btn.configure(style=normal_style))

    def _set_accordion(self, which: str, init: bool = False):
        self._accordion_active = which
        if which == "datos":
            self.panel_conceptos.pack_forget()
            self.panel_datos.pack(fill="x", pady=(0, 14))
        else:
            self.panel_datos.pack_forget()
            self.panel_conceptos.pack(fill="both", expand=True)

        self._refresh_accordion_styles()
        if not init:
            self._pulse_active_header()

    def focus_search(self):
        try:
            self._set_accordion("conceptos")
            if hasattr(self, "panel_conceptos") and self.panel_conceptos:
                self.panel_conceptos.focus_search()
        except Exception:
            pass

    def _mark_saved(self, msg: str = "Guardado"):
        self.controller.set_status(msg, auto_clear_ms=2000)

    def _update_sheet_buttons_state(self):
        has = bool(self._factura_sel)
        is_dup = getattr(self, "_is_duplicate", False)

        if hasattr(self, "btn_aprobar"):
            if has and not is_dup:
                self.btn_aprobar.state(["!disabled"])
            else:
                self.btn_aprobar.state(["disabled"])

        if hasattr(self, "btn_dup_sheet"): self.btn_dup_sheet.state(["!disabled"] if has else ["disabled"])
        if hasattr(self, "btn_del_sheet"): self.btn_del_sheet.state(["!disabled"] if has else ["disabled"])

    def _clear_view(self):
        # Limpiamos el ID de la base de datos para no mezclar ediciones
        self._current_db_id = None

        try:
            if hasattr(self, "panel_sheets") and self.panel_sheets: self.panel_sheets.clear()
            if hasattr(self, "panel_datos") and self.panel_datos: self.panel_datos.clear()
            if hasattr(self, "panel_conceptos") and self.panel_conceptos: self.panel_conceptos.clear()
        except Exception:
            pass

        self._factura_sel = None
        try:
            self.lbl_header.configure(text="Archivo: —")
        except Exception:
            pass
        try:
            self.lbl_warn.configure(text="")
        except Exception:
            pass
        try:
            self._update_sheet_buttons_state()
        except Exception:
            pass

    def _on_archivo_select(self, _evt=None):
        sel = self.lst_archivos.curselection()
        if not sel: return
        idx = sel[0]
        keys = self.panel_left.file_keys_sorted
        if idx < 0 or idx >= len(keys): return
        archivo_key = keys[idx]

        self.panel_sheets.render_for_file(archivo_key)
        facturas = self._by_file.get(archivo_key, [])
        if facturas:
            self._set_factura(sorted(facturas, key=lambda x: (getattr(x, "hoja_origen", "") or ""))[0])

    def _set_factura(self, fact: Factura):
        if fact is None:
            self._clear_view()
            return

        self._factura_sel = fact
        archivo = getattr(fact, "archivo_origen", None) or "SIN_ARCHIVO"
        hoja = getattr(fact, "hoja_origen", None) or ""

        try:
            if hoja:
                self.lbl_header.configure(text=f"Archivo: {archivo}  ·  Hoja: {hoja}")
            else:
                self.lbl_header.configure(text=f"Archivo: {archivo}")
        except Exception:
            pass

        # === VALIDACIÓN DE DUPLICIDAD ===
        db = SessionLocal()
        try:
            existe = db.query(FacturaGuardada).filter_by(archivo_origen=archivo, hoja_origen=hoja).first()
            if existe:
                # Si estamos editando esa misma factura, ignoramos la advertencia de duplicidad
                if self._current_db_id and self._current_db_id == existe.id:
                    self._is_duplicate = False
                    self.lbl_warn.configure(text="✏️ Editando Factura", foreground="#1976D2")
                else:
                    self._is_duplicate = True
                    pal = get_pal(self.controller)
                    self.lbl_warn.configure(text=f"⚠️ Ya en fila ({existe.estado})", foreground=pal["WARN"])
            else:
                self._is_duplicate = False
                self.lbl_warn.configure(text="")
        except Exception:
            self._is_duplicate = False
        finally:
            db.close()

        try:
            if hasattr(self, "panel_sheets") and self.panel_sheets:
                self.panel_sheets.set_active_factura(fact)
            if hasattr(self, "panel_datos") and self.panel_datos:
                self.panel_datos.cargar_datos(fact)
            if hasattr(self, "panel_conceptos") and self.panel_conceptos:
                self.panel_conceptos.set_factura(fact)
        except Exception:
            pass

        try:
            self._update_sheet_buttons_state()
        except Exception:
            pass

    def _file_key_for_fact(self, fact: Factura) -> str:
        return getattr(fact, "archivo_origen", None) or "SIN_ARCHIVO"

    # ========================================================
    # LÓGICA DE EDICIÓN INVERSA (De BD a Memoria)
    # ========================================================
    def cargar_edicion_bd(self, factura_id: int):
        """Reconstruye la factura desde la BD hacia el Visor."""
        db = SessionLocal()
        try:
            fact_db = db.query(FacturaGuardada).get(factura_id)
            if not fact_db: return

            self._current_db_id = fact_db.id

            # 1. Preparamos el Cliente ANTES de crear la factura
            c_obj = Cliente()
            c_obj.proveedor = fact_db.proveedor
            c_obj.rfc = fact_db.rfc_cliente

            # 2. Preparamos los DatosFactura ANTES de crear la factura
            df_obj = DatosFactura()
            df_obj.uso_cfdi = fact_db.uso_cfdi
            df_obj.metodo_pago = fact_db.metodo_pago
            df_obj.forma_pago = fact_db.forma_pago
            df_obj.usd = fact_db.es_usd
            df_obj.tipo_cambio = fact_db.tipo_cambio
            df_obj.sucursal = fact_db.sucursal
            df_obj.emitir_y_enviar = fact_db.emitir_y_enviar
            df_obj.info_extra = fact_db.notas_extra

            # 3. ¡EL FIX! Creamos la Factura entregándole sus datos obligatorios
            f = Factura(
                id=str(fact_db.id),
                cliente=c_obj,
                datos_factura=df_obj
            )
            # Y ahora sí le ponemos el resto
            f.archivo_origen = fact_db.archivo_origen
            f.hoja_origen = fact_db.hoja_origen
            f.total = fact_db.total

            # 4. Reconstruir Conceptos desde el JSON
            f.conceptos = []
            if fact_db.conceptos_json:
                conceptos_dict = json.loads(fact_db.conceptos_json)
                for cd in conceptos_dict:
                    # ¡EL FIX! Le damos al Concepto lo que exige desde que nace
                    c = Concepto(
                        cantidad=cd.get("cantidad"),
                        clave_unidad=cd.get("clave_unidad"),
                        clave_prod_serv=cd.get("clave_prod_serv"),
                        concepto=cd.get("descripcion"),  # Recuerda que mapeamos descripcion -> concepto
                        precio_unitario=cd.get("precio_unitario")
                    )
                    # Y le agregamos los datos opcionales/extra después
                    c.unidad = cd.get("unidad")
                    c.tipo_ps = cd.get("tipo_ps")

                    f.conceptos.append(c)

            # 5. Inyectar en la Interfaz Gráfica
            self._toggle_left_panel(force_collapse=True)
            self._set_factura(f)

            self.controller.set_status(f"Editando factura ID: {fact_db.id} ({fact_db.proveedor})",
                                       auto_clear_ms=4000)

        finally:
            db.close()

    # ========================================================
    # LÓGICA DE BASE DE DATOS Y APROBACIÓN
    # ========================================================
    def _aprobar_factura(self):
        fact = self._factura_sel
        if not fact: return

        try:
            # 1. Extracción súper segura del cliente
            cli = getattr(fact, "cliente", None)
            rfc = (getattr(cli, "rfc", "") or "").strip() if cli else ""

            if not rfc:
                messagebox.showwarning("Faltan datos", "El RFC es obligatorio para aprobar la factura.")
                return

            # 2. Extracción segura de conceptos
            conceptos_list = []
            for c in fact.conceptos:
                conceptos_list.append({
                    "cantidad": float(getattr(c, "cantidad", 0) or 0),
                    "clave_unidad": getattr(c, "clave_unidad", ""),
                    "unidad": getattr(c, "unidad", getattr(c, "unidad_medida", "")),
                    "clave_prod_serv": getattr(c, "clave_prod_serv", ""),
                    "descripcion": getattr(c, "concepto", getattr(c, "descripcion", "")),
                    "precio_unitario": float(getattr(c, "precio_unitario", getattr(c, "valor_unitario", 0)) or 0),
                    "tipo_ps": getattr(c, "tipo_ps", self.panel_conceptos._infer_ps(c)),
                })

            # 3. Guardado en Base de Datos
            db = SessionLocal()
            try:
                # Capturamos interfaz
                metodo_sel = self.panel_datos.var_metodo.get()
                forma_sel = self.panel_datos.var_forma.get()
                uso_sel = self.panel_datos.var_uso.get()
                usd_activo = self.panel_datos.var_usd.get()
                sucursal_sel = self.panel_datos.var_sucursal.get()
                emitir_sel = self.panel_datos.var_emitir_enviar.get()
                tc_valor = self.panel_datos.var_fx.get()
                notas_extra = self.panel_datos.txt_extra.get("1.0", "end-1c")

                prov_name = (getattr(cli, "proveedor", "") or "").strip() if cli else ""

                if getattr(self, "_current_db_id", None):
                    # ACTUALIZAR REGISTRO EXISTENTE
                    fact_update = db.query(FacturaGuardada).get(self._current_db_id)
                    if fact_update:
                        fact_update.rfc_cliente = rfc
                        fact_update.proveedor = prov_name
                        fact_update.metodo_pago = metodo_sel
                        fact_update.forma_pago = forma_sel
                        fact_update.uso_cfdi = uso_sel
                        fact_update.es_usd = bool(usd_activo)
                        fact_update.tipo_cambio = str(tc_valor) if tc_valor else None
                        fact_update.sucursal = sucursal_sel
                        fact_update.emitir_y_enviar = bool(emitir_sel)
                        fact_update.notas_extra = notas_extra
                        fact_update.total = float(getattr(fact, "total", 0.0) or 0.0)
                        fact_update.estado = "Pendiente"
                        fact_update.conceptos_json = json.dumps(conceptos_list, ensure_ascii=False)

                        db.commit()
                        self.controller.set_status(f"Factura ID {self._current_db_id} actualizada correctamente.",
                                                   auto_clear_ms=3000)

                        self._clear_view()
                        self.controller.show("pendientes")
                else:
                    # CREAR NUEVO REGISTRO
                    nueva_factura = FacturaGuardada(
                        archivo_origen=getattr(fact, "archivo_origen", "SIN_ARCHIVO"),
                        hoja_origen=getattr(fact, "hoja_origen", ""),
                        rfc_cliente=rfc,
                        proveedor=prov_name,
                        metodo_pago=metodo_sel,
                        forma_pago=forma_sel,
                        uso_cfdi=uso_sel,
                        es_usd=bool(usd_activo),
                        tipo_cambio=str(tc_valor) if tc_valor else None,
                        sucursal=sucursal_sel,
                        emitir_y_enviar=bool(emitir_sel),
                        total=float(getattr(fact, "total", 0.0) or 0.0),
                        notas_extra=notas_extra,
                        estado="Pendiente",
                        conceptos_json=json.dumps(conceptos_list, ensure_ascii=False)
                    )

                    db.add(nueva_factura)
                    db.commit()
                    self.controller.set_status("Factura aprobada y guardada en pendientes.", auto_clear_ms=3000)
                    self._remover_factura_memoria(fact)

            except Exception as e:
                db.rollback()
                messagebox.showerror("Error de BD", f"No se pudo guardar en la base de datos:\n{e}")
            finally:
                db.close()

        except Exception as ex_general:
            # ¡EL RASTREADOR DE ERRORES! Si algo falla en la memoria de Python, lo atrapamos aquí.
            import traceback
            error_trace = traceback.format_exc()
            print(error_trace)  # Lo mandamos a consola
            messagebox.showerror("Error Crítico de Datos",
                                 f"El programa chocó antes de guardar. Detalle:\n\n{str(ex_general)}")

    def _remover_factura_memoria(self, fact: Factura):
        archivo_key = self._file_key_for_fact(fact)

        if archivo_key in self._by_file and fact in self._by_file[archivo_key]:
            self._by_file[archivo_key].remove(fact)
            if not self._by_file[archivo_key]:
                del self._by_file[archivo_key]

        if fact in self._facturas:
            self._facturas.remove(fact)

        if hasattr(self, "panel_left") and self.panel_left:
            self.panel_left.set_files(self._by_file)

        if archivo_key in self._by_file:
            self.panel_sheets.render_for_file(archivo_key)
            self._set_factura(self._by_file[archivo_key][0])
        else:
            if self._by_file:
                self.panel_left.autoselect_first()
            else:
                self._clear_view()
                self.controller.show("pendientes")
