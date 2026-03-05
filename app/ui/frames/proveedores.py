# app/ui/frames/proveedores.py
import json
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from app.database.database import SessionLocal, ProveedorCredencial, encrypt_password, decrypt_password
from app.ui.theme import get_pal


class ProveedoresFrame(ttk.Frame):
    def __init__(self, master, controller):
        super().__init__(master)
        self.controller = controller

        # Variables del formulario
        self.var_id = tk.StringVar()  # Vacío significa nuevo registro
        self.var_proveedor = tk.StringVar()
        self.var_usuario = tk.StringVar()
        self.var_password = tk.StringVar()
        self._pass_visible = False  # Controla si la contraseña se ve o no

        self._build_ui()

    def _build_ui(self):
        pal = get_pal(self.controller)

        # --- Cabecera ---
        header = ttk.Frame(self)
        header.pack(fill="x", padx=12, pady=(12, 6))

        ttk.Button(header, text="← Menú Principal", command=lambda: self.controller.show("menu")).pack(side="left")
        ttk.Label(header, text="Catálogo de Proveedores", font=("Segoe UI", 16, "bold")).pack(side="left", padx=(12, 0))

        # --- BOTÓN DE MODO CLARO/OSCURO ---
        self.btn_theme = ttk.Button(
            header,
            text=self.controller.theme_button_label(),
            command=self._toggle_theme,
        )
        self.btn_theme.pack(side="right")

        # --- Formulario de Registro / Edición ---
        form_frame = ttk.LabelFrame(self, text="Registrar / Editar Credencial")
        form_frame.pack(fill="x", padx=12, pady=(10, 15))

        inner_form = ttk.Frame(form_frame)
        inner_form.pack(fill="x", padx=10, pady=10)

        # Fila de inputs
        ttk.Label(inner_form, text="Proveedor:").grid(row=0, column=0, sticky="w", padx=(0, 5))
        ttk.Entry(inner_form, textvariable=self.var_proveedor, width=35).grid(row=0, column=1, sticky="w", padx=(0, 15))

        ttk.Label(inner_form, text="Usuario:").grid(row=0, column=2, sticky="w", padx=(0, 5))
        ttk.Entry(inner_form, textvariable=self.var_usuario, width=30).grid(row=0, column=3, sticky="w", padx=(0, 15))

        ttk.Label(inner_form, text="Contraseña:").grid(row=0, column=4, sticky="w", padx=(0, 5))

        # Guardamos la referencia de la entrada de contraseña para poder cambiarle el modo (show)
        self.entry_password = ttk.Entry(inner_form, textvariable=self.var_password, width=25, show="*")
        self.entry_password.grid(row=0, column=5, sticky="w", padx=(0, 5))

        # NUEVO: Botón para mostrar/ocultar contraseña
        self.btn_show_pass = ttk.Button(inner_form, text="Mostrar", width=8, command=self._toggle_password_visibility)
        self.btn_show_pass.grid(row=0, column=6, sticky="w")

        # Botones del formulario
        btn_frame = ttk.Frame(inner_form)
        btn_frame.grid(row=1, column=0, columnspan=7, sticky="e", pady=(15, 0))

        ttk.Button(btn_frame, text="Limpiar", command=self._limpiar_formulario).pack(side="left", padx=(0, 10))
        ttk.Button(btn_frame, text="Guardar", style="Primary.TButton", command=self._guardar_credencial).pack(
            side="left")

        # --- Contenedor de la Tabla ---
        self.tree_frame = ttk.Frame(self)
        self.tree_frame.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        cols = ("id", "proveedor", "usuario", "password")
        self.tree = ttk.Treeview(self.tree_frame, columns=cols, show="headings", style="Treeview")

        self.tree.heading("id", text="ID")
        self.tree.heading("proveedor", text="Proveedor")
        self.tree.heading("usuario", text="Usuario")
        self.tree.heading("password", text="Contraseña")

        self.tree.column("id", width=50, anchor="center")
        self.tree.column("proveedor", width=300)
        self.tree.column("usuario", width=250)
        self.tree.column("password", width=150, anchor="center")

        self.tree.tag_configure("odd", background=pal["ROW_ALT"])
        self.tree.tag_configure("even", background=pal["SURFACE"])

        self.tree.pack(fill="both", expand=True, side="left")

        scrollbar = ttk.Scrollbar(self.tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")

        # --- Botones de Exportar/Importar ---
        table_actions_frame = ttk.Frame(self)
        table_actions_frame.pack(fill="x", padx=12, pady=(0, 12))

        ttk.Button(table_actions_frame, text="Exportar JSON", command=self._exportar_json).pack(side="left",
                                                                                                  padx=(0, 10))
        ttk.Button(table_actions_frame, text="Importar JSON", command=self._importar_json).pack(side="left")

        # --- Menú Contextual ---
        self.menu = tk.Menu(self, tearoff=0)
        self.menu.add_command(label="Cargar para Editar", command=self._cargar_edicion)
        self.menu.add_separator()
        self.menu.add_command(label="Eliminar Proveedor", command=self._eliminar_credencial)

        self.tree.bind("<Button-3>", self._show_menu)

    # --- Lógica de la Contraseña ---
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
        self.var_usuario.set("")
        self.var_password.set("")
        self._pass_visible = False
        self.entry_password.configure(show="*")
        self.btn_show_pass.configure(text="Mostrar")

    def refresh_data(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        db = SessionLocal()
        try:
            credenciales = db.query(ProveedorCredencial).all()
            for index, c in enumerate(credenciales):
                tag = "even" if index % 2 == 0 else "odd"
                self.tree.insert("", "end", iid=str(c.id), values=(
                    c.id,
                    c.nombre_proveedor,
                    c.usuario,
                    "********"  # En la tabla siempre la ocultamos
                ), tags=(tag,))
        finally:
            db.close()

    def _guardar_credencial(self):
        prov = self.var_proveedor.get().strip().upper()
        user = self.var_usuario.get().strip()
        pwd = self.var_password.get().strip()
        record_id = self.var_id.get()

        if not prov or not user or not pwd:
            messagebox.showwarning("Datos incompletos", "Por favor, llena todos los campos.")
            return

        db = SessionLocal()
        try:
            if record_id:
                cred = db.query(ProveedorCredencial).get(int(record_id))
                if cred:
                    cred.nombre_proveedor = prov
                    cred.usuario = user
                    cred.password_encriptado = encrypt_password(pwd)
            else:
                existe = db.query(ProveedorCredencial).filter_by(nombre_proveedor=prov).first()
                if existe:
                    messagebox.showerror("Error", "Este proveedor ya existe en la base de datos.")
                    return

                nueva_cred = ProveedorCredencial(
                    nombre_proveedor=prov,
                    usuario=user,
                    password_encriptado=encrypt_password(pwd)
                )
                db.add(nueva_cred)

            db.commit()
            self._limpiar_formulario()
            self.refresh_data()
            self.controller.set_status("Credencial guardada correctamente.", auto_clear_ms=3000)

        except Exception as e:
            db.rollback()
            messagebox.showerror("Error de Base de Datos", str(e))
        finally:
            db.close()

    def _show_menu(self, event):
        iid = self.tree.identify_row(event.y)
        if iid:
            self.tree.selection_set(iid)
            self.menu.post(event.x_root, event.y_root)

    def _cargar_edicion(self):
        sel = self.tree.selection()
        if not sel: return

        cred_id = int(sel[0])
        db = SessionLocal()
        try:
            cred = db.query(ProveedorCredencial).get(cred_id)
            if cred:
                self.var_id.set(str(cred.id))
                self.var_proveedor.set(cred.nombre_proveedor)
                self.var_usuario.set(cred.usuario)
                pwd_real = decrypt_password(cred.password_encriptado)
                self.var_password.set(pwd_real)
        finally:
            db.close()

    def _eliminar_credencial(self):
        sel = self.tree.selection()
        if not sel: return

        if messagebox.askyesno("Confirmar", "¿Eliminar definitivamente las credenciales de este proveedor?"):
            cred_id = int(sel[0])
            db = SessionLocal()
            try:
                cred = db.query(ProveedorCredencial).get(cred_id)
                if cred:
                    db.delete(cred)
                    db.commit()
            finally:
                db.close()
            self.refresh_data()
            self._limpiar_formulario()

    # --- LÓGICA DE IMPORTAR / EXPORTAR ---
    def _exportar_json(self):
        db = SessionLocal()
        try:
            proveedores = db.query(ProveedorCredencial).all()
            if not proveedores:
                messagebox.showinfo("Exportar", "No hay proveedores en el catálogo para exportar.")
                return

            datos = []
            for p in proveedores:
                datos.append({
                    "nombre_proveedor": p.nombre_proveedor,
                    "usuario": p.usuario,
                    "password": decrypt_password(p.password_encriptado)
                })

            ruta = filedialog.asksaveasfilename(
                defaultextension=".json",
                filetypes=[("Archivos JSON", "*.json")],
                title="Guardar respaldo de Proveedores"
            )

            if ruta:
                with open(ruta, 'w', encoding='utf-8') as f:
                    json.dump(datos, f, indent=4)
                messagebox.showinfo("Éxito", f"Se exportaron {len(datos)} proveedores correctamente.")
        except Exception as e:
            messagebox.showerror("Error", f"Ocurrió un error al exportar: {e}")
        finally:
            db.close()

    def _importar_json(self):
        ruta = filedialog.askopenfilename(
            filetypes=[("Archivos JSON", "*.json")],
            title="Seleccionar respaldo de Proveedores"
        )
        if not ruta:
            return

        db = SessionLocal()
        try:
            with open(ruta, 'r', encoding='utf-8') as f:
                datos = json.load(f)

            agregados = 0
            actualizados = 0

            for d in datos:
                nombre = d.get("nombre_proveedor")
                usuario = d.get("usuario")
                password = d.get("password")

                if not nombre or not usuario or not password:
                    continue

                # Normalizamos a mayúsculas
                nombre = nombre.strip().upper()

                prov_existente = db.query(ProveedorCredencial).filter_by(nombre_proveedor=nombre).first()
                if prov_existente:
                    prov_existente.usuario = usuario
                    prov_existente.password_encriptado = encrypt_password(password)
                    actualizados += 1
                else:
                    nuevo_prov = ProveedorCredencial(
                        nombre_proveedor=nombre,
                        usuario=usuario,
                        password_encriptado=encrypt_password(password)
                    )
                    db.add(nuevo_prov)
                    agregados += 1

            db.commit()
            messagebox.showinfo("Éxito",
                                f"Importación completa.\n\nAgregados: {agregados}\nActualizados: {actualizados}")
            self.refresh_data()

        except Exception as e:
            messagebox.showerror("Error", f"Ocurrió un error al importar: {e}")
        finally:
            db.close()

    # --- LÓGICA DEL TEMA ---
    def _toggle_theme(self):
        self.controller.toggle_theme()

    def on_theme_changed(self):
        try:
            self.btn_theme.configure(text=self.controller.theme_button_label())
            pal = get_pal(self.controller)
            self.tree.tag_configure("odd", background=pal["ROW_ALT"])
            self.tree.tag_configure("even", background=pal["SURFACE"])
        except Exception:
            pass
