"""Icono en la bandeja (junto al reloj) con ctypes, sin dependencias.

La ventana oculta que recibe los mensajes se crea en el hilo principal: el bucle de mensajes de Tk
la atiende. IMPORTANTE: su procedimiento de ventana NO puede llamar a Tk (llamar a tkinter desde un
callback de ctypes lanzado por el bucle de Tk corrompe el estado de hilos de _tkinter y cierra
Python). Solo encola eventos en `events`; la app los atiende con un sondeo ligero.
La ventana existe siempre (permite que una 2.a copia pida mostrar la primera); el icono solo
se muestra mientras la app esta en segundo plano.
"""
import collections
import ctypes
import os
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)
shell32 = ctypes.WinDLL("shell32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)

# Para pruebas: el mismo sufijo que usa la tarea de prueba separa la ventana de la app real.
CLASS = "AltaPrioridad_Tray" + os.environ.get("PRIORIDAD_TEST_TASK", "")
LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)

WM_USER, WM_APP, WM_NULL = 0x400, 0x8000, 0
CALLBACK_MSG = WM_USER + 1
WM_SHOWAPP = WM_APP + 2
WM_LBUTTONUP, WM_LBUTTONDBLCLK, WM_RBUTTONUP = 0x202, 0x203, 0x205
NIM_ADD, NIM_MODIFY, NIM_DELETE = 0, 1, 2
NIF_MESSAGE, NIF_ICON, NIF_TIP, NIF_INFO = 1, 2, 4, 0x10
NIIF_INFO = 1
MF_STRING, MF_SEPARATOR = 0, 0x800
TPM_RIGHTBUTTON, TPM_NONOTIFY, TPM_RETURNCMD = 0x2, 0x80, 0x100
CMD_OPEN, CMD_QUIT = 1, 2


class GUID(ctypes.Structure):
    _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD), ("Data3", wintypes.WORD),
                ("Data4", ctypes.c_ubyte * 8)]


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("hWnd", wintypes.HWND), ("uID", wintypes.UINT),
                ("uFlags", wintypes.UINT), ("uCallbackMessage", wintypes.UINT), ("hIcon", wintypes.HICON),
                ("szTip", wintypes.WCHAR * 128), ("dwState", wintypes.DWORD), ("dwStateMask", wintypes.DWORD),
                ("szInfo", wintypes.WCHAR * 256), ("uTimeout", wintypes.UINT),
                ("szInfoTitle", wintypes.WCHAR * 64), ("dwInfoFlags", wintypes.DWORD),
                ("guidItem", GUID), ("hBalloonIcon", wintypes.HICON)]


class NOTIFYICONIDENTIFIER(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("hWnd", wintypes.HWND), ("uID", wintypes.UINT),
                ("guidItem", GUID)]


class WNDCLASSW(ctypes.Structure):
    _fields_ = [("style", wintypes.UINT), ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int), ("hInstance", wintypes.HINSTANCE), ("hIcon", wintypes.HICON),
                ("hCursor", wintypes.HANDLE), ("hbrBackground", wintypes.HBRUSH),
                ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR)]


class ICONINFO(ctypes.Structure):
    _fields_ = [("fIcon", wintypes.BOOL), ("xHotspot", wintypes.DWORD), ("yHotspot", wintypes.DWORD),
                ("hbmMask", wintypes.HBITMAP), ("hbmColor", wintypes.HBITMAP)]


user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASSW)]
user32.RegisterClassW.restype = wintypes.ATOM
user32.CreateWindowExW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
                                   ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.HWND,
                                   wintypes.HMENU, wintypes.HINSTANCE, ctypes.c_void_p]
user32.CreateWindowExW.restype = wintypes.HWND
user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.DefWindowProcW.restype = LRESULT
user32.DestroyWindow.argtypes = [wintypes.HWND]
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.SendMessageW.restype = LRESULT
user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
user32.FindWindowW.restype = wintypes.HWND
user32.RegisterWindowMessageW.argtypes = [wintypes.LPCWSTR]
user32.RegisterWindowMessageW.restype = wintypes.UINT
user32.CreatePopupMenu.restype = wintypes.HMENU
user32.AppendMenuW.argtypes = [wintypes.HMENU, wintypes.UINT, ctypes.c_size_t, wintypes.LPCWSTR]
user32.TrackPopupMenu.argtypes = [wintypes.HMENU, wintypes.UINT, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                  wintypes.HWND, ctypes.c_void_p]
user32.TrackPopupMenu.restype = ctypes.c_int
user32.DestroyMenu.argtypes = [wintypes.HMENU]
user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.CreateIconIndirect.argtypes = [ctypes.POINTER(ICONINFO)]
user32.CreateIconIndirect.restype = wintypes.HICON
user32.DestroyIcon.argtypes = [wintypes.HICON]
gdi32.CreateBitmap.argtypes = [ctypes.c_int, ctypes.c_int, wintypes.UINT, wintypes.UINT, ctypes.c_void_p]
gdi32.CreateBitmap.restype = wintypes.HBITMAP
gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
shell32.Shell_NotifyIconW.argtypes = [wintypes.DWORD, ctypes.POINTER(NOTIFYICONDATAW)]
shell32.Shell_NotifyIconW.restype = wintypes.BOOL
shell32.Shell_NotifyIconGetRect.argtypes = [ctypes.POINTER(NOTIFYICONIDENTIFIER), ctypes.POINTER(wintypes.RECT)]
shell32.Shell_NotifyIconGetRect.restype = ctypes.c_long
kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
kernel32.GetModuleHandleW.restype = wintypes.HMODULE


