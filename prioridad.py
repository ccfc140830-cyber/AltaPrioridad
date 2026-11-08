"""AltaPrioridad: gestiona la prioridad de CPU de programas via IFEO\\PerfOptions."""
import ctypes
import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import prio_core as core


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


class PickProcess(tk.Toplevel):
    def __init__(self, master, exclude=()):
        super().__init__(master)
        self.title("Elegir proceso en ejecucion")
        self.geometry("360x460")
        self.transient(master)
        self.result = None
        skip = {e.lower() for e in exclude}
        self.names = sorted({e for _, e in core.running_processes() if e.lower() not in skip and core.valid_name(e)},
                            key=str.lower)
        self.q = tk.StringVar()
        self.q.trace_add("write", lambda *_: self.fill())
        ttk.Entry(self, textvariable=self.q).pack(fill="x", padx=8, pady=(8, 4))
        self.lb = tk.Listbox(self, activestyle="dotbox")
        self.lb.pack(fill="both", expand=True, padx=8)
        self.lb.bind("<Double-1>", lambda _: self.ok())
        ttk.Button(self, text="Elegir", command=self.ok).pack(pady=8)
        self.fill()
        self.grab_set()

    def fill(self):
        f = self.q.get().lower()
        self.lb.delete(0, "end")
        for n in self.names:
            if f in n.lower():
                self.lb.insert("end", n)

    def ok(self):
        s = self.lb.curselection()
        if s:
            self.result = self.lb.get(s[0])
            self.destroy()


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Alta Prioridad - gestor de prioridad de CPU")
        self.geometry("820x480")
        self.minsize(700, 380)

        top = ttk.Frame(self, padding=8)
        top.pack(fill="x")
        ttk.Button(top, text="Agregar .exe...", command=self.add_file).pack(side="left")
        ttk.Button(top, text="Agregar proceso en ejecucion...", command=self.add_proc).pack(side="left", padx=6)
        ttk.Button(top, text="Importar...", command=self.do_import).pack(side="right")
        ttk.Button(top, text="Exportar...", command=self.do_export).pack(side="right", padx=6)

        cols = ("exe", "saved", "run", "live")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", selectmode="extended")
        for c, t, w in (("exe", "Programa", 240), ("saved", "Prioridad guardada", 180),
                        ("run", "Corriendo", 90), ("live", "Prioridad en vivo", 200)):
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8)

        bar = ttk.Frame(self, padding=8)
        bar.pack(fill="x")
        ttk.Label(bar, text="Prioridad:").pack(side="left")
        self.rt_ok = tk.BooleanVar(value=False)
        self.prio = tk.StringVar(value="Alta")
        self.combo = ttk.Combobox(bar, textvariable=self.prio, state="readonly", width=26)
        self.combo.pack(side="left", padx=6)
        self.refresh_combo()
        ttk.Checkbutton(bar, text="Permitir Tiempo real", variable=self.rt_ok,
                        command=self.rt_toggle).pack(side="left", padx=6)
        ttk.Button(bar, text="Quitar", command=self.remove).pack(side="right")
        ttk.Button(bar, text="Aplicar ahora", command=self.apply_now).pack(side="right", padx=6)
        ttk.Button(bar, text="Cambiar prioridad", command=self.change).pack(side="right")
        ttk.Button(bar, text="Refrescar", command=self.refresh).pack(side="right", padx=6)

        self.status = tk.StringVar()
        ttk.Label(self, textvariable=self.status, relief="sunken", anchor="w", padding=4).pack(fill="x")
        self.refresh()
        self.after(3000, self.autorefresh)

    # ---- util ----
    def say(self, msg):
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
        sel = set(self.tree.selection())
        try:
            entries = core.list_entries()
        except OSError as e:
            self.say(f"Error leyendo registro: {e}")
            return
        live = core.live_state()
        self.tree.delete(*self.tree.get_children())
        for exe in sorted(entries, key=str.lower):
            inst = live.get(exe.lower(), [])
            vals = sorted({p or "?" for _, p in inst})
            self.tree.insert("", "end", iid=exe, values=(
                exe, entries[exe], f"Si ({len(inst)})" if inst else "No", ", ".join(vals)))
        for s in sel:
            if self.tree.exists(s):
                self.tree.selection_add(s)
        self.say(f"{len(entries)} programa(s) con prioridad guardada.")

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

    # ---- acciones ----
    def add(self, exe):
        if not core.valid_name(exe):
            messagebox.showerror("Nombre invalido", "Debe ser un archivo .exe sin ruta.")
            return
        if not self.guard_admin() or not self.confirm_system(exe):
            return
        p = self.prio.get()
        try:
            core.set_entry(exe, p)
        except OSError as e:
            messagebox.showerror("Error", str(e))
            return
        ok, tot = core.apply_now(exe, p)
        self.refresh()
        extra = f" Aplicada en vivo a {ok}/{tot} proceso(s)." if tot else " Se aplica al proximo arranque."
        self.say(f"{exe}: {p}.{extra}")

    def add_file(self):
        f = filedialog.askopenfilename(title="Elegir programa", filetypes=[("Ejecutable", "*.exe")])
        if f:
            self.add(os.path.basename(f))

    def add_proc(self):
        d = PickProcess(self, exclude=core.list_entries())
        self.wait_window(d)
        if d.result:
            self.add(d.result)

    def selected(self):
        s = list(self.tree.selection())
        if not s:
            self.say("Selecciona al menos un programa de la tabla.")
        return s

    def change(self):
        sel = self.selected()
        if not sel or not self.guard_admin():
            return
        p = self.prio.get()
        for exe in sel:
            if self.confirm_system(exe):
                try:
                    core.set_entry(exe, p)
                    core.apply_now(exe, p)
                except OSError as e:
                    messagebox.showerror("Error", f"{exe}: {e}")
        self.refresh()
        self.say(f"{len(sel)} programa(s) cambiado(s) a {p}.")

    def apply_now(self):
        sel = self.selected()
        if not sel:
            return
        n = 0
        for exe in sel:
            saved = core.list_entries().get(exe)
            if saved in core.PRIORITIES:
                ok, _ = core.apply_now(exe, saved)
                n += ok
        self.refresh()
        self.say(f"Aplicada en vivo a {n} proceso(s).")

    def remove(self):
        sel = self.selected()
        if not sel or not self.guard_admin():
            return
        if not messagebox.askyesno("Quitar", f"¿Quitar la prioridad guardada de {len(sel)} programa(s)?\n"
                                   "Los procesos ya abiertos conservan su prioridad actual."):
            return
        for exe in sel:
            try:
                core.remove_entry(exe)
            except OSError as e:
                messagebox.showerror("Error", f"{exe}: {e}")
        self.refresh()

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
        self.say(f"Importadas {n} entradas.")


if __name__ == "__main__":
    if not is_admin() and not os.environ.get("PRIORIDAD_TEST_KEY"):
        relaunch_as_admin()
        sys.exit(0)
    App().mainloop()
