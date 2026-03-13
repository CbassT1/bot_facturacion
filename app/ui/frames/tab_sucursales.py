# app/ui/frames/tab_sucursales.py
import tkinter as tk
from tkinter import ttk, messagebox
from app.database.database import SessionLocal, ProveedorCredencial, Sucursal
from app.ui.theme import get_pal

class TabSucursales(ttk.Frame):
    def __init__(self, parent, controller, on_data_changed=None):
        super().__init__(parent)
        self.controller = controller
        self.on_data_changed = on_data_changed

        self.var_suc_id = tk.StringVar()
        self.var_suc_nombre = tk.StringVar()
        self.var_suc_prov_id = tk.StringVar()

        self._build_ui()

    def _build_ui(self):
        pal = get_pal(self.controller)

        suc_form = ttk.LabelFrame(self, text="Registrar / Editar Sucursal")
        suc_form.pack(fill="x", padx=12, pady=(10, 15))

        inner_suc = ttk.Frame(suc_form)
        inner_suc.pack(fill="x", padx=10, pady=10)

        ttk.Label(inner_suc, text="Proveedor:").grid(row=0, column=0, sticky="w", padx=(0, 5))
        self.cmb_suc_prov = ttk.Combobox(inner_suc, textvariable=self.var_suc_prov_id, state="readonly", width=25)
        self.cmb_suc_prov.grid(row=0, column=1, sticky="w", padx=(0, 15))

        ttk.Label(inner_suc, text="Nombre Sucursal:").grid(row=0, column=2, sticky="w", padx=(0, 5))
        ttk.Entry(inner_suc, textvariable=self.var_suc_nombre, width=25).grid(row=0, column=3, sticky="w", padx=(0, 15))

        btn_frame_suc = ttk.Frame(inner_suc)
        btn_frame_suc.grid(row=0, column=4, sticky="e")

        ttk.Button(btn_frame_suc, text="Limpiar", command=self._limpiar_form_sucursal).pack(side="left", padx=(0, 10))
        ttk.Button(btn_frame_suc, text="Guardar", style="Primary.TButton", command=self._guardar_sucursal).pack(side="left")

        self.tree_suc_frame = ttk.Frame(self)
        self.tree_suc_frame.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        self.tree_suc = ttk.Treeview(self.tree_suc_frame, columns=("id", "proveedor", "nombre"), show="headings", style="Treeview")
        self.tree_suc.heading("id", text="ID")
        self.tree_suc.heading("proveedor", text="Proveedor")
        self.tree_suc.heading("nombre", text="Nombre de la Sucursal")
        self.tree_suc.column("id", width=80, anchor="center")
        self.tree_suc.column("proveedor", width=250)
        self.tree_suc.column("nombre", width=350)
        self.tree_suc.pack(fill="both", expand=True, side="left")

        scroll_suc = ttk.Scrollbar(self.tree_suc_frame, orient="vertical", command=self.tree_suc.yview)
        self.tree_suc.configure(yscrollcommand=scroll_suc.set)
        scroll_suc.pack(side="right", fill="y")

        self.menu_suc = tk.Menu(self, tearoff=0)
        self.menu_suc.add_command(label="Cargar para Editar", command=self._cargar_edicion_sucursal)
        self.menu_suc.add_separator()
        self.menu_suc.add_command(label="Eliminar Sucursal", command=self._eliminar_sucursal)
        self.tree_suc.bind("<Button-3>", self._show_menu_suc)

        self.on_theme_changed()

    def on_theme_changed(self):
        pal = get_pal(self.controller)
        self.tree_suc.tag_configure("odd", background=pal["ROW_ALT"])
        self.tree_suc.tag_configure("even", background=pal["SURFACE"])

    def _limpiar_form_sucursal(self):
        self.var_suc_id.set("")
        self.var_suc_nombre.set("")
        self.var_suc_prov_id.set("")

    def refresh_data(self):
        for item in self.tree_suc.get_children():
            self.tree_suc.delete(item)

        db = SessionLocal()
        try:
            proveedores = db.query(ProveedorCredencial).all()
            self.cmb_suc_prov['values'] = [f"{p.id} - {p.nombre_proveedor}" for p in proveedores]

            sucursales = db.query(Sucursal).all()
            for index, s in enumerate(sucursales):
                tag = "even" if index % 2 == 0 else "odd"
                nombre_prov = s.proveedor.nombre_proveedor if s.proveedor else "DESCONOCIDO"
                self.tree_suc.insert("", "end", iid=str(s.id), values=(s.id, nombre_prov, s.nombre), tags=(tag,))
        finally:
            db.close()

    def _guardar_sucursal(self):
        nombre = self.var_suc_nombre.get().strip().upper()
        record_id = self.var_suc_id.get()
        prov_seleccionado = self.cmb_suc_prov.get()

        if not nombre or not prov_seleccionado:
            messagebox.showwarning("Datos incompletos", "Elige un proveedor e ingresa el nombre de la sucursal.")
            return

        try:
            prov_id = int(prov_seleccionado.split(" - ")[0])
        except ValueError:
            return

        db = SessionLocal()
        try:
            if record_id:
                suc = db.query(Sucursal).get(int(record_id))
                if suc:
                    suc.nombre = nombre
                    suc.proveedor_id = prov_id
            else:
                if db.query(Sucursal).filter_by(nombre=nombre, proveedor_id=prov_id).first():
                    messagebox.showerror("Error", "Esta sucursal ya existe.")
                    return
                db.add(Sucursal(nombre=nombre, proveedor_id=prov_id))

            db.commit()
            self._limpiar_form_sucursal()
            if self.on_data_changed: self.on_data_changed()
            self.controller.set_status("Sucursal guardada correctamente.", auto_clear_ms=3000)
        except Exception as e:
            db.rollback()
            messagebox.showerror("Error de BD", str(e))
        finally:
            db.close()

    def _show_menu_suc(self, event):
        iid = self.tree_suc.identify_row(event.y)
        if iid:
            self.tree_suc.selection_set(iid)
            self.menu_suc.post(event.x_root, event.y_root)

    def _cargar_edicion_sucursal(self):
        sel = self.tree_suc.selection()
        if not sel: return
        db = SessionLocal()
        try:
            suc = db.query(Sucursal).get(int(sel[0]))
            if suc:
                self.var_suc_id.set(str(suc.id))
                self.var_suc_nombre.set(suc.nombre)
                if suc.proveedor:
                    self.var_suc_prov_id.set(f"{suc.proveedor.id} - {suc.proveedor.nombre_proveedor}")
        finally:
            db.close()

    def _eliminar_sucursal(self):
        sel = self.tree_suc.selection()
        if not sel: return
        if messagebox.askyesno("Confirmar", "¿Eliminar definitivamente esta sucursal?"):
            db = SessionLocal()
            try:
                suc = db.query(Sucursal).get(int(sel[0]))
                if suc: db.delete(suc)
                db.commit()
            finally:
                db.close()
            self._limpiar_form_sucursal()
            if self.on_data_changed: self.on_data_changed()
