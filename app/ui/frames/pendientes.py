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

        ttk.Button(header, text="Menú Principal", command=lambda: self.controller.show("menu")).pack(side="left",
                                                                                                     padx=(8, 0))

        ttk.Label(header, text="Fila de Espera (Centro de Emisión)", font=("Segoe UI", 16, "bold")).pack(side="left",
                                                                                                         padx=(12, 0))

        self.btn_iniciar = ttk.Button(header, text="Iniciar Bot (Playwright)", style="Primary.TButton",
                                      command=self._iniciar_bot)
        self.btn_iniciar.pack(side="right")

        # NUEVO: Botón para vaciar toda la lista
        self.btn_limpiar = ttk.Button(header, text="Limpiar Lista", command=self._limpiar_lista)
        self.btn_limpiar.pack(side="right", padx=(0, 10))

        # --- Barra de Resumen (Dashboard) ---
        resumen_frame = ttk.Frame(self, style="Card.TFrame")
        resumen_frame.pack(fill="x", padx=12, pady=(0, 10))

        inner_res = ttk.Frame(resumen_frame, style="CardInner.TFrame")
        inner_res.pack(fill="x", padx=14, pady=10)

        self.lbl_resumen = ttk.Label(inner_res, text="Cargando resumen...", font=("Segoe UI", 12, "bold"))
        self.lbl_resumen.pack(side="left")

        # --- Contenedor de la Tabla ---
        self.tree_frame = ttk.Frame(self)
        self.tree_frame.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        cols = ("id", "archivo", "hoja", "proveedor", "rfc", "total", "modo", "estado")
        # selectmode="extended" permite arrastrar o usar Shift/Ctrl para multi-selección
        self.tree = ttk.Treeview(self.tree_frame, columns=cols, show="headings", style="Treeview",
                                 selectmode="extended")

        self.tree.heading("id", text="ID")
        self.tree.heading("archivo", text="Archivo Origen")
        self.tree.heading("hoja", text="Hoja")
        self.tree.heading("proveedor", text="Proveedor")
        self.tree.heading("rfc", text="RFC Cliente")
        self.tree.heading("total", text="Total a Emitir")
        self.tree.heading("modo", text="Modo de Ejecución")
        self.tree.heading("estado", text="Estado Actual")

        self.tree.column("id", width=50, anchor="center")
        self.tree.column("archivo", width=180)
        self.tree.column("hoja", width=120)
        self.tree.column("proveedor", width=150)
        self.tree.column("rfc", width=120, anchor="center")
        self.tree.column("total", width=100, anchor="e")
        self.tree.column("modo", width=120, anchor="center")
        self.tree.column("estado", width=120, anchor="center")

        self.tree.tag_configure("odd", background=pal["ROW_ALT"])
        self.tree.tag_configure("even", background=pal["SURFACE"])

        self.tree.pack(fill="both", expand=True, side="left")

        scrollbar = ttk.Scrollbar(self.tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")

        # --- Menú Contextual (Clic Derecho) ---
        self.menu = tk.Menu(self, tearoff=0)
        self.menu.add_command(label="Editar / Devolver al Visor", command=self._editar_factura)
        self.menu.add_command(label="Alternar Modo (Auto/Manual)", command=self._alternar_modo)
        self.menu.add_separator()
        self.menu.add_command(label="Eliminar seleccionadas", command=self._eliminar_factura)

        self.tree.bind("<Button-3>", self._show_menu)
        self.tree.bind("<B1-Motion>", self._on_drag_select)

    def refresh_data(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        db = SessionLocal()
        try:
            facturas = db.query(FacturaGuardada).all()
            total_dinero = 0.0
            pendientes_count = 0

            for index, f in enumerate(facturas):
                modo = "Automático" if f.es_automatica else "Manual"
                estado_display = f.estado

                tag = "even" if index % 2 == 0 else "odd"

                if f.estado == "Pendiente":
                    pendientes_count += 1
                    if f.total:
                        total_dinero += f.total

                self.tree.insert("", "end", iid=str(f.id), values=(
                    f.id,
                    f.archivo_origen,
                    f.hoja_origen or "-",
                    f.proveedor,
                    f.rfc_cliente,
                    f"${f.total:,.2f}" if f.total else "$0.00",
                    modo,
                    estado_display
                ), tags=(tag,))

            pal = get_pal(self.controller)
            self.lbl_resumen.configure(
                text=f"Facturas en espera: {pendientes_count}   |   Suma total a procesar: ${total_dinero:,.2f}",
                foreground=pal["ACCENT"]
            )

        finally:
            db.close()

    def _show_menu(self, event):
        iid = self.tree.identify_row(event.y)
        if iid:
            # Lógica inteligente: Si haces clic derecho en un elemento que NO está seleccionado,
            # borra la selección actual y selecciona solo ese.
            # Pero si haces clic derecho en uno de los varios que ya sombreaste, mantiene la selección múltiple.
            if iid not in self.tree.selection():
                self.tree.selection_set(iid)
            self.menu.post(event.x_root, event.y_root)

    def _on_drag_select(self, event):
        """Permite seleccionar múltiples filas al mantener el clic presionado y arrastrar."""
        item = self.tree.identify_row(event.y)
        if item:
            # Agrega la fila sobre la que pasa el ratón a la selección actual
            self.tree.selection_add(item)

    def _eliminar_factura(self):
        sel = self.tree.selection()
        if not sel: return

        cantidad = len(sel)
        mensaje = f"¿Estás seguro de eliminar las {cantidad} facturas seleccionadas de la fila?" if cantidad > 1 else "¿Estás seguro de eliminar esta factura de la fila?"

        if messagebox.askyesno("Eliminar", mensaje):
            db = SessionLocal()
            try:
                for item_id in sel:
                    f = db.query(FacturaGuardada).get(int(item_id))
                    if f:
                        db.delete(f)
                db.commit()
            finally:
                db.close()
            self.refresh_data()

    def _limpiar_lista(self):
        # Función maestra para borrar toda la tabla
        if messagebox.askyesno("Limpiar Lista",
                               "ADVERTENCIA: ¿Estás seguro de vaciar toda la fila de espera? Esto eliminará todos los registros actuales."):
            db = SessionLocal()
            try:
                db.query(FacturaGuardada).delete()
                db.commit()
            finally:
                db.close()
            self.refresh_data()

    def _alternar_modo(self):
        sel = self.tree.selection()
        if not sel: return

        db = SessionLocal()
        try:
            for item_id in sel:
                f = db.query(FacturaGuardada).get(int(item_id))
                if f:
                    f.es_automatica = not f.es_automatica
            db.commit()
        finally:
            db.close()

        self.refresh_data()

    def _editar_factura(self):
        messagebox.showinfo("Editar",
                            "Esta función regresará el estado de la factura a 'En revisión' en el visor en una próxima actualización.")

    def _iniciar_bot(self):
        # 1. Buscar qué facturas están pendientes
        db = SessionLocal()
        try:
            pendientes = db.query(FacturaGuardada).filter_by(estado="Pendiente").all()
            ids = [f.id for f in pendientes]
        finally:
            db.close()

        if not ids:
            messagebox.showinfo("Aviso", "No hay facturas pendientes para procesar en la base de datos.")
            return

        # 2. Deshabilitar botón para evitar clics dobles
        self.btn_iniciar.state(["disabled"])

        # 3. Función para que el bot actualice la UI de forma segura
        def _log(mensaje):
            self.controller.after(0, lambda: self.lbl_resumen.configure(text=f"Bot: {mensaje}"))

        # 4. Función de trabajo en segundo plano
        def _worker():
            ejecutar_bot(ids, _log)
            # Al terminar, avisar a la UI que reactive todo
            self.controller.after(0, self._on_bot_finished)

        # 5. Lanzar el hilo
        hilo_bot = threading.Thread(target=_worker, daemon=True)
        hilo_bot.start()

    def _on_bot_finished(self):
        self.btn_iniciar.state(["!disabled"])
        self.refresh_data()
        messagebox.showinfo("Completado", "El bot ha terminado su ejecución y el navegador se cerró.")