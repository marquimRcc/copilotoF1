"""Utilitário para criar o atalho do Copiloto F1 na Área de Trabalho do Windows."""

import os
import subprocess
import sys


def create_desktop_shortcut():
    userprofile = os.environ.get("USERPROFILE")
    if not userprofile:
        print("Aviso: Variável %USERPROFILE% não encontrada. Execute este script no Windows.")
        return

    # Procura a pasta Desktop (em inglês ou português)
    desktop_en = os.path.join(userprofile, "Desktop")
    desktop_pt = os.path.join(userprofile, "Área de Trabalho")
    desktop = desktop_pt if os.path.exists(desktop_pt) else desktop_en

    if not os.path.exists(desktop):
        os.makedirs(desktop, exist_ok=True)

    repo_dir = os.path.abspath(os.path.dirname(__file__))
    target_bat = os.path.join(repo_dir, "iniciar_hud.bat")
    shortcut_path = os.path.join(desktop, "Copiloto F1 HUD.lnk")

    # Comando PowerShell para gerar o arquivo .lnk usando WScript.Shell
    ps_command = f"""
    $WshShell = New-Object -ComObject WScript.Shell
    $Shortcut = $WshShell.CreateShortcut('{shortcut_path}')
    $Shortcut.TargetPath = '{target_bat}'
    $Shortcut.WorkingDirectory = '{repo_dir}'
    $Shortcut.Description = 'Copiloto F1 - HUD de Telemetria e Ponto de Frenagem'
    $Shortcut.WindowStyle = 1
    $Shortcut.Save()
    """

    try:
        subprocess.run(["powershell", "-NoProfile", "-Command", ps_command], check=True)
        print("=" * 60)
        print("✅ ATALHO CRIADO COM SUCESSO!")
        print(f"📍 Local: {shortcut_path}")
        print("Agora você pode abrir o Copiloto F1 com 2 cliques na sua Área de Trabalho.")
        print("=" * 60)
    except Exception as e:
        print(f"Erro ao criar atalho via PowerShell: {e}")
        print(f"Alternativa: Você pode clicar com o botão direito no arquivo '{target_bat}' e selecionar 'Enviar para ➔ Área de trabalho'.")


if __name__ == "__main__":
    create_desktop_shortcut()
