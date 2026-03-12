# app/ui/frames/proveedores.py
import json
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from app.database.database import SessionLocal, ProveedorCredencial, Sucursal, CatalogoProveedor, encrypt_password, \
    decrypt_password
from app.ui.theme import get_pal


class ProveedoresFrame(ttk.Frame):
    def __init__(self, master, controller):
        super().__init__(master)
        self.controller = controller

        # --- Variables del formulario PROVEEDORES (Unificadas) ---
        self.var_id = tk.StringVar()
        self.var_proveedor = tk.StringVar()
        self.var_rfc = tk.StringVar()  # <--- NUEVO
        self.var_alias = tk.StringVar()  # <--- NUEVO
        self.var_usuario = tk.StringVar()
        self.var_password = tk.StringVar()
        self._pass_visible = False

        # --- Variables del formulario SUCURSALES ---
        self.var_suc_id = tk.StringVar()
        self.var_suc_nombre = tk.StringVar()

        self._build_ui()

    def _build_ui(self):
        pal = get_pal(self.controller)

        # --- Cabecera ---
        header = ttk.Frame(self)
        header.pack(fill="x", padx=12, pady=(12, 6))

        ttk.Button(header, text="← Menú Principal", command=lambda: self.controller.show("menu")).pack(side="left")
        ttk.Label(header, text="Gestión de Catálogos", font=("Segoe UI", 16, "bold")).pack(side="left", padx=(12, 0))

        # --- BOTÓN DE MODO CLARO/OSCURO ---
        self.btn_theme = ttk.Button(
            header,
            text=self.controller.theme_button_label(),
            command=self._toggle_theme,
        )
        self.btn_theme.pack(side="right")

        # ========================================================
        # NOTEBOOK (PESTAÑAS)
        # ========================================================
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=12, pady=(10, 15))

        # --- PESTAÑA 1: PROVEEDORES ---
        self.tab_proveedores = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_proveedores, text="Proveedores y Credenciales")

        # --- PESTAÑA 2: SUCURSALES ---
        self.tab_sucursales = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_sucursales, text="Sucursales")

        self._build_tab_proveedores(pal)
        self._build_tab_sucursales(pal)

    # ========================================================
    # INTERFAZ: PESTAÑA PROVEEDORES
    # ========================================================
    def _build_tab_proveedores(self, pal):
        form_frame = ttk.LabelFrame(self.tab_proveedores, text="Registrar / Editar Proveedor (Parser y Bot)")
        form_frame.pack(fill="x", padx=12, pady=(10, 15))

        inner_form = ttk.Frame(form_frame)
        inner_form.pack(fill="x", padx=10, pady=10)

        # Fila 1: Datos para Extracción (Parser)
        ttk.Label(inner_form, text="Nombre Oficial:").grid(row=0, column=0, sticky="w", padx=(0, 5))
        ttk.Entry(inner_form, textvariable=self.var_proveedor, width=28).grid(row=0, column=1, sticky="w", padx=(0, 15))

        ttk.Label(inner_form, text="RFC:").grid(row=0, column=2, sticky="w", padx=(0, 5))
        ttk.Entry(inner_form, textvariable=self.var_rfc, width=18).grid(row=0, column=3, sticky="w", padx=(0, 15))

        ttk.Label(inner_form, text="Alias (Comas):").grid(row=0, column=4, sticky="w", padx=(0, 5))
        ttk.Entry(inner_form, textvariable=self.var_alias, width=35).grid(row=0, column=5, sticky="w", padx=(0, 15))

        # Fila 2: Datos para el Bot
        ttk.Label(inner_form, text="Usuario SAT:").grid(row=1, column=0, sticky="w", padx=(0, 5), pady=(10, 0))
        ttk.Entry(inner_form, textvariable=self.var_usuario, width=28).grid(row=1, column=1, sticky="w", padx=(0, 15),
                                                                            pady=(10, 0))

        ttk.Label(inner_form, text="Contraseña:").grid(row=1, column=2, sticky="w", padx=(0, 5), pady=(10, 0))
        self.entry_password = ttk.Entry(inner_form, textvariable=self.var_password, width=18, show="*")
        self.entry_password.grid(row=1, column=3, sticky="w", padx=(0, 5), pady=(10, 0))

        self.btn_show_pass = ttk.Button(inner_form, text="Mostrar", width=8, command=self._toggle_password_visibility)
        self.btn_show_pass.grid(row=1, column=4, sticky="w", pady=(10, 0))

        # Botones
        btn_frame = ttk.Frame(inner_form)
        btn_frame.grid(row=1, column=5, sticky="e", pady=(10, 0))

        ttk.Button(btn_frame, text="Limpiar", command=self._limpiar_formulario).pack(side="left", padx=(0, 10))
        ttk.Button(btn_frame, text="Guardar", style="Primary.TButton", command=self._guardar_proveedor).pack(
            side="left")

        # Tabla de Proveedores Unificada
        self.tree_frame = ttk.Frame(self.tab_proveedores)
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

        self.tree.tag_configure("odd", background=pal["ROW_ALT"])
        self.tree.tag_configure("even", background=pal["SURFACE"])

        self.tree.pack(fill="both", expand=True, side="left")

        scrollbar = ttk.Scrollbar(self.tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")

        table_actions_frame = ttk.Frame(self.tab_proveedores)
        table_actions_frame.pack(fill="x", padx=12, pady=(0, 12))

        ttk.Button(table_actions_frame, text="Exportar JSON", command=self._exportar_json).pack(side="left",
                                                                                                padx=(0, 10))
        ttk.Button(table_actions_frame, text="Importar JSON", command=self._importar_json).pack(side="left")

        self.menu_prov = tk.Menu(self, tearoff=0)
        self.menu_prov.add_command(label="Cargar para Editar", command=self._cargar_edicion)
        self.menu_prov.add_separator()
        self.menu_prov.add_command(label="Eliminar Proveedor", command=self._eliminar_proveedor)

        self.tree.bind("<Button-3>", self._show_menu_prov)

    # ========================================================
    # INTERFAZ: PESTAÑA SUCURSALES (Sin cambios)
    # ========================================================
    def _build_tab_sucursales(self, pal):
        suc_form = ttk.LabelFrame(self.tab_sucursales, text="Registrar / Editar Sucursal")
        suc_form.pack(fill="x", padx=12, pady=(10, 15))

        inner_suc = ttk.Frame(suc_form)
        inner_suc.pack(fill="x", padx=10, pady=10)

        ttk.Label(inner_suc, text="Proveedor:").grid(row=0, column=0, sticky="w", padx=(0, 5))

        self.var_suc_prov_id = tk.StringVar()
        self.cmb_suc_prov = ttk.Combobox(inner_suc, textvariable=self.var_suc_prov_id, state="readonly", width=25)
        self.cmb_suc_prov.grid(row=0, column=1, sticky="w", padx=(0, 15))

        ttk.Label(inner_suc, text="Nombre Sucursal:").grid(row=0, column=2, sticky="w", padx=(0, 5))
        ttk.Entry(inner_suc, textvariable=self.var_suc_nombre, width=25).grid(row=0, column=3, sticky="w", padx=(0, 15))

        btn_frame_suc = ttk.Frame(inner_suc)
        btn_frame_suc.grid(row=0, column=4, sticky="e")

        ttk.Button(btn_frame_suc, text="Limpiar", command=self._limpiar_form_sucursal).pack(side="left", padx=(0, 10))
        ttk.Button(btn_frame_suc, text="Guardar", style="Primary.TButton", command=self._guardar_sucursal).pack(
            side="left")

        self.tree_suc_frame = ttk.Frame(self.tab_sucursales)
        self.tree_suc_frame.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        self.tree_suc = ttk.Treeview(self.tree_suc_frame, columns=("id", "proveedor", "nombre"), show="headings",
                                     style="Treeview")

        self.tree_suc.heading("id", text="ID")
        self.tree_suc.heading("proveedor", text="Proveedor")
        self.tree_suc.heading("nombre", text="Nombre de la Sucursal")

        self.tree_suc.column("id", width=80, anchor="center")
        self.tree_suc.column("proveedor", width=250)
        self.tree_suc.column("nombre", width=350)

        self.tree_suc.tag_configure("odd", background=pal["ROW_ALT"])
        self.tree_suc.tag_configure("even", background=pal["SURFACE"])

        self.tree_suc.pack(fill="both", expand=True, side="left")

        scroll_suc = ttk.Scrollbar(self.tree_suc_frame, orient="vertical", command=self.tree_suc.yview)
        self.tree_suc.configure(yscrollcommand=scroll_suc.set)
        scroll_suc.pack(side="right", fill="y")

        self.menu_suc = tk.Menu(self, tearoff=0)
        self.menu_suc.add_command(label="Cargar para Editar", command=self._cargar_edicion_sucursal)
        self.menu_suc.add_separator()
        self.menu_suc.add_command(label="Eliminar Sucursal", command=self._eliminar_sucursal)

        self.tree_suc.bind("<Button-3>", self._show_menu_suc)

    # ========================================================
    # LÓGICA GENERAL
    # ========================================================
    def refresh_data(self):
        self._refresh_proveedores()
        self._refresh_sucursales()

    def _toggle_theme(self):
        self.controller.toggle_theme()

    def on_theme_changed(self):
        try:
            self.btn_theme.configure(text=self.controller.theme_button_label())
            pal = get_pal(self.controller)
            self.tree.tag_configure("odd", background=pal["ROW_ALT"])
            self.tree.tag_configure("even", background=pal["SURFACE"])
            self.tree_suc.tag_configure("odd", background=pal["ROW_ALT"])
            self.tree_suc.tag_configure("even", background=pal["SURFACE"])
        except Exception:
            pass

    # ========================================================
    # LÓGICA: PROVEEDORES (Unificada)
    # ========================================================
    def _toggle_password_visibility(self):
        self._pass_visible = not self._pass_visible
        if self._pass_visible:
            self.entry_password.configure(show="")
            self.btn_show_pass.configure(text="Ocultar")
        else:
            self.entry_password.configure(show="*")
            self.btn_show_pass.configure(text="Mostrar")

    def _limpiar_formulario(self):
        self.var_id.set("")
        self.var_proveedor.set("")
        self.var_rfc.set("")
        self.var_alias.set("")
        self.var_usuario.set("")
        self.var_password.set("")
        self._pass_visible = False
        self.entry_password.configure(show="*")
        self.btn_show_pass.configure(text="Mostrar")

    def _refresh_proveedores(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        db = SessionLocal()
        try:
            # Traemos todos los proveedores del catálogo
            catalogos = db.query(CatalogoProveedor).all()
            for index, cat in enumerate(catalogos):
                # Buscamos si este proveedor tiene credenciales asociadas
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
        record_id = self.var_id.get()  # Guarda el ID de CatalogoProveedor

        if not prov:
            messagebox.showwarning("Atención", "El Nombre Oficial es obligatorio.")
            return

        db = SessionLocal()
        try:
            nombre_anterior = prov

            # 1. Guardar en Catálogo (Para el Parser)
            if record_id:
                cat = db.query(CatalogoProveedor).get(int(record_id))
                if cat:
                    nombre_anterior = cat.nombre
                    cat.nombre = prov
                    cat.rfc = rfc
                    cat.alias = alias
            else:
                existe = db.query(CatalogoProveedor).filter_by(nombre=prov).first()
                if existe:
                    messagebox.showerror("Error", "Este proveedor ya existe.")
                    return
                cat = CatalogoProveedor(nombre=prov, rfc=rfc, alias=alias)
                db.add(cat)

            # 2. Guardar en Credenciales (Para el Bot)
            cred = db.query(ProveedorCredencial).filter_by(nombre_proveedor=nombre_anterior).first()

            if user and pwd:
                if cred:
                    cred.nombre_proveedor = prov
                    cred.usuario = user
                    cred.password_encriptado = encrypt_password(pwd)
                else:
                    nueva_cred = ProveedorCredencial(nombre_proveedor=prov, usuario=user,
                                                     password_encriptado=encrypt_password(pwd))
                    db.add(nueva_cred)
            elif cred:
                # Si borró el usuario/pass pero ya existía, solo le actualizamos el nombre
                cred.nombre_proveedor = prov

            db.commit()

            # ¡MAGIA! Refrescar la memoria del Parser al instante
            from parser.legacy_excel_parser import cargar_proveedores_en_memoria
            cargar_proveedores_en_memoria()

            self._limpiar_formulario()
            self.refresh_data()  # Actualiza ambas tablas
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

        cat_id = int(sel[0])
        db = SessionLocal()
        try:
            cat = db.query(CatalogoProveedor).get(cat_id)
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

        if messagebox.askyesno("Confirmar",
                               f"¿Eliminar definitivamente {len(sel)} proveedor(es)? Esto también eliminará sus sucursales."):
            db = SessionLocal()
            try:
                for item_id in sel:
                    cat = db.query(CatalogoProveedor).get(int(item_id))
                    if cat:
                        # Buscamos si tiene credenciales para eliminarlas también (Cascade borra las sucursales)
                        cred = db.query(ProveedorCredencial).filter_by(nombre_proveedor=cat.nombre).first()
                        if cred:
                            db.delete(cred)
                        db.delete(cat)
                db.commit()

                from parser.legacy_excel_parser import cargar_proveedores_en_memoria
                cargar_proveedores_en_memoria()

            finally:
                db.close()
            self.refresh_data()
            self._limpiar_formulario()

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
                    "nombre_proveedor": cat.nombre,
                    "rfc": cat.rfc or "",
                    "alias": cat.alias or "",
                    "usuario": cred.usuario if cred else "",
                    "password": decrypt_password(cred.password_encriptado) if cred else "",
                    "sucursales": sucursales
                })

            ruta = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("Archivos JSON", "*.json")],
                                                title="Guardar respaldo")
            if ruta:
                with open(ruta, 'w', encoding='utf-8') as f:
                    json.dump(datos, f, indent=4)
                messagebox.showinfo("Éxito", f"Se exportaron {len(datos)} proveedores con sus alias y sucursales.")
        except Exception as e:
            messagebox.showerror("Error", str(e))
        finally:
            db.close()

    def _importar_json(self):
        ruta = filedialog.askopenfilename(filetypes=[("Archivos JSON", "*.json")], title="Seleccionar respaldo")
        if not ruta: return

        db = SessionLocal()
        try:
            with open(ruta, 'r', encoding='utf-8') as f:
                datos = json.load(f)

            agregados, actualizados = 0, 0
            for d in datos:
                nombre = (d.get("nombre_proveedor") or "").strip().upper()
                rfc = (d.get("rfc") or "").strip().upper()
                alias = (d.get("alias") or "").strip().upper()
                usuario = d.get("usuario")
                password = d.get("password")
                sucursales_json = d.get("sucursales", [])

                if not nombre: continue

                # 1. Importar Catálogo (Parser)
                cat = db.query(CatalogoProveedor).filter_by(nombre=nombre).first()
                if cat:
                    cat.rfc = rfc
                    cat.alias = alias
                    actualizados += 1
                else:
                    cat = CatalogoProveedor(nombre=nombre, rfc=rfc, alias=alias)
                    db.add(cat)
                    agregados += 1

                # 2. Importar Credenciales
                if usuario and password:
                    cred = db.query(ProveedorCredencial).filter_by(nombre_proveedor=nombre).first()
                    if cred:
                        cred.usuario = usuario
                        cred.password_encriptado = encrypt_password(password)
                    else:
                        cred = ProveedorCredencial(nombre_proveedor=nombre, usuario=usuario,
                                                   password_encriptado=encrypt_password(password))
                        db.add(cred)

                    db.flush()  # Forzamos que se asigne ID a la credencial

                    # 3. Importar Sucursales
                    for suc_nombre in sucursales_json:
                        existe_suc = db.query(Sucursal).filter_by(nombre=suc_nombre, proveedor_id=cred.id).first()
                        if not existe_suc:
                            db.add(Sucursal(nombre=suc_nombre, proveedor_id=cred.id))

            db.commit()

            from parser.legacy_excel_parser import cargar_proveedores_en_memoria
            cargar_proveedores_en_memoria()

            messagebox.showinfo("Éxito", f"Importación completa.\nAgregados: {agregados}\nActualizados: {actualizados}")
            self.refresh_data()
        except Exception as e:
            db.rollback()
            messagebox.showerror("Error", str(e))
        finally:
            db.close()

    # ========================================================
    # LÓGICA: SUCURSALES (Sin cambios funcionales)
    # ========================================================
    def _limpiar_form_sucursal(self):
        self.var_suc_id.set("")
        self.var_suc_nombre.set("")
        self.var_suc_prov_id.set("")

    def _refresh_sucursales(self):
        for item in self.tree_suc.get_children():
            self.tree_suc.delete(item)

        db = SessionLocal()
        try:
            proveedores = db.query(ProveedorCredencial).all()
            lista_provs = [f"{p.id} - {p.nombre_proveedor}" for p in proveedores]
            self.cmb_suc_prov['values'] = lista_provs

            sucursales = db.query(Sucursal).all()
            for index, s in enumerate(sucursales):
                tag = "even" if index % 2 == 0 else "odd"
                nombre_prov = s.proveedor.nombre_proveedor if s.proveedor else "DESCONOCIDO"

                self.tree_suc.insert("", "end", iid=str(s.id), values=(
                    s.id, nombre_prov, s.nombre
                ), tags=(tag,))
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
            messagebox.showerror("Error", "Formato de proveedor inválido.")
            return

        db = SessionLocal()
        try:
            if record_id:
                suc = db.query(Sucursal).get(int(record_id))
                if suc:
                    suc.nombre = nombre
                    suc.proveedor_id = prov_id
            else:
                existe = db.query(Sucursal).filter_by(nombre=nombre, proveedor_id=prov_id).first()
                if existe:
                    messagebox.showerror("Error", "Esta sucursal ya existe para este proveedor.")
                    return
                db.add(Sucursal(nombre=nombre, proveedor_id=prov_id))

            db.commit()
            self._limpiar_form_sucursal()
            self._refresh_sucursales()
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
                if suc:
                    db.delete(suc)
                    db.commit()
            finally:
                db.close()
            self._refresh_sucursales()
            self._limpiar_form_sucursal()
