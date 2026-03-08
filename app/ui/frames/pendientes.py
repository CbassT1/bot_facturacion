# app/ui/frames/pendientes.py
import tkinter as tk
from tkinter import ttk, messagebox
from app.database.database import SessionLocal, FacturaGuardada
from app.ui.theme import get_pal
import threading
from app.automation.bot import ejecutar_bot


class PendientesFrame(ttk.Frame):
    def __init__(self, master, controller):
        super().__init__(master)
        self.controller = controller
        self._build_ui()

    def _build_ui(self):
        pal = get_pal(self.controller)

        # --- Cabecera ---
        header = ttk.Frame(self)
        header.pack(fill="x", padx=12, pady=(12, 6))

        ttk.Button(header, text="← Menú Principal", command=lambda: self.controller.show("menu")).pack(side="left",
                                                                                                       padx=(8, 0))
        ttk.Label(header, text="Centro de Emisión y Registros", font=("Segoe UI", 16, "bold")).pack(side="left",
                                                                                                    padx=(12, 0))

        self.btn_iniciar = ttk.Button(header, text="▶ Iniciar Bot", style="Primary.TButton", command=self._iniciar_bot)
        self.btn_iniciar.pack(side="right")

        # ========================================================
        # NOTEBOOK (PESTAÑAS)
        # ========================================================
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=12, pady=(10, 15))

        # --- PESTAÑA 1: FILA DE TRABAJO ---
        self.tab_pend = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_pend, text="Fila de Trabajo (Pendientes)")

        # --- PESTAÑA 2: HISTORIAL ---
        self.tab_hist = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_hist, text="Historial (Terminadas)")

        self._build_tab_pendientes(pal)
        self._build_tab_historial(pal)

    # ========================================================
    # INTERFAZ: FILA DE TRABAJO
    # ========================================================
    def _build_tab_pendientes(self, pal):
        # Barra de herramientas superior
        toolbar = ttk.Frame(self.tab_pend)
        toolbar.pack(fill="x", padx=10, pady=(10, 5))

        self.lbl_resumen_pend = ttk.Label(toolbar, text="Cargando resumen...", font=("Segoe UI", 11, "bold"))
        self.lbl_resumen_pend.pack(side="left")

        ttk.Button(toolbar, text="Limpiar Fila", command=self._limpiar_pendientes).pack(side="right")

        # Tabla
        self.tree_pend_frame = ttk.Frame(self.tab_pend)
        self.tree_pend_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        cols = ("id", "archivo", "hoja", "proveedor", "rfc", "total", "modo", "estado")
        self.tree_pend = ttk.Treeview(self.tree_pend_frame, columns=cols, show="headings", style="Treeview",
                                      selectmode="extended")

        self.tree_pend.heading("id", text="ID")
        self.tree_pend.heading("archivo", text="Archivo Origen")
        self.tree_pend.heading("hoja", text="Hoja")
        self.tree_pend.heading("proveedor", text="Proveedor")
        self.tree_pend.heading("rfc", text="RFC Cliente")
        self.tree_pend.heading("total", text="Total")
        self.tree_pend.heading("modo", text="Modo")
        self.tree_pend.heading("estado", text="Estado")

        self.tree_pend.column("id", width=50, anchor="center")
        self.tree_pend.column("archivo", width=180)
        self.tree_pend.column("hoja", width=100)
        self.tree_pend.column("proveedor", width=150)
        self.tree_pend.column("rfc", width=120, anchor="center")
        self.tree_pend.column("total", width=100, anchor="e")
        self.tree_pend.column("modo", width=100, anchor="center")
        self.tree_pend.column("estado", width=120, anchor="center")

        self.tree_pend.tag_configure("odd", background=pal["ROW_ALT"])
        self.tree_pend.tag_configure("even", background=pal["SURFACE"])

        self.tree_pend.pack(fill="both", expand=True, side="left")

        scrollbar = ttk.Scrollbar(self.tree_pend_frame, orient="vertical", command=self.tree_pend.yview)
        self.tree_pend.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")

        # Menú Contextual
        self.menu_pend = tk.Menu(self, tearoff=0)
        self.menu_pend.add_command(label="Editar / Devolver al Visor", command=self._editar_factura)
        self.menu_pend.add_command(label="Alternar Modo (Auto/Manual)", command=self._alternar_modo)
        self.menu_pend.add_separator()
        self.menu_pend.add_command(label="Eliminar seleccionadas",
                                   command=lambda: self._eliminar_seleccionadas(self.tree_pend))

        self.tree_pend.bind("<Button-3>", lambda e: self._show_menu(e, self.tree_pend, self.menu_pend))

        def _drag_select_pend(event):
            item = self.tree_pend.identify_row(event.y)
            if item:
                self.tree_pend.selection_add(item)

        self.tree_pend.bind("<B1-Motion>", _drag_select_pend)

    # ========================================================
    # INTERFAZ: HISTORIAL
    # ========================================================
    def _build_tab_historial(self, pal):
        toolbar = ttk.Frame(self.tab_hist)
        toolbar.pack(fill="x", padx=10, pady=(10, 5))

        self.lbl_resumen_hist = ttk.Label(toolbar, text="Cargando historial...", font=("Segoe UI", 11, "bold"))
        self.lbl_resumen_hist.pack(side="left")

        ttk.Button(toolbar, text="Vaciar Historial", command=self._limpiar_historial).pack(side="right")

        self.tree_hist_frame = ttk.Frame(self.tab_hist)
        self.tree_hist_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        cols = ("id", "archivo", "proveedor", "rfc", "total", "modo", "estado")
        self.tree_hist = ttk.Treeview(self.tree_hist_frame, columns=cols, show="headings", style="Treeview",
                                      selectmode="extended")

        self.tree_hist.heading("id", text="ID")
        self.tree_hist.heading("archivo", text="Archivo Origen")
        self.tree_hist.heading("proveedor", text="Proveedor")
        self.tree_hist.heading("rfc", text="RFC Cliente")
        self.tree_hist.heading("total", text="Total")
        self.tree_hist.heading("modo", text="Modo (Cómo se ejecutó)")
        self.tree_hist.heading("estado", text="Resultado")

        self.tree_hist.column("id", width=50, anchor="center")
        self.tree_hist.column("archivo", width=180)
        self.tree_hist.column("proveedor", width=150)
        self.tree_hist.column("rfc", width=120, anchor="center")
        self.tree_hist.column("total", width=100, anchor="e")
        self.tree_hist.column("modo", width=150, anchor="center")
        self.tree_hist.column("estado", width=150, anchor="center")

        self.tree_hist.tag_configure("odd", background=pal["ROW_ALT"])
        self.tree_hist.tag_configure("even", background=pal["SURFACE"])

        self.tree_hist.pack(fill="both", expand=True, side="left")

        scrollbar = ttk.Scrollbar(self.tree_hist_frame, orient="vertical", command=self.tree_hist.yview)
        self.tree_hist.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")

        self.menu_hist = tk.Menu(self, tearoff=0)
        self.menu_hist.add_command(label="Eliminar del registro",
                                   command=lambda: self._eliminar_seleccionadas(self.tree_hist))

        self.tree_hist.bind("<Button-3>", lambda e: self._show_menu(e, self.tree_hist, self.menu_hist))

        def _drag_select_hist(event):
            item = self.tree_hist.identify_row(event.y)
            if item:
                self.tree_hist.selection_add(item)

        self.tree_hist.bind("<B1-Motion>", _drag_select_hist)

    # ========================================================
    # LÓGICA DE DATOS
    # ========================================================
    def refresh_data(self):
        for item in self.tree_pend.get_children(): self.tree_pend.delete(item)
        for item in self.tree_hist.get_children(): self.tree_hist.delete(item)

        db = SessionLocal()
        try:
            facturas = db.query(FacturaGuardada).all()

            p_dinero, p_count = 0.0, 0
            h_count = 0

            for f in facturas:
                modo_texto = "Automático" if getattr(f, "emitir_y_enviar", False) else "Manual"
                estado = f.estado or ""

                # Clasificamos: Si es Emitida o Borrador va al historial. Si no, va a pendientes.
                es_historial = "Emitida" in estado or "Borrador" in estado

                if es_historial:
                    tag = "even" if h_count % 2 == 0 else "odd"
                    self.tree_hist.insert("", "end", iid=str(f.id), values=(
                        f.id, getattr(f, "archivo_origen", "-"), getattr(f, "proveedor", ""),
                        getattr(f, "rfc_cliente", ""), f"${f.total:,.2f}" if f.total else "$0.00",
                        modo_texto, estado
                    ), tags=(tag,))
                    h_count += 1
                else:
                    tag = "even" if p_count % 2 == 0 else "odd"
                    self.tree_pend.insert("", "end", iid=str(f.id), values=(
                        f.id, getattr(f, "archivo_origen", "-"), getattr(f, "hoja_origen", "-"),
                        getattr(f, "proveedor", ""), getattr(f, "rfc_cliente", ""),
                        f"${f.total:,.2f}" if f.total else "$0.00", modo_texto, estado
                    ), tags=(tag,))
                    p_count += 1
                    if f.total: p_dinero += f.total

            pal = get_pal(self.controller)
            self.lbl_resumen_pend.configure(
                text=f"En fila: {p_count} facturas   |   Total a procesar: ${p_dinero:,.2f}", foreground=pal["ACCENT"])
            self.lbl_resumen_hist.configure(text=f"Facturas procesadas históricas: {h_count}", foreground=pal["MUTED"])

        finally:
            db.close()

    # ========================================================
    # ACCIONES DE MENÚ Y BOTONES
    # ========================================================
    def _show_menu(self, event, tree, menu):
        iid = tree.identify_row(event.y)
        if iid:
            if iid not in tree.selection():
                tree.selection_set(iid)
            menu.post(event.x_root, event.y_root)

    def _eliminar_seleccionadas(self, tree):
        sel = tree.selection()
        if not sel: return

        if messagebox.askyesno("Eliminar", f"¿Eliminar definitivamente {len(sel)} registro(s) de la base de datos?"):
            db = SessionLocal()
            try:
                for item_id in sel:
                    f = db.query(FacturaGuardada).get(int(item_id))
                    if f: db.delete(f)
                db.commit()
            finally:
                db.close()
            self.refresh_data()

    def _limpiar_pendientes(self):
        if messagebox.askyesno("Limpiar Fila",
                               "ADVERTENCIA: ¿Vaciar toda la Fila de Trabajo? (El historial no se borrará)."):
            db = SessionLocal()
            try:
                # Borramos solo las que no son historial
                db.query(FacturaGuardada).filter(
                    FacturaGuardada.estado.not_in(["Emitida", "Completada (Borrador)"])).delete(
                    synchronize_session=False)
                db.commit()
            finally:
                db.close()
            self.refresh_data()

    def _limpiar_historial(self):
        if messagebox.askyesno("Limpiar Historial",
                               "¿Estás seguro de borrar todo el historial de facturas procesadas?"):
            db = SessionLocal()
            try:
                db.query(FacturaGuardada).filter(
                    FacturaGuardada.estado.in_(["Emitida", "Completada (Borrador)"])).delete(synchronize_session=False)
                db.commit()
            finally:
                db.close()
            self.refresh_data()

    def _alternar_modo(self):
        sel = self.tree_pend.selection()
        if not sel: return

        db = SessionLocal()
        try:
            for item_id in sel:
                f = db.query(FacturaGuardada).get(int(item_id))
                if f:
                    f.emitir_y_enviar = not getattr(f, "emitir_y_enviar", False)
            db.commit()
        finally:
            db.close()
        self.refresh_data()

    def _editar_factura(self):
        sel = self.tree_pend.selection()
        if not sel: return
        factura_id = int(sel[0])

        visor_frame = None
        visor_key = None
        for key, frame in self.controller.frames.items():
            if type(frame).__name__ == "VisorFacturasFrame":
                visor_frame = frame
                visor_key = key
                break

        if visor_frame:
            try:
                visor_frame.cargar_edicion_bd(factura_id)
                self.controller.show(visor_key)
            except Exception as e:
                import traceback
                print(traceback.format_exc())
                messagebox.showerror("Error de Edición", f"Chocó al cargar: {str(e)}")
        else:
            messagebox.showerror("Error", "No se encontró el Visor.")

    # ========================================================
    # LÓGICA DEL BOT
    # ========================================================
    def _iniciar_bot(self):
        db = SessionLocal()
        try:
            # Solo enviamos al bot las que NO están en el historial
            pendientes = db.query(FacturaGuardada).filter(
                FacturaGuardada.estado.not_in(["Emitida", "Completada (Borrador)"])).all()
            ids = [f.id for f in pendientes]
        finally:
            db.close()

        if not ids:
            messagebox.showinfo("Aviso", "No hay facturas en la Fila de Trabajo para procesar.")
            return

        self.btn_iniciar.state(["disabled"])

        def _log(mensaje):
            self.controller.after(0, lambda: self.lbl_resumen_pend.configure(text=f"Bot: {mensaje}"))

        def _worker():
            import asyncio
            asyncio.set_event_loop(asyncio.new_event_loop())
            ejecutar_bot(ids, _log)
            self.controller.after(0, self._on_bot_finished)

        threading.Thread(target=_worker, daemon=True).start()

    def _on_bot_finished(self):
        self.btn_iniciar.state(["!disabled"])
        self.refresh_data()
        messagebox.showinfo("Completado", "El bot terminó. Las facturas completadas se movieron al Historial.")