def _make_icon(n=32):
    """Icono propio: cuadrado azul redondeado con un rombo blanco (simetrico: no depende del orden de filas)."""
    px = bytearray(n * n * 4)
    r, c = 7, (n - 1) / 2
    for y in range(n):
        for x in range(n):
            dx, dy = max(r - x, x - (n - 1 - r), 0), max(r - y, y - (n - 1 - r), 0)
            if dx * dx + dy * dy > r * r:
                continue
            d = abs(x - c) + abs(y - c)
            white = (3.5 < d <= 9) or d <= 2
            b, g, rr = (255, 255, 255) if white else (0xE6, 0x6B, 0x2E)
            i = (y * n + x) * 4
            px[i:i + 4] = bytes((b, g, rr, 255))
    color = gdi32.CreateBitmap(n, n, 1, 32, (ctypes.c_ubyte * len(px)).from_buffer(px))
    mask_bits = bytes(((n + 15) // 16 * 2) * n)
    mask = gdi32.CreateBitmap(n, n, 1, 1, (ctypes.c_ubyte * len(mask_bits)).from_buffer_copy(mask_bits))
    info = ICONINFO(True, 0, 0, mask, color)
    icon = user32.CreateIconIndirect(ctypes.byref(info))
    gdi32.DeleteObject(color)
    gdi32.DeleteObject(mask)
    return icon


def signal_existing():
    """Pide a la copia ya abierta que muestre su ventana. True si la encontro."""
    hwnd = user32.FindWindowW(CLASS, None)
    if not hwnd:
        return False
    user32.PostMessageW(hwnd, WM_SHOWAPP, 0, 0)
    return True


class Tray:
    def __init__(self, tip):
        self.tip = tip[:127]
        self.events = collections.deque()   # "show" | "quit"; los consume la app
        self._shown = False
        self._proc = WNDPROC(self._wndproc)       # mantener la referencia viva
        hinst = kernel32.GetModuleHandleW(None)
        wc = WNDCLASSW()
        wc.lpfnWndProc, wc.hInstance, wc.lpszClassName = self._proc, hinst, CLASS
        if not user32.RegisterClassW(ctypes.byref(wc)) and ctypes.get_last_error() != 1410:  # 1410: ya existe
            raise OSError(ctypes.get_last_error(), "RegisterClassW")
        self.hwnd = user32.CreateWindowExW(0, CLASS, "AltaPrioridad", 0, 0, 0, 0, 0, None, None, hinst, None)
        if not self.hwnd:
            raise OSError(ctypes.get_last_error(), "CreateWindowExW")
        self.hicon = _make_icon()
        self._taskbar_msg = user32.RegisterWindowMessageW("TaskbarCreated")  # el Explorador se reinicio

    def _nid(self, flags):
        n = NOTIFYICONDATAW()
        n.cbSize, n.hWnd, n.uID, n.uFlags = ctypes.sizeof(n), self.hwnd, 1, flags
        n.uCallbackMessage, n.hIcon, n.szTip = CALLBACK_MSG, self.hicon, self.tip
        return n

    def show_icon(self):
        if not self._shown:
            self._shown = bool(shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(
                self._nid(NIF_MESSAGE | NIF_ICON | NIF_TIP))))
        return self._shown

    def hide_icon(self):
        if self._shown:
            shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(self._nid(0)))
            self._shown = False

    def notify(self, title, text):
        """Globo de aviso junto al icono (solo si el icono esta visible)."""
        if self._shown:
            n = self._nid(NIF_INFO)
            n.szInfoTitle, n.szInfo, n.dwInfoFlags = title[:63], text[:255], NIIF_INFO
            shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(n))

    def exists(self):
        """True si Windows tiene registrado el icono (devuelve su rectangulo)."""
        ident = NOTIFYICONIDENTIFIER(ctypes.sizeof(NOTIFYICONIDENTIFIER), self.hwnd, 1)
        return shell32.Shell_NotifyIconGetRect(ctypes.byref(ident), ctypes.byref(wintypes.RECT())) == 0

    def handle_command(self, cmd):
        if cmd == CMD_OPEN:
            self.events.append("show")
        elif cmd == CMD_QUIT:
            self.events.append("quit")

    def popup(self):
        menu = user32.CreatePopupMenu()
        user32.AppendMenuW(menu, MF_STRING, CMD_OPEN, "Abrir Alta Prioridad")
        user32.AppendMenuW(menu, MF_SEPARATOR, 0, None)
        user32.AppendMenuW(menu, MF_STRING, CMD_QUIT, "Salir (detener la vigilancia)")
        pt = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        user32.SetForegroundWindow(self.hwnd)      # sin esto el menu no se cierra al hacer clic fuera
        cmd = user32.TrackPopupMenu(menu, TPM_RETURNCMD | TPM_RIGHTBUTTON | TPM_NONOTIFY, pt.x, pt.y, 0,
                                    self.hwnd, None)
        user32.PostMessageW(self.hwnd, WM_NULL, 0, 0)
        user32.DestroyMenu(menu)
        self.handle_command(cmd)

    def _wndproc(self, hwnd, msg, wp, lp):
        try:
            if msg == CALLBACK_MSG:
                if lp in (WM_LBUTTONUP, WM_LBUTTONDBLCLK):
                    self.events.append("show")
                elif lp == WM_RBUTTONUP:
                    self.popup()
                return 0
            if msg == WM_SHOWAPP:
                self.events.append("show")
                return 0
            if msg == self._taskbar_msg and self._shown:
                self._shown = False
                self.show_icon()
        except Exception:      # una excepcion no puede cruzar el callback de ctypes
            pass
        return user32.DefWindowProcW(hwnd, msg, wp, lp)

    def destroy(self):
        self.hide_icon()
        if self.hwnd:
            user32.DestroyWindow(self.hwnd)
            self.hwnd = None
        if self.hicon:
            user32.DestroyIcon(self.hicon)
            self.hicon = None
