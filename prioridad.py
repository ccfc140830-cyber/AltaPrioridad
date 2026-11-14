"""AltaPrioridad: gestiona la prioridad de CPU de programas via IFEO\\PerfOptions."""
import ctypes
import os
import sys
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import prio_core as core
import prio_profiles as prof

PANEL_W = 330   # ancho inicial del panel de procesos desplegado
PANEL_MIN, PANEL_MAX = 200, 700   # limites al arrastrar el divisor
STRIP_W = 28    # ancho de la tira con la flecha cuando esta plegado
CHK_ON, CHK_OFF = "☑", "☐"
# Orden semantico de prioridades al ordenar una columna (nombre largo y corto).
RANK = {"?": -1, "inactiva (idle)": 0, "inactiva": 0, "por debajo de lo normal": 1, "baja": 1, "normal": 2,
        "por encima de lo normal": 3, "sobre normal": 3, "alta": 4, "tiempo real (peligroso)": 5,
        "tiempo real": 5}
SHORT = {"Inactiva (Idle)": "Inactiva", "Por debajo de lo normal": "Baja", "Normal": "Normal",
         "Por encima de lo normal": "Sobre normal", "Alta": "Alta", "Tiempo real (peligroso)": "Tiempo real"}


def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def relaunch_as_admin():
    if getattr(sys, "frozen", False):
        exe, params = sys.executable, ""
    else:
        exe = sys.executable
        params = f'"{os.path.abspath(__file__)}"'
    ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, params, None, 1)


class CheckTree(ttk.Treeview):
    """Lista con casilla por fila. Clic en la casilla marca; clic en el encabezado marca todo.

    picked() devuelve las filas marcadas o, si no hay ninguna, las resaltadas.
    """

    def __init__(self, master, cols, height=8, selectmode="extended"):
        super().__init__(master, columns=[c[0] for c in cols], show="tree headings",
                         selectmode=selectmode, height=height)
        self.heading("#0", text=CHK_OFF, command=self.toggle_all)
        self.column("#0", width=44, minwidth=44, stretch=False, anchor="center")
        self._titles = {}
        for cid, title, w in cols:
            self._titles[cid] = title
            self.heading(cid, text=title, command=lambda c=cid: self.sort_by(c))
            self.column(cid, width=w, minwidth=30, anchor="w")
        self._cols = [c[0] for c in cols]
        self._sort = None      # (columna, descendente)
        self._checked = set()
        self._enabled = True
        self.tag_configure("off", foreground="#999999")
        self.on_double = None  # callback(iid): doble clic fuera de la casilla
        self.bind("<Button-1>", self._click, add="+")
        self.bind("<Double-1>", self._dbl)
        self.bind("<space>", self._space)

    # ---- ordenar por columna ----
    @staticmethod
    def _key(v):
        s = str(v).strip().lower()
        if s in RANK:
            return (0, RANK[s], "")
        try:
            return (0, float(s), "")
        except ValueError:
            return (1, 0, s)

    def sort_by(self, col, reverse=None):
        """Clic en un encabezado: ascendente; otro clic en el mismo: descendente."""
        if not self._enabled:
            return
        if reverse is None:
            reverse = self._sort == (col, False)
        self._sort = (col, reverse)
        self._apply_sort()
        self._arrows()

    def _apply_sort(self):
        if not self._sort:
            return
        col, rev = self._sort
        first = self._cols[0]
        kids = list(self.get_children())
        order = sorted(kids, key=lambda i: (self._key(self.set(i, col)), str(self.set(i, first)).lower()),
                       reverse=rev)
        if order != kids:
            for pos, i in enumerate(order):
                self.move(i, "", pos)

    def _arrows(self):
        for cid, title in self._titles.items():
            mark = ""
            if self._sort and self._sort[0] == cid:
                mark = " ▼" if self._sort[1] else " ▲"
            self.heading(cid, text=title + mark)

    # ---- habilitar / deshabilitar ----
    def set_enabled(self, flag):
        self._enabled = flag
        self._tag_all()

    def _tag_all(self):
        for i in self.get_children():
            self.item(i, tags=() if self._enabled else ("off",))

    def _dbl(self, e):
        if not self._enabled:
            return "break"
        # El 2.o clic rapido llega como Double-1: en la casilla tambien debe marcar.
        if self.identify_column(e.x) == "#0":
            return self._click(e)
        iid = self.identify_row(e.y)
        if iid and self.on_double:
            self.on_double(iid)
        return None

    def _click(self, e):
        if not self._enabled:
            return "break"
        if self.identify_region(e.x, e.y) in ("tree", "cell") and self.identify_column(e.x) == "#0":
            iid = self.identify_row(e.y)
            if iid:
                self.toggle(iid)
                return "break"
        return None

    def _space(self, _e):
        if not self._enabled:
            return "break"
        sel = self.selection()
        if sel:
            on = sel[0] not in self._checked
            for i in sel:
                self.toggle(i, on)
        return "break"

    def _paint(self, iid):
        if self.exists(iid):
            self.item(iid, text=CHK_ON if iid in self._checked else CHK_OFF)

    def _head(self):
        kids = self.get_children()
        on = bool(kids) and all(k in self._checked for k in kids)
        self.heading("#0", text=CHK_ON if on else CHK_OFF)

    def toggle(self, iid, state=None):
        on = (iid not in self._checked) if state is None else state
        (self._checked.add if on else self._checked.discard)(iid)
        self._paint(iid)
        self._head()

    def toggle_all(self):
        if not self._enabled:
            return
        kids = self.get_children()
        on = not (bool(kids) and all(k in self._checked for k in kids))
        for k in kids:
            self.toggle(k, on)

    def uncheck(self, iids):
        for i in iids:
            self._checked.discard(i)
            self._paint(i)
        self._head()

    def checked(self):
        return [i for i in self.get_children() if i in self._checked]

    def picked(self):
        return self.checked() or list(self.selection())

    def set_rows(self, rows):
        """rows = [(iid, values)]. Actualiza en sitio: conserva seleccion y casillas."""
        want = [r[0] for r in rows]
        keep = set(want)
        for iid in self.get_children():
            if iid not in keep:
                self.delete(iid)
        for pos, (iid, vals) in enumerate(rows):
            if self.exists(iid):
                self.item(iid, values=vals)
                if not self._sort and self.index(iid) != pos:
                    self.move(iid, "", pos)
            else:
                self.insert("", pos, iid=iid, values=vals)
            self._paint(iid)
        self._apply_sort()
        self._tag_all()
        self._head()


