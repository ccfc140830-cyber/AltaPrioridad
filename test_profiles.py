import os, shutil, subprocess, tempfile, time
import prio_core as core
import prio_profiles as pp

ping = os.path.join(os.environ["WINDIR"], "System32", "PING.EXE")
root = tempfile.mkdtemp(prefix="prio_prof_")
gdir = os.path.join(root, "Juegos", "FakeGame")
odir = os.path.join(root, "Otros", "Otro")
os.makedirs(gdir); os.makedirs(odir)
exes = {"game": os.path.join(gdir, "fakegame.exe"), "helper": os.path.join(gdir, "fakehelper.exe"),
        "other": os.path.join(odir, "fakeother.exe"), "related": os.path.join(odir, "fakerel.exe"),
        "keep": os.path.join(odir, "fakekeep.exe")}
for p in exes.values():
    shutil.copy(ping, p)
procs = []

def start(key):
    p = subprocess.Popen([exes[key], "-n", "60", "127.0.0.1"], stdout=subprocess.DEVNULL)
    procs.append(p)
    time.sleep(0.4)
    return p

def cls(p):
    return core.get_class_flag(p.pid)

HIGH, NORM, ABOVE = 0x80, 0x20, 0x8000
try:
    prof = pp.new_profile("FakeGame", ["fakegame.exe"], related=["fakerel.exe"], keep=["fakekeep.exe"])
    eng = pp.Engine()

    other = start("other"); core.set_class_flag(other.pid, HIGH)
    rel = start("related")           # Normal; debe subir a Alta por 'related'
    keep = start("keep"); core.set_class_flag(keep.pid, ABOVE)

    eng.tick([prof])
    assert eng.active == {} and cls(other) == HIGH, "sin juego no debe tocar nada"
    print("sin juego: no toca nada OK")

    game = start("game"); helper = start("helper")
    eng.tick([prof])
    assert cls(game) == HIGH, cls(game)
    assert cls(helper) == HIGH, "helper misma carpeta -> Alta"
    assert cls(rel) == HIGH, "related -> Alta"
    assert cls(other) == NORM, "otro en Alta debe bajar a Normal"
    assert cls(keep) == ABOVE, "'keep' no se toca"
    print("activar OK  status:", eng.status())

    eng.tick([prof])   # idempotente
    assert cls(other) == NORM
    # un proceso nuevo en Alta aparece durante el juego
    other2 = start("other"); core.set_class_flag(other2.pid, HIGH)
    eng.tick([prof])
    assert cls(other2) == NORM
    print("proceso nuevo en Alta durante el juego -> Normal OK")

    game.kill(); game.wait(); time.sleep(0.3)
    eng.tick([prof])
    assert eng.active == {}
    assert cls(other) == HIGH, "otro debe volver a Alta (original)"
    assert cls(helper) == NORM, "helper vuelve a Normal"
    assert cls(rel) == NORM
    print("restaurar al cerrar el juego OK")

    # deshabilitar perfil activo restaura
    game = start("game")
    eng.tick([prof]); assert cls(other) == NORM
    prof["enabled"] = False
    eng.tick([prof]); assert cls(other) == HIGH and eng.active == {}
    prof["enabled"] = True
    print("deshabilitar restaura OK")

    # restore_all (cierre de app)
    eng.tick([prof]); assert cls(other) == NORM
    eng.restore_all(); assert cls(other) == HIGH
    print("restore_all OK")
finally:
    for p in procs:
        p.kill()
    time.sleep(0.5)
    shutil.rmtree(root, ignore_errors=True)

# ---- logica pura con API falsa: hijos, candidatos, carpetas seguras ----
class Fake:
    def __init__(s):
        s.cls = {}
        s.procs = [(10, 1, "game.exe"), (11, 10, "child.exe"), (12, 11, "grandchild.exe"),
                   (20, 1, "other.exe"), (30, 1, "launcher.exe"), (40, 1, "newgame.exe"),
                   (50, 1, "csrss.exe")]
        s.paths = {10: r"C:\Games\G\game.exe", 11: r"D:\x\child.exe", 12: r"D:\y\g.exe",
                   20: r"C:\Apps\other.exe", 40: r"C:\Program Files (x86)\Steam\steamapps\common\N\newgame.exe",
                   30: r"C:\Program Files (x86)\Steam\steamapps\common\N\launcher.exe", 50: r"C:\Windows\System32\csrss.exe"}
        s.flags = {10: 0x20, 11: 0x20, 12: 0x20, 20: 0x80, 30: 0x20, 40: 0x20, 50: 0x80}
    def process_info(s): return list(s.procs)
    def exe_path(s, pid): return s.paths.get(pid, "")
    def get_class_flag(s, pid): return s.flags.get(pid)
    def set_class_flag(s, pid, f): s.flags[pid] = f; return True

f = Fake(); e = pp.Engine(f)
pr = pp.new_profile("G", ["game.exe"], same_folder=False)
e.tick([pr])
assert f.flags[11] == 0x80 and f.flags[12] == 0x80, "hijos y nietos -> Alta"
assert f.flags[20] == 0x20, "otro bajado"
assert f.flags[50] == 0x80, "proceso del sistema nunca se baja"
print("hijos/nietos OK, sistema protegido OK")
c = e.candidates([pr])
assert [x[0] for x in c] == ["newgame.exe"], c      # launcher filtrado por ruido
print("candidatos OK:", c)
for bad in (r"C:\Windows\System32", r"C:\Program Files", "C:\\", r"C:\Games"):
    assert not pp.safe_folder(bad), bad
assert pp.safe_folder(r"C:\Games\G") and pp.safe_folder(r"C:\Program Files\Foo")
print("safe_folder OK")
print("TODO OK")
