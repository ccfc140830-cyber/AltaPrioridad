# AltaPrioridad

Gestor gráfico de prioridad de CPU por programa para Windows. Guarda la prioridad en el registro (`Image File Execution Options\<programa.exe>\PerfOptions`, valor `CpuPriorityClass`), de modo que Windows la aplica cada vez que el programa arranca.

## Uso

Descarga `AltaPrioridad.exe` desde *Releases*. Es portable (Windows 10/11 de 64 bits, sin instalar Python) y pide permisos de administrador porque escribe en HKLM.

- **Agregar .exe…** / **Agregar proceso en ejecución…**: asigna la prioridad elegida (por defecto Alta). El selector oculta los programas que ya tienen prioridad guardada.
- **Cambiar prioridad**, **Quitar**, **Aplicar ahora** (cambia la prioridad del proceso ya abierto), **Importar / Exportar** (JSON).
- Cada cambio genera un respaldo JSON en `%LOCALAPPDATA%\AltaPrioridad\respaldos` (últimos 20).
- *Tiempo real* está bloqueado hasta marcar la casilla y confirmar; los procesos críticos de Windows piden confirmación.

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
