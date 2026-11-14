"""Gerenciador de configurações persistentes da aplicação (config/settings.json)."""

import json
import os
from dataclasses import asdict, dataclass
from typing import Any, Dict


@dataclass
class AppSettings:
    window_x: int = 40
    window_y: int = 40
    active_theme: str = "padrao"
    active_layout: int = 1
    selected_track_id: int = -1  # -1 = Automático
    locked_click_through: bool = False


class SettingsManager:
    """Carrega e persiste as preferências do usuário em disco."""

    def __init__(self, config_path: str = "config/settings.json"):
        self.config_path = config_path
        self.settings = AppSettings()
        self.load()

    def load(self) -> AppSettings:
        """Lê o arquivo de configurações se existir."""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.settings = AppSettings(
                        window_x=data.get("window_x", 40),
                        window_y=data.get("window_y", 40),
                        active_theme=data.get("active_theme", "padrao"),
                        active_layout=data.get("active_layout", 1),
                        selected_track_id=data.get("selected_track_id", -1),
                        locked_click_through=data.get("locked_click_through", False),
                    )
            except Exception:
                pass
        return self.settings

    def save(self) -> bool:
        """Salva as configurações atuais no arquivo JSON."""
        try:
            os.makedirs(os.path.dirname(os.path.abspath(self.config_path)), exist_ok=True)
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(asdict(self.settings), f, indent=2)
            return True
        except Exception:
            return False

    def update(self, **kwargs: Any) -> bool:
        """Atualiza campos específicos e grava em disco."""
        changed = False
        for k, v in kwargs.items():
            if hasattr(self.settings, k):
                setattr(self.settings, k, v)
                changed = True
        if changed:
            return self.save()
        return False
