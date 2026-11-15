"""Integração nativa Win32 via ctypes para controle avançado de janela e foco no Windows."""

import ctypes
import sys
from typing import Optional

GWL_EXSTYLE = -20
WS_EX_TOPMOST = 0x00000008
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_LAYERED = 0x00080000
WS_EX_NOACTIVATE = 0x08000000

HWND_TOPMOST = -1
HWND_NOTOPMOST = -2

SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040

IS_WINDOWS = sys.platform == "win32"

if IS_WINDOWS:
    from ctypes import wintypes

    _user32 = ctypes.windll.user32
    _user32.GetParent.argtypes = [wintypes.HWND]
    _user32.GetParent.restype = wintypes.HWND
    _user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
    _user32.GetWindowLongW.restype = wintypes.LONG
    _user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.LONG]
    _user32.SetWindowLongW.restype = wintypes.LONG
    _user32.SetWindowPos.argtypes = [
        wintypes.HWND,
        wintypes.HWND,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.UINT,
    ]
    _user32.SetWindowPos.restype = wintypes.BOOL


class Win32WindowManager:
    """Gerenciador de atributos avançados de janela para Desktop Window Manager (DWM)."""

    def __init__(self, root=None):
        self.root = root
        self.hwnd: Optional[int] = None
        self.click_through_active = False

        if IS_WINDOWS and self.root:
            self.refresh_hwnd()

    def refresh_hwnd(self) -> Optional[int]:
        """Obtém ou atualiza o handle (HWND) nativo da janela Tkinter."""
        if not IS_WINDOWS or not self.root:
            return None
        try:
            self.root.update_idletasks()
            raw_id = self.root.winfo_id()
            parent = _user32.GetParent(raw_id)
            self.hwnd = parent if parent else raw_id
            return self.hwnd
        except Exception:
            return None

    def apply_overlay_styles(self) -> bool:
        """Aplica estilos para impedir roubo de foco do jogo e remover do Alt+Tab."""
        if not IS_WINDOWS or not self.hwnd:
            return False
        try:
            style = _user32.GetWindowLongW(self.hwnd, GWL_EXSTYLE)
            new_style = style | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW | WS_EX_TOPMOST
            _user32.SetWindowLongW(self.hwnd, GWL_EXSTYLE, new_style)
            self.force_topmost()
            return True
        except Exception:
            return False

    def force_topmost(self) -> bool:
        """Força a posição no topo da pilha Z-order sem ativar foco."""
        if not IS_WINDOWS or not self.hwnd:
            return False
        try:
            _user32.SetWindowPos(
                self.hwnd,
                wintypes.HWND(HWND_TOPMOST),
                0,
                0,
                0,
                0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW,
            )
            return True
        except Exception:
            return False

    def set_click_through(self, enabled: bool) -> bool:
        """Ativa ou desativa o modo Click-Through (clique passa direto para o jogo)."""
        if not IS_WINDOWS or not self.hwnd:
            self.click_through_active = enabled
            return False
        try:
            style = _user32.GetWindowLongW(self.hwnd, GWL_EXSTYLE)
            if enabled:
                new_style = style | WS_EX_TRANSPARENT | WS_EX_LAYERED
            else:
                new_style = style & ~WS_EX_TRANSPARENT

            _user32.SetWindowLongW(self.hwnd, GWL_EXSTYLE, new_style)
            self.force_topmost()
            self.click_through_active = enabled
            return True
        except Exception:
            return False
