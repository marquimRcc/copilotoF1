"""Read-only Steam/F1 25 discovery and safe Steam launch helpers."""
from __future__ import annotations

import os
import re
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

APP_ID = 3059520
GAME_PROCESS = "F1_25.exe"
STEAM_PROCESS = "steam.exe"


@dataclass(frozen=True)
class Installation:
    steam_executable: str | None
    steam_root: str | None
    game_directory: str | None
    app_manifest: str | None
    app_id: int = APP_ID

    def to_dict(self) -> dict:
        return asdict(self)


def _registry_steam_path() -> Path | None:
    if os.name != "nt":
        return None
    try:
        import winreg  # type: ignore
        for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            for key_name in (r"Software\\Valve\\Steam", r"Software\\WOW6432Node\\Valve\\Steam"):
                try:
                    with winreg.OpenKey(hive, key_name) as key:
                        value, _ = winreg.QueryValueEx(key, "SteamPath")
                        candidate = Path(value)
                        if candidate.exists():
                            return candidate
                except OSError:
                    continue
    except ImportError:
        return None
    return None


def find_steam_root() -> Path | None:
    candidates: list[Path] = []
    registered = _registry_steam_path()
    if registered:
        candidates.append(registered)
    for variable in ("PROGRAMFILES(X86)", "PROGRAMFILES"):
        base = os.environ.get(variable)
        if base:
            candidates.append(Path(base) / "Steam")
    local = os.environ.get("LOCALAPPDATA")
    if local:
        candidates.append(Path(local) / "Programs" / "Steam")
    for candidate in candidates:
        if (candidate / "steam.exe").is_file():
            return candidate.resolve()
    return None


def _library_paths(steam_root: Path) -> list[Path]:
    libraries = [steam_root]
    vdf = steam_root / "steamapps" / "libraryfolders.vdf"
    if not vdf.is_file():
        return libraries
    try:
        text = vdf.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return libraries
    # Supports modern VDF entries: "path" "D:\\SteamLibrary".
    for raw in re.findall(r'"path"\\s+"((?:\\\\.|[^"])*)"', text):
        decoded = raw.replace("\\\\", "\\").replace("\\/", "/")
        path = Path(decoded)
        if path not in libraries:
            libraries.append(path)
    return libraries


def discover_installation() -> Installation:
    steam_root = find_steam_root()
    if not steam_root:
        return Installation(None, None, None, None)
    manifest = None
    game_dir = None
    for library in _library_paths(steam_root):
        candidate = library / "steamapps" / f"appmanifest_{APP_ID}.acf"
        if not candidate.is_file():
            continue
        manifest = candidate
        try:
            content = candidate.read_text(encoding="utf-8", errors="replace")
            match = re.search(r'"installdir"\\s+"([^"]+)"', content)
            if match:
                game_dir = library / "steamapps" / "common" / match.group(1)
        except OSError:
            pass
        break
    return Installation(
        steam_executable=str(steam_root / "steam.exe"),
        steam_root=str(steam_root),
        game_directory=str(game_dir) if game_dir else None,
        app_manifest=str(manifest) if manifest else None,
    )


def _tasklist_image_names() -> set[str]:
    if os.name != "nt":
        return set()
    try:
        result = subprocess.run(
            ["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=10, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return set()
    return {name.lower() for name in re.findall(r'^"([^"]+)"', result.stdout, re.MULTILINE)}


def is_game_running() -> bool:
    return GAME_PROCESS.lower() in _tasklist_image_names()


def launch_game(installation: Installation | None = None) -> tuple[bool, str]:
    """Launch through Steam's app URL; never bypass EA AntiCheat or execute the game EXE."""
    installation = installation or discover_installation()
    if is_game_running():
        return False, "F1 25 já está em execução; nenhuma segunda instância foi iniciada."
    if not installation.steam_executable:
        return False, "Steam não encontrada. Abra a Steam uma vez e execute novamente."
    if os.name != "nt":
        return False, "A inicialização automática está disponível somente no Windows."
    try:
        os.startfile(f"steam://run/{APP_ID}")  # type: ignore[attr-defined]
        return True, f"Solicitação enviada à Steam para iniciar o F1 25 (AppID {APP_ID})."
    except OSError as exc:
        return False, f"Não foi possível abrir o protocolo Steam: {exc}"


def wait_for_game(timeout_seconds: int = 180, poll_seconds: float = 2.0) -> bool:
    deadline = time.monotonic() + max(0, timeout_seconds)
    while time.monotonic() <= deadline:
        if is_game_running():
            return True
        time.sleep(max(0.2, poll_seconds))
    return False