def tree_box(master, cols, height=8, selectmode="extended"):
    box = ttk.Frame(master)
    t = CheckTree(box, cols, height, selectmode)
    sb = ttk.Scrollbar(box, orient="vertical", command=t.yview)
    t.configure(yscrollcommand=sb.set)
    t.pack(side="left", fill="both", expand=True)
    sb.pack(side="right", fill="y")
    return box, t


class PickProcess(tk.Toplevel):
    """Elegir uno o varios procesos en ejecucion (con casillas). result = lista o None."""

    def __init__(self, master):
        super().__init__(master)
        self.title("Elegir procesos en ejecucion")
        self.geometry("380x500")
        self.transient(master)
        self.result = None
        self.names = sorted({e for _, e in core.running_processes() if core.valid_name(e)}, key=str.lower)
        self.q = tk.StringVar()
        self.q.trace_add("write", lambda *_: self.fill())
        ttk.Entry(self, textvariable=self.q).pack(fill="x", padx=8, pady=(8, 4))
        box, self.ct = tree_box(self, [("exe", "Programa", 260)], height=16)
        box.pack(fill="both", expand=True, padx=8)
        self.ct.on_double = self.dbl
        ttk.Button(self, text="Agregar marcados", command=self.ok).pack(pady=8)
        self.fill()
        self.grab_set()

    def fill(self):
        f = self.q.get().lower()
        self.ct.set_rows([(n, (n,)) for n in self.names if f in n.lower()])

    def dbl(self, iid):
        self.result = [iid]
        self.destroy()

    def ok(self):
        sel = self.ct.picked()
        if sel:
            self.result = sel
            self.destroy()


def split_names(text):
    return [x.strip() for x in text.replace(";", ",").replace("\n", ",").split(",") if x.strip()]


