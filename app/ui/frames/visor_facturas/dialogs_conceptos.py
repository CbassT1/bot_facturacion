# app/ui/frames/visor_facturas/dialogs_conceptos.py
import tkinter as tk
from tkinter import ttk
import re
from decimal import Decimal, InvalidOperation
from typing import Callable, Optional
from app.ui.theme import get_pal


class EditCellDialog(tk.Toplevel):
    def __init__(self, parent, controller, label: str, current_val: str, mode: str, catalogs,
                 on_save: Callable[[str], None]):
        super().__init__(parent)
        self.title(f"Editar: {label}")
        self.transient(controller)
        self.grab_set()
        self.resizable(False, False)

        self.mode = mode
        self.catalogs = catalogs
        self.on_save = on_save

        pal = get_pal(controller)
        self.configure(bg=pal["BG"])

        wrap = ttk.Frame(self)
        wrap.pack(padx=18, pady=16)

        ttk.Label(wrap, text=label, font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(0, 8))

        if mode == "text":
            self.txt = tk.Text(wrap, width=70, height=6, wrap="word")
            self.txt.insert("1.0", current_val)
            self.txt.pack(fill="both", expand=True)
            self.txt.focus_set()
        else:
            self.ent = ttk.Entry(wrap, width=42)
            self.ent.insert(0, current_val)
            self.ent.pack(fill="x")
            self.ent.focus_set()
            self.ent.selection_range(0, "end")

        btns = ttk.Frame(wrap)
        btns.pack(fill="x", pady=(12, 0))

        ttk.Button(btns, text="Cancelar", command=self.destroy).pack(side="right")
        ttk.Button(btns, text="Guardar", command=self._save).pack(side="right", padx=(0, 10))

        self.bind("<Escape>", lambda _e: self.destroy())
        self.bind("<Return>", lambda _e: self._save())

    def _save(self):
        val = self.txt.get("1.0", "end").strip() if self.mode == "text" else self.ent.get().strip()
        self.on_save(val)
        self.destroy()


class SearchKeyDialog(tk.Toplevel):
    def __init__(self, parent, controller, target: str, current_key: str, catalogs, on_select: Callable[[str], None]):
        super().__init__(parent)
        self.title("Buscador Inteligente SAT")
        # Aumentamos un poco el alto por defecto y fijamos un tamaño mínimo
        self.geometry("750x600")
        self.minsize(650, 450)
        self.transient(parent.winfo_toplevel())
        self.grab_set()

        self.target = target
        self.catalogs = catalogs
        self.on_select = on_select

        pal = get_pal(controller)
        self.configure(bg=pal["BG"])

        wrap = ttk.Frame(self, style="Dialog.TFrame")
        wrap.pack(fill="both", expand=True, padx=15, pady=15)

        # 1. EMPAQUETAMOS LOS BOTONES PRIMERO (Así nunca se ocultan)
        btns = ttk.Frame(wrap, style="Dialog.TFrame")
        btns.pack(side="bottom", fill="x", pady=(10, 0))
        ttk.Button(btns, text="Cancelar", command=self.destroy).pack(side="right")
        ttk.Button(btns, text="Sustituir clave", command=self._apply_selected).pack(side="right", padx=(0, 10))

        # 2. LUEGO EMPAQUETAMOS LA CABECERA
        src_name = "unidades_medida.xlsx" if target == "unidad" else "claves_sat.xlsx"
        ttk.Label(wrap, text=f"Fuente: {src_name}", style="Dialog.TLabel", font=("Segoe UI", 11, "bold")).pack(
            anchor="w", pady=(0, 6))
        ttk.Label(wrap, text=f"Clave actual: {current_key}", style="DialogMuted.TLabel").pack(anchor="w", pady=(0, 8))

        self.q_var = tk.StringVar(value="")
        ent = ttk.Entry(wrap, textvariable=self.q_var, style="Dialog.TEntry")
        ent.pack(fill="x")
        ent.focus_set()

        # 3. Y AL FINAL LA LISTA EXPANDIBLE
        self.tv = ttk.Treeview(wrap, columns=("clave", "nombre"), show="headings", height=16, style="Dialog.Treeview")
        self.tv.heading("clave", text="Clave")
        self.tv.heading("nombre", text="Nombre")
        self.tv.column("clave", width=140, anchor="w", stretch=False)
        self.tv.column("nombre", width=520, anchor="w", stretch=True)
        self.tv.pack(side="top", fill="both", expand=True, pady=(10, 0))

        self.data_dict = catalogs.unidad_name if target == "unidad" else catalogs.prodserv_name

        self._fill_list("")
        self.q_var.trace_add("write", lambda *_: self._fill_list(self.q_var.get()))

        self.tv.bind("<Double-1>", lambda _e: self._apply_selected())
        self.bind("<Escape>", lambda _e: self.destroy())
        self.bind("<Return>", lambda _e: self._apply_selected())

    # ============================================================
    # MOTOR DE BÚSQUEDA POR PUNTUACIÓN (SCORING)
    # ============================================================
    def _fill_list(self, query: str):
        for it in self.tv.get_children():
            self.tv.delete(it)

        query_clean = query.strip().lower()
        terms = query_clean.split()

        # Si está vacío, solo cargamos los primeros 300
        if not terms:
            count = 0
            for k, name in self.data_dict.items():
                self.tv.insert("", "end", values=(k, name))
                count += 1
                if count >= 300: break
            return

        results = []

        for k, name in self.data_dict.items():
            k_str = str(k).lower()
            name_lower = str(name).lower()
            haystack = f"{k_str} {name_lower}"

            # Condición base: Todos los términos deben existir en la cadena
            if all(term in haystack for term in terms):
                score = 0

                # Regla 1: Coincidencia exacta de la clave (Aporta muchísimos puntos)
                if query_clean == k_str:
                    score += 1000

                # Regla 2: Coincidencia de la frase completa como palabra exacta (Ej. "Metro cuadrado")
                if re.search(rf"\b{re.escape(query_clean)}\b", name_lower):
                    score += 500

                # Regla 3: Análisis término por término
                for term in terms:
                    # Si el término es una palabra completa (ej. "Metro" en lugar de "Espectrómetro")
                    if re.search(rf"\b{re.escape(term)}\b", name_lower):
                        score += 50
                    else:
                        # Si es una coincidencia parcial (ej. "metro" dentro de "centímetro")
                        score += 10

                # Regla 4: Penalización ligera por longitud (Prioriza nombres cortos y directos)
                score -= len(name_lower) * 0.1

                results.append((score, k, name))

        # Ordenamos la lista de mayor a menor puntuación
        results.sort(key=lambda x: x[0], reverse=True)

        # Insertamos solo el Top 300 en la tabla
        for r in results[:300]:
            self.tv.insert("", "end", values=(r[1], r[2]))

    def _apply_selected(self):
        sel2 = self.tv.selection()
        if not sel2: return
        vals = self.tv.item(sel2[0], "values")
        if not vals: return

        new_key = str(vals[0]).strip()
        self.on_select(new_key)
        self.destroy()
