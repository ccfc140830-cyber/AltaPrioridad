"""Logica de AltaPrioridad: registro IFEO\\PerfOptions + prioridad en vivo.

Solo toca el valor CpuPriorityClass de la subclave PerfOptions.
Nunca lee ni escribe 'Debugger' ni ningun otro valor de IFEO.
"""
import ctypes
import json
import os
import time
import winreg
from ctypes import wintypes

IFEO_BASE = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Image File Execution Options"
VALUE = "CpuPriorityClass"
SUB = "PerfOptions"

# Para pruebas: PRIORIDAD_TEST_KEY=Software\AltaPrioridadTest usa HKCU en vez de HKLM.
_TEST = os.environ.get("PRIORIDAD_TEST_KEY")
HIVE = winreg.HKEY_CURRENT_USER if _TEST else winreg.HKEY_LOCAL_MACHINE
BASE = _TEST if _TEST else IFEO_BASE
VIEW = winreg.KEY_WOW64_64KEY

# nombre -> (valor registro, flag SetPriorityClass)
PRIORITIES = {
    "Inactiva (Idle)": (1, 0x00000040),
    "Por debajo de lo normal": (5, 0x00004000),
    "Normal": (2, 0x00000020),
    "Por encima de lo normal": (6, 0x00008000),
    "Alta": (3, 0x00000080),
    "Tiempo real (peligroso)": (4, 0x00000100),
}
REG_TO_NAME = {v[0]: k for k, v in PRIORITIES.items()}
CLS_TO_NAME = {v[1]: k for k, v in PRIORITIES.items()}
REALTIME = "Tiempo real (peligroso)"

SYSTEM_EXES = {
    "system", "smss.exe", "csrss.exe", "wininit.exe", "winlogon.exe",
    "services.exe", "lsass.exe", "svchost.exe", "dwm.exe", "audiodg.exe",
    "fontdrvhost.exe", "registry",
}


def valid_name(name):
    n = name.strip()
    return bool(n) and "\\" not in n and "/" not in n and n.lower().endswith(".exe")


def _open(path, access):
    return winreg.OpenKey(HIVE, path, 0, access | VIEW)


def list_entries():
    """{exe: nombre_prioridad} de todas las claves con PerfOptions\\CpuPriorityClass."""
    out = {}
    try:
        base = _open(BASE, winreg.KEY_READ)
    except FileNotFoundError:
        return out
    with base:
        i = 0
        while True:
            try:
                exe = winreg.EnumKey(base, i)
            except OSError:
                break
            i += 1
            try:
                with _open(f"{BASE}\\{exe}\\{SUB}", winreg.KEY_READ) as k:
                    val, typ = winreg.QueryValueEx(k, VALUE)
                if typ == winreg.REG_DWORD:
                    out[exe] = REG_TO_NAME.get(val, f"Desconocida ({val})")
            except OSError:
                continue
    return out


def set_entry(exe, prio_name, do_backup=True):
    if not valid_name(exe):
        raise ValueError("Nombre invalido: debe ser un .exe sin ruta")
    if prio_name not in PRIORITIES:
        raise ValueError("Prioridad invalida")
    if do_backup:
        backup()
    path = f"{BASE}\\{exe.strip()}\\{SUB}"
    with winreg.CreateKeyEx(HIVE, path, 0, winreg.KEY_SET_VALUE | VIEW) as k:
        winreg.SetValueEx(k, VALUE, 0, winreg.REG_DWORD, PRIORITIES[prio_name][0])


def _is_empty(path):
    try:
        with _open(path, winreg.KEY_READ) as k:
            nsub, nval, _ = winreg.QueryInfoKey(k)
            return nsub == 0 and nval == 0
    except FileNotFoundError:
        return False


def remove_entry(exe, do_backup=True):
    """Borra solo CpuPriorityClass; limpia claves vacias, deja lo demas."""
    if do_backup:
        backup()
    perf = f"{BASE}\\{exe}\\{SUB}"
    try:
        with _open(perf, winreg.KEY_SET_VALUE) as k:
            winreg.DeleteValue(k, VALUE)
    except FileNotFoundError:
        pass
    for path in (perf, f"{BASE}\\{exe}"):
        if _is_empty(path):
            winreg.DeleteKeyEx(HIVE, path, VIEW, 0)
        else:
            break


# ---- respaldo / import / export ----
def backup_dir():
    d = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
                     "AltaPrioridad", "respaldos")
    os.makedirs(d, exist_ok=True)
    return d


