import os, shutil, subprocess, tempfile, time, winreg
tmp = tempfile.mkdtemp(prefix="prio_gui_")
os.environ["LOCALAPPDATA"] = tmp                       # no tocar perfiles.json ni respaldos reales
os.environ["PRIORIDAD_TEST_KEY"] = r"Software\AltaPrioridadTest"
import prioridad as ui, prio_core as core, prio_profiles as pp

gdir = os.path.join(tmp, "Juegos", "GameX"); os.makedirs(gdir)
exes = {n: os.path.join(gdir, n) for n in ("gamex.exe", "otro.exe", "otro2.exe")}
for p in exes.values():
    shutil.copy(os.path.join(os.environ["WINDIR"], "System32", "PING.EXE"), p)
procs = [subprocess.Popen([p, "-n", "90", "127.0.0.1"], stdout=subprocess.DEVNULL) for p in exes.values()]
time.sleep(0.6)

def cleanup_reg():
    base = r"Software\AltaPrioridadTest"
    for exe in ("gamex.exe", "otro.exe", "otro2.exe"):
        for path in (f"{base}\\{exe}\\PerfOptions", f"{base}\\{exe}"):
            try: winreg.DeleteKeyEx(winreg.HKEY_CURRENT_USER, path, core.VIEW, 0)
            except OSError: pass
    try: winreg.DeleteKeyEx(winreg.HKEY_CURRENT_USER, base, core.VIEW, 0)
    except OSError: pass

