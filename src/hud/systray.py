"""Controlador isolado do ícone da bandeja do sistema (Pystray) para o HUD."""

import os
import threading
from typing import Callable, Dict, Optional
from PIL import Image
import pystray


class SystrayController:
    """Gerencia o ícone da bandeja do sistema e seus menus contextuais."""

    def __init__(
        self,
        icon_path: str,
        on_change_layout: Callable[[int], None],
        on_change_theme: Callable[[str], None],
        on_change_track: Callable[[int, bool], None],
        on_toggle_click_through: Callable[[bool], None],
        on_quit: Callable[[], None],
        initial_layout: int = 1,
        initial_theme: str = "padrao",
        initial_click_through: bool = False,
    ):
        self.icon_path = icon_path
        self.on_change_layout = on_change_layout
        self.on_change_theme = on_change_theme
        self.on_change_track = on_change_track
        self.on_toggle_click_through = on_toggle_click_through
        self.on_quit = on_quit

        self.active_layout = initial_layout
        self.active_theme = initial_theme
        self.click_through_locked = initial_click_through
        self.selected_track_id = -1  # -1 = Automático

        self.icon: Optional[pystray.Icon] = None
        self.thread: Optional[threading.Thread] = None

    def start(self):
        """Inicializa e executa o pystray em thread dedicada."""
        image = self._load_icon_image()
        menu = self._build_menu()

        self.icon = pystray.Icon("copiloto_f1_hud", image, "Copiloto F1 - HUD de Telemetria", menu)
        self.thread = threading.Thread(target=self.icon.run, daemon=True)
        self.thread.start()

    def stop(self):
        """Encerra o ícone da bandeja."""
        if self.icon:
            try:
                self.icon.stop()
            except Exception:
                pass

    def _load_icon_image(self) -> Image.Image:
        candidates = [
            self.icon_path,
            os.path.join(os.path.dirname(__file__), "..", "..", "assets", "icon.png"),
            os.path.join(os.getcwd(), "assets", "icon.png"),
        ]
        for p in candidates:
            if os.path.exists(p):
                try:
                    return Image.open(p)
                except Exception:
                    pass
        # Fallback para imagem simples se não encontrar arquivo
        return Image.new("RGBA", (64, 64), color=(225, 6, 0, 255))

    def _build_menu(self) -> pystray.Menu:
        from core.state import THEMES
        from packets.session import TRACK_NAMES

        # Submenu de Layouts
        layout_items = [
            pystray.MenuItem(
                "Layout 1 (Cards)",
                lambda item: self._set_layout(1),
                checked=lambda item: self.active_layout == 1,
                radio=True,
            ),
            pystray.MenuItem(
                "Layout 2 (Barras)",
                lambda item: self._set_layout(2),
                checked=lambda item: self.active_layout == 2,
                radio=True,
            ),
            pystray.MenuItem(
                "Layout 3 (Minimalista)",
                lambda item: self._set_layout(3),
                checked=lambda item: self.active_layout == 3,
                radio=True,
            ),
        ]

        # Submenu de Temas
        theme_items = [
            pystray.MenuItem(
                data["label"],
                lambda item, k=key: self._set_theme(k),
                checked=lambda item, k=key: self.active_theme == k,
                radio=True,
            )
            for key, data in THEMES.items()
        ]

        # Submenu de Pistas
        track_items = [
            pystray.MenuItem(
                "Automático (Detecção UDP)",
                lambda item: self._set_track(-1, manual=False),
                checked=lambda item: self.selected_track_id == -1,
                radio=True,
            ),
            pystray.Menu.SEPARATOR,
        ]
        for tid in sorted(TRACK_NAMES.keys()):
            name = TRACK_NAMES[tid]
            track_items.append(
                pystray.MenuItem(
                    f"{name} [ID {tid}]",
                    lambda item, t=tid: self._set_track(t, manual=True),
                    checked=lambda item, t=tid: self.selected_track_id == t,
                    radio=True,
                )
            )

        return pystray.Menu(
            pystray.MenuItem("Copiloto F1 (EA SPORTS F1 25)", None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Layouts", pystray.Menu(*layout_items)),
            pystray.MenuItem("Temas de Cores", pystray.Menu(*theme_items)),
            pystray.MenuItem("Circuito", pystray.Menu(*track_items)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "🔒 Travar Posição (Click-Through)",
                self._toggle_click_through,
                checked=lambda item: self.click_through_locked,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Encerrar Copiloto F1", lambda: self.on_quit()),
        )

    def _set_layout(self, layout_id: int):
        self.active_layout = layout_id
        self.on_change_layout(layout_id)
        if self.icon:
            self.icon.update_menu()

    def _set_theme(self, theme_key: str):
        self.active_theme = theme_key
        self.on_change_theme(theme_key)
        if self.icon:
            self.icon.update_menu()

    def _set_track(self, track_id: int, manual: bool):
        self.selected_track_id = track_id
        self.on_change_track(track_id, manual)
        if self.icon:
            self.icon.update_menu()

    def _toggle_click_through(self):
        self.click_through_locked = not self.click_through_locked
        self.on_toggle_click_through(self.click_through_locked)
        if self.icon:
            self.icon.update_menu()
