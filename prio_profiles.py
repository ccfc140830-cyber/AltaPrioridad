"""Perfiles de juego: detecta el juego, sube su grupo de procesos y baja el resto.

Todo es en vivo (SetPriorityClass): no escribe en el registro. Al cerrarse el
juego (o al cerrar la app) restaura la prioridad original de cada proceso tocado.
"""
import json
import os

import prio_core as core

NORMAL = 0x20
HIGH_FLAGS = (0x80, 0x8000)  # Alta, Por encima de lo normal: lo unico que se baja

# Carpetas tipicas de bibliotecas de juegos, para sugerir perfiles.
GAME_HINTS = ("\\steamapps\\common\\", "\\epic games\\", "\\gog galaxy\\games\\", "\\gog games\\",
              "\\xboxgames\\", "\\riot games\\", "\\ubisoft game launcher\\games\\",
              "\\ea games\\", "\\origin games\\")
NOISE = ("crash", "anticheat", "beclient", "battleye", "launcher", "redist", "setup", "helper",
         "unins", "webhelper", "report", "updater", "service")


def data_path():
    d = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "AltaPrioridad")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "perfiles.json")


def load():
    try:
        with open(data_path(), encoding="utf-8") as f:
            d = json.load(f)
        d.setdefault("watch", True)
        d.setdefault("profiles", [])
        return d
    except (OSError, ValueError):
        return {"watch": True, "profiles": []}


def save(d):
    with open(data_path(), "w", encoding="utf-8") as f:
        json.dump(d, f, indent=2, ensure_ascii=False)


def new_profile(name, triggers, **kw):
    p = {"name": name, "triggers": list(triggers), "related": [], "keep": [],
         "children": True, "same_folder": True, "lower_others": True,
         "priority": "Alta", "enabled": True}
    p.update(kw)
    return p


def safe_folder(folder):
    """Evita tratar como 'carpeta del juego' una raiz generica del sistema."""
    f = os.path.normcase(os.path.normpath(folder))
    drive, rest = os.path.splitdrive(f)
    if len([x for x in rest.split(os.sep) if x]) < 2:
        return False
    for env in ("WINDIR", "ProgramFiles", "ProgramFiles(x86)", "ProgramData", "USERPROFILE"):
        root = os.environ.get(env)
        if root and f == os.path.normcase(os.path.normpath(root)):
            return False
    win = os.environ.get("WINDIR")
    return not (win and f.startswith(os.path.normcase(os.path.normpath(win)) + os.sep))


class Engine:
    def __init__(self, api=core):
        self.api = api
        self.active = {}      # nombre perfil -> estado
        self.alive = {}       # ultimo snapshot {pid: (ppid, exe)}
        self._paths = {}      # pid -> (exe, ruta)

    # ---- utilidades ----
    def path_of(self, pid, exe):
        c = self._paths.get(pid)
        if c and c[0] == exe:
            return c[1]
        p = self.api.exe_path(pid) or ""
        self._paths[pid] = (exe, p)
        return p

    def group_of(self, prof, tpids):
        alive = self.alive
        g = set(tpids)
        if prof.get("children", True):
            kids = {}
            for pid, (pp, _) in alive.items():
                kids.setdefault(pp, []).append(pid)
            stack = list(tpids)
            while stack:
                for c in kids.get(stack.pop(), []):
                    if c not in g:
                        g.add(c)
                        stack.append(c)
        rel = {x.lower() for x in prof.get("related", [])}
        if rel:
            g |= {pid for pid, (_, exe) in alive.items() if exe.lower() in rel}
        if prof.get("same_folder", True):
            folders = set()
            for pid in tpids:
                p = self.path_of(pid, alive[pid][1])
                if p and safe_folder(os.path.dirname(p)):
                    folders.add(os.path.normcase(os.path.dirname(p)) + os.sep)
            if folders:
                for pid, (_, exe) in alive.items():
                    p = os.path.normcase(self.path_of(pid, exe))
                    if p and any(p.startswith(f) for f in folders):
                        g.add(pid)
        return g

    def _set(self, st, pid, exe, flag):
        cur = self.api.get_class_flag(pid)
        if cur is None:
            st["failed"].add(pid)
            return
        if cur == flag:
            return
        if self.api.set_class_flag(pid, flag):
            st["saved"].setdefault(pid, (exe.lower(), cur))
            st["failed"].discard(pid)
        else:
            st["failed"].add(pid)

    # ---- ciclo principal ----
    def tick(self, profiles):
        self.alive = {pid: (pp, exe) for pid, pp, exe in self.api.process_info()}
        for pid in [p for p in self._paths if p not in self.alive]:
            del self._paths[pid]

        groups, by_name = {}, {}
        for prof in profiles:
            by_name[prof["name"]] = prof
            if not prof.get("enabled", True):
                continue
            trig = {x.lower() for x in prof["triggers"]}
            tp = [pid for pid, (_, exe) in self.alive.items() if exe.lower() in trig]
            if tp:
                groups[prof["name"]] = self.group_of(prof, tp)
        protected = set().union(*groups.values()) if groups else set()

        for name, grp in groups.items():
            prof = by_name[name]
            st = self.active.setdefault(name, {"saved": {}, "failed": set(), "game": set()})
            st["game"] = grp
            flag = core.PRIORITIES[prof.get("priority", "Alta")][1]
            for pid in grp:
                self._set(st, pid, self.alive[pid][1], flag)
            if prof.get("lower_others", True):
                keep = {x.lower() for x in prof.get("keep", [])} | core.SYSTEM_EXES
                for pid, (_, exe) in self.alive.items():
                    if pid in protected or exe.lower() in keep:
                        continue
                    if self.api.get_class_flag(pid) in HIGH_FLAGS:
                        self._set(st, pid, exe, NORMAL)

        for name in [n for n in self.active if n not in groups]:
            self.restore(name)

    def restore(self, name):
        st = self.active.pop(name, None)
        if not st:
            return 0
        n = 0
        for pid, (exe, orig) in st["saved"].items():
            cur = self.alive.get(pid)
            if cur and cur[1].lower() == exe and self.api.set_class_flag(pid, orig):
                n += 1
        return n

    def restore_all(self):
        self.alive = {pid: (pp, exe) for pid, pp, exe in self.api.process_info()}
        for name in list(self.active):
            self.restore(name)

    def status(self):
        """{perfil: (en_grupo, bajados_a_normal, fallidos)}"""
        out = {}
        for name, st in self.active.items():
            lowered = sum(1 for p in st["saved"] if p not in st["game"])
            out[name] = (len(st["game"]), lowered, len(st["failed"]))
        return out

    def candidates(self, profiles):
        """Juegos en ejecucion (por carpeta de biblioteca) que aun no tienen perfil."""
        known = {t.lower() for p in profiles for t in p["triggers"]}
        seen, out = set(), []
        for pid, (_, exe) in self.alive.items():
            low = exe.lower()
            if low in known or low in seen or any(w in low for w in NOISE):
                continue
            path = self.path_of(pid, exe)
            if any(h in path.lower() for h in GAME_HINTS):
                seen.add(low)
                out.append((exe, path))
        return sorted(out, key=lambda x: x[0].lower())
