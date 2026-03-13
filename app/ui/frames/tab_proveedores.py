# app/ui/frames/tab_proveedores.py
import json
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from app.database.database import SessionLocal, ProveedorCredencial, CatalogoProveedor, encrypt_password, \
    decrypt_password
from app.ui.theme import get_pal


class TabProveedores(ttk.Frame):
    def __init__(self, parent, controller, on_data_changed=None):
        super().__init__(parent)
        self.controller = controller
        self.on_data_changed = on_data_changed  # Avisa al jefe si hay que refrescar otras pestañas

        self.var_id = tk.StringVar()
        self.var_proveedor = tk.StringVar()
        self.var_rfc = tk.StringVar()
        self.var_alias = tk.StringVar()
        self.var_usuario = tk.StringVar()
        self.var_password = tk.StringVar()
        self._pass_visible = False

        self._build_ui()

    def _build_ui(self):
        pal = get_pal(self.controller)

        form_frame = ttk.LabelFrame(self, text="Registrar / Editar Proveedor (Parser y Bot)")
        form_frame.pack(fill="x", padx=12, pady=(10, 15))

        inner_form = ttk.Frame(form_frame)
        inner_form.pack(fill="x", padx=10, pady=10)

        # Fila 1
        ttk.Label(inner_form, text="Nombre Oficial:").grid(row=0, column=0, sticky="w", padx=(0, 5))
        ttk.Entry(inner_form, textvariable=self.var_proveedor, width=28).grid(row=0, column=1, sticky="w", padx=(0, 15))

        ttk.Label(inner_form, text="RFC:").grid(row=0, column=2, sticky="w", padx=(0, 5))
        ttk.Entry(inner_form, textvariable=self.var_rfc, width=18).grid(row=0, column=3, sticky="w", padx=(0, 15))

        ttk.Label(inner_form, text="Alias (Comas):").grid(row=0, column=4, sticky="w", padx=(0, 5))
        ttk.Entry(inner_form, textvariable=self.var_alias, width=35).grid(row=0, column=5, sticky="w", padx=(0, 15))

        # Fila 2
        ttk.Label(inner_form, text="Usuario SAT:").grid(row=1, column=0, sticky="w", padx=(0, 5), pady=(10, 0))
        ttk.Entry(inner_form, textvariable=self.var_usuario, width=28).grid(row=1, column=1, sticky="w", padx=(0, 15),
                                                                            pady=(10, 0))

        ttk.Label(inner_form, text="Contraseña:").grid(row=1, column=2, sticky="w", padx=(0, 5), pady=(10, 0))
        self.entry_password = ttk.Entry(inner_form, textvariable=self.var_password, width=18, show="*")
        self.entry_password.grid(row=1, column=3, sticky="w", padx=(0, 5), pady=(10, 0))

        self.btn_show_pass = ttk.Button(inner_form, text="Mostrar", width=8, command=self._toggle_password_visibility)
        self.btn_show_pass.grid(row=1, column=4, sticky="w", pady=(10, 0))

        btn_frame = ttk.Frame(inner_form)
        btn_frame.grid(row=1, column=5, sticky="e", pady=(10, 0))
        ttk.Button(btn_frame, text="Limpiar", command=self._limpiar_formulario).pack(side="left", padx=(0, 10))
        ttk.Button(btn_frame, text="Guardar", style="Primary.TButton", command=self._guardar_proveedor).pack(
            side="left")

        # Tabla
        self.tree_frame = ttk.Frame(self)
        self.tree_frame.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        cols = ("id", "proveedor", "rfc", "alias", "usuario", "password")
        self.tree = ttk.Treeview(self.tree_frame, columns=cols, show="headings", style="Treeview")

        self.tree.heading("id", text="ID")
        self.tree.heading("proveedor", text="Proveedor")
        self.tree.heading("rfc", text="RFC")
        self.tree.heading("alias", text="Alias")
        self.tree.heading("usuario", text="Usuario")
        self.tree.heading("password", text="Contraseña")

        self.tree.column("id", width=40, anchor="center")
        self.tree.column("proveedor", width=200)
        self.tree.column("rfc", width=120, anchor="center")
        self.tree.column("alias", width=200)
        self.tree.column("usuario", width=150)
        self.tree.column("password", width=100, anchor="center")

        self.tree.pack(fill="both", expand=True, side="left")
        scrollbar = ttk.Scrollbar(self.tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")

        table_actions_frame = ttk.Frame(self)
        table_actions_frame.pack(fill="x", padx=12, pady=(0, 12))

        ttk.Button(table_actions_frame, text="Exportar JSON", command=self._exportar_json).pack(side="left",
                                                                                                padx=(0, 10))
        ttk.Button(table_actions_frame, text="Importar JSON", command=self._importar_json).pack(side="left")

        self.menu_prov = tk.Menu(self, tearoff=0)
        self.menu_prov.add_command(label="Cargar para Editar", command=self._cargar_edicion)
        self.menu_prov.add_separator()
        self.menu_prov.add_command(label="Eliminar Proveedor", command=self._eliminar_proveedor)
        self.tree.bind("<Button-3>", self._show_menu_prov)

        self.on_theme_changed()

    def on_theme_changed(self):
        pal = get_pal(self.controller)
        self.tree.tag_configure("odd", background=pal["ROW_ALT"])
        self.tree.tag_configure("even", background=pal["SURFACE"])

    def _toggle_password_visibility(self):
        self._pass_visible = not self._pass_visible
        self.entry_password.configure(show="" if self._pass_visible else "*")
        self.btn_show_pass.configure(text="Ocultar" if self._pass_visible else "Mostrar")

    def _limpiar_formulario(self):
        for var in [self.var_id, self.var_proveedor, self.var_rfc, self.var_alias, self.var_usuario, self.var_password]:
            var.set("")
        self._pass_visible = False
        self.entry_password.configure(show="*")
        self.btn_show_pass.configure(text="Mostrar")

    def refresh_data(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        db = SessionLocal()
        try:
            catalogos = db.query(CatalogoProveedor).all()
            for index, cat in enumerate(catalogos):
                cred = db.query(ProveedorCredencial).filter_by(nombre_proveedor=cat.nombre).first()
                usuario = cred.usuario if cred else "-"
                password_disp = "********" if cred else "-"

                tag = "even" if index % 2 == 0 else "odd"
                self.tree.insert("", "end", iid=str(cat.id), values=(
                    cat.id, cat.nombre, cat.rfc or "", cat.alias or "", usuario, password_disp
                ), tags=(tag,))
        finally:
            db.close()

    def _guardar_proveedor(self):
        prov = self.var_proveedor.get().strip().upper()
        rfc = self.var_rfc.get().strip().upper()
        alias = self.var_alias.get().strip().upper()
        user = self.var_usuario.get().strip()
        pwd = self.var_password.get().strip()
        record_id = self.var_id.get()

        if not prov:
            messagebox.showwarning("Atención", "El Nombre Oficial es obligatorio.")
            return

        db = SessionLocal()
        try:
            nombre_anterior = prov
            if record_id:
                cat = db.query(CatalogoProveedor).get(int(record_id))
                if cat:
                    nombre_anterior = cat.nombre
                    cat.nombre = prov
                    cat.rfc = rfc
                    cat.alias = alias
            else:
                if db.query(CatalogoProveedor).filter_by(nombre=prov).first():
                    messagebox.showerror("Error", "Este proveedor ya existe.")
                    return
                db.add(CatalogoProveedor(nombre=prov, rfc=rfc, alias=alias))

            cred = db.query(ProveedorCredencial).filter_by(nombre_proveedor=nombre_anterior).first()
            if user and pwd:
                if cred:
                    cred.nombre_proveedor = prov
                    cred.usuario = user
                    cred.password_encriptado = encrypt_password(pwd)
                else:
                    db.add(ProveedorCredencial(nombre_proveedor=prov, usuario=user,
                                               password_encriptado=encrypt_password(pwd)))
            elif cred:
                cred.nombre_proveedor = prov

            db.commit()

            from parser.legacy_excel_parser import cargar_proveedores_en_memoria
            cargar_proveedores_en_memoria()

            self._limpiar_formulario()
            if self.on_data_changed: self.on_data_changed()
            self.controller.set_status("Proveedor guardado correctamente.", auto_clear_ms=3000)
        except Exception as e:
            db.rollback()
            messagebox.showerror("Error", str(e))
        finally:
            db.close()

    def _show_menu_prov(self, event):
        iid = self.tree.identify_row(event.y)
        if iid:
            self.tree.selection_set(iid)
            self.menu_prov.post(event.x_root, event.y_root)

    def _cargar_edicion(self):
        sel = self.tree.selection()
        if not sel: return
        db = SessionLocal()
        try:
            cat = db.query(CatalogoProveedor).get(int(sel[0]))
            if cat:
                self.var_id.set(str(cat.id))
                self.var_proveedor.set(cat.nombre)
                self.var_rfc.set(cat.rfc or "")
                self.var_alias.set(cat.alias or "")
                cred = db.query(ProveedorCredencial).filter_by(nombre_proveedor=cat.nombre).first()
                if cred:
                    self.var_usuario.set(cred.usuario)
                    self.var_password.set(decrypt_password(cred.password_encriptado))
                else:
                    self.var_usuario.set("")
                    self.var_password.set("")
        finally:
            db.close()

    def _eliminar_proveedor(self):
        sel = self.tree.selection()
        if not sel: return
        if messagebox.askyesno("Confirmar", f"¿Eliminar definitivamente {len(sel)} proveedor(es)?"):
            db = SessionLocal()
            try:
                for item_id in sel:
                    cat = db.query(CatalogoProveedor).get(int(item_id))
                    if cat:
                        cred = db.query(ProveedorCredencial).filter_by(nombre_proveedor=cat.nombre).first()
                        if cred: db.delete(cred)
                        db.delete(cat)
                db.commit()
                from parser.legacy_excel_parser import cargar_proveedores_en_memoria
                cargar_proveedores_en_memoria()
            finally:
                db.close()
            self._limpiar_formulario()
            if self.on_data_changed: self.on_data_changed()

    def _exportar_json(self):
        db = SessionLocal()
        try:
            catalogos = db.query(CatalogoProveedor).all()
            if not catalogos:
                messagebox.showinfo("Exportar", "No hay proveedores para exportar.")
                return
            datos = []
            for cat in catalogos:
                cred = db.query(ProveedorCredencial).filter_by(nombre_proveedor=cat.nombre).first()
                sucursales = [s.nombre for s in cred.sucursales] if cred else []
                datos.append({
                    "nombre_proveedor": cat.nombre, "rfc": cat.rfc or "", "alias": cat.alias or "",
                    "usuario": cred.usuario if cred else "",
                    "password": decrypt_password(cred.password_encriptado) if cred else "",
                    "sucursales": sucursales
                })
            ruta = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")],
                                                title="Guardar respaldo")
            if ruta:
                with open(ruta, 'w', encoding='utf-8') as f: json.dump(datos, f, indent=4)
                messagebox.showinfo("Éxito", f"Se exportaron {len(datos)} proveedores.")
        except Exception as e:
            messagebox.showerror("Error", str(e))
        finally:
            db.close()

    def _importar_json(self):
        ruta = filedialog.askopenfilename(filetypes=[("JSON", "*.json")], title="Seleccionar respaldo")
        if not ruta: return
        from app.database.database import Sucursal
        db = SessionLocal()
        try:
            with open(ruta, 'r', encoding='utf-8') as f:
                datos = json.load(f)
            agregados, actualizados = 0, 0
            for d in datos:
                nombre = (d.get("nombre_proveedor") or "").strip().upper()
                if not nombre: continue
                cat = db.query(CatalogoProveedor).filter_by(nombre=nombre).first()
                if cat:
                    cat.rfc = (d.get("rfc") or "").strip().upper()
                    cat.alias = (d.get("alias") or "").strip().upper()
                    actualizados += 1
                else:
                    cat = CatalogoProveedor(nombre=nombre, rfc=(d.get("rfc") or "").strip().upper(),
                                            alias=(d.get("alias") or "").strip().upper())
                    db.add(cat)
                    agregados += 1

                user, pwd = d.get("usuario"), d.get("password")
                if user and pwd:
                    cred = db.query(ProveedorCredencial).filter_by(nombre_proveedor=nombre).first()
                    if cred:
                        cred.usuario = user
                        cred.password_encriptado = encrypt_password(pwd)
                    else:
                        cred = ProveedorCredencial(nombre_proveedor=nombre, usuario=user,
                                                   password_encriptado=encrypt_password(pwd))
                        db.add(cred)
                    db.flush()
                    for suc_nombre in d.get("sucursales", []):
                        if not db.query(Sucursal).filter_by(nombre=suc_nombre, proveedor_id=cred.id).first():
                            db.add(Sucursal(nombre=suc_nombre, proveedor_id=cred.id))
            db.commit()
            from parser.legacy_excel_parser import cargar_proveedores_en_memoria
            cargar_proveedores_en_memoria()
            messagebox.showinfo("Éxito", f"Importación completa.\nAgregados: {agregados}\nActualizados: {actualizados}")
            if self.on_data_changed: self.on_data_changed()
        except Exception as e:
            db.rollback()
            messagebox.showerror("Error", str(e))
        finally:
            db.close()
