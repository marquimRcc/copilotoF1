from pathlib import Path

from launcher import steam


def test_discover_without_steam(monkeypatch):
    monkeypatch.setattr(steam, "find_steam_root", lambda: None)
    result = steam.discover_installation()
    assert result.steam_executable is None
    assert result.game_directory is None


def test_library_paths_reads_vdf(tmp_path: Path):
    (tmp_path / "steamapps").mkdir()
    (tmp_path / "steamapps" / "libraryfolders.vdf").write_text(
        '"libraryfolders" { "0" { "path" "C:\\\\Steam" } "1" { "path" "D:\\\\Games" } }',
        encoding="utf-8",
    )
    paths = steam._library_paths(tmp_path)
    assert tmp_path in paths
    assert Path("D:/Games") in paths


def test_launch_does_not_start_duplicate(monkeypatch):
    installation = steam.Installation("C:/Steam/steam.exe", "C:/Steam", None, None)
    monkeypatch.setattr(steam, "is_game_running", lambda: True)
    ok, message = steam.launch_game(installation)
    assert not ok
    assert "já está em execução" in message