def backup():
    d = backup_dir()
    p = os.path.join(d, time.strftime("lista_%Y%m%d_%H%M%S.json"))
    export_json(p)
    files = sorted(f for f in os.listdir(d) if f.startswith("lista_"))
    for old in files[:-20]:
        try:
            os.remove(os.path.join(d, old))
        except OSError:
            pass
    return p


def export_json(path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(list_entries(), f, indent=2, ensure_ascii=False)


def import_json(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    n = 0
    backup()
    for exe, prio in data.items():
        if valid_name(exe) and prio in PRIORITIES:
            set_entry(exe, prio, do_backup=False)
            n += 1
    return n


# ---- procesos en vivo ----
k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.OpenProcess.restype = wintypes.HANDLE
k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
k32.GetPriorityClass.restype = wintypes.DWORD
k32.GetPriorityClass.argtypes = [wintypes.HANDLE]
k32.SetPriorityClass.restype = wintypes.BOOL
k32.SetPriorityClass.argtypes = [wintypes.HANDLE, wintypes.DWORD]
k32.CloseHandle.argtypes = [wintypes.HANDLE]
k32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
k32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]

k32.Process32FirstW.restype = wintypes.BOOL
k32.Process32NextW.restype = wintypes.BOOL
k32.Process32FirstW.argtypes = k32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.c_void_p]

PROCESS_SET_INFORMATION = 0x0200
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
TH32CS_SNAPPROCESS = 0x2


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD), ("th32DefaultHeapID", ctypes.c_size_t),
        ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", wintypes.LONG),
        ("dwFlags", wintypes.DWORD), ("szExeFile", wintypes.WCHAR * 260),
    ]


def process_info():
    """[(pid, ppid, nombre.exe)] de todos los procesos."""
    snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    out = []
    if snap in (None, wintypes.HANDLE(-1).value):
        return out
    pe = PROCESSENTRY32W()
    pe.dwSize = ctypes.sizeof(pe)
    ok = k32.Process32FirstW(wintypes.HANDLE(snap), ctypes.byref(pe))
    while ok:
        out.append((pe.th32ProcessID, pe.th32ParentProcessID, pe.szExeFile))
        ok = k32.Process32NextW(wintypes.HANDLE(snap), ctypes.byref(pe))
    k32.CloseHandle(wintypes.HANDLE(snap))
    return out


def running_processes():
    """[(pid, nombre.exe)] de todos los procesos."""
    return [(p, e) for p, _, e in process_info()]


k32.QueryFullProcessImageNameW.restype = wintypes.BOOL
k32.QueryFullProcessImageNameW.argtypes = [
    wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]


def exe_path(pid):
    """Ruta completa del .exe del proceso, o '' si no se puede leer."""
    h = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(1024)
        n = wintypes.DWORD(len(buf))
        return buf.value if k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n)) else ""
    finally:
        k32.CloseHandle(h)


def get_class_flag(pid):
    """Flag crudo de GetPriorityClass (0x20 Normal, 0x80 High...), o None."""
    h = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        return None
    try:
        return k32.GetPriorityClass(h) or None
    finally:
        k32.CloseHandle(h)


def set_class_flag(pid, flag):
    h = k32.OpenProcess(PROCESS_SET_INFORMATION, False, pid)
    if not h:
        return False
    try:
        return bool(k32.SetPriorityClass(h, flag))
    finally:
        k32.CloseHandle(h)


def live_priority(pid):
    h = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        return None
    try:
        return CLS_TO_NAME.get(k32.GetPriorityClass(h))
    finally:
        k32.CloseHandle(h)


def set_live_priority(pid, prio_name):
    h = k32.OpenProcess(PROCESS_SET_INFORMATION, False, pid)
    if not h:
        return False
    try:
        return bool(k32.SetPriorityClass(h, PRIORITIES[prio_name][1]))
    finally:
        k32.CloseHandle(h)


def live_state():
    """{exe_lower: [(pid, prio_en_vivo)]}"""
    out = {}
    for pid, exe in running_processes():
        out.setdefault(exe.lower(), []).append((pid, live_priority(pid)))
    return out


def apply_now(exe, prio_name):
    """Aplica a todas las instancias en ejecucion. Devuelve (ok, total)."""
    pids = [p for p, e in running_processes() if e.lower() == exe.lower()]
    ok = sum(1 for p in pids if set_live_priority(p, prio_name))
    return ok, len(pids)
