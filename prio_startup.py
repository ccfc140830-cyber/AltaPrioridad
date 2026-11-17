"""Inicio con Windows mediante una tarea programada al iniciar sesion.

La app pide administrador; Windows no arranca programas elevados desde la clave Run
(los bloquea sin aviso). Una tarea con 'privilegios mas altos' si los arranca sin UAC.
La tarea no tiene limite de ejecucion ni se detiene con bateria, y evita instancias dobles.
"""
import html
import os
import re
import subprocess
import sys
import tempfile
from xml.sax.saxutils import escape

# Para pruebas: PRIORIDAD_TEST_TASK=NombreDePrueba evita tocar la tarea real.
TASK = os.environ.get("PRIORIDAD_TEST_TASK", "AltaPrioridad")
ARG_MIN = "--minimizado"
NO_WINDOW = 0x08000000


def _run(args):
    r = subprocess.run(args, capture_output=True, encoding="oem", errors="replace",
                       stdin=subprocess.DEVNULL, creationflags=NO_WINDOW, timeout=30)
    return r.returncode, (r.stdout + r.stderr).strip()


def launch_command():
    """(programa, argumentos) con que Windows debe arrancar esta misma app."""
    if getattr(sys, "frozen", False):
        return sys.executable, ARG_MIN
    exe = sys.executable
    pyw = os.path.join(os.path.dirname(exe), "pythonw.exe")   # sin ventana de consola
    if os.path.exists(pyw):
        exe = pyw
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prioridad.py")
    return exe, f'"{script}" {ARG_MIN}'


def _task_xml(user, command, arguments, highest):
    e = escape
    level = "HighestAvailable" if highest else "LeastPrivilege"
    return f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>Inicia AltaPrioridad (prioridad de CPU y perfiles de juego) al iniciar sesion.</Description>
  </RegistrationInfo>
  <Triggers>
    <LogonTrigger>
      <Enabled>true</Enabled>
      <UserId>{e(user)}</UserId>
      <Delay>PT10S</Delay>
    </LogonTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <UserId>{e(user)}</UserId>
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>{level}</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>false</StartWhenAvailable>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>{e(command)}</Command>
      <Arguments>{e(arguments)}</Arguments>
      <WorkingDirectory>{e(os.path.dirname(command))}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
"""


def _user():
    dom = os.environ.get("USERDOMAIN", "")
    name = os.environ.get("USERNAME", "")
    return f"{dom}\\{name}" if dom else name


def is_enabled():
    return _run(["schtasks", "/Query", "/TN", TASK])[0] == 0


def points_here():
    """True si la tarea existente arranca esta misma copia de la app (misma ruta y argumentos)."""
    code, out = _run(["schtasks", "/Query", "/TN", TASK, "/XML"])
    if code != 0:
        return False
    cmd = re.search(r"<Command>(.*?)</Command>", out, re.S)
    args = re.search(r"<Arguments>(.*?)</Arguments>", out, re.S)
    if not cmd:
        return False
    want_cmd, want_args = launch_command()
    return (os.path.normcase(html.unescape(cmd.group(1)).strip()) == os.path.normcase(want_cmd)
            and html.unescape(args.group(1)).strip() == want_args if args else False)


def enable(highest=True):
    """Crea o reemplaza la tarea. Devuelve (ok, mensaje). 'highest' solo se baja en pruebas."""
    cmd, args = launch_command()
    fd, path = tempfile.mkstemp(suffix=".xml")
    os.close(fd)
    try:
        with open(path, "w", encoding="utf-16") as f:
            f.write(_task_xml(_user(), cmd, args, highest))
        code, out = _run(["schtasks", "/Create", "/TN", TASK, "/XML", path, "/F"])
    finally:
        try:
            os.remove(path)
        except OSError:
            pass
    return code == 0, out


def disable():
    code, out = _run(["schtasks", "/Delete", "/TN", TASK, "/F"])
    return code == 0 or not is_enabled(), out
