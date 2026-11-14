# AltaPrioridad

Gestor gráfico de prioridad de CPU por programa para Windows. Guarda la prioridad en el registro (`Image File Execution Options\<programa.exe>\PerfOptions`, valor `CpuPriorityClass`), de modo que Windows la aplica cada vez que el programa arranca.

## Uso

Descarga `AltaPrioridad.exe` desde *Releases*. Es portable (Windows 10/11 de 64 bits, sin instalar Python) y pide permisos de administrador porque escribe en HKLM.

- **Agregar .exe…** / **Agregar proceso en ejecución…**: asigna la prioridad elegida (por defecto Alta). El selector oculta los programas que ya tienen prioridad guardada.
- **Cambiar prioridad**, **Quitar**, **Aplicar ahora** (cambia la prioridad del proceso ya abierto), **Importar / Exportar** (JSON).
- Cada cambio genera un respaldo JSON en `%LOCALAPPDATA%\AltaPrioridad\respaldos` (últimos 20).
- *Tiempo real* está bloqueado hasta marcar la casilla y confirmar; los procesos críticos de Windows piden confirmación.

## Panel de procesos

A la derecha de la ventana hay un panel acoplado con los procesos en ejecución. Se pliega y despliega con la flecha de su borde (la ventana se estrecha o se ensancha con él; el estado se recuerda).

- **Ancho ajustable**: arrastra el divisor entre el panel general y el de procesos. El ancho es independiente del panel general y se recuerda.
- **Doble clic** en un proceso, o **◀ Agregar**: lo agrega al registro permanente con la prioridad elegida. Los ya agregados salen del panel. **Quitar ▶** quita los marcados del registro.
- El panel solo funciona en la pestaña **Permanente**; en **Perfiles de juego** queda deshabilitado (gris). Allí los ejecutables de un perfil se agregan con *Agregar procesos...* y se quitan con *Quitar marcados*.
- Todas las listas tienen **casillas**: clic en la casilla marca una fila, clic en el encabezado de casillas marca o desmarca todas, y las acciones usan las filas marcadas (si no hay ninguna, las resaltadas).
- **Ordenar**: clic en el encabezado de cualquier columna ordena ascendente (▲); otro clic, descendente (▼). Números como números y prioridades por nivel (Inactiva < Baja < Normal < Sobre normal < Alta < Tiempo real).

## Perfiles de juego

Pestaña **Perfiles de juego**: cada perfil lista los ejecutables del juego. Mientras la app está abierta y la vigilancia activa (revisa cada 2 s), al detectar el juego:

- Sube a la prioridad del perfil (Alta por defecto) el juego, sus procesos hijos, los procesos de su carpeta y los "relacionados" que indiques.
- Baja a Normal el resto de programas que estén en Alta o Por encima de lo normal (no sube los que están en Inactiva o Por debajo de lo normal, ni toca procesos del sistema ni los de "Nunca tocar").
- Al cerrar el juego, al desactivar el perfil o al cerrar la app, cada proceso vuelve a la prioridad que tenía.
- Es en vivo (`SetPriorityClass`): no escribe en el registro. Si la app se cierra a la fuerza con un perfil activo, los cambios quedan hasta reiniciar esos procesos.
- Lista "Juegos detectados": procesos en carpetas de Steam, Epic, GOG, Xbox, etc. que aún no tienen perfil.

Prioridades (`CpuPriorityClass`): Idle=1, Normal=2, Alta=3, Tiempo real=4, Por debajo de lo normal=5, Por encima de lo normal=6.

## Límites

- La clave se asocia al nombre del archivo, no a la ruta.
- Solo se escribe en la vista de 64 bits del registro; programas de 32 bits sin verificar.
- El `.exe` no está firmado: un antivirus o EDR corporativo puede marcarlo, porque escribe en IFEO.

## Desarrollo

```bash
python prioridad.py          # ejecutar (pide administrador)
python test_core.py          # pruebas contra HKCU, no toca HKLM
python -m PyInstaller --noconfirm --onefile --windowed --uac-admin --name AltaPrioridad prioridad.py
```

Solo toca el valor `CpuPriorityClass` de `PerfOptions`; nunca `Debugger` ni otros valores de IFEO.
