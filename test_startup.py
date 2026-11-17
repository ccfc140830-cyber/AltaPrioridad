import os
os.environ["PRIORIDAD_TEST_TASK"] = "AltaPrioridadPrueba"
import prio_startup as st

try:
    st.disable()
    assert not st.is_enabled()

    # Tarea de prueba SIN privilegios elevados (esta consola no es admin) pero con el mismo XML.
    ok, out = st.enable(highest=False)
    assert ok, out
    assert st.is_enabled() and st.points_here(), "la tarea apunta a esta app"
    code, xml = st._run(["schtasks", "/Query", "/TN", st.TASK, "/XML"])
    for must in ("<LogonTrigger>", "PT10S", "<ExecutionTimeLimit>PT0S", "--minimizado",
                 "<DisallowStartIfOnBatteries>false", "<MultipleInstancesPolicy>IgnoreNew"):
        assert must in xml, must
    print("crear tarea (XML valido, sin limite de ejecucion, minimizado) OK")

    ok, out = st.enable(highest=False)       # reemplazo idempotente
    assert ok, out

    # el XML con privilegios maximos debe pasar la validacion de esquema (puede fallar solo por permisos)
    ok_h, out_h = st.enable(highest=True)
    print("highest:", "creada (consola elevada)" if ok_h else out_h[:90])
    if ok_h:
        code, xml = st._run(["schtasks", "/Query", "/TN", st.TASK, "/XML"])
        assert "HighestAvailable" in xml
    else:
        assert "formato" not in out_h.lower() and "format" not in out_h.lower() and "xml" not in out_h.lower(), out_h

    ok, out = st.disable()
    assert ok and not st.is_enabled(), out
    ok, out = st.disable()                   # borrar lo que no existe tampoco falla
    assert ok
    print("borrar tarea OK")

    # ruta distinta: la tarea creada desde otro programa no 'apunta aqui'
    real_launch = st.launch_command
    st.enable(highest=False)
    st.launch_command = lambda: (r"C:\otra\AltaPrioridad.exe", "--minimizado")
    assert not st.points_here()
    st.launch_command = real_launch
    st.disable()
    print("deteccion de ruta distinta OK")
    print("TODO OK")
finally:
    st.disable()
