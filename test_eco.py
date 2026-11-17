"""Minimizada: modo ahorro (prioridad baja, EcoQoS, sin refrescos) y el motor sigue aplicando perfiles."""
import ctypes, os, shutil, subprocess, tempfile, time
from ctypes import wintypes

tmp = tempfile.mkdtemp(prefix="prio_eco_")
os.environ["LOCALAPPDATA"] = tmp
os.environ["PRIORIDAD_TEST_KEY"] = r"Software\AltaPrioridadTest"
os.environ["PRIORIDAD_TEST_TASK"] = "AltaPrioridadPrueba"
import prioridad as ui, prio_core as core, prio_profiles as pp

exe = os.path.join(tmp, "Juegos", "EcoGame", "ecogame.exe")
os.makedirs(os.path.dirname(exe))
shutil.copy(os.path.join(os.environ["WINDIR"], "System32", "PING.EXE"), exe)


class PMC(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
        (n, ctypes.c_size_t) for n in ("PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
                                       "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage",
                                       "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage")]


_gpmi = ctypes.WinDLL("psapi").GetProcessMemoryInfo
_gpmi.argtypes = [wintypes.HANDLE, ctypes.POINTER(PMC), wintypes.DWORD]
_gcp = ctypes.WinDLL("kernel32").GetCurrentProcess
_gcp.restype = wintypes.HANDLE


def rss_mb():
    c = PMC(); c.cb = ctypes.sizeof(c)
    _gpmi(_gcp(), ctypes.byref(c), c.cb)
    return c.WorkingSetSize / 1048576


app = ui.App()
app.pdata["profiles"].append(pp.new_profile("EcoGame", ["ecogame.exe"], lower_others=False))
app.save_profiles()
R, game = {}, []
me = os.getpid()


def at(sec, fn):
    app.after(int(sec * 1000), fn)


def start_visible():
    R["cpu0"], R["rss_vis"] = time.process_time(), rss_mb()


def end_visible_go_min():
    R["cpu_visible"] = time.process_time() - R["cpu0"]
    R["prio_before"] = core.get_class_flag(me)
    app.go_background(notify=False)          # segundo plano: sin ventana, con icono en la bandeja


def min_started():
    R["eco"] = app._eco
    R["hidden"] = app.state() == "withdrawn"
    R["tray"] = app.tray.exists()
    R["prio_min"] = core.get_class_flag(me)
    R["cpu1"] = time.process_time()


def min_idle_done():
    R["cpu_min"] = time.process_time() - R["cpu1"]
    R["rss_min"] = rss_mb()
    game.append(subprocess.Popen([exe, "-n", "60", "127.0.0.1"], stdout=subprocess.DEVNULL))


def check_applied():
    R["game_high_while_min"] = core.get_class_flag(game[0].pid) == 0x80
    R["still_eco"] = app._eco
    game[0].kill()


def check_restored_then_restore_window():
    app.show_window()


def final():
    R["eco_off"] = not app._eco
    R["prio_after"] = core.get_class_flag(me)
    R["auto_running"] = app._auto_id is not None
    app.destroy()


at(0.5, start_visible)
at(10.5, end_visible_go_min)
at(12.0, min_started)
at(22.0, min_idle_done)
at(28.0, check_applied)
at(31.0, check_restored_then_restore_window)
at(33.0, final)
try:
    app.mainloop()
finally:
    for g in game:
        g.kill()
    time.sleep(0.4); shutil.rmtree(tmp, ignore_errors=True)

print({k: (round(v, 3) if isinstance(v, float) else v) for k, v in R.items()})
assert R["eco"] and R["hidden"] and R["tray"], "segundo plano: sin ventana, con icono, en modo ahorro"
assert R["prio_min"] == 0x4000, "el modo ahorro baja la prioridad a Por debajo de lo normal"
assert R["game_high_while_min"], "minimizada, el motor detecto el juego y le puso Alta"
assert R["still_eco"], "sigue en modo ahorro mientras aplica el perfil"
assert R["eco_off"] and R["prio_after"] == R["prio_before"] and R["auto_running"], \
    "al restaurar vuelve a la prioridad que tenia y reanuda el refresco"
print(f"CPU en 10 s: visible {R['cpu_visible']:.3f} s -> minimizada {R['cpu_min']:.3f} s;"
      f" memoria {R['rss_vis']:.0f} MB -> {R['rss_min']:.0f} MB")
assert R["cpu_min"] < R["cpu_visible"], "minimizada gasta menos CPU"
print("TODO OK")