def click_check(tree, iid):
    tree.see(iid); tree.update()
    x, y, w, h = tree.bbox(iid, "#0")
    tree.event_generate("<Button-1>", x=x + 8, y=y + h // 2)
    tree.update()

try:
    cleanup_reg()
    app = ui.App(); app.update(); app.engine.alive = {pid: (pp_, e) for pid, pp_, e in core.process_info()}
    app.refresh_panel(); app.update()

    # --- panel visible, lista procesos con casillas ---
    assert app.body.winfo_ismapped() and app.panel_open
    names = set(app.pp.get_children())
    assert {"gamex.exe", "otro.exe", "otro2.exe"} <= names, names
    assert "csrss.exe" not in names, "procesos del sistema ocultos por defecto"
    print("panel lista procesos OK:", len(names))

    # --- casillas: clic en casilla, encabezado y espacio ---
    click_check(app.pp, "otro.exe")
    assert app.pp.checked() == ["otro.exe"], app.pp.checked()
    assert app.pp.item("otro.exe", "text") == ui.CHK_ON
    click_check(app.pp, "otro.exe"); assert app.pp.checked() == []
    app.pp.toggle_all(); assert len(app.pp.checked()) == len(app.pp.get_children())
    assert app.pp.heading("#0", "text") == ui.CHK_ON
    app.pp.toggle_all(); assert app.pp.checked() == []
    print("casillas OK (clic, encabezado)")

    # --- plegar / desplegar ---
    w0, nb0 = app.winfo_width(), app.nb.winfo_width()
    app.toggle_panel(); app.update()
    assert not app.body.winfo_ismapped() and app.pdata["panel"] is False
    w1 = app.winfo_width(); assert w1 == w0 - (app.panel_w - ui.STRIP_W), (w0, w1)
    assert abs(app.nb.winfo_width() - nb0) <= 3, "plegar no cambia el panel general"
    app.toggle_panel(); app.update()
    assert app.body.winfo_ismapped() and app.winfo_width() == w0
    print("plegar/desplegar OK:", w0, "->", w1, "->", w0)

    # --- divisor arrastrable: el ancho del panel es independiente del panel general ---
    d0 = app.dock.winfo_width(); assert abs(d0 - app.panel_w) <= 2, (d0, app.panel_w)
    sx, sy = app.paned.sash_coord(0)
    app.paned.sash_place(0, sx - 100, sy); app.update(); app.sync_from_sash()
    d1 = app.dock.winfo_width()
    assert d1 >= d0 + 90 and app.winfo_width() == w0, (d0, d1)
    assert app.nb.winfo_width() <= nb0 - 90, "el panel general cede ancho"
    assert pp.load()["panel_w"] == d1 == app.panel_w, "ancho recordado"
    app.toggle_panel(); app.update(); app.toggle_panel(); app.update()
    assert abs(app.dock.winfo_width() - d1) <= 2, "al reabrir usa el ancho elegido"
    app.paned.sash_place(0, app.paned.sash_coord(0)[0] + 100, sy); app.update(); app.sync_from_sash()
    assert abs(app.dock.winfo_width() - d0) <= 4
    print("divisor ajustable OK:", d0, "->", d1, "->", app.dock.winfo_width())

    # --- ordenar por columna ---
    box, t = ui.tree_box(app.nb, [("n", "Nombre", 100), ("c", "Cant.", 50), ("p", "Prioridad", 80)])
    rows = [("a", ("beta", 10, "Alta")), ("b", ("alfa", 9, "Normal")), ("c", ("Gamma", 100, "Baja"))]
    t.set_rows(rows)
    t.sort_by("n"); assert list(t.get_children()) == ["b", "a", "c"], "texto sin distinguir mayusculas"
    assert "▲" in t.heading("n", "text")
    t.sort_by("n"); assert list(t.get_children()) == ["c", "a", "b"] and "▼" in t.heading("n", "text")
    t.sort_by("c"); assert list(t.get_children()) == ["b", "a", "c"], "numerico, no alfabetico"
    t.sort_by("p"); assert list(t.get_children()) == ["c", "b", "a"], "prioridades por rango"
    t.sort_by("c")
    t.set_rows([("a", ("beta", 1000, "Alta")), ("b", ("alfa", 9, "Normal")), ("c", ("Gamma", 100, "Baja"))])
    assert list(t.get_children()) == ["b", "c", "a"], "set_rows conserva el orden elegido"
    # clic real en el encabezado
    t.sort_by("n"); t.sort_by("n")             # descendente
    box.place(x=0, y=0, width=300, height=120); app.update()
    t.event_generate("<Button-1>", x=44 + 100 + 20, y=8); t.event_generate("<ButtonRelease-1>", x=44 + 100 + 20, y=8)
    t.update()
    assert t._sort == ("c", False), t._sort
    box.destroy()
    for tr in (app.rt, app.pt, app.tt, app.ct, app.pp):
        for col in tr["columns"]:
            assert tr.heading(col, "command"), (tr, col)
            tr.sort_by(col); tr.sort_by(col)
            assert "▼" in tr.heading(col, "text")
        tr._sort = None; tr._arrows()
    print("ordenar por columna OK (todas las listas)")

    # --- el panel se deshabilita en la pestana Perfiles ---
    first = app.pp.get_children()[0]
    app.nb.select(1); app.update()
    assert app.pp._enabled is False and app.btn_add.instate(["disabled"]) and app.pq_entry.instate(["disabled"])
    assert "Desactivado" in app.target_var.get()
    n0 = len(core.list_entries())
    click_check(app.pp, first); assert app.pp.checked() == [], "casilla inerte"
    app.panel_add([first]); app.update(); assert len(core.list_entries()) == n0, "no agrega"
    app.nb.select(0); app.update()
    assert app.pp._enabled is True and not app.btn_add.instate(["disabled"])
    print("panel deshabilitado en Perfiles OK")

    # --- pestana registro: agregar con flecha, doble clic y quitar ---
    app.prio.set("Alta")
    app.pp.toggle("otro.exe", True); app.pp.toggle("otro2.exe", True)
    app.panel_add(); app.update()
    assert core.list_entries() == {"otro.exe": "Alta", "otro2.exe": "Alta"}, core.list_entries()
    assert core.get_class_flag(procs[1].pid) == 0x80, "aplica en vivo"
    assert "otro.exe" not in app.pp.get_children(), "agregados salen del panel"
    assert set(app.rt.get_children()) == {"otro.exe", "otro2.exe"}
    class Ev: pass                          # event_generate no admite Double-1
    # doble clic sobre la casilla: solo marca, no agrega
    first = app.pp.get_children()[0]
    app.pp.see(first); app.update()
    bx, by, bw, bh = app.pp.bbox(first, "#0")
    ev0 = Ev(); ev0.x, ev0.y = bx + 8, by + bh // 2
    n0 = len(core.list_entries())
    app.pp._dbl(ev0)
    assert app.pp.checked() == [first] and len(core.list_entries()) == n0, "doble clic en casilla solo marca"
    app.pp.uncheck([first])
    # doble clic en el nombre: agrega
    app.pp.see("gamex.exe"); app.update()
    x, y, w, h = app.pp.bbox("gamex.exe", "exe")
    ev = Ev(); ev.x, ev.y = x + 10, y + h // 2
    app.pp._dbl(ev); app.update()
    assert "gamex.exe" in core.list_entries(), "doble clic agrega"
    # quitar con flecha: marca en la lista de destino
    app.rt.toggle("otro.exe", True); app.rt.toggle("gamex.exe", True)
    ui.messagebox.askyesno = lambda *a, **k: True
    app.panel_remove(); app.update()
    assert core.list_entries() == {"otro2.exe": "Alta"}, core.list_entries()
    assert "otro.exe" in app.pp.get_children(), "quitados vuelven al panel"
    print("registro: flecha agregar, doble clic y quitar OK")
    app.rt.toggle("otro2.exe", True); app.remove(); app.update()
    assert core.list_entries() == {}

    # --- pestana perfiles ---
    app.pdata["profiles"].append(pp.new_profile("GameX", ["gamex.exe"], lower_others=False))
    app.pdata["watch"] = False; app.watch.set(False)
    app.nb.select(1); app.update()
    app.refresh_profiles(); app.pt.selection_set("GameX"); app.update()
    assert app.cur_profile()["name"] == "GameX"
    assert [app.tt.set(i, "exe") for i in app.tt.get_children()] == ["gamex.exe"]
    class FakePick:                           # el dialogo modal se sustituye por una lista fija
        def __init__(self, master): self.result = ["otro.exe", "otro2.exe", "GameX.exe"]
    ui.PickProcess = FakePick; app.wait_window = lambda d: None
    app.prof_add_triggers(); app.update()
    assert app.cur_profile()["triggers"] == ["gamex.exe", "otro.exe", "otro2.exe"], app.cur_profile()["triggers"]
    assert len(app.tt.get_children()) == 3
    app.tt.toggle("otro.exe", True); app.prof_remove_triggers(); app.update()
    assert app.cur_profile()["triggers"] == ["gamex.exe", "otro2.exe"]
    app.tt.toggle("gamex.exe", True); app.tt.toggle("otro2.exe", True)
    shown = []
    ui.messagebox.showerror = lambda *a, **k: shown.append(a)
    app.prof_remove_triggers(); assert shown and len(app.cur_profile()["triggers"]) == 2, "no deja perfil vacio"
    app.tt.uncheck(["gamex.exe", "otro2.exe"])
    print("perfiles: agregar/quitar ejecutables OK")

    # --- casillas en perfiles: activar/desactivar y crear varios desde detectados ---
    app.pt.toggle("GameX", True); app.prof_toggle()
    assert app.pdata["profiles"][0]["enabled"] is False
    app.prof_toggle(); assert app.pdata["profiles"][0]["enabled"] is True
    app.engine.candidates = lambda profiles: [("a.exe", r"C:\x\a.exe"), ("b.exe", r"C:\x\b.exe")]
    app.refresh_profiles(); app.ct.toggle_all()
    assert len(app.ct.checked()) == 2
    app.prof_from_candidates()
    assert {p["name"] for p in app.pdata["profiles"]} == {"GameX", "a", "b"}
    app.pt.uncheck(["GameX"]); app.pt.toggle("a", True); app.pt.toggle("b", True)
    app.prof_delete(); assert [p["name"] for p in app.pdata["profiles"]] == ["GameX"]
    print("perfiles: casillas en todas las listas OK")

    # --- persistencia del panel ---
    app.toggle_panel(); assert pp.load()["panel"] is False
    app.on_close()
    print("TODO OK")
finally:
    for p in procs: p.kill()
    time.sleep(0.4); cleanup_reg(); shutil.rmtree(tmp, ignore_errors=True)
