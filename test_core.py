import os
os.environ["PRIORIDAD_TEST_KEY"] = r"Software\AltaPrioridadTest"
import subprocess, time, winreg
import prio_core as c

def cleanup():
    try:
        winreg.DeleteKeyEx(winreg.HKEY_CURRENT_USER, r"Software\AltaPrioridadTest\ping.exe\PerfOptions", c.VIEW, 0)
    except OSError: pass
    for p in (r"Software\AltaPrioridadTest\ping.exe", r"Software\AltaPrioridadTest\otro.exe\PerfOptions",
              r"Software\AltaPrioridadTest\otro.exe", r"Software\AltaPrioridadTest"):
        try: winreg.DeleteKeyEx(winreg.HKEY_CURRENT_USER, p, c.VIEW, 0)
        except OSError: pass

cleanup()
assert c.list_entries() == {}
c.set_entry("ping.exe", "Alta")
c.set_entry("otro.exe", "Por debajo de lo normal")
assert c.list_entries() == {"ping.exe": "Alta", "otro.exe": "Por debajo de lo normal"}, c.list_entries()
print("set/list OK")

# valor ajeno en la clave del exe debe sobrevivir a remove
with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, r"Software\AltaPrioridadTest\otro.exe", 0,
                        winreg.KEY_SET_VALUE | c.VIEW) as k:
    winreg.SetValueEx(k, "Ajeno", 0, winreg.REG_SZ, "x")
c.remove_entry("otro.exe")
with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\AltaPrioridadTest\otro.exe", 0, winreg.KEY_READ | c.VIEW) as k:
    assert winreg.QueryValueEx(k, "Ajeno")[0] == "x"
assert "otro.exe" not in c.list_entries()
print("remove conserva valores ajenos OK")

c.remove_entry("ping.exe")
try:
    winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\AltaPrioridadTest\ping.exe", 0, winreg.KEY_READ | c.VIEW)
    raise SystemExit("FALLO: clave ping.exe no se limpio")
except FileNotFoundError:
    print("remove limpia claves vacias OK")

for bad in ("a\\b.exe", "x.txt", "", "C:\\x.exe"):
    assert not c.valid_name(bad), bad
print("validacion OK")

# prioridad en vivo sobre proceso propio
p = subprocess.Popen(["ping.exe", "-n", "20", "127.0.0.1"], stdout=subprocess.DEVNULL)
time.sleep(0.5)
try:
    print("antes:", c.live_priority(p.pid))
    ok, tot = c.apply_now("ping.exe", "Alta")
    print("apply_now:", ok, tot)
    assert c.live_priority(p.pid) == "Alta"
    c.set_live_priority(p.pid, "Por debajo de lo normal")
    assert c.live_priority(p.pid) == "Por debajo de lo normal"
    assert any(e.lower() == "ping.exe" for _, e in c.running_processes())
    print("prioridad en vivo OK")
finally:
    p.kill()

# backup/export/import
c.set_entry("ping.exe", "Normal")
c.export_json(os.path.join(os.environ["TEMP"], "prio_test.json"))
c.remove_entry("ping.exe")
assert c.import_json(os.path.join(os.environ["TEMP"], "prio_test.json")) == 1
assert c.list_entries() == {"ping.exe": "Normal"}
c.remove_entry("ping.exe")
cleanup()
print("export/import OK")