class ProfileDialog(tk.Toplevel):
    """Crea o edita un perfil. result = dict del perfil o None."""

    def __init__(self, master, profile, others, triggers=(), name=""):
        super().__init__(master)
        self.title("Perfil de juego")
        self.transient(master)
        self.result = None
        self.profile = profile
        self.others = [p["name"] for p in others if p is not profile]
        p = profile or prof.new_profile(name, triggers)
        self.v_name = tk.StringVar(value=p["name"])
        self.v_trig = tk.StringVar(value=", ".join(p["triggers"]))
        self.v_rel = tk.StringVar(value=", ".join(p["related"]))
        self.v_keep = tk.StringVar(value=", ".join(p["keep"]))
        self.v_prio = tk.StringVar(value=p["priority"])
        self.v_kids = tk.BooleanVar(value=p["children"])
        self.v_folder = tk.BooleanVar(value=p["same_folder"])
        self.v_low = tk.BooleanVar(value=p["lower_others"])

        f = ttk.Frame(self, padding=12)
        f.pack(fill="both", expand=True)
        f.columnconfigure(1, weight=1)

        def row(r, label, var, hint=None):
            ttk.Label(f, text=label).grid(row=r, column=0, sticky="w", pady=3)
            ttk.Entry(f, textvariable=var, width=52).grid(row=r, column=1, sticky="we", padx=6, pady=3)
            if hint:
                ttk.Label(f, text=hint, foreground="gray").grid(row=r + 1, column=1, sticky="w", padx=6)

        row(0, "Nombre del perfil", self.v_name)
        row(1, "Ejecutables del juego", self.v_trig, "Cuando alguno este abierto, el perfil se activa. Separados por coma.")
        bb = ttk.Frame(f)
        bb.grid(row=3, column=1, sticky="w", padx=6)
        ttk.Button(bb, text="Elegir procesos en ejecucion...", command=lambda: self.pick_proc(self.v_trig)).pack(side="left")
        ttk.Button(bb, text="Elegir .exe...", command=lambda: self.pick_file(self.v_trig)).pack(side="left", padx=6)
        row(4, "Procesos relacionados", self.v_rel, "Extras que tambien suben (lanzador, anti-trampas...). Opcional.")
        row(6, "Nunca tocar", self.v_keep, "Programas que no se bajan a Normal aunque esten en Alta. Opcional.")
        ttk.Label(f, text="Prioridad del juego").grid(row=8, column=0, sticky="w", pady=6)
        ttk.Combobox(f, textvariable=self.v_prio, state="readonly", width=26,
                     values=[n for n in core.PRIORITIES if n != core.REALTIME]).grid(row=8, column=1, sticky="w", padx=6)
        ttk.Checkbutton(f, text="Incluir procesos hijos del juego", variable=self.v_kids).grid(
            row=9, column=0, columnspan=2, sticky="w")
        ttk.Checkbutton(f, text="Incluir procesos que corren desde la carpeta del juego",
                        variable=self.v_folder).grid(row=10, column=0, columnspan=2, sticky="w")
        ttk.Checkbutton(f, text="Bajar a Normal los demas programas que esten en Alta o Por encima de lo normal "
                        "(al cerrar el juego vuelven como estaban)",
                        variable=self.v_low).grid(row=11, column=0, columnspan=2, sticky="w")
        bt = ttk.Frame(f)
        bt.grid(row=12, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(bt, text="Guardar", command=self.ok).pack(side="left")
        ttk.Button(bt, text="Cancelar", command=self.destroy).pack(side="left", padx=6)
        self.grab_set()

    def pick_proc(self, var):
        d = PickProcess(self)
        self.wait_window(d)
        for n in d.result or []:
            self.append(var, n)

    def pick_file(self, var):
        fn = filedialog.askopenfilename(parent=self, title="Elegir programa", filetypes=[("Ejecutable", "*.exe")])
        if fn:
            self.append(var, os.path.basename(fn))

    @staticmethod
    def append(var, name):
        cur = split_names(var.get())
        if name.lower() not in [c.lower() for c in cur]:
            cur.append(name)
        var.set(", ".join(cur))

    def ok(self):
        name = self.v_name.get().strip()
        trig = split_names(self.v_trig.get())
        rel = split_names(self.v_rel.get())
        keep = split_names(self.v_keep.get())
        if not name or name in self.others:
            messagebox.showerror("Nombre", "Escribe un nombre unico para el perfil.", parent=self)
            return
        bad = [x for x in trig + rel + keep if not core.valid_name(x)]
        if not trig or bad:
            messagebox.showerror("Ejecutables", "Indica al menos un ejecutable del juego. Todos deben ser "
                                 f"nombres .exe sin ruta.{(' Invalidos: ' + ', '.join(bad)) if bad else ''}", parent=self)
            return
        enabled = self.profile.get("enabled", True) if self.profile else True
        self.result = prof.new_profile(
            name, trig, related=rel, keep=keep, priority=self.v_prio.get(), children=self.v_kids.get(),
            same_folder=self.v_folder.get(), lower_others=self.v_low.get(), enabled=enabled)
        self.destroy()


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Alta Prioridad - gestor de prioridad de CPU")
        self.pdata = prof.load()
        self.pdata.setdefault("panel", True)
        self.engine = prof.Engine()
        self.engine.alive = {pid: (pp, exe) for pid, pp, exe in core.process_info()}
        self.panel_open = bool(self.pdata["panel"])
        try:
            self.panel_w = max(PANEL_MIN, min(PANEL_MAX, int(self.pdata.get("panel_w", PANEL_W))))
        except (TypeError, ValueError):
            self.panel_w = PANEL_W
        self._entries = {}
        self._cand_cache = None
        self._msg_until = 0.0
        self.geometry(f"{880 + (self.panel_w if self.panel_open else STRIP_W)}x640")
        self.minsize(700, 560)

        self.status = tk.StringVar()
        ttk.Label(self, textvariable=self.status, relief="sunken", anchor="w", padding=4).pack(side="bottom", fill="x")
        # Divisor arrastrable: el ancho del panel de procesos es independiente del panel general.
        self.paned = tk.PanedWindow(self, orient="horizontal", sashwidth=6, sashrelief="raised",
                                    bd=0, bg="#c8c8c8", opaqueresize=True)
        self.paned.pack(fill="both", expand=True)
        self.nb = ttk.Notebook(self.paned)
        self.dock = ttk.Frame(self.paned)
        self.paned.add(self.nb, stretch="always", minsize=420)
        self.paned.add(self.dock, stretch="never", minsize=STRIP_W,
                       width=self.panel_w if self.panel_open else STRIP_W)
        self.paned.bind("<ButtonRelease-1>", lambda _e: self.after_idle(self.sync_from_sash))
        reg = ttk.Frame(self.nb)
        self.nb.add(reg, text="Permanente (registro)")
        ptab = ttk.Frame(self.nb)
        self.nb.add(ptab, text="Perfiles de juego")
        self.build_registry(reg)
        self.build_profiles(ptab)
        self.build_dock()
        self.nb.bind("<<NotebookTabChanged>>", lambda _: self.on_context())
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.set_panel(self.panel_open, resize=False)
        self.apply_panel_state()
        self.refresh()
        self.refresh_profiles()
        self.after(3000, self.autorefresh)
        self.after(1500, self.prof_tick)

    # ---- construccion de pestanas ----
    def build_registry(self, reg):
        top = ttk.Frame(reg, padding=8)
        top.pack(fill="x")
        ttk.Button(top, text="Agregar .exe...", command=self.add_file).pack(side="left")
        ttk.Label(top, text="  o usa el panel de la derecha (doble clic o ◀ Agregar)",
                  foreground="gray").pack(side="left")
        ttk.Button(top, text="Importar...", command=self.do_import).pack(side="right")
        ttk.Button(top, text="Exportar...", command=self.do_export).pack(side="right", padx=6)

        box, self.rt = tree_box(reg, [("exe", "Programa", 230), ("saved", "Prioridad guardada", 170),
                                      ("run", "Corriendo", 90), ("live", "Prioridad en vivo", 180)], height=14)
        box.pack(fill="both", expand=True, padx=8)

        bar = ttk.Frame(reg, padding=8)
        bar.pack(fill="x")
        ttk.Label(bar, text="Prioridad:").pack(side="left")
        self.rt_ok = tk.BooleanVar(value=False)
        self.prio = tk.StringVar(value="Alta")
        self.combo = ttk.Combobox(bar, textvariable=self.prio, state="readonly", width=26)
        self.combo.pack(side="left", padx=6)
        self.combo.bind("<<ComboboxSelected>>", lambda _: self.update_target())
        self.refresh_combo()
        ttk.Checkbutton(bar, text="Permitir Tiempo real", variable=self.rt_ok,
                        command=self.rt_toggle).pack(side="left", padx=6)
        ttk.Button(bar, text="Quitar marcados", command=self.remove).pack(side="right")
        ttk.Button(bar, text="Aplicar ahora", command=self.apply_now).pack(side="right", padx=6)
        ttk.Button(bar, text="Cambiar prioridad", command=self.change).pack(side="right")
        ttk.Button(bar, text="Refrescar", command=self.refresh).pack(side="right", padx=6)

    def build_profiles(self, tab):
        top = ttk.Frame(tab, padding=8)
        top.pack(fill="x")
        self.watch = tk.BooleanVar(value=self.pdata["watch"])
        ttk.Checkbutton(top, text="Vigilar y aplicar perfiles automaticamente", variable=self.watch,
                        command=self.watch_changed).pack(side="left")
        ttk.Button(top, text="Nuevo perfil...", command=self.prof_new).pack(side="right")

        box, self.pt = tree_box(tab, [("name", "Perfil", 150), ("games", "Ejecutables del juego", 230),
                                      ("state", "Estado", 300)], height=5, selectmode="browse")
        box.pack(fill="x", padx=8)
        self.pt.bind("<<TreeviewSelect>>", lambda _: self.on_context())
        self.pt.on_double = lambda _iid: self.prof_edit()
        pb = ttk.Frame(tab, padding=(8, 4))
        pb.pack(fill="x")
        ttk.Button(pb, text="Editar...", command=self.prof_edit).pack(side="left")
        ttk.Button(pb, text="Activar / Desactivar marcados", command=self.prof_toggle).pack(side="left", padx=6)
        ttk.Button(pb, text="Eliminar marcados", command=self.prof_delete).pack(side="left")

        self.tlabel = tk.StringVar()
        ttk.Label(tab, textvariable=self.tlabel, padding=(8, 6, 8, 2)).pack(anchor="w")
        box, self.tt = tree_box(tab, [("exe", "Ejecutable", 260), ("run", "Estado", 160)], height=4)
        box.pack(fill="x", padx=8)
        tb = ttk.Frame(tab, padding=(8, 4))
        tb.pack(fill="x")
        ttk.Button(tb, text="Agregar procesos...", command=self.prof_add_triggers).pack(side="left")
        ttk.Button(tb, text="Quitar marcados", command=self.prof_remove_triggers).pack(side="left", padx=6)
        ttk.Label(tb, text="(el panel de procesos esta desactivado en esta pestana)",
                  foreground="gray").pack(side="left", padx=6)

        ttk.Label(tab, text="Juegos detectados en ejecucion sin perfil (carpetas de Steam, Epic, GOG, Xbox...):",
                  padding=(8, 8, 8, 2)).pack(anchor="w")
        box, self.ct = tree_box(tab, [("exe", "Programa", 200), ("path", "Ruta", 420)], height=4)
        box.pack(fill="x", padx=8)
        self.ct.on_double = self.ct_dbl
        ttk.Button(tab, text="Crear perfil con los marcados", command=self.prof_from_candidates
                   ).pack(anchor="w", padx=8, pady=6)

    def build_dock(self):
        strip = ttk.Frame(self.dock, width=STRIP_W)
        strip.pack(side="left", fill="y")
        self.tbtn = ttk.Button(strip, text="▶", width=2, command=self.toggle_panel)
        self.tbtn.pack(pady=(6, 4), padx=2)
        ttk.Label(strip, text="\n".join("PROCESOS"), foreground="gray", justify="center").pack()

        self.body = ttk.Frame(self.dock)
        ttk.Label(self.body, text="Procesos en ejecucion", font=("Segoe UI", 10, "bold")
                  ).pack(anchor="w", padx=6, pady=(8, 0))
        self.target_var = tk.StringVar()
        wrapped = [ttk.Label(self.body, textvariable=self.target_var, foreground="#555", justify="left")]
        wrapped[0].pack(anchor="w", padx=6, pady=(0, 4))
        f = ttk.Frame(self.body)
        f.pack(fill="x", padx=6)
        ttk.Label(f, text="Buscar:").pack(side="left")
        self.pq = tk.StringVar()
        self.pq.trace_add("write", lambda *_: self.refresh_panel())
        self.pq_entry = ttk.Entry(f, textvariable=self.pq)
        self.pq_entry.pack(side="left", fill="x", expand=True, padx=4)
        self.hide_sys = tk.BooleanVar(value=True)
        self.hide_cb = ttk.Checkbutton(self.body, text="Ocultar procesos del sistema", variable=self.hide_sys,
                                       command=self.refresh_panel)
        self.hide_cb.pack(anchor="w", padx=6, pady=2)
        box, self.pp = tree_box(self.body, [("exe", "Programa", 112), ("n", "Inst.", 36), ("prio", "Prioridad", 74)],
                                height=18)
        box.pack(fill="both", expand=True, padx=6)
        self.pp.on_double = lambda iid: self.panel_add([self.pp.set(iid, "exe")])
        bb = ttk.Frame(self.body)
        bb.pack(fill="x", padx=6, pady=6)
        self.btn_add = ttk.Button(bb, text="◀ Agregar", command=self.panel_add)
        self.btn_add.pack(side="left", expand=True, fill="x")
        self.btn_rm = ttk.Button(bb, text="Quitar ▶", command=self.panel_remove)
        self.btn_rm.pack(side="left", expand=True, fill="x", padx=(6, 0))
        wrapped.append(ttk.Label(self.body, text="Doble clic en un proceso = agregar. Marca casillas para varios a la vez. "
                                 "Arrastra el borde izquierdo del panel para cambiar su ancho.",
                                 foreground="gray", justify="left"))
        wrapped[1].pack(anchor="w", padx=6, pady=(0, 6))
        # El texto se reajusta al ancho que el usuario le de al panel.
        self.body.bind("<Configure>", lambda e: [w.config(wraplength=max(120, e.width - 24)) for w in wrapped])

    # ---- panel plegable ----
    def toggle_panel(self):
        self.set_panel(not self.panel_open)
        self.save_profiles()

    def set_panel(self, open_, resize=True):
        was = self.panel_open
        self.panel_open = open_
        self.pdata["panel"] = open_
        dw = self.dock.winfo_width()
        if open_:
            self.body.pack(side="left", fill="both", expand=True)
            self.tbtn.config(text="▶")
        else:
            self.body.pack_forget()
            self.tbtn.config(text="◀")
        target = self.panel_w if open_ else STRIP_W
        if resize and was != open_ and self.state() == "normal":
            # la ventana crece o se encoge lo mismo que el panel: el panel general no cambia de ancho
            self.update_idletasks()
            self.geometry(f"{max(self.winfo_width() + target - dw, 560)}x{self.winfo_height()}")
        self.paned.paneconfigure(self.dock, minsize=PANEL_MIN if open_ else STRIP_W, width=target)
        if open_:
            self.update_target()
            self.refresh_panel()

    def sync_from_sash(self):
        """Tras arrastrar el divisor: recuerda el ancho elegido (o abre el panel si estaba plegado)."""
        w = self.dock.winfo_width()
        if not self.panel_open:
            if w <= STRIP_W + 40:
                return
            self.set_panel(True, resize=False)
        self.panel_w = max(PANEL_MIN, min(PANEL_MAX, w))
        self.pdata["panel_w"] = self.panel_w
        self.save_profiles()

    def tab_kind(self):
        return "reg" if self.nb.index(self.nb.select()) == 0 else "prof"

    def update_target(self):
        if self.tab_kind() == "reg":
            self.target_var.set(f"Destino: registro permanente, prioridad {self.prio.get()} (se escribe en HKLM).")
        else:
            self.target_var.set("Desactivado en la pestana Perfiles de juego. Vuelve a Permanente (registro) "
                                "para usar este panel.")

    def apply_panel_state(self):
        """El panel solo funciona en la pestana Permanente; en Perfiles queda deshabilitado."""
        on = self.tab_kind() == "reg"
        self.pp.set_enabled(on)
        for w in (self.pq_entry, self.hide_cb, self.btn_add, self.btn_rm):
            w.state(["!disabled"] if on else ["disabled"])
        self.update_target()
        if on:
            self.refresh_panel()

    def on_context(self):
        self.apply_panel_state()
        self.refresh_triggers()

    def panel_excluded(self):
        return {e.lower() for e in self._entries}

    def refresh_panel(self):
        if not self.panel_open or self.tab_kind() != "reg":
            return
        excl = self.panel_excluded()
        q = self.pq.get().strip().lower()
        hide = self.hide_sys.get()
        groups = {}
        for pid, (_, exe) in self.engine.alive.items():
            low = exe.lower()
            if not core.valid_name(exe) or low in excl or (hide and low in core.SYSTEM_EXES) or (q and q not in low):
                continue
            groups.setdefault(low, [exe, []])[1].append(pid)
        rows = []
        for low in sorted(groups):
            exe, pids = groups[low]
            rows.append((low, (exe, len(pids), SHORT.get(core.live_priority(pids[0]), "?"))))
        self.pp.set_rows(rows)

    def panel_add(self, names=None):
        if self.tab_kind() != "reg":
            return
        if names is None:
            names = [self.pp.set(i, "exe") for i in self.pp.picked()]
        if not names:
            self.say("Marca casillas o selecciona procesos en el panel.")
            return
        self.add_many(names)

    def panel_remove(self):
        if self.tab_kind() == "reg":
            self.remove()

    # ---- ejecutables de un perfil (con el panel desactivado en esta pestana) ----
    def prof_add_triggers(self):
        p = self.cur_profile()
        if not p:
            self.say("Selecciona primero un perfil de la tabla.")
            return
        d = PickProcess(self)
        self.wait_window(d)
        have = {t.lower() for t in p["triggers"]}
        new = [n for n in d.result or [] if n.lower() not in have]
        if not new:
            return
        p["triggers"].extend(new)
        self.save_profiles()
        self.prof_tick(reschedule=False)
        self.say(f"{len(new)} ejecutable(s) agregado(s) al perfil «{p['name']}».")

    def prof_remove_triggers(self):
        p = self.cur_profile()
        if not p:
            self.say("Selecciona primero un perfil de la tabla.")
            return
        sel = self.tt.picked()
        if not sel:
            self.say("Marca casillas en la lista de ejecutables del perfil.")
            return
        drop = {s.lower() for s in sel}
        left = [t for t in p["triggers"] if t.lower() not in drop]
        if not left:
            messagebox.showerror("Perfil", "Un perfil necesita al menos un ejecutable del juego.\n"
                                 "Si ya no lo quieres, elimina el perfil.")
            return
        p["triggers"] = left
        self.tt.uncheck(sel)
        self.save_profiles()
        self.prof_tick(reschedule=False)
        self.say(f"{len(sel)} ejecutable(s) quitado(s) del perfil «{p['name']}».")

    # ---- perfiles de juego ----
    def save_profiles(self):
        self.pdata["watch"] = self.watch.get()
        prof.save(self.pdata)

    def watch_changed(self):
        self.save_profiles()
        self.prof_tick(reschedule=False)

    def prof_tick(self, reschedule=True):
        try:
            self.engine.tick(self.pdata["profiles"] if self.pdata["watch"] else [])
            self.refresh_profiles()
            self.refresh_panel()
        except Exception as e:  # el motor nunca debe tumbar la app
            self.say(f"Perfiles: {e}")
        if reschedule:
            self.after(2000, self.prof_tick)

    def refresh_profiles(self):
        st = self.engine.status()
        rows = []
        for p in self.pdata["profiles"]:
            n = p["name"]
            if not p.get("enabled", True):
                s = "Desactivado"
            elif not self.pdata["watch"]:
                s = "Vigilancia apagada"
            elif n in st:
                g, low, fail = st[n]
                s = f"ACTIVO: {g} proceso(s) en {p['priority']}, {low} bajado(s) a Normal"
                if fail:
                    s += f", {fail} sin permiso"
            else:
                s = "Esperando el juego"
            rows.append((n, (n, ", ".join(p["triggers"]), s)))
        self.pt.set_rows(rows)
        self.refresh_triggers()
        cands = self.engine.candidates(self.pdata["profiles"])
        if cands != self._cand_cache:
            self._cand_cache = cands
            self.ct.set_rows([(exe, (exe, path)) for exe, path in cands])

    def refresh_triggers(self):
        p = self.cur_profile()
        if not p:
            self.tlabel.set("Ejecutables del perfil: selecciona un perfil en la tabla de arriba.")
            self.tt.set_rows([])
            return
        running = {exe.lower() for _, exe in self.engine.alive.values()}
        self.tlabel.set(f"Ejecutables del perfil «{p['name']}»:")
        self.tt.set_rows([(t.lower(), (t, "Corriendo" if t.lower() in running else "-")) for t in p["triggers"]])

    def cur_profile(self):
        s = self.pt.selection()
        if not s:
            return None
        return next((p for p in self.pdata["profiles"] if p["name"] == s[0]), None)

    def picked_profiles(self):
        names = self.pt.picked()
        return [p for p in self.pdata["profiles"] if p["name"] in names]

    def prof_new(self, triggers=(), name=""):
        d = ProfileDialog(self, None, self.pdata["profiles"], triggers=triggers, name=name)
        self.wait_window(d)
        if d.result:
            self.pdata["profiles"].append(d.result)
            self.save_profiles()
            self.prof_tick(reschedule=False)

    def prof_edit(self):
        p = self.cur_profile()
        if not p:
            self.say("Selecciona un perfil de la tabla.")
            return
        d = ProfileDialog(self, p, self.pdata["profiles"])
        self.wait_window(d)
        if d.result:
            if p["name"] in self.engine.active:
                self.engine.restore(p["name"])
            p.clear()
            p.update(d.result)
            self.save_profiles()
            self.prof_tick(reschedule=False)

    def prof_toggle(self):
        ps = self.picked_profiles()
        if not ps:
            self.say("Marca o selecciona al menos un perfil.")
            return
        new = not all(p.get("enabled", True) for p in ps)
        for p in ps:
            p["enabled"] = new
        self.save_profiles()
        self.prof_tick(reschedule=False)
        self.say(f"{len(ps)} perfil(es) {'activado(s)' if new else 'desactivado(s)'}.")

    def prof_delete(self):
        ps = self.picked_profiles()
        if not ps:
            self.say("Marca o selecciona al menos un perfil.")
            return
        if not messagebox.askyesno("Eliminar", f"¿Eliminar {len(ps)} perfil(es)?"):
            return
        for p in ps:
            self.engine.restore(p["name"])
            self.pdata["profiles"].remove(p)
        self.pt.uncheck([p["name"] for p in ps])
        self.save_profiles()
        self.prof_tick(reschedule=False)

    def ct_dbl(self, iid):
        self.prof_new(triggers=[iid], name=os.path.splitext(iid)[0])

    def prof_from_candidates(self):
        sel = self.ct.picked()
        if not sel:
            self.say("Marca o selecciona juegos de la lista de detectados.")
            return
        if len(sel) == 1:
            self.prof_new(triggers=[sel[0]], name=os.path.splitext(sel[0])[0])
            return
        names = {p["name"] for p in self.pdata["profiles"]}
        made = 0
        for exe in sel:
            n = os.path.splitext(exe)[0]
            if n not in names:
                self.pdata["profiles"].append(prof.new_profile(n, [exe]))
                names.add(n)
                made += 1
        self.ct.uncheck(sel)
        self.save_profiles()
        self.prof_tick(reschedule=False)
        self.say(f"{made} perfil(es) creado(s) con valores por defecto. Ajustalos con Editar...")

    def on_close(self):
        try:
            self.engine.restore_all()
        finally:
            self.destroy()

    # ---- registro permanente ----
    def say(self, msg):
        self.status.set(msg)
        self._msg_until = time.time() + 6

    def idle_say(self, msg):
        if time.time() > self._msg_until:
            self.status.set(msg)

    def refresh_combo(self):
        names = [n for n in core.PRIORITIES if n != core.REALTIME or self.rt_ok.get()]
        self.combo["values"] = names
        if self.prio.get() not in names:
            self.prio.set("Alta")

    def rt_toggle(self):
        if self.rt_ok.get() and not messagebox.askyesno(
                "Tiempo real", "Tiempo real puede congelar todo el equipo, incluso el mouse y el teclado.\n"
                "Un programa mal hecho en Tiempo real obliga a reiniciar a la fuerza.\n\n¿Habilitar la opcion?",
                icon="warning", default="no"):
            self.rt_ok.set(False)
        self.refresh_combo()

    def refresh(self):
        try:
            entries = core.list_entries()
        except OSError as e:
            self.say(f"Error leyendo registro: {e}")
            return
        self._entries = entries
        live = core.live_state()
        rows = []
        for exe in sorted(entries, key=str.lower):
            inst = live.get(exe.lower(), [])
            vals = sorted({p or "?" for _, p in inst})
            rows.append((exe, (exe, entries[exe], f"Si ({len(inst)})" if inst else "No", ", ".join(vals))))
        self.rt.set_rows(rows)
        self.idle_say(f"{len(entries)} programa(s) con prioridad guardada.")

    def autorefresh(self):
        self.refresh()
        self.after(3000, self.autorefresh)

    def confirm_system(self, exe):
        if exe.lower() in core.SYSTEM_EXES:
            return messagebox.askyesno(
                "Proceso del sistema",
                f"{exe} es un proceso critico de Windows.\nCambiar su prioridad puede volver inestable el sistema.\n\n¿Continuar?",
                icon="warning", default="no")
        return True

    def guard_admin(self):
        if not is_admin() and not os.environ.get("PRIORIDAD_TEST_KEY"):
            messagebox.showerror("Permisos", "Se necesitan permisos de administrador para escribir en el registro.")
            return False
        return True

    def add_many(self, exes):
        if not self.guard_admin():
            return
        exes = [e for e in exes if core.valid_name(e)]
        if not exes:
            messagebox.showerror("Nombre invalido", "Debe ser un archivo .exe sin ruta.")
            return
        p = self.prio.get()
        try:
            core.backup()
        except OSError as e:
            messagebox.showerror("Respaldo", f"No se pudo crear el respaldo: {e}")
            return
        done, live = [], 0
        for exe in exes:
            if not self.confirm_system(exe):
                continue
            try:
                core.set_entry(exe, p, do_backup=False)
            except OSError as e:
                messagebox.showerror("Error", f"{exe}: {e}")
                continue
            live += core.apply_now(exe, p)[0]
            done.append(exe)
        self.pp.uncheck([e.lower() for e in exes])
        self.refresh()
        self.refresh_panel()
        self.say(f"{len(done)} programa(s) con prioridad {p}. En vivo: {live} proceso(s); "
                 "los demas la toman al proximo arranque.")

    def add_file(self):
        f = filedialog.askopenfilename(title="Elegir programa", filetypes=[("Ejecutable", "*.exe")])
        if f:
            self.add_many([os.path.basename(f)])

    def change(self):
        sel = self.rt.picked()
        if not sel:
            self.say("Marca casillas o selecciona programas de la tabla.")
            return
        if not self.guard_admin():
            return
        p = self.prio.get()
        core.backup()
        n = 0
        for exe in sel:
            if self.confirm_system(exe):
                try:
                    core.set_entry(exe, p, do_backup=False)
                    core.apply_now(exe, p)
                    n += 1
                except OSError as e:
                    messagebox.showerror("Error", f"{exe}: {e}")
        self.refresh()
        self.say(f"{n} programa(s) cambiado(s) a {p}.")

    def apply_now(self):
        sel = self.rt.picked()
        if not sel:
            self.say("Marca casillas o selecciona programas de la tabla.")
            return
        saved = core.list_entries()
        n = 0
        for exe in sel:
            if saved.get(exe) in core.PRIORITIES:
                n += core.apply_now(exe, saved[exe])[0]
        self.refresh()
        self.say(f"Aplicada en vivo a {n} proceso(s).")

    def remove(self):
        sel = self.rt.picked()
        if not sel:
            self.say("Marca casillas o selecciona programas de la tabla.")
            return
        if not self.guard_admin():
            return
        if not messagebox.askyesno("Quitar", f"¿Quitar la prioridad guardada de {len(sel)} programa(s)?\n"
                                   "Los procesos ya abiertos conservan su prioridad actual."):
            return
        core.backup()
        for exe in sel:
            try:
                core.remove_entry(exe, do_backup=False)
            except OSError as e:
                messagebox.showerror("Error", f"{exe}: {e}")
        self.rt.uncheck(sel)
        self.refresh()
        self.refresh_panel()
        self.say(f"{len(sel)} programa(s) quitado(s) del registro.")

    def do_export(self):
        f = filedialog.asksaveasfilename(defaultextension=".json", initialfile="prioridades.json",
                                         filetypes=[("JSON", "*.json")])
        if f:
            core.export_json(f)
            self.say(f"Exportado: {f}")

    def do_import(self):
        if not self.guard_admin():
            return
        f = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if not f:
            return
        try:
            n = core.import_json(f)
        except (OSError, ValueError) as e:
            messagebox.showerror("Error", str(e))
            return
        self.refresh()
        self.refresh_panel()
        self.say(f"Importadas {n} entradas.")


if __name__ == "__main__":
    if not is_admin() and not os.environ.get("PRIORIDAD_TEST_KEY"):
        relaunch_as_admin()
        sys.exit(0)
    App().mainloop()
