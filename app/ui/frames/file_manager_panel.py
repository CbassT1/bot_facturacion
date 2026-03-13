# app/ui/frames/file_manager_panel.py
import os
from pathlib import Path
from typing import List
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog

from app.ui.utils import open_file_native, parse_dnd_file_list
from app.ui.theme import get_pal, restyle_listbox

try:
    from tkinterdnd2 import DND_FILES

    _HAS_DND = True
except Exception:
    DND_FILES = None
    _HAS_DND = False


class FileManagerPanel(ttk.Frame):
    """
    Componente especializado en la interfaz de gestión de archivos.
    Maneja el Drag & Drop, la lista visual y las operaciones del disco duro.
    """

    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self._paths: List[str] = []
        self._files_clipboard = {"mode": None, "paths": []}

        self._build_ui()

    def _build_ui(self):
        pal = get_pal(self.controller)

        # --- Zona Drop ---
        drop = ttk.LabelFrame(self, text="Arrastra y suelta (opcional)")
        drop.pack(fill="x", pady=(0, 10))

        dnd_text = "Arrastra aquí tus archivos" if _HAS_DND else "Drag & Drop no disponible"
        self.drop_area = tk.Label(
            drop, text=dnd_text, bg=pal["SURFACE2"], fg=pal["TEXT"], bd=1,
            relief="solid", padx=14, pady=12, font=("Segoe UI", 11), anchor="w",
        )
        self.drop_area.pack(fill="x", padx=12, pady=12)

        # --- Botones de Acción ---
        actions = ttk.Frame(self)
        actions.pack(fill="x", pady=(0, 12))

        ttk.Button(actions, text="Seleccionar archivos (Ctrl+O)", command=self._select_files).pack(side="left")
        ttk.Button(actions, text="Limpiar lista", command=self.clear_files).pack(side="left", padx=(10, 0))

        # --- Lista Visual ---
        list_frame = ttk.LabelFrame(self, text="Archivos listos")
        list_frame.pack(fill="both", expand=True)

        self.listbox = tk.Listbox(
            list_frame, activestyle="none", bg=pal["SURFACE"], fg=pal["TEXT"],
            selectbackground=pal["LIST_SELECT"], selectforeground=pal["TEXT"],
            highlightthickness=1, highlightbackground=pal["BORDER"], relief="flat",
            bd=0, font=("Segoe UI", 11),
        )
        self.listbox.configure(selectmode=tk.EXTENDED, exportselection=False)
        self.listbox.pack(fill="both", expand=True, padx=12, pady=12)

        # --- Binds ---
        self._build_ready_files_menu()
        self.listbox.bind("<Button-3>", self._on_ready_files_right_click)
        self.listbox.bind("<Double-Button-1>", lambda _e: self._ready_open_selected())
        self.listbox.bind("<Button-1>", lambda _e: (self.listbox.focus_set(), None))
        self.listbox.bind("<Delete>", lambda _e: self._ready_remove_selected())

        self.listbox.bind("<Control-c>", lambda _e: (self._ready_copy(), "break"))
        self.listbox.bind("<Control-x>", lambda _e: (self._ready_cut(), "break"))
        self.listbox.bind("<Control-v>", lambda _e: (self._ready_paste(), "break"))

        self.listbox.bind("<B1-Motion>", lambda event: self.listbox.selection_set(
            self.listbox.nearest(event.y)) if self.listbox.nearest(event.y) >= 0 else None)

        self._bind_dnd()

    # --- API Pública ---
    def get_paths(self) -> List[str]:
        return self._paths

    def clear_files(self):
        self._paths = []
        self._refresh_list()
        self.controller.set_status("Lista limpiada.", auto_clear_ms=1500)

    def on_theme_changed(self):
        restyle_listbox(self.controller, self.listbox)
        pal = get_pal(self.controller)
        self.drop_area.configure(bg=pal["SURFACE2"], fg=pal["TEXT"], highlightbackground=pal["BORDER"])

    def trigger_select_files(self):
        """Permite que el atajo Ctrl+O global llame a esta función"""
        self._select_files()

    # --- Lógica Interna ---
    def _bind_dnd(self):
        if not _HAS_DND: return
        for w in (self.drop_area, self.listbox):
            try:
                w.drop_target_register(DND_FILES)
                w.dnd_bind("<<Drop>>", self._on_drop)
            except Exception:
                pass

    def _on_drop(self, event):
        self._add_files(parse_dnd_file_list(str(event.data)))

    def _select_files(self):
        last_dir = getattr(self.controller._settings, "last_dir", "") if getattr(self.controller, "_settings",
                                                                                 None) else None
        paths = filedialog.askopenfilenames(
            title="Selecciona archivos", initialdir=last_dir,
            filetypes=[("Excel o PDF", "*.xlsx *.pdf"), ("Excel", "*.xlsx"), ("PDF", "*.pdf"),
                       ("Todos los archivos", "*.*")]
        )
        if paths:
            try:
                if getattr(self.controller, "_settings", None):
                    self.controller._settings.last_dir = str(paths[0]).replace("\\", "/").rsplit("/", 1)[0]
            except Exception:
                pass
            self._add_files(list(paths))

    def _add_files(self, paths: List[str]):
        added = sum(1 for p in paths if
                    str(p).lower().endswith(('.xlsx', '.pdf')) and p not in self._paths and not self._paths.append(
                        str(p)))
        if added:
            self._refresh_list()
            self.controller.set_status(f"Se agregaron {added} archivo(s). Total: {len(self._paths)}.",
                                       auto_clear_ms=2500)

    def _refresh_list(self):
        self.listbox.delete(0, tk.END)
        for p in self._paths:
            self.listbox.insert(tk.END, Path(p).name)

    # --- Operaciones de Archivos (Menú Contextual) ---
    def _build_ready_files_menu(self):
        self._ready_menu = tk.Menu(self, tearoff=False)
        self._ready_menu.add_command(label="Abrir archivo", command=self._ready_open_selected)
        self._ready_menu.add_command(label="Ver ruta", command=self._ready_show_path)
        self._ready_menu.add_separator()
        self._ready_menu.add_command(label="Copiar nombre", command=lambda: self._clipboard_text(
            Path(self._ready_get_selected_paths()[0]).name if self._ready_get_selected_paths() else ""))
        self._ready_menu.add_command(label="Copiar ruta", command=lambda: self._clipboard_text(
            str(self._ready_get_selected_paths()[0]) if self._ready_get_selected_paths() else ""))
        self._ready_menu.add_separator()
        self._ready_menu.add_command(label="Cortar", command=self._ready_cut)
        self._ready_menu.add_command(label="Copiar", command=self._ready_copy)
        self._ready_menu.add_command(label="Pegar", command=self._ready_paste)
        self._ready_menu.add_separator()
        self._ready_menu.add_command(label="Duplicar", command=self._ready_duplicate)
        self._ready_menu.add_command(label="Renombrar archivo...", command=self._ready_rename_on_disk)
        self._ready_menu.add_separator()
        self._ready_menu.add_command(label="Eliminar de la lista", command=self._ready_remove_selected)

    def _clipboard_text(self, text):
        if text:
            self.clipboard_clear()
            self.clipboard_append(text)

    def _on_ready_files_right_click(self, event):
        idx = self.listbox.nearest(event.y)
        if idx >= 0 and idx not in set(self.listbox.curselection()):
            self.listbox.selection_clear(0, tk.END)
            self.listbox.selection_set(idx)
            self.listbox.activate(idx)

        has_sel = bool(self.listbox.curselection())
        can_paste = bool(self._files_clipboard.get("paths"))

        for lbl in ("Abrir archivo", "Ver ruta", "Copiar nombre", "Copiar ruta", "Cortar", "Copiar", "Duplicar",
                    "Renombrar archivo...", "Eliminar de la lista"):
            self._ready_menu.entryconfigure(lbl, state=("normal" if has_sel else "disabled"))
        self._ready_menu.entryconfigure("Pegar", state=("normal" if can_paste else "disabled"))

        self._ready_menu.tk_popup(event.x_root, event.y_root)

    def _ready_get_selected_paths(self):
        return [self._paths[int(i)] for i in (self.listbox.curselection() or []) if 0 <= int(i) < len(self._paths)]

    def _ready_open_selected(self):
        if paths := self._ready_get_selected_paths(): open_file_native(paths[0], parent=self)

    def _ready_show_path(self):
        if paths := self._ready_get_selected_paths(): messagebox.showinfo("Ruta", str(paths[0]), parent=self)

    def _ready_copy(self):
        if paths := self._ready_get_selected_paths(): self._files_clipboard = {"mode": "copy", "paths": list(paths)}

    def _ready_cut(self):
        if paths := self._ready_get_selected_paths():
            self._files_clipboard = {"mode": "cut", "paths": list(paths)}
            self._paths = [p for p in self._paths if p not in set(paths)]
            self._refresh_list()
            self.controller.set_status(f"Cortado: {len(paths)} archivo(s).", auto_clear_ms=1500)

    def _ready_paste(self):
        clip_paths = self._files_clipboard.get("paths") or []
        if not clip_paths: return
        sel = self.listbox.curselection()
        insert_at = min((max(sel) + 1) if sel else len(self._paths), len(self._paths))

        for p in clip_paths:
            self._paths.insert(insert_at, p)
            insert_at += 1

        if self._files_clipboard.get("mode") == "cut":
            self._files_clipboard = {"mode": None, "paths": []}

        self._refresh_list()

    def _ready_duplicate(self):
        if paths := self._ready_get_selected_paths():
            self._paths.extend(paths)
            self._refresh_list()

    def _ready_rename_on_disk(self):
        if not (paths := self._ready_get_selected_paths()): return
        old_path = Path(paths[0])
        if not old_path.exists():
            messagebox.showerror("Error", f"No existe:\n{old_path}", parent=self)
            return

        new_name = simpledialog.askstring("Renombrar", "Nuevo nombre (con extensión):", initialvalue=old_path.name,
                                          parent=self)
        if not new_name or not new_name.strip(): return

        new_path = old_path.with_name(new_name.strip())
        if new_path.exists():
            messagebox.showerror("Error", f"Ya existe:\n{new_path.name}", parent=self)
            return

        try:
            old_path.rename(new_path)
            for i, p in enumerate(self._paths):
                if Path(p) == old_path: self._paths[i] = str(new_path)
            self._refresh_list()
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo renombrar:\n{e}", parent=self)

    def _ready_remove_selected(self):
        if sel := self.listbox.curselection():
            eliminados = 0
            for idx in reversed(sel):
                try:
                    self._paths.pop(int(idx))
                    eliminados += 1
                except Exception:
                    continue
            self._refresh_list()
            self.controller.set_status(f"Se eliminaron {eliminados} archivo(s).", auto_clear_ms=1500)
